#!/usr/bin/env python3
"""발행 직전 품질 게이트.

목표:
- 쇼츠/롱폼/블로그 발행 직전에 고품질 기준 미달 콘텐츠 차단
- 미달 시 reviewed -> revised 루프로 돌려 품질 우선 운영

사용법:
  python3 prepublish_gate.py <draft.md>

exit code:
  0  : 통과
  10 : 품질 미달
  1+ : 실행 오류
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from llm_client import generate_json, MODEL_SCORING

BASE = Path(__file__).resolve().parent.parent
QA_DIR = BASE / "data" / "qa_reports"
QA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_THRESHOLDS = {
    "shorts": float(os.environ.get("HERMES_QA_MIN_SHORTS", "8.2")),
    "longform": float(os.environ.get("HERMES_QA_MIN_LONGFORM", "8.0")),
    "blog": float(os.environ.get("HERMES_QA_MIN_BLOG", "7.8")),
}

BANNED_BODY_RULES = [
    (re.compile(r"수정\s*내역\s*요약", re.IGNORECASE), "편집 메모(수정 내역 요약) 섹션이 본문에 포함됨 — 발행 전 삭제 필요"),
    (re.compile(r"편집자\s*(노트|참고용|메모)", re.IGNORECASE), "편집자 노트/참고용 문구가 본문에 포함됨 — 발행 금지"),
]

QA_PROMPT = """당신은 수익형 콘텐츠 발행 최종 심사관입니다.
엄격하게 평가하고, 품질이 낮으면 절대 통과시키지 마세요.

콘텐츠 타입: {ctype}
주제: {topic}

평가 기준(각 1~10점):
- hook: 첫 1~3문장이 즉시 관심을 끄는가
- clarity: 문장/구조가 명확하고 이해가 쉬운가
- specificity: 숫자/근거/조건 등 구체성이 충분한가
- retention: 끝까지 보게 만드는 전개력
- cta_power: CTA가 자연스럽고 행동 유도가 강한가
- monetization_fit: 오퍼/전환 경로와의 적합도

판정 규칙:
- overall >= {threshold} 이면 pass
- 그 외 fail

응답은 아래 JSON만:
{{
  "hook": N,
  "clarity": N,
  "specificity": N,
  "retention": N,
  "cta_power": N,
  "monetization_fit": N,
  "overall": N,
  "decision": "pass|fail",
  "must_fix": ["핵심수정1", "핵심수정2", "핵심수정3"]
}}

