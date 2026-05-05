#!/usr/bin/env python3
"""Synchronize rotating localhost.run tracking tunnel across dashboard state and Pages gateway.

Usage:
  python3 scripts/sync_tracking_tunnel.py --url https://xxxx.lhr.life [--commit] [--push]

This intentionally uses only Python stdlib so it works in the user's cron/macOS env.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import http.client
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STABLE_GATEWAY = "https://araelaver.github.io/revenue-ops-dashboard/track.html"
TRACK_RE = re.compile(r"^https://[a-z0-9]{8,32}\.lhr\.life/?$")
FALLBACK_RE = re.compile(r"const embeddedFallbackBase = 'https://[a-z0-9]+\.lhr\.life';")


def now_iso() -> str:
    return _dt.datetime.now().astimezone().isoformat(timespec="seconds")


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch(url: str, timeout: int = 12) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "HermesTrackingSync/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status), r.geturl(), r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return int(e.code), e.geturl(), e.read().decode("utf-8", "replace")


def fetch_retry(url: str, timeout: int = 12, attempts: int = 5, delay: float = 2.0) -> tuple[int, str, str]:
    last_error = None
    for i in range(1, attempts + 1):
        try:
            return fetch(url, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.RemoteDisconnected, http.client.BadStatusLine) as e:
            last_error = e
            if i < attempts:
                time.sleep(delay * i)
    raise RuntimeError(f"fetch_retry failed url={url} attempts={attempts} last_error={last_error!r}")


def verify_backend(base: str) -> dict:
    health_status, _, health_body = fetch_retry(base.rstrip("/") + "/health", attempts=6, delay=2.0)
    target = urllib.parse.quote("https://unpre.co.kr/", safe="")
    test_url = f"{base.rstrip('/')}/t?site=unpre&slot=sync-check&content_id=sync-{int(_dt.datetime.now().timestamp())}&target={target}"
    req = urllib.request.Request(test_url, headers={"User-Agent": "HermesTrackingSync/1.0"})
    redirect_status, redirect_url = 0, ""
    last_redirect_error = None
    for i in range(1, 7):
        try:
            opener = urllib.request.build_opener(NoRedirectHandler)
            opener.open(req, timeout=12)
            redirect_status, redirect_url = 0, ""
            break
        except urllib.error.HTTPError as e:
            redirect_status = int(e.code)
            redirect_url = e.headers.get("Location", "")
            if redirect_status >= 500 and i < 6:
                last_redirect_error = f"HTTP {redirect_status}"
                time.sleep(2.0 * i)
                continue
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.RemoteDisconnected, http.client.BadStatusLine) as e:
            last_redirect_error = repr(e)
            if i < 6:
                time.sleep(2.0 * i)
    return {
        "health_status": health_status,
        "health_ok": health_status == 200 and "hermes-tracking" in health_body,
        "redirect_status": redirect_status,
        "redirect_url": redirect_url,
        "redirect_ok": redirect_status in (301, 302, 303, 307, 308) and redirect_url.startswith("https://unpre.co.kr"),
        "last_redirect_error": last_redirect_error,
    }


class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def update_tracking_json(new_url: str, stamp: str) -> None:
    p = ROOT / "data/tracking_public_url.json"
    data = read_json(p)
    history = data.setdefault("history", [])
    if not any(isinstance(h, dict) and (h.get("url") or h.get("public_tracking_url")) == new_url for h in history):
        history.append({"updated_at": stamp, "url": new_url, "source": "sync_tracking_tunnel.py"})
    data.update({
        "public_tracking_url": new_url,
        "current_backend_url": new_url,
        "stable_gateway_url": STABLE_GATEWAY,
        "mode": "stable_gateway_to_rotating_tunnel",
        "last_rotated_at": stamp,
        "last_updated": stamp,
        "source": "sync_tracking_tunnel.py",
        "stable": False,
        "rotation_automation": {
            "status": "script_managed",
            "script": str(ROOT / "scripts/sync_tracking_tunnel.py"),
            "manual_update_needed": False,
            "long_term_recommendation": "Replace anonymous localhost.run with account-backed localhost.run, Cloudflare Tunnel, VPS, or custom domain."
        },
    })
    write_json(p, data)


def update_status_files(new_url: str, stamp: str, verification: dict) -> None:
    for rel in ["data/status.json", "data/issue_resolution_status.json", "data/hermes_feature_activation_matrix.json"]:
        fp = ROOT / rel
        if not fp.exists():
            continue
        obj = read_json(fp)
        obj["last_updated"] = stamp
        obj.setdefault("tracking", {})
        obj["tracking"].update({
            "status": "active_stable_gateway_backend_rotated",
            "stable_gateway_url": STABLE_GATEWAY,
            "public_tracking_url": new_url,
            "current_backend_url": new_url,
            "last_rotated_at": stamp,
            "rotation_automation": "sync_tracking_tunnel.py",
            "backend_health_ok": verification.get("health_ok"),
            "backend_redirect_ok": verification.get("redirect_ok"),
            "note": "localhost.run backend rotated; content CTA remains stable via GitHub Pages gateway.",
        })
        obj.setdefault("bottleneck_board", {})
        tracking_card = {
            "status": "watch",
            "title": "CTA tracking backend",
            "root_cause": "localhost.run anonymous tunnel rotates frequently.",
            "next_action": "sync_tracking_tunnel.py updates backend config/track fallback and deploys Pages; migrate to account-backed tunnel or Cloudflare/VPS for durable fix.",
            "stable_gateway_url": STABLE_GATEWAY,
            "current_backend_url": new_url,
            "last_rotated_at": stamp,
        }
        bottleneck = obj.get("bottleneck_board")
        if isinstance(bottleneck, list):
            bottleneck = [x for x in bottleneck if not (isinstance(x, dict) and (x.get("area") == "Tracking" or x.get("name") == "Tracking" or x.get("title") == "CTA tracking backend"))]
            bottleneck.append({"area": "Tracking", **tracking_card})
            obj["bottleneck_board"] = bottleneck
        elif isinstance(bottleneck, dict):
            bottleneck["tracking"] = tracking_card
            obj["bottleneck_board"] = bottleneck
        else:
            obj["bottleneck_board"] = {"tracking": tracking_card}
        write_json(fp, obj)


def update_track_html(new_url: str) -> None:
    path = ROOT / "track.html"
    html = path.read_text(encoding="utf-8")
    html2, n = FALLBACK_RE.subn(f"const embeddedFallbackBase = '{new_url}';", html)
    if n != 1:
        raise RuntimeError("track.html embeddedFallbackBase replacement failed")
    path.write_text(html2, encoding="utf-8")


def validate_files() -> None:
    for rel in [
        "data/tracking_public_url.json",
        "data/status.json",
        "data/issue_resolution_status.json",
        "data/hermes_feature_activation_matrix.json",
    ]:
        json.loads((ROOT / rel).read_text(encoding="utf-8"))
    html = (ROOT / "track.html").read_text(encoding="utf-8")
    m = re.search(r"<script>(.*?)</script>", html, re.S)
    if not m:
        raise RuntimeError("track.html script block missing")
    tmp = ROOT / ".tmp_track_inline_check.js"
    tmp.write_text(m.group(1), encoding="utf-8")
    try:
        subprocess.check_call(["node", "--check", str(tmp)], cwd=str(ROOT), stdout=subprocess.DEVNULL)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
    subprocess.check_call(["node", "--check", "app.js"], cwd=str(ROOT), stdout=subprocess.DEVNULL)


def git_commit_push(commit: bool, push: bool, new_url: str) -> dict:
    result = {"committed": False, "pushed": False, "commit_hash": None}
    if not commit:
        return result
    files = [
        "track.html",
        "data/tracking_public_url.json",
        "data/status.json",
        "data/issue_resolution_status.json",
        "data/hermes_feature_activation_matrix.json",
    ]
    subprocess.check_call(["git", "add", *files], cwd=str(ROOT))
    diff = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=str(ROOT))
    if diff.returncode == 0:
        return result
    msg = f"Sync tracking backend tunnel {new_url.split('//',1)[1].split('.',1)[0]}"
    subprocess.check_call(["git", "commit", "-m", msg], cwd=str(ROOT))
    rev = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=str(ROOT), text=True).strip()
    result["committed"] = True
    result["commit_hash"] = rev
    if push:
        subprocess.check_call(["git", "push"], cwd=str(ROOT))
        result["pushed"] = True
    return result


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True, help="Current https://xxxx.lhr.life tunnel URL")
    ap.add_argument("--commit", action="store_true")
    ap.add_argument("--push", action="store_true")
    args = ap.parse_args()

    new_url = args.url.rstrip("/")
    if not TRACK_RE.match(new_url + "/") and not TRACK_RE.match(new_url):
        raise SystemExit(f"invalid localhost.run URL: {new_url}")
    stamp = now_iso()
    verification = verify_backend(new_url)
    if not verification.get("health_ok") or not verification.get("redirect_ok"):
        print(json.dumps({"ok": False, "stage": "verify_backend", "url": new_url, "verification": verification}, ensure_ascii=False, indent=2))
        return 2

    update_tracking_json(new_url, stamp)
    update_status_files(new_url, stamp, verification)
    update_track_html(new_url)
    validate_files()
    git_result = git_commit_push(args.commit, args.push, new_url)

    out = {
        "ok": True,
        "updated": stamp,
        "public_tracking_url": new_url,
        "stable_gateway_url": STABLE_GATEWAY,
        "verification": verification,
        "git": git_result,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
