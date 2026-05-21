#!/usr/bin/env bash
# YouTube 쇼츠 자동 발행 (채널별)
# HERMES_CHANNEL 환경변수로 채널 지정
# shorts_today 가드 + YouTube quota 가드
set -uo pipefail
CRON_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$CRON_DIR/_common.sh"

REVIEWED="$HERMES_ROOT/drafts/reviewed"
PUBLISHED="$HERMES_ROOT/drafts/published"
BLOG_AUTO="${BLOG_AUTO:-/Volumes/WorkDrive/Develop/37_blog-auto}"

CHANNEL="${HERMES_CHANNEL:-araelaver}"
PRIVACY="${HERMES_YT_PRIVACY:-public}"

# LLM/렌더 안정성 기본값(필요 시 외부 env로 덮어쓰기)
export HERMES_LLM_BACKEND="${HERMES_LLM_BACKEND:-codex}"
export HERMES_LLM_TIMEOUT="${HERMES_LLM_TIMEOUT:-180}"
export HERMES_SHORTS_FAST_RENDER="${HERMES_SHORTS_FAST_RENDER:-1}"
export HERMES_SHORTS_FPS="${HERMES_SHORTS_FPS:-8}"

mkdir -p "$PUBLISHED"
LOCK_FILE="/tmp/hermes_publish_shorts_${CHANNEL}.lock"
if [ -f "$LOCK_FILE" ]; then
    old_pid="$(cat "$LOCK_FILE" 2>/dev/null || true)"
    if [ -n "$old_pid" ] && kill -0 "$old_pid" 2>/dev/null; then
        log "WARN: [$CHANNEL] 기존 Shorts 발행 실행 중(pid=$old_pid) — 중복 실행 방지 skip"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
cleanup_lock() { rm -f "$LOCK_FILE"; }
trap cleanup_lock EXIT INT TERM

# 격일 가드. 수동 수익/전환 실험은 HERMES_FORCE_SHORTS_TODAY=1로만 명시 우회.
if ! shorts_today; then
    if [ "${HERMES_FORCE_SHORTS_TODAY:-0}" = "1" ]; then
        log "[$CHANNEL] 쇼츠 비대상일 — HERMES_FORCE_SHORTS_TODAY=1로 수동 발행 계속"
    else
        log "[$CHANNEL] 쇼츠 비대상일 — skip"
        exit 0
    fi
fi

[ -d "$REVIEWED" ] || { log "reviewed 디렉토리 없음 — skip"; exit 0; }
[ -d "$BLOG_AUTO" ] || { log "37_blog-auto 없음 — skip"; exit 0; }

# 신규: YYYYMMDD_yt-<channel>-shorts_<slug>.md
# 레거시: *_shorts.md
candidates=$(hermes_find "$REVIEWED" "*_yt-${CHANNEL}-shorts_*.md")
[ -z "$candidates" ] && candidates=$(hermes_find "$REVIEWED" "*_shorts.md")

draft=""
while IFS= read -r f; do
    [ -z "$f" ] && continue
    if [[ "$f" == *"_yt-${CHANNEL}-shorts_"* ]]; then
        draft="$f"
        break
    fi
    target=$(hermes_read_field "$f" "target")
    if [[ "$target" == "yt:${CHANNEL}:shorts" ]]; then
        draft="$f"
        break
    fi
done <<< "$candidates"

[ -z "$draft" ] && { log "[$CHANNEL] 쇼츠 발행 대상 없음 — skip"; exit 0; }

name="$(basename "$draft" .md)"

# 포맷 분할 상한 가드 (쇼츠 일일 최대치)
shorts_used_today=$("$PYTHON_BIN" - <<'PY'
import json
from datetime import date
from pathlib import Path
p=Path('/Volumes/WorkDrive/Develop/48.HermesAgent/dashboard/data/yt_quota.json')
if not p.exists():
    print(0)
else:
    d=json.loads(p.read_text(encoding='utf-8'))
    today=date.today().isoformat()
    h=d.get('history',[]) if d.get('date')==today else []
    print(sum(1 for x in h if str(x.get('label','')).startswith('shorts:')))
PY
)
if [ "${shorts_used_today:-0}" -ge "${HERMES_YT_MAX_SHORTS_PER_DAY:-4}" ]; then
    log "WARN: Shorts 일일 상한 도달(${shorts_used_today}/${HERMES_YT_MAX_SHORTS_PER_DAY}) — skip ($name) — reviewed/ 유지"
    exit 0