콘텐츠 본문:
---
{body}
---
"""


def _parse_frontmatter(text: str) -> dict:
    if not text.startswith("---"):
        return {}
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    block = m.group(1)
    data = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        data[k.strip()] = v.strip().strip('"')
    return data


def _body_without_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) >= 3:
        return parts[2].strip()
    return text


def _infer_type(meta: dict, path: Path) -> str:
    ctype = (meta.get("type") or "").strip().lower()
    if ctype in ("shorts", "longform", "blog"):
        return ctype

    name = path.name.lower()
    if "-shorts_" in name:
        return "shorts"
    if "-longform_" in name:
        return "longform"
    if "_wp-" in name or ctype == "post":
        return "blog"
    return "blog"


def _evaluate_shorts_rule_based(body: str, threshold: float) -> dict:
    text = body.strip()
    must_fix = []

    # Hard blockers: these are publishing/metadata defects that numeric scoring used to miss.
    # If they appear in the spoken body, Shorts can be uploaded with broken titles or TTS reading
    # source/frontmatter lines. Do not pass even when CTA/number scores look high.
    first_block = "\n".join(text.splitlines()[:8]).strip().lower()
    hard_block = False
    if re.match(r"^(source_urls|offer_id|lead_url|channel|title):", first_block):
        must_fix.append("쇼츠 본문 시작에 frontmatter/source_urls가 노출됨 — TTS가 메타데이터를 읽을 위험")
        hard_block = True
    if re.search(r"^#{1,3}\s*(설명란\s*CTA|고정댓글\s*CTA)\s*$", text, flags=re.MULTILINE):
        must_fix.append("쇼츠 제목/본문 구조 오류 — '설명란 CTA' 또는 '고정댓글 CTA'가 제목처럼 노출됨")
        hard_block = True

    char_len = len(text)
    if char_len < 180:
        must_fix.append("쇼츠 본문 길이가 너무 짧음(180자 미만) — 40~55초 분량으로 확장 필요")
        length_score = 4
    elif char_len < 260:
        length_score = 7
    elif char_len <= 700:
        length_score = 9
    else:
        length_score = 7

    has_number = bool(re.search(r"\d", text))
    specificity = 9 if has_number else 5
    if not has_number:
        must_fix.append("숫자/연도/비교 근거 부족 — 최소 1개 이상 수치 추가 필요")

    cta_keywords = ["구독", "팔로우", "댓글", "설명란", "고정 댓글", "링크", "롱폼"]
    cta_hits = sum(1 for k in cta_keywords if k in text)
    if cta_hits >= 3:
        cta_power = 9
        monetization_fit = 8
    elif cta_hits >= 2:
        cta_power = 7
        monetization_fit = 7
        must_fix.append("CTA 전환 강도 보강 필요 — 설명란/고정댓글 링크 유도 문구 추가")
    else:
        cta_power = 5
        monetization_fit = 5
        must_fix.append("전환 경로 부족 — 롱폼 브릿지 + 링크 클릭 유도 CTA 추가 필요")

    first_sent = re.split(r"[.!?\n]", text)[0].strip()
    hook_score = 8 if (len(first_sent) >= 12 and has_number) else 6
    if hook_score < 7:
        must_fix.append("첫 문장 훅 약함 — 손실/비용/숫자 중심으로 재작성 필요")

    clarity = 8 if char_len >= 220 else 6
    retention = 8 if cta_hits >= 2 and char_len >= 220 else 6

    overall = round((hook_score + clarity + specificity + retention + cta_power + monetization_fit) / 6, 2)
    if hard_block:
        overall = min(overall, threshold - 0.1)
        decision = "fail"
    else:
        decision = "pass" if overall >= threshold else "fail"

    return {
        "hook": hook_score,
        "clarity": clarity,
        "specificity": specificity,
        "retention": retention,
        "cta_power": cta_power,
        "monetization_fit": monetization_fit,
        "overall": overall,
        "decision": decision,
        "must_fix": must_fix[:3],
    }


def _evaluate_blog_rule_based(body: str, threshold: float) -> dict:
    text = body.strip()
    must_fix = []

    char_len = len(text)
    heading_count = len(re.findall(r"^##\s+", text, flags=re.MULTILINE))
    has_number = bool(re.search(r"\d", text))
    source_links = len(re.findall(r"https?://", text))
    cta_hits = sum(1 for k in ["체크리스트", "링크", "확인", "신청", "지금"] if k in text)

    if char_len < 1800:
        clarity = 6
        retention = 6
        must_fix.append("본문 길이 부족(1800자 미만) — 사례/절차 설명 보강 필요")
    elif char_len < 2600:
        clarity = 7
        retention = 7
    else:
        clarity = 8
        retention = 8

    if heading_count < 4:
        clarity = min(clarity, 6)
        must_fix.append("섹션 구조 부족(## 제목 4개 미만) — 단계별 소제목 보강 필요")

    specificity = 8 if has_number else 6
    if not has_number:
        must_fix.append("숫자/연도/조건 근거 부족 — 최소 3개 이상 수치 추가 필요")

    hook_line = text.splitlines()[0] if text else ""
    hook = 8 if len(hook_line) >= 12 else 6

    if source_links >= 3:
        monetization_fit = 8
    elif source_links >= 1:
        monetization_fit = 7
        must_fix.append("공식 출처 링크 부족 — 신뢰용 출처 2개 이상 추가 권장")
    else:
        monetization_fit = 5
        must_fix.append("출처 링크 없음 — 공식 사이트 출처 추가 필요")

    if cta_hits >= 3 and "http" in text:
        cta_power = 8
    elif cta_hits >= 2:
        cta_power = 7
        must_fix.append("CTA 행동유도 문구 보강 필요(언제/왜/무엇을 확인할지 명확화)")
    else:
        cta_power = 5
        must_fix.append("전환 CTA 부족 — 체크리스트/다음 행동 1개를 명확히 제시 필요")

    overall = round((hook + clarity + specificity + retention + cta_power + monetization_fit) / 6, 2)
    decision = "pass" if overall >= threshold else "fail"

    return {
        "hook": hook,
        "clarity": clarity,
        "specificity": specificity,
        "retention": retention,
        "cta_power": cta_power,
        "monetization_fit": monetization_fit,
        "overall": overall,
        "decision": decision,
        "must_fix": must_fix[:3],
    }


def _evaluate_longform_rule_based(body: str, threshold: float) -> dict:
    text = body.strip()
    must_fix = []

    char_len = len(text)
    heading_count = len(re.findall(r"^##\s+", text, flags=re.MULTILINE))
    source_links = len(re.findall(r"https?://", text))
    has_number = bool(re.search(r"\d", text))
    cta_hits = sum(1 for k in ["설명란", "고정 댓글", "고정댓글", "링크", "구독", "체크리스트", "다음", "자료"] if k in text)

    if char_len < 4200:
        clarity = 6
        retention = 6
        must_fix.append("롱폼 분량 부족(4200자 미만) — 사례/근거/마무리 보강 필요")
    elif char_len < 5200:
        clarity = 7
        retention = 7
    else:
        clarity = 8
        retention = 8

    if heading_count < 4:
        clarity = min(clarity, 6)
        must_fix.append("롱폼 섹션 구조 부족(## 제목 4개 미만) — 도입/근거/사례/정리 구조 보강 필요")

    specificity = 8 if has_number else 6
    if not has_number:
        must_fix.append("숫자/연도/조건 근거 부족 — 최소 3개 이상 수치/연도 추가 필요")

    first_nonempty = next((line.strip() for line in text.splitlines() if line.strip() and not line.startswith("---") and not line.lstrip().startswith("#")), "")
    hook = 8 if len(first_nonempty) >= 18 and (has_number or any(k in first_nonempty for k in ["왜", "진짜", "결과", "위험", "손해", "사라", "끝", "세액", "사건"])) else 7

    if source_links >= 2:
        trust_score = 8
    elif source_links == 1:
        trust_score = 7
        must_fix.append("출처 링크 부족 — 설명란/참고자료에 공식 또는 1차 출처 2개 이상 권장")
    else:
        trust_score = 5
        must_fix.append("출처 링크 없음 — 정보성 롱폼은 공식/신뢰 출처 URL 추가 필요")

    if cta_hits >= 4 and source_links >= 1:
        cta_power = 8
        monetization_fit = 8
    elif cta_hits >= 2:
        cta_power = 7
        monetization_fit = 7
        must_fix.append("CTA 전환 경로 보강 필요 — 설명란/고정댓글에서 무엇을 확인할지 명확화")
    else:
        cta_power = 5
        monetization_fit = 5
        must_fix.append("전환 CTA 부족 — 설명란 링크/고정댓글/구독/다음 영상 연결 문구 추가 필요")

    # Longform은 정보 신뢰가 핵심이므로 출처 신뢰 점수를 specificity에 반영한다.
    specificity = min(9, round((specificity + trust_score) / 2, 2))
    overall = round((hook + clarity + specificity + retention + cta_power + monetization_fit) / 6, 2)
    decision = "pass" if overall >= threshold else "fail"

    return {
        "hook": hook,
        "clarity": clarity,
        "specificity": specificity,
        "retention": retention,
        "cta_power": cta_power,
        "monetization_fit": monetization_fit,
        "overall": overall,
        "decision": decision,
        "must_fix": must_fix[:3],
    }


def evaluate(path: Path) -> tuple[bool, dict, float, str]:
    text = path.read_text(encoding="utf-8")
    meta = _parse_frontmatter(text)
    body = _body_without_frontmatter(text)
    ctype = _infer_type(meta, path)
    threshold = DEFAULT_THRESHOLDS.get(ctype, 8.0)
    topic = meta.get("topic", path.stem)

    hard_violations: list[str] = []
    for rx, reason in BANNED_BODY_RULES:
        if rx.search(body):
            hard_violations.append(reason)

    if hard_violations:
        result = {
            "hook": 0,
            "clarity": 0,
            "specificity": 0,
            "retention": 0,
            "cta_power": 0,
            "monetization_fit": 0,
            "overall": 0,
            "decision": "fail",
            "must_fix": hard_violations[:3],
        }
    elif ctype == "shorts":
        result = _evaluate_shorts_rule_based(body, threshold)
    elif ctype == "blog" and os.environ.get("HERMES_QA_FAST_BLOG", "0") == "1":
        result = _evaluate_blog_rule_based(body, threshold)
    elif ctype == "longform" and os.environ.get("HERMES_QA_FAST_LONGFORM", "0") == "1":
        result = _evaluate_longform_rule_based(body, threshold)
    else:
        prompt = QA_PROMPT.format(
            ctype=ctype,
            topic=topic,
            threshold=threshold,
            body=body[:6000],
        )
        result = generate_json(prompt, model=MODEL_SCORING, temperature=0.2)

    overall = float(result.get("overall", 0))
    decision = str(result.get("decision", "fail")).lower()
    passed = decision == "pass" and overall >= threshold

    report = {
        "file": str(path),
        "type": ctype,
        "topic": topic,
        "threshold": threshold,
        "result": result,
    }

    report_path = QA_DIR / f"{path.stem}.qa.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    return passed, result, threshold, str(report_path)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: prepublish_gate.py <draft.md>")
        return 1

    draft = Path(sys.argv[1])
    if not draft.exists():
        print(f"ERROR: 파일 없음: {draft}")
        return 1

    passed, result, threshold, report_path = evaluate(draft)
    overall = result.get("overall", 0)
    decision = result.get("decision", "fail")
    must_fix = result.get("must_fix", [])

    print(json.dumps({
        "file": str(draft),
        "overall": overall,
        "threshold": threshold,
        "decision": decision,
        "must_fix": must_fix,
        "report": report_path,
    }, ensure_ascii=False))

    if passed:
        print(f"[qa] PASS ({overall} >= {threshold})")
        return 0

    print(f"[qa] FAIL ({overall} < {threshold})")
    return 10


if __name__ == "__main__":
    raise SystemExit(main())
