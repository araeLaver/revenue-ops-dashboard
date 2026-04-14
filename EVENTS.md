# Dashboard Event Model

This document defines how OpenClaw and Hermes should update the dashboard in a stable, long-term way.

Primary public URL
- https://300fafceb00687.lhr.life

Secondary public URL
- https://05d52ded25c010.lhr.life

Source of truth
- `dashboard/data/status.json`

Goal
- Turn the dashboard into a real operating console, not just a static page
- Keep queue state, active work, risks, and notes synchronized with the actual automation pipeline

Event producers
1. OpenClaw
- topic discovery
- initial draft generation
- draft packaging
- publish queue movement

2. Hermes
- topic scoring
- content quality review
- rewrite decisions
- winner/middle/loser classification
- operational risk updates

Canonical stages
- intake
- scoring
- approved
- draft
- review
- revise
- queued
- published
- refresh
- pruned

Allowed stage transitions
- intake -> scoring
- scoring -> approved
- scoring -> pruned
- approved -> draft
- draft -> review
- review -> revise
- review -> queued
- revise -> review
- queued -> published
- published -> refresh
- refresh -> review
- refresh -> pruned

Priority levels
- high
- medium
- low

UI status values
- healthy
- watch
- blocked
- done

Recommended event types
- topic_discovered
- topic_scored
- topic_rejected
- topic_approved
- draft_created
- shorts_created
- wordpress_created
- quality_review_completed
- revision_requested
- revision_completed
- queued_for_publish
- published
- kpi_snapshot_updated
- content_classified
- risk_updated

Update rules
1. Every event should update `last_updated`
2. Every event should append or refresh one `active_work` item
3. Every series should have one stable `content_queue` item keyed by `name`
4. Do not create duplicate queue items for the same series name
5. Hermes should not overwrite OpenClaw-specific fields blindly; merge by item name
6. Update `system_status` only when system-wide state changes

System status guidance
- healthy: pipeline moving normally
- watch: non-blocking issue exists
- blocked: monetization/offer/quality bottleneck stops useful progress
- done: one-off milestone completed

What OpenClaw should update
- `content_queue`
- `active_work`
- `notes`
- optional `focus_areas` if weekly priorities changed

What Hermes should update
- `content_queue`
- `active_work`
- `risks`
- `notes`
- optional `monthly_review` after classification

Recommended identity model
- queue identity = `name`
- active work identity = append-only recent timeline
- notes identity = append-only recent timeline

Best practice
- Use one updater script to merge partial payloads into the main status file
- Let producers emit small event JSON payloads rather than rewriting the whole dashboard file
