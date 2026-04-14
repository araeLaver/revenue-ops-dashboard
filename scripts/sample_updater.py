#!/usr/bin/env python3
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
STATUS_PATH = BASE / "data" / "status.json"


def load_status():
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def save_status(data):
    data["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    STATUS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def upsert_queue_item(data, item):
    queue = data.setdefault("content_queue", [])
    for idx, existing in enumerate(queue):
        if existing.get("name") == item.get("name"):
            queue[idx] = {**existing, **item}
            return
    queue.append(item)


def append_active_work(data, title, detail, status="watch", status_label="업데이트됨"):
    active = data.setdefault("active_work", [])
    active.insert(0, {
        "title": title,
        "detail": detail,
        "status": status,
        "status_label": status_label,
    })
    del active[8:]


def set_system_status(data, value):
    data["system_status"] = value


def demo_update():
    data = load_status()
    set_system_status(data, "운영 중 / 자동 업데이트 테스트")
    upsert_queue_item(data, {
        "name": "툴 비교 시리즈",
        "stage": "review",
        "priority": "high",
        "status": "watch",
        "next_action": "quality review 결과 반영 후 CTA 재검토"
    })
    append_active_work(
        data,
        "자동 업데이트 테스트",
        "sample_updater.py 가 status.json을 갱신함",
        status="done",
        status_label="스크립트 실행 완료"
    )
    notes = data.setdefault("notes", [])
    notes.insert(0, {
        "title": "자동 갱신 확인",
        "detail": "sample_updater.py 실행으로 대시보드 상태가 갱신되었습니다."
    })
    del notes[8:]
    save_status(data)


if __name__ == "__main__":
    demo_update()
