#!/usr/bin/env python3
"""Keep an accountless fixed-subdomain localtunnel backend alive for Hermes tracking.

Purpose:
- Provide a practical no-Cloudflare-auth fallback to rotating lhr.life.
- Use a fixed localtunnel subdomain when available.
- Validate /health, /t redirect, and /lead before updating canonical tracking JSON.

This is still less durable than Cloudflare named tunnel or VPS, but it solves the
immediate lhr.life rotating/503 regression without operator browser auth.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path('/Volumes/WorkDrive/Develop/48.HermesAgent/dashboard')
DATA = ROOT / 'data'
LOGS = ROOT / 'logs'
TRACKING_JSON = DATA / 'tracking_public_url.json'
STATUS_OUT = DATA / 'localtunnel_tracking_backend_status.json'
PIDFILE = ROOT / '.localtunnel_tracking.pid'
LOGFILE = LOGS / 'localtunnel_tracking_backend.log'
SUBDOMAIN = os.environ.get('HERMES_LOCALTUNNEL_SUBDOMAIN', 'hermes-revenue-tracking-48')
PUBLIC_URL = f'https://{SUBDOMAIN}.loca.lt'
LOCAL_PORT = int(os.environ.get('HERMES_TRACKING_PORT', '8431'))
LOCAL_URL = f'http://127.0.0.1:{LOCAL_PORT}'
DASHBOARD_FILES = [
    DATA / 'status.json',
    DATA / 'performance_snapshot.json',
    DATA / 'growth_ops_status.json',
    DATA / 'revenue_conversion_fix_status.json',
    DATA / 'fixed_tracking_backend_status.json',
]


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def fetch(url: str, timeout: int = 10) -> tuple[int, str, str]:
    req = urllib.request.Request(url, headers={'User-Agent': 'HermesLocaltunnelManager/1.0'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return int(r.status), r.geturl(), r.read().decode('utf-8', 'replace')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def health_ok(base: str) -> tuple[bool, dict]:
    try:
        status, _, body = fetch(base.rstrip('/') + '/health')
        ok = status == 200 and 'hermes-tracking' in body
        return ok, {'status': status, 'ok': ok, 'tracking_ok': 'hermes-tracking' in body}
    except Exception as e:
        return False, {'ok': False, 'error': type(e).__name__}


def redirect_ok(base: str) -> dict:
    target = urllib.parse.quote('https://unpre.co.kr/', safe='')
    url = f"{base.rstrip('/')}/t?site=unpre&slot=localtunnel-check&offer_id=unpre_check&content_id=lt-{int(time.time())}&target={target}"
    opener = urllib.request.build_opener(NoRedirect)
    try:
        opener.open(urllib.request.Request(url, headers={'User-Agent': 'HermesLocaltunnelManager/1.0'}), timeout=10)
        return {'ok': False, 'error': 'redirect_not_raised'}
    except urllib.error.HTTPError as e:
        loc = e.headers.get('Location', '')
        return {'status': int(e.code), 'location': loc, 'ok': int(e.code) in (301, 302, 303, 307, 308) and loc.startswith('https://unpre.co.kr')}
    except Exception as e:
        return {'ok': False, 'error': type(e).__name__}


def lead_ok(base: str) -> dict:
    payload = json.dumps({
        'site': 'unpre',
        'content_id': 'localtunnel_tracking_manager',
        'offer_id': 'localtunnel_fixed_probe',
        'lead_type': 'ops_probe',
        'email_hash': 'synthetic_localtunnel_probe',
        'source': 'localtunnel_tracking_manager',
    }).encode('utf-8')
    req = urllib.request.Request(
        base.rstrip('/') + '/lead',
        data=payload,
        headers={'Content-Type': 'application/json', 'User-Agent': 'HermesLocaltunnelManager/1.0'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            body = r.read(500).decode('utf-8', 'ignore')
            return {'status': int(r.status), 'ok': int(r.status) == 200 and 'event_id' in body}
    except Exception as e:
        return {'ok': False, 'error': type(e).__name__}


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def known_pid() -> int | None:
    try:
        pid = int(PIDFILE.read_text().strip())
        if pid_alive(pid):
            return pid
    except Exception:
        pass
    return None


def start_tunnel() -> int:
    LOGS.mkdir(parents=True, exist_ok=True)
    log = open(LOGFILE, 'ab', buffering=0)
    cmd = ['npx', '--yes', 'localtunnel', '--port', str(LOCAL_PORT), '--subdomain', SUBDOMAIN]
    proc = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=log,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        close_fds=True,
    )
    PIDFILE.write_text(str(proc.pid) + '\n', encoding='utf-8')
    return int(proc.pid)


def ensure_tunnel() -> tuple[int | None, bool]:
    pid = known_pid()
    if pid:
        return pid, False
    return start_tunnel(), True


def wait_until_healthy(base: str, seconds: int = 35) -> tuple[bool, dict]:
    last = {'ok': False, 'error': 'not_checked'}
    deadline = time.time() + seconds
    while time.time() < deadline:
        ok, detail = health_ok(base)
        last = detail
        if ok:
            return True, detail
        time.sleep(2)
    return False, last


def update_canonical(stamp: str, verification: dict, pid: int | None, restarted: bool) -> None:
    cfg = read_json(TRACKING_JSON)
    history = cfg.setdefault('history', [])
    history.append({'updated_at': stamp, 'url': PUBLIC_URL, 'source': 'localtunnel_tracking_manager', 'kind': 'localtunnel_fixed_subdomain'})
    if len(history) > 120:
        cfg['history'] = history[:5] + history[-90:]
    cfg.update({
        'updated_at': stamp,
        'last_updated': stamp,
        'public_tracking_url': PUBLIC_URL,
        'current_backend_url': PUBLIC_URL,
        'kind': 'localtunnel_fixed_subdomain',
        'mode': 'fixed_subdomain_to_local_tracking_server',
        'stable': False,
        'fixed_backend': True,
        'fixed_backend_level': 'accountless_fixed_subdomain_watchdog_protected',
        'local_server': LOCAL_URL,
        'manager_policy': 'localtunnel_fixed_subdomain_preferred_over_lhr_and_trycloudflare_when_healthy',
        'last_fixed_backend_verified_at': stamp,
        'last_fixed_backend_verification': verification,
        'localtunnel_pid': pid,
        'localtunnel_restarted': restarted,
    })
    write_json(TRACKING_JSON, cfg)


def update_dashboards(stamp: str, status: dict) -> None:
    for fp in DASHBOARD_FILES:
        data = read_json(fp)
        data['updated_at'] = stamp
        data['last_updated'] = stamp
        data['localtunnel_tracking_backend'] = status
        data.setdefault('tracking_backend', {}).update({
            'current_backend_url': PUBLIC_URL,
            'kind': 'localtunnel_fixed_subdomain',
            'stable': False,
            'fixed_backend': True,
            'fixed_backend_level': 'accountless_fixed_subdomain_watchdog_protected',
            'public_health': status.get('health'),
            'lead_probe': status.get('lead_probe'),
            'watchdog_status': status.get('action'),
            'next_action': 'Cloudflare named tunnel or VPS remains the production-grade final fix; localtunnel fixed subdomain is the no-auth operational replacement for lhr.life.',
        })
        write_json(fp, data)


def main() -> int:
    stamp = now_iso()
    pid, restarted = ensure_tunnel()
    health_pass, health = wait_until_healthy(PUBLIC_URL)
    redirect = redirect_ok(PUBLIC_URL) if health_pass else {'ok': False, 'skipped': True}
    lead = lead_ok(PUBLIC_URL) if health_pass else {'ok': False, 'skipped': True}
    ok = bool(health_pass and redirect.get('ok') and lead.get('ok'))
    verification = {'health': health, 'redirect': redirect, 'lead_probe': lead}
    status = {
        'updated_at': stamp,
        'action': 'localtunnel_fixed_subdomain_healthy' if ok and not restarted else ('localtunnel_started_and_healthy' if ok else 'localtunnel_unhealthy'),
        'public_tracking_url': PUBLIC_URL,
        'kind': 'localtunnel_fixed_subdomain',
        'stable': False,
        'fixed_backend': True,
        'pid': pid,
        'restarted': restarted,
        'health': health,
        'redirect': redirect,
        'lead_probe': lead,
        'production_note': 'No-auth fixed-subdomain fallback; Cloudflare named tunnel/VPS is still stronger for production SLA.',
    }
    if ok:
        update_canonical(stamp, verification, pid, restarted)
    write_json(STATUS_OUT, status)
    update_dashboards(stamp, status)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if ok else 2


if __name__ == '__main__':
    raise SystemExit(main())
