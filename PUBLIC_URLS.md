# Hermes Ops Dashboard URLs

기준: 2026-05-10 21:33 KST 실측

## 현재 사용 가능한 외부 주소

### 1) 외부 대시보드 — 정상

- https://araelaver.github.io/revenue-ops-dashboard/
- 확인: HTTP 200
- 용도: 운영 대시보드 외부 확인

### 2) 외부 상태 JSON — 정상

- https://araelaver.github.io/revenue-ops-dashboard/data/status.json
- 확인: HTTP 200
- 용도: 대시보드 원본 상태 데이터 확인

### 3) 외부 Lead 폼 — 정상

- https://araelaver.github.io/revenue-ops-dashboard/lead.html?site=unpre&offer_id=unpre_insurance_quote
- 확인: HTTP 200
- 용도: offer_id별 lead 수집 폼

### 4) 현재 외부 Tracking backend — 정상

- https://vocal-tennis-ink-album.trycloudflare.com
- health: https://vocal-tennis-ink-album.trycloudflare.com/health
- 확인: /health HTTP 200
- 확인: /t HTTP 302
- 확인: /lead POST HTTP 200
- kind: cloudflare_quick_tunnel
- stable: false
- fixed_backend: false

주의: 현재 watchdog가 localtunnel `/t` 지연을 감지해서 Cloudflare quick tunnel로 복구했습니다. Cloudflare quick tunnel도 임시 터널이므로 production-grade stable 주소는 아닙니다.

## 내부 주소

- 내부 대시보드: http://127.0.0.1:8420
- 내부 LAN 후보: http://192.168.0.18:8420
- 내부 tracking health: http://127.0.0.1:8431/health

## 참고/fallback 주소

### localtunnel fallback — 일부 지연 있음

- https://hermes-revenue-tracking-48.loca.lt
- health: https://hermes-revenue-tracking-48.loca.lt/health
- 상태: /health는 200이나 `/t` probe에서 timeout 발생 가능
- kind: localtunnel_fixed_subdomain
- stable: false
- fixed_backend: true

## 사용 금지: 만료된 lhr.life 주소

아래 주소는 2026-05-10 21:32 KST 확인 시 503입니다.

- https://658e72994195a7.lhr.life
- https://13f81b053c0178.lhr.life
- https://932d4b5f253410.lhr.life

## 사용 방법

- 대시보드 외부 확인: https://araelaver.github.io/revenue-ops-dashboard/
- 상태 원본 확인: https://araelaver.github.io/revenue-ops-dashboard/data/status.json
- Lead 폼 열기: https://araelaver.github.io/revenue-ops-dashboard/lead.html?site=unpre&offer_id=unpre_insurance_quote
- Tracking 서버 상태 확인: https://vocal-tennis-ink-album.trycloudflare.com/health
- `/lead`는 GET으로 열면 404가 정상입니다. 실제 lead 수집은 POST로 동작합니다.
- `/t`는 `target=`에 허용 도메인 URL이 들어가야 302 redirect가 정상 동작합니다.

## 운영상 주의

- 현재 외부 대시보드는 GitHub Pages가 정상 주소입니다.
- 현재 외부 tracking은 Cloudflare quick tunnel입니다.
- quick tunnel/localtunnel은 모두 stable=false입니다.
- 장기 안정 주소는 Cloudflare named tunnel 또는 VPS reverse proxy로 전환해야 합니다.
