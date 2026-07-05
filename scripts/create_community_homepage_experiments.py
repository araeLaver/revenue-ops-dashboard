from datetime import datetime, timezone, timedelta
import json, html, os
from urllib.parse import urlencode

base = '/Volumes/WorkDrive/Develop/48.HermesAgent/dashboard'
KST = timezone(timedelta(hours=9))
now = datetime.now(KST).isoformat(timespec='seconds')

experiments = [
  {
    'day': 1, 'slug': 'car-insurance-renewal-club', 'site':'unpre', 'segment':'자동차보험 갱신 30~45일 전 직장인/자영업자',
    'title':'자동차보험 갱신 전 보험료 줄이는 사람들의 30초 체크룸',
    'subtitle':'갱신 알림을 받고도 미루는 사람을 위한 비교·특약·마일리지 환급 체크 커뮤니티',
    'promise':'보험료 비교 전, 갱신월·현재 보험료·특약 누락을 먼저 확인합니다.',
    'offer_id':'unpre_insurance_quote', 'intent':'insurance_quote', 'primary_cta':'내 보험료 30초 점검하기',
    'community_name':'보험료 갱신 체크룸', 'tone':'trust-blue',
    'pain':['작년과 같은 조건으로 자동 갱신해 보험료가 오른 경우','마일리지·블랙박스·자녀·안전운전 특약을 놓친 경우','비교 견적을 보긴 봤지만 무엇을 바꿔야 할지 모르는 경우'],
    'sections':['갱신월별 할 일표','특약 누락 체크','보험료 구간별 비교 질문','실제 견적 보기 전 준비사항'],
    'seed_posts':['갱신 45일 전에는 무엇부터 확인해야 하나요?','블랙박스/마일리지 특약을 동시에 챙기는 순서','월 10만원 이상이면 먼저 볼 항목 3가지'],
    'traffic_hooks':['네이버 카페 자동차보험 갱신 질문 답변용 링크','자동차보험 관련 WP 글 하단 CTA','유튜브 쇼츠 고정댓글: 갱신 전 체크']
  },
  {
    'day': 2, 'slug': 'loan-refinance-rate-room', 'site':'unpre', 'segment':'신용대출/전세대출 금리 부담이 커진 20~40대',
    'title':'대출 금리 갈아타기 전에 내 조건부터 보는 비교룸',
    'subtitle':'금리·잔액·소득유형을 정리하고 갈아타기 가능성을 빠르게 분류하는 커뮤니티형 체크 페이지',
    'promise':'대출 비교 버튼을 누르기 전, 내 금리 구간과 갈아타기 가능성을 먼저 기록합니다.',
    'offer_id':'unpre_loan_rate_check', 'intent':'loan_rate', 'primary_cta':'금리 낮출 수 있는지 확인하기',
    'community_name':'금리갈아타기 비교룸', 'tone':'dark-green',
    'pain':['현재 금리가 높은지 낮은지 기준이 없는 경우','신용대출·전세대출·주담대 중 어디부터 비교해야 할지 모르는 경우','중도상환수수료와 실제 절감액을 같이 못 보는 경우'],
    'sections':['대출 유형별 우선순위','현재 금리 구간 체크','비교 전 준비 서류','갈아타기 질문 게시판'],
    'seed_posts':['6%대 신용대출이면 지금 비교할 만한가요?','전세대출 갈아타기 전에 확인할 수수료','사업자대출은 어떤 조건부터 봐야 하나요?'],
    'traffic_hooks':['대출 금리 WP 글 내부 CTA','재테크 유튜브 설명란','커뮤니티 Q&A 답변용 진단 링크']
  },
  {
    'day': 3, 'slug': 'small-business-policy-fund-desk', 'site':'untab', 'segment':'정책자금·폐업지원·재창업 지원을 찾는 소상공인',
    'title':'소상공인 정책자금 신청 전 서류·마감 체크 데스크',
    'subtitle':'사업 상태, 지역, 업종, 자금 목적을 먼저 정리해 상담/대행 가능성을 빠르게 확인합니다.',
    'promise':'지원사업 공고를 읽고 끝내지 않고, 신청 가능성·마감·서류 누락을 바로 체크합니다.',
    'offer_id':'untab_policy_fund_consult', 'intent':'policy_fund', 'primary_cta':'정책자금 상담 가능성 확인하기',
    'community_name':'정책자금 체크데스크', 'tone':'orange',
    'pain':['공고는 봤는데 내 업종이 되는지 모르는 경우','마감일이 임박했는데 서류가 복잡한 경우','운영자금/시설자금/폐업지원 중 무엇이 맞는지 헷갈리는 경우'],
    'sections':['지역별 공고 체크','사업상태별 신청 루트','서류 누락 방지표','상담 전 질문 모음'],
    'seed_posts':['운영 중인데 폐업지원도 같이 볼 수 있나요?','정책자금 신청 전 사업자등록증 외 필요한 것','음식점/온라인몰 업종별 먼저 볼 지원사업'],
    'traffic_hooks':['소상공인 지원금 WP 글 CTA','지역 커뮤니티 답변 링크','카카오 상담 전 사전진단 링크']
  },
  {
    'day': 4, 'slug': 'youth-subsidy-deadline-board', 'site':'untab', 'segment':'청년월세·긴급복지·에너지바우처 등 마감형 지원금 신청자',
    'title':'지원금 마감 전에 대상 여부부터 확인하는 신청 보드',
    'subtitle':'지역·신청자 유형·마감일을 30초로 정리하고 지원금 체크리스트로 이동합니다.',
    'promise':'헷갈리는 공고를 모아보는 것이 아니라, 내 조건 기준으로 신청 가능성을 먼저 봅니다.',
    'offer_id':'untab_subsidy_eligibility', 'intent':'subsidy_eligibility', 'primary_cta':'지원금 대상 여부 확인하기',
    'community_name':'지원금 마감 알림보드', 'tone':'yellow',
    'pain':['청년/가구/소상공인 조건이 뒤섞여 헷갈리는 경우','마감일을 놓쳐 신청 기회를 잃는 경우','서류 하나가 빠져 다시 제출하는 경우'],
    'sections':['이번 주 마감 체크','신청자 유형별 조건','반려 잦은 서류','질문 답변 스레드'],
    'seed_posts':['청년월세와 긴급복지를 같이 볼 수 있나요?','에너지바우처 7월 신청 전 확인할 것','지원금 서류 제출 전 PDF 저장 팁'],
    'traffic_hooks':['지원금 글 상단 CTA','맘카페/지역카페 정보글 답변','쇼츠 설명란 신청 전 체크']
  },
  {
    'day': 5, 'slug': 'supplement-stack-lab', 'site':'skewese', 'segment':'피로·수면·혈행·다이어트 목적 영양제 구매 직전 사용자',
    'title':'영양제 장바구니 넣기 전 성분 조합 체크랩',
    'subtitle':'광고 문구 대신 목적·함량·중복 성분·주의사항을 먼저 보는 구매 전 커뮤니티',
    'promise':'무작정 최저가로 이동하기 전, 내 목적에 맞는 성분 조합을 확인합니다.',
    'offer_id':'skewese_supplement_buying_check', 'intent':'supplement_buying', 'primary_cta':'내 목적에 맞는 성분 확인하기',
    'community_name':'성분조합 체크랩', 'tone':'purple',
    'pain':['오메가3·마그네슘·유산균을 같이 먹어도 되는지 모르는 경우','함량보다 리뷰만 보고 구매하는 경우','이미 먹는 제품과 중복되는 성분을 놓치는 경우'],
    'sections':['목적별 성분표','중복 섭취 체크','구매 전 질문','가격 비교 이동'],
    'seed_posts':['피로 목적이면 마그네슘부터 봐야 하나요?','오메가3 rTG와 일반형 차이','유산균 구매 전 균수보다 먼저 볼 것'],
    'traffic_hooks':['건강/영양제 WP 글 CTA','쿠팡 상품 비교 전 중간 페이지','Shorts 고정댓글: 성분 체크']
  },
  {
    'day': 6, 'slug': 'relationship-pattern-room', 'site':'micheuhasi', 'segment':'이별 후/회피형/불안형 관계 패턴을 검색하는 20~30대',
    'title':'반복되는 관계 패턴을 조용히 체크하는 대화 회복룸',
    'subtitle':'상대 탓으로 끝내지 않고, 내 반복 패턴과 필요한 도움을 체크리스트로 정리합니다.',
    'promise':'영상 시청 후 감정만 남지 않게, 내 상황을 저장 가능한 체크리스트로 바꿉니다.',
    'offer_id':'micheuhasi_relationship_pattern_check', 'intent':'relationship_pattern_check', 'primary_cta':'내 관계 패턴 체크하기',
    'community_name':'관계패턴 회복룸', 'tone':'rose',
    'pain':['연락 텀 때문에 불안이 커지는 경우','갈등만 생기면 웃어넘기거나 회피하는 경우','이별 후 같은 패턴을 반복하는 경우'],
    'sections':['상황별 대화 예시','회피/불안 패턴 체크','7일 회복 루틴','다음 편 알림 신청'],
    'seed_posts':['답장이 늦을 때 불안을 줄이는 문장','회피형에게 장문을 보내기 전 체크','갈등 후 먼저 웃어넘기는 습관의 문제'],
    'traffic_hooks':['관계심리 Shorts 고정댓글','롱폼 설명란 워크북 링크','커뮤니티 사연 답변용 링크']
  },
  {
    'day': 7, 'slug': 'mystery-casefile-club', 'site':'kdowndan', 'segment':'실화 미스터리/미제 사건 타임라인을 좋아하는 구독자',
    'title':'미제 사건 타임라인을 함께 정리하는 사건파일 클럽',
    'subtitle':'영상에서 놓치기 쉬운 날짜·장소·증거 흐름을 PDF/뉴스레터형 자료로 이어갑니다.',
    'promise':'조회수만 남기는 공포 콘텐츠가 아니라, 자료집·뉴스레터·도서 제휴로 전환 경로를 만듭니다.',
    'offer_id':'kdowndan_casefile_newsletter', 'intent':'casefile_newsletter', 'primary_cta':'사건 타임라인 PDF 받기',
    'community_name':'사건파일 클럽', 'tone':'slate',
    'pain':['영상 내용은 흥미롭지만 사건 흐름을 다시 찾기 어려운 경우','출처와 날짜를 한 장으로 보고 싶은 경우','다음 편 알림과 관련 도서를 함께 받고 싶은 경우'],
    'sections':['사건 타임라인','증거/증언 체크','출처 링크 모음','다음 편 투표'],
    'seed_posts':['해변에서 발견된 단서의 날짜 순서','도시전설과 실제 사건을 구분하는 기준','미제 사건 자료집에 넣을 필수 항목'],
    'traffic_hooks':['미스터리 유튜브 설명란','고정댓글 PDF 링크','관련 도서 제휴 전환 페이지']
  }
]

