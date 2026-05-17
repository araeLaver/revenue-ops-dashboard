#!/usr/bin/env python3
"""Lightweight Hermes revenue tracking server.

Endpoints:
  GET  /health
  GET  /t?site=unpre&slot=lead&target=https%3A%2F%2F...
  POST /lead
  POST /revenue

Writes dependency-free JSONL events under dashboard/data/analytics/.
No cookies, no PII requirement; IP/user-agent are hashed for coarse dedupe only.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote
from pathlib import Path
import json, os, sys, time, hashlib, datetime, uuid

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
ANALYTICS = DATA / 'analytics'
ANALYTICS.mkdir(parents=True, exist_ok=True)
LINK_REGISTRY = DATA / 'link_registry.json'
HOST = os.getenv('HERMES_TRACKING_HOST', '127.0.0.1')
PORT = int(os.getenv('HERMES_TRACKING_PORT', '8431'))
ALLOWED_REDIRECT_HOSTS = {
    'unpre.co.kr','untab.co.kr','skewese.com','www.coupang.com','lpweb.kr',
    'youtube.com','www.youtube.com','youtu.be'
}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec='seconds')


def sha(s):
    return hashlib.sha256((s or '').encode('utf-8')).hexdigest()[:16]


def load_links():
    try:
        return json.loads(LINK_REGISTRY.read_text(encoding='utf-8'))
    except Exception:
        return {}


def resolve_placeholder(site, placeholder):
    links = load_links()
    return (links.get('wp_links', {}).get(site, {}) or {}).get(placeholder)


def safe_target(url):
    if not url:
        return ''
    parsed = urlparse(url)
    if parsed.scheme not in ('http','https'):
        return ''
    if parsed.netloc not in ALLOWED_REDIRECT_HOSTS:
        return ''
    return url


def append_jsonl(name, payload):
    payload = dict(payload)
    payload.setdefault('event_id', f"evt_{int(time.time()*1000)}_{uuid.uuid4().hex[:8]}")
    payload.setdefault('timestamp', now_iso())
    path = ANALYTICS / name
    with path.open('a', encoding='utf-8') as f:
        f.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + '\n')
    return payload


def update_rollup(event_type):
    rollup = DATA / 'performance_snapshot.json'
    try:
        obj = json.loads(rollup.read_text(encoding='utf-8'))
    except Exception:
        obj = {}
    obj.setdefault('conversion_event_rollup', {})
    obj['conversion_event_rollup']['updated_at'] = now_iso()
    for key, file_name in [('cta_clicks','cta_click_events.jsonl'), ('leads','lead_events.jsonl'), ('revenue_events','revenue_events.jsonl')]:
        p = ANALYTICS / file_name
        try:
            obj['conversion_event_rollup'][key] = sum(1 for _ in p.open(encoding='utf-8')) if p.exists() else 0
        except Exception:
            obj['conversion_event_rollup'][key] = 0
    obj['conversion_event_rollup']['latest_event_type'] = event_type
    rollup.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


class Handler(BaseHTTPRequestHandler):
    server_version = 'HermesTracking/1.0'

    def _client_meta(self):
        ip = self.headers.get('X-Forwarded-For', self.client_address[0] if self.client_address else '')
        ua = self.headers.get('User-Agent', '')
        return {'ip_hash': sha(ip), 'ua_hash': sha(ua), 'referrer': self.headers.get('Referer', '')[:500]}

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        qs = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        if parsed.path == '/health':
            self._json(200, {'ok': True, 'service': 'hermes-tracking', 'time': now_iso()})
            return
        if parsed.path in ('/t', '/track'):
            site = qs.get('site','unknown')[:80]
            slot = qs.get('slot','unknown')[:80]
            content_id = qs.get('content_id','')[:200]
            placeholder = qs.get('placeholder','')[:80]
            target = safe_target(unquote(qs.get('target','')))
            if not target and placeholder:
                target = safe_target(resolve_placeholder(site, placeholder))
            if not target:
                self._json(400, {'ok': False, 'error': 'missing_or_unsafe_target'})
                return
            target_parsed = urlparse(target)
            offer_id = (qs.get('offer_id') or qs.get('offer') or slot or placeholder or 'unknown')[:120]
            intent = qs.get('intent', '')[:120]
            utm_source = qs.get('utm_source', '')[:120]
            utm_medium = qs.get('utm_medium', '')[:120]
            utm_campaign = qs.get('utm_campaign', '')[:160]
            client_meta = self._client_meta()
            event = append_jsonl('cta_click_events.jsonl', {
                'type': 'cta_click',
                'site': site,
                'slot': slot,
                'offer_id': offer_id,
                'intent': intent,
                'utm_source': utm_source,
                'utm_medium': utm_medium,
                'utm_campaign': utm_campaign,
                'content_id': content_id,
                'placeholder': placeholder,
                'target': target,
                'target_host': target_parsed.netloc[:160],
                'target_path': target_parsed.path[:240],
                **client_meta
            })
            if intent == 'lead_page_outbound' or slot == 'lead_page_outbound':
                append_jsonl('revenue_events.jsonl', {
                    'type': 'revenue_proxy',
                    'site': site,
                    'content_id': content_id,
                    'offer_id': offer_id,
                    'amount': '0',
                    'currency': 'KRW',
                    'source': 'lead_page_outbound',
                    'target_host': target_parsed.netloc[:160],
                    'target_path': target_parsed.path[:240],
                    'utm_source': utm_source,
                    'utm_medium': utm_medium,
                    'utm_campaign': utm_campaign,
                    'order_ref_hash': '',
                    **client_meta
                })
                update_rollup('revenue_proxy')
            else:
                update_rollup('cta_click')
            self.send_response(302)
            self.send_header('Location', target)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return
        self._json(404, {'ok': False, 'error': 'not_found'})

    def _read_payload(self):
        n = int(self.headers.get('Content-Length','0') or 0)
        raw = self.rfile.read(min(n, 1024*1024)) if n else b''
        ctype = self.headers.get('Content-Type','')
        if 'application/json' in ctype:
            try:
                return json.loads(raw.decode('utf-8')) if raw else {}
            except Exception:
                return {'_raw': raw.decode('utf-8','replace')}
        return {k: v[0] for k, v in parse_qs(raw.decode('utf-8','replace')).items()}

    def do_POST(self):
        parsed = urlparse(self.path)
        payload = self._read_payload()
        if parsed.path == '/lead':
            allowed = {k: str(payload.get(k,''))[:1000] for k in ['site','content_id','offer_id','lead_type','email_hash','source','note']}
            event = append_jsonl('lead_events.jsonl', {'type':'lead', **allowed, **self._client_meta()})
            update_rollup('lead')
            self._json(200, {'ok': True, 'event_id': event['event_id']})
            return
        if parsed.path == '/revenue':
            allowed = {k: str(payload.get(k,''))[:1000] for k in ['site','content_id','offer_id','amount','currency','source','order_ref_hash']}
            event = append_jsonl('revenue_events.jsonl', {'type':'revenue', **allowed, **self._client_meta()})
            update_rollup('revenue')
            self._json(200, {'ok': True, 'event_id': event['event_id']})
            return
        self._json(404, {'ok': False, 'error': 'not_found'})

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (now_iso(), fmt % args))


if __name__ == '__main__':
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(json.dumps({'ok': True, 'service':'hermes-tracking', 'host':HOST, 'port':PORT, 'root':str(ROOT)}, ensure_ascii=False), flush=True)
    httpd.serve_forever()
