# Confirmed revenue import

이 폴더에 제휴/매출 확정 리포트 CSV 또는 JSON을 넣고 아래 스크립트를 실행합니다.

실행:
python3 /Volumes/WorkDrive/Develop/48.HermesAgent/dashboard/scripts/import_confirmed_revenue.py

CSV 필수/권장 컬럼:
- date: 전환/승인 날짜. 예: 2026-05-18
- network: coupang, linkprice, manual 등
- offer_id: dashboard/data/offers.json의 offer_id
- content_id: YouTube video id 또는 WP post slug/id. 없으면 공란 가능하지만 매칭률이 떨어집니다.
- amount_krw: 확정 수익 금액
- currency: KRW
- order_ref: 주문/전환 ID. 원문은 저장하지 않고 hash만 저장됩니다.
- status: confirmed, approved, paid, settled 중 하나일 때만 확정 매출로 집계
- utm_source: youtube_shorts, wp 등
- target_host: www.coupang.com 등
- notes: 선택

주의:
- template_confirmed_revenue.csv는 샘플이므로 import 대상에서 자동 제외됩니다.
- status가 pending/rejected/cancelled이면 confirmed revenue에 합산하지 않습니다.
- revenue_proxy는 확정 매출이 아니며, confirmed revenue와 분리 표시됩니다.