colors = {
 'trust-blue':('#dbeafe','#1d4ed8','#0f172a','#eff6ff'), 'dark-green':('#dcfce7','#15803d','#052e16','#f0fdf4'),
 'orange':('#ffedd5','#ea580c','#431407','#fff7ed'), 'yellow':('#fef9c3','#ca8a04','#422006','#fefce8'),
 'purple':('#f3e8ff','#9333ea','#3b0764','#faf5ff'), 'rose':('#ffe4e6','#e11d48','#4c0519','#fff1f2'),
 'slate':('#e2e8f0','#475569','#020617','#f8fafc')
}

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)

def track_url(exp, slot, campaign='community_homepage_daily'):
    # 일반 브라우저에서 localtunnel interstitial이 뜨면 CTA 전환이 끊기므로,
    # 커뮤니티 홈 1차 CTA는 lead.html로 직접 보낸다. lead.html 내부의
    # quick-interest/outbound 버튼이 canonical backend로 lead/revenue_proxy를 기록한다.
    qs = {
      'site': exp['site'],
      'intent': exp['intent'],
      'offer_id': exp['offer_id'],
      'content_id': f"community-{exp['slug']}",
      'utm_source': 'community_homepage',
      'utm_medium': slot,
      'utm_campaign': campaign,
    }
    return '../lead.html?' + urlencode(qs)

