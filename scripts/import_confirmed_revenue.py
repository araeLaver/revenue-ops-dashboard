#!/usr/bin/env python3
"""Import confirmed affiliate/service revenue and reconcile it with revenue_proxy events.

Input files:
  data/revenue_imports/*.csv
  data/revenue_imports/*.json

CSV columns:
  date,network,offer_id,content_id,amount_krw,currency,order_ref,status,utm_source,target_host,notes

Outputs:
  data/confirmed_revenue.json
  data/confirmed_revenue_matches.json
  data/revenue_reconciliation_status.json

Rules:
- Only rows with status in confirmed/approved/paid/settled are counted as confirmed revenue.
- order_ref is hashed in outputs; raw order refs are not persisted.
- revenue_proxy is behavioral intent, not revenue. Matching is best-effort by offer_id/content_id/date/network hints.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
IMPORT_DIR = DATA / "revenue_imports"
ANALYTICS = DATA / "analytics"
REVENUE_EVENTS = ANALYTICS / "revenue_events.jsonl"
OUT_CONFIRMED = DATA / "confirmed_revenue.json"
OUT_MATCHES = DATA / "confirmed_revenue_matches.json"
OUT_STATUS = DATA / "revenue_reconciliation_status.json"
STATUS_JSON = DATA / "status.json"

CONFIRMED_STATUSES = {"confirmed", "approved", "paid", "settled", "확정", "승인", "지급"}
PENDING_STATUSES = {"pending", "open", "review", "검토", "대기"}
REJECTED_STATUSES = {"rejected", "cancelled", "canceled", "void", "취소", "거절"}
PROBE_PATTERNS = re.compile(r"probe|smoke|watchdog|healthcheck|debug|fixed_backend|ops", re.I)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def sha_ref(value: str) -> str:
    v = (value or "").strip()
    if not v:
        return ""
    return hashlib.sha256(v.encode("utf-8")).hexdigest()[:16]


def parse_amount(v: Any) -> int:
    if v is None:
        return 0
    s = str(v).strip().replace(",", "").replace("₩", "").replace("KRW", "").strip()
    if not s:
        return 0
    try:
        return int(round(float(s)))
    except Exception:
        return 0


def normalize_status(v: Any) -> str:
    return str(v or "").strip().lower()


def normalize_row(row: dict[str, Any], source_file: str) -> dict[str, Any]:
    status = normalize_status(row.get("status") or row.get("state") or row.get("conversion_status"))
    amount = parse_amount(row.get("amount_krw") or row.get("commission_krw") or row.get("amount") or row.get("commission"))
    order_ref = str(row.get("order_ref") or row.get("order_id") or row.get("transaction_id") or row.get("conversion_id") or "").strip()
    return {
        "date": str(row.get("date") or row.get("conversion_date") or row.get("created_at") or "").strip(),
        "network": str(row.get("network") or row.get("affiliate_network") or "manual").strip().lower() or "manual",
        "offer_id": str(row.get("offer_id") or "").strip(),
        "content_id": str(row.get("content_id") or row.get("sub_id") or row.get("subid") or "").strip(),
        "amount_krw": amount,
        "currency": str(row.get("currency") or "KRW").strip().upper() or "KRW",
        "order_ref_hash": sha_ref(order_ref),
        "status": status,
        "utm_source": str(row.get("utm_source") or "").strip(),
        "target_host": str(row.get("target_host") or row.get("merchant") or "").strip().lower(),
        "notes": str(row.get("notes") or "").strip()[:300],
        "source_file": source_file,
        "is_confirmed": status in CONFIRMED_STATUSES and amount > 0,
        "is_pending": status in PENDING_STATUSES,
        "is_rejected": status in REJECTED_STATUSES,
    }


def load_imports() -> list[dict[str, Any]]:
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for p in sorted(IMPORT_DIR.glob("*")):
        if p.name.startswith("template_") or p.name.startswith("README"):
            continue
        if p.suffix.lower() == ".csv":
            with p.open("r", encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    rows.append(normalize_row(row, p.name))
        elif p.suffix.lower() == ".json":
            data = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data = data.get("rows") or data.get("conversions") or data.get("items") or []
            if isinstance(data, list):
                for row in data:
                    if isinstance(row, dict):
                        rows.append(normalize_row(row, p.name))
    return rows


def load_proxy_events() -> list[dict[str, Any]]:
    events = []
    if not REVENUE_EVENTS.exists():
        return events
    for line in REVENUE_EVENTS.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except Exception:
            continue
        blob = json.dumps(ev, ensure_ascii=False)
        if PROBE_PATTERNS.search(blob):
            continue
        if ev.get("type") == "revenue_proxy" or ev.get("source") == "lead_page_outbound":
            events.append(ev)
    return events


def date_key(s: str) -> str:
    return (s or "")[:10]


def match_row(row: dict[str, Any], proxies: list[dict[str, Any]]) -> dict[str, Any] | None:
    best = None
    best_score = 0
    for ev in proxies:
        score = 0
        if row.get("offer_id") and row.get("offer_id") == ev.get("offer_id"):
            score += 4
        if row.get("content_id") and row.get("content_id") == ev.get("content_id"):
            score += 5
        if row.get("utm_source") and row.get("utm_source") == ev.get("utm_source"):
            score += 1
        if row.get("target_host") and row.get("target_host") == ev.get("target_host"):
            score += 1
        if row.get("date") and date_key(row.get("date")) == date_key(ev.get("timestamp", "")):
            score += 2
        if score > best_score:
            best_score = score
            best = ev
    if best and best_score >= 4:
        return {
            "score": best_score,
            "proxy_event_id": best.get("event_id", ""),
            "proxy_timestamp": best.get("timestamp", ""),
            "proxy_offer_id": best.get("offer_id", ""),
            "proxy_content_id": best.get("content_id", ""),
            "proxy_utm_source": best.get("utm_source", ""),
            "proxy_target_host": best.get("target_host", ""),
        }
    return None


def update_status(summary: dict[str, Any]) -> None:
    status = {}
    if STATUS_JSON.exists():
        try:
            status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
        except Exception:
            status = {}
    status["confirmed_revenue"] = summary
    status["confirmed_revenue_krw"] = summary.get("confirmed_amount_krw", 0)
    status["confirmed_revenue_count"] = summary.get("confirmed_count", 0)
    status["updated_at"] = now_iso()
    STATUS_JSON.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    rows = load_imports()
    proxies = load_proxy_events()

    confirmed = [r for r in rows if r["is_confirmed"]]
    pending = [r for r in rows if r["is_pending"]]
    rejected = [r for r in rows if r["is_rejected"]]

    matches = []
    unmatched_confirmed = []
    for r in confirmed:
        m = match_row(r, proxies)
        safe_row = dict(r)
        if m:
            matches.append({"confirmed": safe_row, "match": m})
        else:
            unmatched_confirmed.append(safe_row)

    by_offer = defaultdict(int)
    by_network = defaultdict(int)
    for r in confirmed:
        by_offer[r.get("offer_id") or "unknown"] += r["amount_krw"]
        by_network[r.get("network") or "manual"] += r["amount_krw"]

    summary = {
        "updated_at": now_iso(),
        "import_dir": str(IMPORT_DIR),
        "rows_imported": len(rows),
        "confirmed_count": len(confirmed),
        "confirmed_amount_krw": sum(r["amount_krw"] for r in confirmed),
        "pending_count": len(pending),
        "rejected_count": len(rejected),
        "revenue_proxy_events_considered": len(proxies),
        "matched_confirmed_count": len(matches),
        "unmatched_confirmed_count": len(unmatched_confirmed),
        "by_offer_amount_krw": dict(sorted(by_offer.items())),
        "by_network_amount_krw": dict(sorted(by_network.items())),
        "status": "no_confirmed_revenue_imported" if not confirmed else "confirmed_revenue_imported",
        "notes": [
            "revenue_proxy is not confirmed revenue",
            "raw order_ref values are hashed and not persisted",
            "drop CSV/JSON reports into data/revenue_imports/ and rerun this script",
        ],
    }

    OUT_CONFIRMED.write_text(json.dumps({"summary": summary, "confirmed_rows": confirmed}, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_MATCHES.write_text(json.dumps({"matches": matches, "unmatched_confirmed": unmatched_confirmed}, ensure_ascii=False, indent=2), encoding="utf-8")
    OUT_STATUS.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    update_status(summary)
    print(json.dumps({"ok": True, **summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