fi

# YouTube quota 가드 (1600 cost)
quota_label="shorts:$CHANNEL:$name"
if ! yt_quota_reserve 1600 "$quota_label"; then
    log "WARN: YouTube quota 한도 도달 — skip ($name) — reviewed/ 유지"
    exit 0
fi
quota_reserved=1

log "=== YT 쇼츠 발행 시작 ($CHANNEL, privacy=$PRIVACY): $name ==="

# 발행 직전 고품질 게이트
if qa_output=$(run_python prepublish_gate.py "$draft" 2>&1); then
    echo "$qa_output"
else
    qa_rc=$?
    echo "$qa_output"
    if [ "${quota_reserved:-0}" = "1" ]; then
        yt_quota_release 1600 "$quota_label" || true
        log "WARN: $name QA 미통과/실패 -> quota 예약분 복구 ($quota_label)"
    fi
    if [ "$qa_rc" -eq 10 ]; then
        log "WARN: 품질 게이트 미통과 -> revised/ 이동"
        hermes_mv "$draft" "$HERMES_ROOT/drafts/revised/"
    else
        log "ERROR: 품질 게이트 실행 실패 (rc=$qa_rc)"
    fi
    exit 0
fi

shorts_timeout="${HERMES_SHORTS_RENDER_TIMEOUT:-900}"
if output=$(cd "$BLOG_AUTO" && "$PYTHON_BIN" "$HERMES_ROOT/scripts/run_with_timeout.py" "$shorts_timeout" -- "$NODE_BIN" scripts/hermes-publish-shorts.mjs "$draft" --channel="$CHANNEL" --privacy="$PRIVACY" 2>&1); then
    echo "$output"
    url=$(echo "$output" | grep -oE 'https://[^ "]+' | head -1)
    title=$(hermes_read_field "$draft" "topic")
    hermes_mv "$draft" "$PUBLISHED/"
    log "→ published/"
    bash "$CRON_DIR/notify-telegram.sh" "SHORTS" "$CHANNEL" "$title" "$url" "success" &
else
    publish_rc=$?
    echo "$output"
    url=$(echo "$output" | grep -oE 'https://[^ "]+' | grep -E 'youtu\.be|youtube\.com' | head -1 || true)
    if [ -n "$url" ] && echo "$output" | grep -Eq '업로드 완료|✅ 업로드 완료|youtube.com/shorts|youtu.be'; then
        title=$(hermes_read_field "$draft" "topic")
        if [ -e "$draft" ]; then
            hermes_mv "$draft" "$PUBLISHED/"
            log "WARN: uploader rc=$publish_rc 이지만 URL 확인 -> 성공으로 상태 동기화: $url"
            log "→ published/"
        else
            log "WARN: uploader rc=$publish_rc 이지만 URL 확인, draft는 이미 이동됨: $url"
        fi
        bash "$CRON_DIR/notify-telegram.sh" "SHORTS" "$CHANNEL" "$title" "$url" "success" &
    else
        if [ "${quota_reserved:-0}" = "1" ]; then
            yt_quota_release 1600 "$quota_label" || true
            log "WARN: $name 발행 실패/타임아웃 -> quota 예약분 복구 ($quota_label)"
        fi
        if [ "$publish_rc" -eq 124 ]; then
            log "ERROR: $name Shorts renderer timeout ${shorts_timeout}s (reviewed/ 유지)"
        else
            log "ERROR: $name 발행 실패 rc=$publish_rc (reviewed/ 유지)"
        fi
        bash "$CRON_DIR/notify-telegram.sh" "SHORTS" "$CHANNEL" "$name" "" "fail" &
    fi
fi
log "=== 완료 ==="