def render_page(exp):
    bg, accent, dark, pale = colors[exp['tone']]
    pain = ''.join(f"<li>{html.escape(x)}</li>" for x in exp['pain'])
    sections = ''.join(f"<article><b>{html.escape(x)}</b><span>오늘 바로 답변/자료/CTA로 연결할 섹션입니다.</span></article>" for x in exp['sections'])
    posts = ''.join(f"<li><a href='{track_url(exp, 'seed_post')}'>#{i+1} {html.escape(x)}</a></li>" for i,x in enumerate(exp['seed_posts']))
    hooks = ''.join(f"<li>{html.escape(x)}</li>" for x in exp['traffic_hooks'])
    return f'''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{html.escape(exp['title'])}</title>
<meta name="description" content="{html.escape(exp['subtitle'])}" />
<style>
:root{{--bg:{bg};--accent:{accent};--dark:{dark};--pale:{pale};--text:#111827;--muted:#64748b;--line:#e5e7eb}}
*{{box-sizing:border-box}} body{{margin:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:linear-gradient(180deg,var(--pale),#fff);color:var(--text);line-height:1.6}}
a{{color:inherit}} .wrap{{max-width:1120px;margin:0 auto;padding:28px 18px 56px}} .hero{{display:grid;grid-template-columns:1.15fr .85fr;gap:24px;align-items:center;padding:42px 0}}
.badge{{display:inline-flex;background:var(--bg);color:var(--accent);border:1px solid #e5e7eb;border-radius:999px;padding:7px 12px;font-size:13px;font-weight:900}}
h1{{font-size:clamp(32px,5vw,58px);line-height:1.05;margin:16px 0 12px;letter-spacing:-.04em}} .sub{{font-size:19px;color:#475569;margin:0 0 22px}} .promise{{background:#fff;border:1px solid var(--line);border-left:6px solid var(--accent);border-radius:18px;padding:17px 18px;font-weight:800}}
.actions{{display:flex;gap:10px;flex-wrap:wrap;margin-top:22px}} .btn{{display:inline-flex;align-items:center;justify-content:center;text-decoration:none;border-radius:15px;padding:15px 18px;font-weight:950}} .primary{{background:var(--accent);color:#fff;box-shadow:0 18px 42px rgba(15,23,42,.14)}} .secondary{{background:#fff;border:1px solid var(--line);color:#0f172a}}
.panel{{background:#fff;border:1px solid var(--line);border-radius:24px;padding:22px;box-shadow:0 18px 60px rgba(15,23,42,.08)}} .metric{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:18px}} .metric div{{background:var(--pale);border-radius:16px;padding:14px}} .metric strong{{display:block;font-size:24px;color:var(--accent)}}
.grid{{display:grid;grid-template-columns:repeat(12,1fr);gap:16px;margin-top:18px}} .card{{grid-column:span 4;background:#fff;border:1px solid var(--line);border-radius:22px;padding:20px}} .wide{{grid-column:span 8}} .full{{grid-column:1/-1}} h2{{margin:0 0 12px;font-size:22px}} ul{{padding-left:20px;margin:8px 0}} li{{margin:7px 0}} .sections{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}} .sections article{{background:var(--pale);border:1px solid var(--line);border-radius:17px;padding:15px}} .sections span{{display:block;color:#64748b;font-size:14px;margin-top:5px}}
.posts a{{text-decoration:none;border-bottom:1px solid var(--accent)}} .footerCta{{display:flex;align-items:center;justify-content:space-between;gap:16px;background:var(--dark);color:white;border-radius:26px;padding:24px;margin-top:18px}} .footerCta p{{color:#cbd5e1;margin:4px 0 0}} .mini{{font-size:13px;color:#64748b}} @media(max-width:820px){{.hero{{grid-template-columns:1fr;padding:24px 0}}.grid{{display:block}}.card{{margin:14px 0}}.sections{{grid-template-columns:1fr}}.footerCta{{display:block}}.actions .btn{{width:100%}}}}
</style>
</head>
<body>
<main class="wrap">
  <section class="hero">
    <div>
      <span class="badge">DAY {exp['day']} · {html.escape(exp['community_name'])}</span>
      <h1>{html.escape(exp['title'])}</h1>
      <p class="sub">{html.escape(exp['subtitle'])}</p>
      <div class="promise">{html.escape(exp['promise'])}</div>
      <div class="actions">
        <a class="btn primary" href="{track_url(exp, 'hero_primary')}">{html.escape(exp['primary_cta'])}</a>
        <a class="btn secondary" href="#community">커뮤니티 구성 보기</a>
      </div>
      <p class="mini">타겟: {html.escape(exp['segment'])} · offer_id: <code>{html.escape(exp['offer_id'])}</code></p>
    </div>
    <aside class="panel">
      <h2>오늘 이 홈페이지의 목적</h2>
      <p>하루 하나씩 외부 커뮤니티/댓글/영상 설명란에 붙여보고, 클릭·quick-interest lead·폼 제출을 비교합니다.</p>
      <div class="metric">
        <div><strong>1</strong>명확한 타겟</div><div><strong>1</strong>전환 CTA</div><div><strong>3+</strong>유입 훅</div><div><strong>0</strong>낚시성 문구</div>
      </div>
    </aside>
  </section>
  <section class="grid" id="community">
    <div class="card wide"><h2>이 사람들이 바로 반응합니다</h2><ul>{pain}</ul></div>
    <div class="card"><h2>바로 연결할 오퍼</h2><p><b>{html.escape(exp['primary_cta'])}</b></p><p class="mini">클릭은 lead.html로 바로 이동하고, lead 페이지 내부에서 quick-interest/outbound 전환을 기록합니다.</p><a class="btn primary" href="{track_url(exp, 'offer_card')}">오퍼 페이지 열기</a></div>
    <div class="card full"><h2>커뮤니티 홈 섹션</h2><div class="sections">{sections}</div></div>
    <div class="card wide posts"><h2>초기 게시글/스레드 씨앗</h2><ul>{posts}</ul></div>
    <div class="card"><h2>오늘 배포 위치</h2><ul>{hooks}</ul></div>
  </section>
  <section class="footerCta">
    <div><h2>오늘은 이 CTA 하나만 검증합니다</h2><p>페이지 조회보다 CTA 클릭, quick-interest lead, 실제 문의 가능성을 우선 봅니다.</p></div>
    <a class="btn primary" href="{track_url(exp, 'footer_primary')}">{html.escape(exp['primary_cta'])}</a>
  </section>
</main>
</body>
</html>
'''

