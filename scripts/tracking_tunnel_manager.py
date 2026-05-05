#!/usr/bin/env python3
"""Managed localhost.run tunnel for Hermes tracking.

Starts ssh reverse tunnel, watches stdout for https://*.lhr.life, and immediately
runs sync_tracking_tunnel.py so GitHub Pages gateway/config stay current.

Stdlib only; intended for Hermes terminal/background or LaunchAgent use.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import select
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_PATH = LOG_DIR / "tracking_tunnel_manager.log"
STATE_PATH = ROOT / "data/tracking_tunnel_manager_state.json"
URL_RE = re.compile(r"https://[a-z0-9]{8,32}\.lhr\.life")


def stamp() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def log(msg: str) -> None:
    line = f"{stamp()} {msg}"
    print(line, flush=True)
    with LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_state(**kwargs) -> None:
    state = {}
    if STATE_PATH.exists():
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    state.update(kwargs)
    state["updated_at"] = stamp()
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sync_url(url: str, commit: bool, push: bool) -> bool:
    cmd = [sys.executable, str(ROOT / "scripts/sync_tracking_tunnel.py"), "--url", url]
    if commit:
        cmd.append("--commit")
    if push:
        cmd.append("--push")
    log("SYNC_START url=" + url)
    p = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
    for line in p.stdout.splitlines():
        log("SYNC_OUT " + line)
    ok = p.returncode == 0
    write_state(last_sync_url=url, last_sync_ok=ok, last_sync_rc=p.returncode)
    log(f"SYNC_DONE url={url} ok={ok} rc={p.returncode}")
    return ok


def quick_backend_ok(url: str, timeout: int = 8) -> tuple[bool, str]:
    """Cheap periodic health check for an already-synced tunnel."""
    target = "https%3A%2F%2Funpre.co.kr%2F"
    checks = [
        (url.rstrip("/") + "/health", "health"),
        (url.rstrip("/") + f"/t?site=unpre&slot=manager-health&content_id=manager-health&target={target}", "redirect"),
    ]
    opener = urllib.request.build_opener(urllib.request.HTTPRedirectHandler)
    for check_url, kind in checks:
        try:
            req = urllib.request.Request(check_url, headers={"User-Agent": "HermesTrackingTunnelManager/1.0"})
            with opener.open(req, timeout=timeout) as resp:
                status = getattr(resp, "status", resp.getcode())
                final_url = resp.geturl()
                if kind == "health" and status == 200:
                    continue
                if kind == "redirect" and final_url.startswith("https://unpre.co.kr"):
                    continue
                return False, f"bad_status kind={kind} status={status} final={final_url}"
        except urllib.error.HTTPError as e:
            return False, f"http_error kind={kind} code={e.code}"
        except Exception as e:
            return False, f"exception kind={kind} error={type(e).__name__}: {e}"
    return True, "ok"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8431)
    ap.add_argument("--commit", action="store_true", default=True)
    ap.add_argument("--no-commit", dest="commit", action="store_false")
    ap.add_argument("--push", action="store_true", default=True)
    ap.add_argument("--no-push", dest="push", action="store_false")
    ap.add_argument("--restart-delay", type=int, default=10)
    ap.add_argument("--health-interval", type=int, default=60)
    args = ap.parse_args()

    stopping = False

    def handle_signal(signum, frame):
        nonlocal stopping
        stopping = True
        log(f"SIGNAL signum={signum}; stopping after child termination")

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    last_url = None
    while not stopping:
        cmd = [
            "ssh", "-T",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ServerAliveInterval=30",
            "-R", f"80:localhost:{args.port}",
            "nokey@localhost.run",
        ]
        log("TUNNEL_START " + " ".join(cmd))
        write_state(status="starting", command=" ".join(cmd), port=args.port, pid=os.getpid())
        child = subprocess.Popen(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1)
        write_state(status="running", tunnel_pid=child.pid, manager_pid=os.getpid())
        try:
            assert child.stdout is not None
            current_url = None
            last_health_check = 0.0
            restart_requested = False
            while not stopping and child.poll() is None and not restart_requested:
                ready, _, _ = select.select([child.stdout], [], [], 1.0)
                if ready:
                    raw = child.stdout.readline()
                    if raw == "":
                        break
                    line = raw.rstrip("\n")
                    log("TUNNEL_OUT " + line)
                    urls = URL_RE.findall(line)
                    for url in urls:
                        if url == last_url:
                            continue
                        last_url = url
                        current_url = url
                        last_health_check = time.time()
                        write_state(status="url_detected", current_url=url, detected_at=stamp(), tunnel_pid=child.pid, manager_pid=os.getpid())
                        ok = sync_url(url, commit=args.commit, push=args.push)
                        if not ok:
                            log(f"SYNC_FAILED_RESTART_TUNNEL url={url}")
                            write_state(status="sync_failed_restarting", failed_url=url, tunnel_pid=child.pid, manager_pid=os.getpid())
                            restart_requested = True
                            if child.poll() is None:
                                child.terminate()
                            break
                if current_url and (time.time() - last_health_check) >= args.health_interval:
                    last_health_check = time.time()
                    ok, detail = quick_backend_ok(current_url)
                    write_state(status="health_ok" if ok else "health_failed_restarting", current_url=current_url, last_health_ok=ok, last_health_detail=detail, last_health_at=stamp(), tunnel_pid=child.pid, manager_pid=os.getpid())
                    log(f"HEALTH_CHECK url={current_url} ok={ok} detail={detail}")
                    if not ok:
                        log(f"HEALTH_FAILED_RESTART_TUNNEL url={current_url}")
                        restart_requested = True
                        if child.poll() is None:
                            child.terminate()
                if stopping:
                    break
        finally:
            if stopping and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
            rc = child.wait()
            log(f"TUNNEL_EXIT rc={rc}")
            write_state(status="stopped" if stopping else "exited", tunnel_rc=rc)
        if not stopping:
            time.sleep(args.restart_delay)
    write_state(status="stopped")
    log("MANAGER_STOPPED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
