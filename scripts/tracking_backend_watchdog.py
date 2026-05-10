#!/usr/bin/env python3
"""Watch and protect Hermes tracking backend configuration.

Interim purpose:
- Keep Cloudflare quick tunnel as canonical while fixed backend auth/domain is blocked.
- Detect accidental fallback to anonymous lhr.life and restore the last healthy trycloudflare URL.
- Write dashboard-visible status without printing secrets.

This is not a replacement for a fixed Cloudflare named tunnel/VPS backend.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path('/Volumes/WorkDrive/Develop/48.HermesAgent/dashboard')
TRACKING_JSON = ROOT / 'data/tracking_public_url.json'
CF_LOG = ROOT / 'logs/cloudflare_quick_tracking_tunnel.log'
STATUS_OUT = ROOT / 'data/tracking_backend_watchdog_status.json'
DASHBOARD_FILES = [
    ROOT / 'data/status.json',
    ROOT / 'data/performance_snapshot.json',
    ROOT / 'data/growth_ops_status.json',
    ROOT / 'data/revenue_conversion_fix_status.json',
]


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def health_ok(base: str, timeout: int = 8) -> tuple[bool, dict]:
    base = base.rstrip('/')
    try:
        with urllib.request.urlopen(base + '/health', timeout=timeout) as r:
            body = r.read(500).decode('utf-8', 'ignore')
            ok = r.status == 200 and 'hermes-tracking' in body
            return ok, {'status': r.status, 'ok': ok, 'tracking_ok': 'hermes-tracking' in body}
    except Exception as e:
        return False, {'ok': False, 'error': type(e).__name__}


def lead_probe(base: str) -> dict:
    payload = json.dumps({
        'site': 'unpre',
        'content_id': 'tracking_backend_watchdog',
        'offer_id': 'unpre_lead_magnet',
        'lead_type': 'ops_watchdog',
        'email_hash': 'synthetic_watchdog',
        'source': 'tracking_backend_watchdog',
    }).encode('utf-8')
    req = urllib.request.Request(
        base.rstrip('/') + '/lead',
        data=payload,
        headers={'content-type': 'application/json', 'user-agent': 'HermesTrackingWatchdog/1.0'},
        method='POST',
    )
    last_error = None
    for attempt in range(1, 4):
        try:
            with urllib.request.urlopen(req, timeout=18) as r:
                body = r.read(500).decode('utf-8', 'ignore')
                return {'status': r.status, 'ok': r.status == 200 and 'event_id' in body, 'attempt': attempt}
        except Exception as e:
            last_error = type(e).__name__
    return {'ok': False, 'error': last_error, 'attempts': 3}


def find_healthy_trycloudflare() -> tuple[str | None, list[dict]]:
    candidates: list[str] = []
    if CF_LOG.exists():
        for u in re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', CF_LOG.read_text(errors='ignore')):
            if u not in candidates:
                candidates.append(u)
    checked: list[dict] = []
    for u in reversed(candidates):
        ok, detail = health_ok(u)
        checked.append({'url': u, 'health': detail})
        if ok:
            return u, checked
    return None, checked


def is_lhr(url: str) -> bool:
    return bool(re.search(r'https://[a-z0-9]+\.lhr\.life', url or ''))


def main() -> int:
    stamp = now_iso()
    cfg = read_json(TRACKING_JSON)
    current = str(cfg.get('current_backend_url') or cfg.get('public_tracking_url') or '').rstrip('/')
    current_ok, current_health = health_ok(current) if current else (False, {'ok': False, 'error': 'missing_current_backend'})
    action = 'none'
    restored_url = None
    checked_cf: list[dict] = []

    should_restore = (not current_ok) or is_lhr(current)
    if should_restore:
        restored_url, checked_cf = find_healthy_trycloudflare()
        if restored_url:
            history = cfg.setdefault('history', [])
            history.append({'updated_at': stamp, 'url': restored_url, 'source': 'tracking_backend_watchdog_restore', 'stable': False})
            if len(history) > 120:
                cfg['history'] = history[:5] + history[-90:]
            cfg.update({
                'updated_at': stamp,
                'last_updated': stamp,
                'public_tracking_url': restored_url,
                'current_backend_url': restored_url,
                'kind': 'cloudflare_quick_tunnel',
                'stable': False,
                'fixed_backend': False,
                'manager_policy': 'watchdog_protects_against_lhr_canonical_regression',
                'watchdog_restored_at': stamp,
                'watchdog_reason': 'current_unhealthy_or_lhr',
            })
            write_json(TRACKING_JSON, cfg)
            current = restored_url
            current_ok, current_health = health_ok(current)
            action = 'restored_cloudflare_quick_tunnel'
        else:
            action = 'restore_needed_but_no_healthy_trycloudflare_found'
    else:
        action = 'current_backend_healthy'

    lead = lead_probe(current) if current_ok else {'ok': False, 'skipped': True}
    status = {
        'updated_at': stamp,
        'action': action,
        'current_backend_url': current,
        'kind': cfg.get('kind'),
        'stable': bool(cfg.get('stable')),
        'fixed_backend': bool(cfg.get('fixed_backend')),
        'current_health': current_health,
        'lead_probe': lead,
        'checked_trycloudflare_candidates': checked_cf[-5:],
        'fixed_backend_blocker': 'cloudflare_cert_or_managed_hostname_required' if not cfg.get('fixed_backend') else None,
    }
    write_json(STATUS_OUT, status)

    for fp in DASHBOARD_FILES:
        data = read_json(fp)
        data['last_updated'] = stamp
        data.setdefault('tracking_backend_watchdog', {}).update(status)
        data.setdefault('tracking_backend', {}).update({
            'current_backend_url': current,
            'watchdog_status': action,
            'watchdog_last_updated': stamp,
            'public_health': current_health,
            'lead_probe': lead,
            'stable': bool(cfg.get('stable')),
            'fixed_backend': bool(cfg.get('fixed_backend')),
        })
        write_json(fp, data)

    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if current_ok and lead.get('ok') else 2


if __name__ == '__main__':
    raise SystemExit(main())
