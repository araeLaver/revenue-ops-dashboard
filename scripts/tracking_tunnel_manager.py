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
    """Print and best-effort append to the manager log.

    The tunnel manager is an observer/safety process. On macOS/external volumes,
    the log file can intermittently raise PermissionError even when the directory
    is normally writable. Logging must never crash the tunnel watcher.
    """
    line = f"{stamp()} {msg}"
    print(line, flush=True)
    try:
        LOG_DIR.mkdir(exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        print(f"{stamp()} LOG_WRITE_FAILED path={LOG_PATH} error={type(e).__name__}", file=sys.stderr, flush=True)


def write_state(**kwargs) -> None:
    """Best-effort state writer.

    The manager is only an lhr observer in --no-commit --no-push mode. A transient
    macOS/external-volume PermissionError while writing the state file must not
    crash the observer or affect the protected canonical backend.
    """
    state = {}
    try:
        if STATE_PATH.exists():
            try:
                state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            except Exception:
                state = {}
        state.update(kwargs)
        state["updated_at"] = stamp()
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_PATH.with_suffix(STATE_PATH.suffix + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(STATE_PATH)
    except OSError as e:
        log(f"STATE_WRITE_FAILED path={STATE_PATH} error={type(e).__name__}")


def protected_backend_active() -> tuple[bool, str]:
    """Return true when a non-lhr interim/fixed backend is already configured and healthy.

    This prevents the localhost.run observer from overwriting a healthier Cloudflare
    quick/named/VPS backend in data/tracking_public_url.json. The lhr manager may
    still monitor lhr.life, but it must not become canonical while a protected
    backend is alive.
    """
    cfg_path = ROOT / "data/tracking_public_url.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except Exception:
        return False, "no_config"
    url = str(cfg.get("current_backend_url") or cfg.get("public_tracking_url") or "").rstrip("/")
    kind = str(cfg.get("kind") or "")
    if not url or ".lhr.life" in url:
        return False, "no_protected_backend"
    if kind in {"cloudflare_quick_tunnel", "cloudflare_named_tunnel", "vps_reverse_proxy", "localhostrun_account_key", "custom_fixed_backend"}:
        ok, detail = quick_backend_ok(url)
        return ok, f"{kind}:{url}:{detail}"
    return False, f"unprotected_kind={kind}"


def sync_url(url: str, commit: bool, push: bool) -> bool:
    if not commit and not push:
        log(f"SYNC_SKIPPED_OBSERVE_ONLY observed_lhr={url} reason=no_commit_no_push")
        write_state(last_observed_lhr_url=url, last_sync_url=url, last_sync_ok=True, last_sync_rc="skipped_observe_only")
        return True
    protected_ok, protected_detail = protected_backend_active()
    if protected_ok:
        log(f"SYNC_SKIPPED_PROTECTED_BACKEND observed_lhr={url} protected={protected_detail}")
        write_state(last_observed_lhr_url=url, last_sync_url=url, last_sync_ok=True, last_sync_rc="skipped_protected_backend", protected_backend_detail=protected_detail)
        return True
    cmd = [sys.executable, str(ROOT / "scripts/sync_tracking_tunnel.py"), "--url", url]
    if commit:
        cmd.append("--commit")
    if push:
        cmd.append("--push")
    log("SYNC_START url=" + url)
    try:
        p = subprocess.run(cmd, cwd=str(ROOT), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
    except subprocess.TimeoutExpired as e:
        partial = e.stdout or ""
        if isinstance(partial, bytes):
            partial = partial.decode("utf-8", "replace")
        for line in str(partial).splitlines():
            log("SYNC_OUT " + line)
        write_state(last_sync_url=url, last_sync_ok=False, last_sync_rc="timeout")
        log(f"SYNC_TIMEOUT url={url} timeout=90s")
        return False
    for line in p.stdout.splitlines():
        log("SYNC_OUT " + line)
    ok = p.returncode == 0
    write_state(last_sync_url=url, last_sync_ok=ok, last_sync_rc=p.returncode)
    log(f"SYNC_DONE url={url} ok={ok} rc={p.returncode}")
    return ok


def mark_provider_degraded(url: str, detail: str) -> None:
    """Reflect tunnel provider failure in dashboard JSON without accepting a bad backend as healthy."""
    now = stamp()
    data_dir = ROOT / "data"
    stable_gateway = "https://araelaver.github.io/revenue-ops-dashboard/track.html"
    tracking_card = {
        "area": "Tracking",
        "name": "Tracking",
        "status": "blocked",
        "status_label": "provider_degraded",
        "summary": "localhost.run anonymous tunnel is repeatedly failing health checks.",
        "detail": "Stable gateway is preserved, but the current rotating backend is unhealthy.",
        "current_backend": url,
        "gateway": stable_gateway,
        "root_cause": detail,
        "next_action": "Use account-backed localhost.run, Cloudflare Tunnel, VPS reverse proxy, or custom tracking domain for durable public tracking.",
        "updated_at": now,
    }
    for rel in ["status.json", "issue_resolution_status.json", "hermes_feature_activation_matrix.json"]:
        path = data_dir / rel
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if rel == "status.json":
            payload["tracking_public_backend_status"] = tracking_card
            payload["tracking_gateway_status"] = "provider_degraded"
            payload["tracking_last_error"] = detail
            board = payload.get("bottleneck_board")
            if isinstance(board, list):
                board = [x for x in board if not (isinstance(x, dict) and (x.get("area") == "Tracking" or x.get("name") == "Tracking"))]
                board.append(tracking_card)
                payload["bottleneck_board"] = board
            elif isinstance(board, dict):
                board["tracking"] = tracking_card
                payload["bottleneck_board"] = board
            else:
                payload["bottleneck_board"] = [tracking_card]
        else:
            payload.setdefault("tracking", {})
            if isinstance(payload.get("tracking"), dict):
                payload["tracking"].update(tracking_card)
            payload["tracking_gateway_status"] = "provider_degraded"
            payload["tracking_last_error"] = detail
        payload["last_updated"] = now
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    ap.add_argument("--commit", action="store_true", default=False)
    ap.add_argument("--no-commit", dest="commit", action="store_false")
    ap.add_argument("--push", action="store_true", default=False)
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
                        pre_ok, pre_detail = quick_backend_ok(url)
                        log(f"PRE_SYNC_HEALTH url={url} ok={pre_ok} detail={pre_detail}")
                        if not pre_ok:
                            mark_provider_degraded(url, pre_detail)
                            write_state(status="pre_sync_health_failed_restarting", failed_url=url, current_url=url, last_health_ok=False, last_health_detail=pre_detail, last_health_at=stamp(), tunnel_pid=child.pid, manager_pid=os.getpid())
                            restart_requested = True
                            if child.poll() is None:
                                child.terminate()
                            break
                        ok = sync_url(url, commit=args.commit, push=args.push)
                        if not ok:
                            mark_provider_degraded(url, f"sync_failed rc={0 if ok else 'nonzero'}")
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
                        mark_provider_degraded(current_url, detail)
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
