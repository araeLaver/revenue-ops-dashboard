#!/usr/bin/env python3
"""CTA 라이브러리 — 사이트/채널별 오퍼 연동 CTA 자동 생성.

offers.json의 오퍼 정의를 기반으로 콘텐츠 위치별 CTA 텍스트를 반환.
post_processor.py, prompts.py, generate_draft.py에서 호출.

사용법:
  python3 cta_library.py unpre "실손보험 청구"       # WP 사이트 CTA 3종
  python3 cta_library.py araelaver "클레오파트라"     # YT 채널 CTA
  python3 cta_library.py --all                        # 전체 CTA 미리보기
"""
import json
import random
import sys
from pathlib import Path

OFFERS_FILE = Path(__file__).resolve().parent.parent / "data" / "offers.json"
REGISTRY_FILE = Path(__file__).resolve().parent.parent / "data" / "link_registry.json"


def load_offers() -> dict:
    return json.loads(OFFERS_FILE.read_text(encoding="utf-8"))


# ─────────────────────────────────────────
# WP 블로그용 CTA 템플릿
# ─────────────────────────────────────────

_WP_CTA_TEMPLATES = {
    "coupang_affiliate": [
        "\n> **{topic} 관련 추천 상품이 궁금하다면?**\n> [{cta_action}]({placeholder}) — 쿠팡 로켓배송으로 빠르게 받아보세요.\n",
        "\n> 이 글에서 다룬 상품, 직접 비교해보세요.\n> [{cta_action}]({placeholder})\n",
        "\n> **지금 가장 많이 팔리는 {topic} 상품**\n> [{cta_action}]({placeholder}) — 실시간 가격 확인\n",
    ],
    "linkprice_affiliate": [
        "\n> **해외 직구도 고려 중이라면?**\n> [{cta_action}]({placeholder}) — 공식 할인가 적용 링크\n",
        "\n> 국내 제품과 해외 제품 가격 차이, 직접 비교해보세요.\n> [{cta_action}]({placeholder})\n",
    ],
    "affiliate": [
        "\n> **내 조건에 맞는 상품, 30초면 비교 가능합니다.**\n> [{cta_action}]({placeholder})\n",
        "\n> 비교 없이 가입하면 매달 수만 원 차이. 지금 확인하세요.\n> [{cta_action}]({placeholder})\n",
        "\n> **{topic}, 어디가 가장 유리할까?**\n> [{cta_action}]({placeholder}) — 무료 비교 서비스\n",
    ],
    "lead_capture": [
        "\n> **이 글의 핵심을 한 장에 정리했습니다.**\n> [{cta_action}]({placeholder}) — 무료 PDF\n",
        "\n> 매번 검색하기 귀찮다면, 체크리스트 하나면 끝.\n> [{cta_action}]({placeholder})\n",
        "\n> **{topic} 시작 전 꼭 확인해야 할 항목들**\n> [{cta_action}]({placeholder}) — 이메일로 바로 발송\n",
    ],
    "service_inquiry": [
        "\n> **혼자 하기 어렵다면 전문가 도움을 받으세요.**\n> [{cta_action}]({placeholder}) — 무료 초기 상담\n",
        "\n> 서류 준비부터 신청까지, 대행 서비스 이용해보세요.\n> [{cta_action}]({placeholder})\n",
    ],
}

# ─────────────────────────────────────────
# YT 채널용 CTA 템플릿
# ─────────────────────────────────────────

_YT_CTA_TEMPLATES = {
    "shorts_end": [
        "이런 이야기가 더 궁금하다면 구독 눌러주세요. 매일 새로운 이야기가 올라옵니다.",
        "다음 편이 궁금하다면 팔로우. 알림 켜두면 놓치지 않아요.",
        "구독하면 매일 이런 이야기를 받아볼 수 있어요.",
    ],
    "shorts_longform_bridge": [
        "더 자세한 이야기는 롱폼 영상에서 다뤘어요. 프로필에서 확인해보세요.",
        "이 주제, 10분짜리 영상으로 깊게 파봤습니다. 채널에서 찾아보세요.",
    ],
    "longform_end": [
        "다음 {series_format}편에서는 더 놀라운 이야기를 준비했습니다. 구독과 알림 설정, 부탁드려요.",
        "이 이야기가 흥미로웠다면 좋아요 한 번만 눌러주세요. 다음 편 만드는 힘이 됩니다.",
        "댓글로 여러분의 생각을 알려주세요. 다음 주제 선정에 반영하겠습니다.",
    ],
    "longform_comment_prompt": [
        "여러분은 어떻게 생각하세요? 댓글로 알려주세요.",
        "이 중에서 가장 놀라웠던 건 뭔가요? 댓글로 남겨주세요.",
    ],
}


def _resolve_placeholder(offer_type: str, site_id: str) -> str:
    """오퍼 타입 → 실제 URL.

    우선순위:
    1. link_registry.json의 명시 링크
    2. offers.json lead_capture_setup.form_urls의 실제 lead/service URL
    3. 플레이스홀더
    """
    placeholder_map = {
        "coupang_affiliate": "[COUPANG_LINK]",
        "linkprice_affiliate": "[LINKPRICE_LINK]",
        "affiliate": "[AFFILIATE_LINK]",
        "lead_capture": "[LEAD_FORM_LINK]",
        "service_inquiry": "[SERVICE_LINK]",
    }
    placeholder = placeholder_map.get(offer_type, "[OFFER_LINK]")

    try:
        import json
        registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))
        url = registry.get("wp_links", {}).get(site_id, {}).get(placeholder, "")
        if url and not url.startswith("TODO"):
            return url
    except Exception:
        pass

    if offer_type in {"lead_capture", "service_inquiry"}:
        try:
            offers = load_offers()
            form_urls = offers.get("lead_capture_setup", {}).get("form_urls", {})
            url = form_urls.get(site_id) or (form_urls.get("kakao_channel") if offer_type == "service_inquiry" else "")
            if url and not str(url).startswith("TODO"):
                return str(url)
        except Exception:
            pass

    return placeholder


