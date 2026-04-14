# Dashboard Integration Contract

Current public URL (ephemeral tunnel):
- https://05d52ded25c010.lhr.life

Local URL:
- http://127.0.0.1:8420

Purpose
- Let OpenClaw, Hermes, cron jobs, or shell scripts update the dashboard in near real time
- Keep one shared source of truth: `dashboard/data/status.json`

Core rule
- Anything that changes workflow state should write to `dashboard/data/status.json`
- The dashboard polls this file every 3 seconds

Recommended update events
1. Topic scored
2. Topic approved/rejected
3. Long-form draft created
4. Shorts derived
5. WordPress article generated
6. Quality review completed
7. Content approved/revise/reject decision made
8. Draft published or queued
9. KPI snapshot refreshed
10. Winner/middle/loser classification updated

Minimum fields to update every run
- `last_updated`
- `system_status`
- `active_work`
- `content_queue`
- `notes`

Suggested pipeline mapping

OpenClaw writes:
- topic intake
- initial draft state
- queue stage changes

Hermes writes:
- scoring results
- quality review decisions
- rewrite targets
- weekly/monthly review notes
- risk changes

Simple state model
- scoring
- draft
- review
- revise
- approved
- published
- refresh
- pruned

Status labels used by the UI
- healthy
- watch
- blocked
- done

Example queue item
{
  "name": "툴 비교 시리즈",
  "stage": "review",
  "priority": "high",
  "status": "watch",
  "next_action": "hook score가 7 미만이라 첫 20초 재작성"
}

Example active work item
{
  "title": "롱폼 품질평가",
  "detail": "CTR 예상치는 양호하지만 CTA 자연스러움이 약해 재작성 필요",
  "status": "watch",
  "status_label": "revise 필요"
}

Operational recommendation
- Do not let every tool rewrite the whole file blindly.
- Use one updater script that loads JSON, patches only target sections, updates `last_updated`, then saves.
- Keep queue item names stable so they can be updated by identity.

Long-term recommendation
- Move from file polling to webhook/API later.
- For now, file-based status is enough and easiest to maintain.
