#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STATUS_PATH = BASE / "data" / "status.json"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_status():
    return load_json(STATUS_PATH)


def save_status(data):
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STATUS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_by_name(items, payload):
    name = payload.get("name")
    if not name:
        return items
    for i, item in enumerate(items):
        if item.get("name") == name:
            items[i] = {**item, **payload}
            return items
    items.append(payload)
    return items


def append_recent(items, payload, limit=8):
    if payload:
        items.insert(0, payload)
        del items[limit:]
    return items


def apply_event(event):
    data = load_status()

    if event.get("system_status"):
        data["system_status"] = event["system_status"]

    if event.get("queue_update"):
        data.setdefault("content_queue", [])
        data["content_queue"] = upsert_by_name(data["content_queue"], event["queue_update"])

    if event.get("active_work_append"):
        data.setdefault("active_work", [])
        data["active_work"] = append_recent(data["active_work"], event["active_work_append"])

    if event.get("risk_append"):
        data.setdefault("risks", [])
        data["risks"] = append_recent(data["risks"], event["risk_append"])

    if event.get("note_append"):
        data.setdefault("notes", [])
        data["notes"] = append_recent(data["notes"], event["note_append"])

    save_status(data)


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: apply_event.py path/to/event.json")
    event = load_json(sys.argv[1])
    apply_event(event)