def get_wp_cta(site_id: str, slot: str, topic: str = "") -> str:
    """WP 블로그 CTA 반환. slot: section_1, section_3, conclusion"""
    offers = load_offers()
    site_offers = offers.get("wp_offers", {}).get(site_id)
    if not site_offers:
        return ""

    slots_map = site_offers.get("cta_slots", {})
    offer_key = slots_map.get(slot, "")
    if not offer_key:
        return ""

    offer = site_offers.get(offer_key)
    if not offer:
        return ""

    offer_type = offer.get("type", "affiliate")
    cta_action = offer.get("cta_action", "자세히 보기")
    templates = _WP_CTA_TEMPLATES.get(offer_type, _WP_CTA_TEMPLATES["affiliate"])

    # link_registry에서 실제 URL 조회, 없으면 플레이스홀더
    placeholder = _resolve_placeholder(offer_type, site_id)

    template = random.choice(templates)
    return template.format(topic=topic or site_offers.get("niche", ""), cta_action=cta_action, placeholder=placeholder)


def get_wp_cta_set(site_id: str, topic: str = "") -> dict:
    """WP 블로그 CTA 3종 세트 반환."""
    return {
        "section_1": get_wp_cta(site_id, "section_1", topic),
        "section_3": get_wp_cta(site_id, "section_3", topic),
        "conclusion": get_wp_cta(site_id, "conclusion", topic),
    }


def get_yt_cta(channel_id: str, doc_type: str, series_format: str = "") -> dict:
    """YT 채널 CTA 반환."""
    if doc_type == "shorts":
        return {
            "end": random.choice(_YT_CTA_TEMPLATES["shorts_end"]),
            "bridge": random.choice(_YT_CTA_TEMPLATES["shorts_longform_bridge"]),
        }
    else:
        return {
            "end": random.choice(_YT_CTA_TEMPLATES["longform_end"]).format(
                series_format=series_format or "다음"
            ),
            "comment": random.choice(_YT_CTA_TEMPLATES["longform_comment_prompt"]),
        }


def get_offer_summary(site_id: str) -> str:
    """프롬프트에 주입할 오퍼 요약 텍스트."""
    offers = load_offers()
    site = offers.get("wp_offers", {}).get(site_id)
    if not site:
        return ""

    lines = [f"이 글의 수익 경로:"]
    slots = site.get("cta_slots", {})
    for slot_name, offer_key in slots.items():
        offer = site.get(offer_key, {})
        if offer:
            lines.append(f"- {slot_name}: {offer.get('name', '')} → \"{offer.get('cta_action', '')}\"")
    return "\n".join(lines)


def get_yt_offer_summary(channel_id: str) -> str:
    """YT 프롬프트 주입용 오퍼 요약 텍스트."""
    offers = load_offers()
    ch = offers.get("yt_offers", {}).get(channel_id)
    if not ch:
        return ""
    return "\n".join([
        "이 영상의 전환 경로:",
        f"- primary_cta: {ch.get('primary_cta', '')}",
        f"- secondary_cta: {ch.get('secondary_cta', '')}",
        f"- description_link: {ch.get('description_link', '')}",
        f"- end_screen: {ch.get('end_screen', '')}",
    ])


# ─────────────────────────────────────────
# CLI
# ─────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    if sys.argv[1] == "--all":
        offers = load_offers()
        for site_id in offers.get("wp_offers", {}):
            print(f"\n{'='*50}")
            print(f"WP: {site_id}")
            print(f"{'='*50}")
            ctas = get_wp_cta_set(site_id, "테스트 주제")
            for slot, cta in ctas.items():
                print(f"\n[{slot}]{cta}")
            print(f"\n오퍼 요약:\n{get_offer_summary(site_id)}")

        for ch_id in offers.get("yt_offers", {}):
            print(f"\n{'='*50}")
            print(f"YT: {ch_id}")
            print(f"{'='*50}")
            for dtype in ("shorts", "longform"):
                cta = get_yt_cta(ch_id, dtype)
                print(f"\n[{dtype}] {json.dumps(cta, ensure_ascii=False, indent=2)}")
        return

    target_id = sys.argv[1]
    topic = sys.argv[2] if len(sys.argv) > 2 else ""

    # WP or YT?
    offers = load_offers()
    if target_id in offers.get("wp_offers", {}):
        print(f"\nWP CTA ({target_id}) — 주제: {topic or '기본'}\n")
        ctas = get_wp_cta_set(target_id, topic)
        for slot, cta in ctas.items():
            print(f"[{slot}]{cta}")
        print(f"\n오퍼 요약:\n{get_offer_summary(target_id)}")
    elif target_id in offers.get("yt_offers", {}):
        print(f"\nYT CTA ({target_id}) — 주제: {topic or '기본'}\n")
        for dtype in ("shorts", "longform"):
            cta = get_yt_cta(target_id, dtype)
            print(f"[{dtype}] {json.dumps(cta, ensure_ascii=False, indent=2)}")
    else:
        print(f"알 수 없는 ID: {target_id}")
        print(f"WP: {list(offers.get('wp_offers', {}).keys())}")
        print(f"YT: {list(offers.get('yt_offers', {}).keys())}")


if __name__ == "__main__":
    main()
