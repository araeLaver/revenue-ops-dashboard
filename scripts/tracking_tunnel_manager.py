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
import signal
import subprocess
import sys
import time
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8431)
    ap.add_argument("--commit", action="store_true", default=True)
    ap.add_argument("--no-commit", dest="commit", action="store_false")
    ap.add_argument("--push", action="store_true", default=True)
    ap.add_argument("--no-push", dest="push", action="store_false")
    ap.add_argument("--restart-delay", type=int, default=10)
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
            for raw in child.stdout:
                line = raw.rstrip("\n")
                log("TUNNEL_OUT " + line)
                urls = URL_RE.findall(line)
                for url in urls:
                    if url == last_url:
                        continue
                    last_url = url
                    write_state(status="url_detected", current_url=url, detected_at=stamp(), tunnel_pid=child.pid, manager_pid=os.getpid())
                    ok = sync_url(url, commit=args.commit, push=args.push)
                    if not ok:
                        log(f"SYNC_FAILED_RESTART_TUNNEL url={url}")
                        write_state(status="sync_failed_restarting", failed_url=url, tunnel_pid=child.pid, manager_pid=os.getpid())
                        if child.poll() is None:
                            child.terminate()
                        break
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
