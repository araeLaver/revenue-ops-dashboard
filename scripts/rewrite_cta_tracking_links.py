#!/usr/bin/env python3
"""Rewrite CTA links/placeholders to Hermes tracking redirect URLs.

Default is dry-run and targets draft states that have not been externally published yet.
Use --apply to write changes.

Examples:
  python3 scripts/rewrite_cta_tracking_links.py --dry-run
  python3 scripts/rewrite_cta_tracking_links.py --apply --states pending reviewed revised

This intentionally skips drafts/published by default to avoid mutating archival source after publication.
"""
from __future__ import annotations
from pathlib import Path
from urllib.parse import quote
import argparse, datetime, json, re

ROOT = Path('/Volumes/WorkDrive/Develop/48.HermesAgent/dashboard')
DATA = ROOT / 'data'
DRAFTS = ROOT / 'drafts'
DEFAULT_BASE = 'http://127.0.0.1:8431'
PLACEHOLDERS = ['[LEAD_FORM_LINK]', '[AFFILIATE_LINK]', '[COUPANG_LINK]', '[LINKPRICE_LINK]', '[SERVICE_LINK]']
SITE_RE = re.compile(r'(?:^|[_-])wp[-_](unpre|untab|skewese)(?:[_-]|$)|(?:^|[_-])(unpre|untab|skewese)(?:[_-]|$)', re.I)
YT_RE = re.compile(r'yt[-_](araelaver|kdowndan|micheuhasi|untabcompany)', re.I)
URL_RE = re.compile(r'https?://(?:unpre\.co\.kr|untab\.co\.kr|skewese\.com|www\.coupang\.com|lpweb\.kr)[^\s\)\]\}\<"\']+')


def now():
    return datetime.datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')


def load_json(p, default):
    try:
        return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return default


def infer_site(path: Path, text: str) -> str:
    m = SITE_RE.search(path.name)
    if m:
        return (m.group(1) or m.group(2)).lower()
    # YT channels generally bridge to unpre unless explicit site appears in body.
    for site in ['unpre','untab','skewese']:
        if site in text.lower():
            return site
    return 'unpre'


def tracking_url(base: str, site: str, slot: str, content_id: str, target: str = '', placeholder: str = '') -> str:
    qs = [f'site={quote(site)}', f'slot={quote(slot)}', f'content_id={quote(content_id)}']
    if placeholder:
        qs.append(f'placeholder={quote(placeholder)}')
    if target:
        qs.append(f'target={quote(target, safe="")}')
    clean = base.rstrip('/')
    # Stable static gateway mode: e.g. GitHub Pages /track.html reads data/tracking_public_url.json
    # and forwards to the current live /t endpoint. This keeps published CTA URLs stable even
    # when localhost.run tunnel URLs rotate.
    if clean.endswith('.html'):
        sep = '&' if '?' in clean else '?'
        return clean + sep + '&'.join(qs)
    return clean + '/t?' + '&'.join(qs)


def rewrite_text(path: Path, text: str, base: str):
    site = infer_site(path, text)
    content_id = path.stem
    changes = []
    out = text

    # Normalize previously rewritten local tracking URLs to the currently configured public base.
    # This keeps unpublished drafts usable after moving from localhost to a tunnel/domain.
    clean_base = base.rstrip('/')
    if clean_base != DEFAULT_BASE:
        local_count = out.count(DEFAULT_BASE)
        if local_count:
            out = out.replace(DEFAULT_BASE, clean_base)
            changes.append({'kind':'tracking_base_normalized','from':DEFAULT_BASE,'to':clean_base,'count':local_count})
        # Convert rotating localhost.run direct tracking URLs to the stable gateway/current base.
        # Example: https://abc123.lhr.life/t?... -> https://araelaver.github.io/revenue-ops-dashboard/track.html?...
        def lhr_tracking_sub(m):
            qs = m.group(1)
            if clean_base.endswith('.html'):
                sep = '&' if '?' in clean_base else '?'
                repl = clean_base + sep + qs
            else:
                repl = clean_base + '/t?' + qs
            changes.append({'kind':'rotating_lhr_tracking_normalized','to':clean_base})
            return repl
        out = re.sub(r'https://[a-f0-9]{12,16}\.lhr\.life/t\?([^\s\)\]\}\<"\']+)', lhr_tracking_sub, out)

    # Replace placeholders only when not already inside a tracking URL.
    for ph in PLACEHOLDERS:
        if ph in out:
            slot = ph.strip('[]').lower().replace('_link','')
            repl = tracking_url(base, site, slot, content_id, placeholder=ph)
            count = out.count(ph)
            out = out.replace(ph, repl)
            changes.append({'kind':'placeholder','placeholder':ph,'count':count,'tracking_url':repl})

    # Wrap direct monetization URLs unless already tracking server URL.
    def url_sub(m):
        url = m.group(0)
        if '/t?' in url or '127.0.0.1:8431' in url:
            return url
        host = url.split('/')[2]
        slot = 'direct'
        if 'coupang.com' in host: slot = 'coupang'
        elif 'lpweb.kr' in host: slot = 'linkprice'
        elif '/checklist/' in url: slot = 'lead'
        elif '/consulting/' in url: slot = 'service'
        repl = tracking_url(base, site, slot, content_id, target=url)
        changes.append({'kind':'direct_url','url':url,'slot':slot,'tracking_url':repl})
        return repl

    out = URL_RE.sub(url_sub, out)
    return out, changes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--base-url', default=DEFAULT_BASE)
    ap.add_argument('--states', nargs='+', default=['pending','reviewed','revised'])
    ap.add_argument('--limit', type=int, default=0)
    args = ap.parse_args()

    manifest = {'updated_at': now(), 'apply': bool(args.apply), 'base_url': args.base_url, 'states': args.states, 'files': [], 'summary': {'scanned':0,'changed_files':0,'changes':0}}
    count = 0
    for state in args.states:
        d = DRAFTS / state
        if not d.exists():
            continue
        for path in sorted(d.glob('*.md')):
            if args.limit and count >= args.limit:
                break
            count += 1
            text = path.read_text(encoding='utf-8')
            new, changes = rewrite_text(path, text, args.base_url)
            manifest['summary']['scanned'] += 1
            if changes:
                manifest['summary']['changed_files'] += 1
                manifest['summary']['changes'] += len(changes)
                entry = {'state':state,'path':str(path),'change_count':len(changes),'changes':changes[:20]}
                manifest['files'].append(entry)
                if args.apply:
                    path.write_text(new, encoding='utf-8')
        if args.limit and count >= args.limit:
            break
    out = DATA / 'cta_tracking_rewrite_manifest.json'
    out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'ok': True, 'manifest': str(out), **manifest['summary']}, ensure_ascii=False))

if __name__ == '__main__':
    main()
