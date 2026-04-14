# Revenue Ops Dashboard

Long-term operating dashboard for a YouTube + WordPress revenue system.

Live features
- Strategy and monetization overview
- KPI panel
- Funnel visualization
- Active work timeline
- Weekly cadence and monthly review
- Content queue
- Polling-based live updates from `data/status.json`

Local development

```bash
cd dashboard
python3 -m http.server 8420
```

Deployment
- GitHub Pages via `.github/workflows/deploy-pages.yml`

Data source
- `data/status.json`

Update examples
- `examples/openclaw.draft_created.json`
- `examples/hermes.quality_review_completed.json`

Updater scripts
- `scripts/sample_updater.py`
- `scripts/apply_event.py`