pages_dir = os.path.join(base, 'communities')
os.makedirs(pages_dir, exist_ok=True)
for exp in experiments:
    write(os.path.join(pages_dir, exp['slug'] + '.html'), render_page(exp))

cards = []
for exp in experiments:
    cards.append(f"<article><span>DAY {exp['day']} · {html.escape(exp['site'])}</span><h2>{html.escape(exp['title'])}</h2><p>{html.escape(exp['segment'])}</p><a href='{exp['slug']}.html'>홈페이지 보기</a><code>{html.escape(exp['offer_id'])}</code></article>")
index = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Daily Community Homepage Experiments</title><style>body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;margin:0;background:#f8fafc;color:#0f172a}}.wrap{{max-width:1120px;margin:0 auto;padding:36px 18px}}h1{{font-size:44px;letter-spacing:-.04em;margin:0 0 8px}}.sub{{color:#64748b;font-size:18px}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:24px}}article{{background:white;border:1px solid #e5e7eb;border-radius:22px;padding:20px;box-shadow:0 12px 40px rgba(15,23,42,.06)}}span{{font-size:13px;font-weight:900;color:#2563eb}}h2{{font-size:20px}}a{{display:inline-flex;margin:10px 0;padding:11px 13px;border-radius:12px;background:#0f172a;color:white;text-decoration:none;font-weight:900}}code{{display:block;color:#64748b}}@media(max-width:820px){{.grid{{grid-template-columns:1fr}}h1{{font-size:32px}}}}</style></head><body><main class="wrap"><h1>하루 1개 커뮤니티 홈페이지 실험</h1><p class="sub">자동 발행 콘텐츠와 별도로, 특정 타겟에게 직접 던질 수 있는 커뮤니티형 홈/랜딩 7종입니다. 모든 CTA는 추적 링크를 거쳐 lead.html로 연결됩니다.</p><section class="grid">{''.join(cards)}</section><p class="sub">updated_at: {now}</p></main></body></html>'''
write(os.path.join(pages_dir, 'index.html'), index)

