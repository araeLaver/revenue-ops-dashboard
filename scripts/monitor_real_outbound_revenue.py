#!/usr/bin/env python3
"""Monitor real customer outbound/revenue_proxy events, excluding probes.
Writes a compact JSON status for dashboard and cron reports.
"""
from pathlib import Path
import json, datetime, os

ROOT = Path('/Volumes/WorkDrive/Develop/48.HermesAgent/dashboard')
AN = ROOT / 'data' / 'analytics'
OUT = ROOT / 'data' / 'real_outbound_revenue_monitor.json'
PROBE_TERMS = [
    'manager-health','sync-check','smoke','probe','verify','test','rotation-check','tunnel-rotation','ops_smoke',
    'fixed_backend_probe','observer_alert_probe','localtunnel_fixed_probe','tracking_backend_watchdog','backend_watchdog',
    'watchdog','healthcheck','health-check','post_upload_probe','upload_probe','tracking_backend_check','localtunnel-check',
    'cf-quick-check','fixed-check','fixed-backend-check','localtunnel-test','unpre_check','address_check','debug',
    'manager-restart','fallback-check','fixed-backend-smoke','ops','agent-check','backend-check','revenue_proxy_probe',
    'fixed_backend_revenue_proxy_probe','fixed_backend_check','HermesRevenueProxyProbe'.lower(), 'HermesMonetizationVerify'.lower()
]
MONEY_CAMPAIGNS = ['money_cta_expansion','offer_match_fix','loan_money_fix','shorts_revenue_fix','revenue_zero_fix']

def now():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds')

def iter_jsonl(name):
    p = AN / name
    if not p.exists():
        return
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        if not line.strip():
            continue
        try:
            yield json.loads(line)
        except Exception:
            continue

def is_probe(obj):
    blob = json.dumps(obj, ensure_ascii=False).lower()
    return any(t.lower() in blob for t in PROBE_TERMS)

def summarize(name):
    raw = real = 0
    real_money = 0
    by_offer = {}
    by_source = {}
    latest_real = []
    for obj in iter_jsonl(name) or []:
        raw += 1
        if is_probe(obj):
            continue
        real += 1
        blob = json.dumps(obj, ensure_ascii=False)
        if any(c in blob for c in MONEY_CAMPAIGNS) or obj.get('type') == 'revenue_proxy' or obj.get('source') == 'lead_page_outbound':
            real_money += 1
        offer = obj.get('offer_id') or 'unknown'
        src = obj.get('source') or obj.get('utm_source') or obj.get('slot') or 'unknown'
        by_offer[offer] = by_offer.get(offer, 0) + 1
        by_source[src] = by_source.get(src, 0) + 1
        latest_real.append(obj)
        latest_real = latest_real[-10:]
    return {'raw': raw, 'real': real, 'real_money_path': real_money, 'by_offer': by_offer, 'by_source': by_source, 'latest_real': latest_real}

out = {
    'updated_at': now(),
    'cta_clicks': summarize('cta_click_events.jsonl'),
    'leads': summarize('lead_events.jsonl'),
    'revenue_events': summarize('revenue_events.jsonl'),
    'status': 'waiting_for_customer_events',
    'notes': [
        'probe/debug/watchdog events excluded',
        'revenue_proxy is not confirmed revenue; it is a tracked money-path outbound action',
        'confirmed revenue remains separate and requires affiliate/CRM reconciliation'
    ]
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(json.dumps(out, ensure_ascii=False, indent=2))