manifest = {
  'updated_at': now,
  'purpose': '하루 1개씩 특정 타겟 커뮤니티형 홈페이지를 배포해 real CTA click/quick-interest lead/revenue_proxy를 검증',
  'public_index_path': 'communities/index.html',
  'public_index_url': 'https://araelaver.github.io/revenue-ops-dashboard/communities/',
  'daily_rotation': [dict({k: exp[k] for k in ['day','slug','site','segment','title','offer_id','intent','primary_cta']}, traffic_hooks=exp['traffic_hooks'], url=f"https://araelaver.github.io/revenue-ops-dashboard/communities/{exp['slug']}.html") for exp in experiments],
  'success_metrics': ['community_page_view', 'track.html CTA click', 'lead.html quick-interest click', 'lead form submit', 'offer outbound/revenue_proxy'],
  'next_manual_action': '오늘 DAY 1 자동차보험 갱신 체크룸 링크를 자동차보험/재테크 글 하단, 관련 커뮤니티 답변, YouTube 고정댓글 중 1곳 이상에 배포'
}
write(os.path.join(base, 'data', 'community_homepage_experiments.json'), json.dumps(manifest, ensure_ascii=False, indent=2))

print(json.dumps({'created_html_pages': len(experiments)+1, 'manifest': os.path.join(base,'data/community_homepage_experiments.json'), 'index': os.path.join(pages_dir,'index.html')}, ensure_ascii=False))
