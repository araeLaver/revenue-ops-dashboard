/* ─── Hermes Control Center ─── */

const S = { healthy: 'ok', watch: 'warn', blocked: 'bad', done: 'ok' };

function el(html) {
  const t = document.createElement('template');
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

function $(id) { return document.getElementById(id); }
function setText(id, v) { const n = $(id); if (n) n.textContent = v ?? '-'; }

/* ─── TABS ─── */
document.querySelectorAll('.tab').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
    btn.classList.add('active');
    $('tab-' + btn.dataset.tab).classList.add('active');
  });
});

/* ─── DATA LOADERS ─── */
async function loadJSON(path) {
  try {
    const r = await fetch(`data/${path}?t=${Date.now()}`);
    return r.ok ? r.json() : null;
  } catch { return null; }
}

/* ─── OVERVIEW RENDERERS ─── */

function renderStats(data, drafts) {
  const pub = $('stat-published');
  const pend = $('stat-pending');
  const rev = $('stat-revised');
  const counts = drafts?.counts || drafts?.by_state || data?.ops_snapshot?.queue || {};
  const published = counts.published?.total ?? drafts?.published ?? data?.queue_snapshot?.published ?? '-';
  const pending = counts.pending?.total ?? drafts?.pending ?? data?.queue_snapshot?.pending ?? '0';
  const revised = counts.revised?.total ?? drafts?.revised ?? data?.queue_snapshot?.revised ?? '-';
  if (pub) pub.querySelector('.stat-number').textContent = published;
  if (pend) pend.querySelector('.stat-number').textContent = pending;
  if (rev) rev.querySelector('.stat-number').textContent = revised;
}

function renderYtQuota(quota) {
  const card = $('stat-yt-quota');
  if (!card || !quota) return;
  const safeLimit = quota.safe_limit || 9600;
  const used = quota.used || 0;
  const remaining = quota.remaining ?? Math.max(0, safeLimit - used);
  card.querySelector('.stat-number').textContent = remaining.toLocaleString();
  if (remaining < 2000) card.querySelector('.stat-number').style.color = 'var(--bad)';
}

function renderTasks(items) {
  const root = $('active-work');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    root.appendChild(el(`
      <article class="task-item" data-status="${item.status}">
        <h3>${item.title}</h3>
        <p>${item.detail}</p>
        <div class="status-pill ${S[item.status] || 'warn'}">${item.status_label}</div>
      </article>
    `));
  });
}

function renderHermesFeatureUsage(data) {
  const root = $('hermes-feature-usage');
  if (!root) return;
  root.innerHTML = '';
  let features = [];
  if (Array.isArray(data?.features)) {
    features = data.features;
  } else if (data?.features && typeof data.features === 'object') {
    features = Object.entries(data.features).map(([name, value]) => ({
      name,
      status: value.status === 'active' || value.status === 'present' || value.status === 'configured' ? 'in_use' : (value.status || 'partial'),
      current_use: value.evidence || value.status || JSON.stringify(value.inventory || value).slice(0, 120),
      next_use: value.inventory ? `inventory ${JSON.stringify(value.inventory)}` : '운영 증거 기반 계속 갱신'
    }));
  } else if (Array.isArray(data?.hermes_capability_usage)) {
    features = data.hermes_capability_usage.map(x => ({ name: x.capability, status: x.status, current_use: x.evidence, next_use: data.answer || '' }));
  }
  if (!features.length) {
    root.appendChild(el('<article class="mini-feature"><strong>데이터 없음</strong><p>hermes_feature_usage.json 필요</p></article>'));
    return;
  }
  features.slice(0, 15).forEach(f => {
    const cls = f.status === 'in_use' || f.status === 'active' || f.status === 'configured' ? 'ok' : (f.status === 'partial' || f.status === 'planned' ? 'warn' : 'bad');
    root.appendChild(el(`
      <article class="mini-feature">
        <div class="feature-top"><strong>${f.name}</strong><span class="status-pill ${cls}">${f.status}</span></div>
        <p>${f.current_use || '-'}</p>
        <small>${f.next_use || ''}</small>
      </article>
    `));
  });
}

function renderDailyGoalStatus(data) {
  const root = $('daily-goal-status');
  if (!root) return;
  root.innerHTML = '';
  setText('daily-goal-updated', data?.updated || '-');
  if (!data) {
    root.appendChild(el('<article class="risk-item"><strong>데이터 없음</strong><p>daily_goal_status.json 필요</p></article>'));
    return;
  }
  const msgCls = data.overall_status === 'hit' ? 'ok' : (data.overall_status === 'partial_success' ? 'warn' : 'bad');
  root.appendChild(el(`
    <article class="daily-goal-summary">
      <div><strong>${data.overall_message || '일일 목표 상태'}</strong><p>전체 +${data.actual_delta?.total ?? 0} · WP +${data.actual_delta?.wp ?? 0} · Shorts +${data.actual_delta?.shorts ?? 0} · Longform +${data.actual_delta?.longform ?? 0}</p></div>
      <div class="status-pill ${msgCls}">${data.overall_status}</div>
    </article>
  `));
  const rows = (data.goals || []).map(g => {
    const cls = g.status === 'hit' ? 'ok' : (g.status === 'partial' ? 'warn' : 'bad');
    const pct = g.target ? Math.round((Number(g.actual || 0) / Number(g.target || 1)) * 100) : 0;
    return `<tr>
      <td><strong>${g.format}</strong></td>
      <td>${g.target}</td>
      <td>${g.actual}</td>
      <td>${pct}%</td>
      <td><span class="status-pill ${cls}">${g.status}</span></td>
      <td>${g.failure_reason || '-'}</td>
      <td>${g.next_action || '-'}</td>
    </tr>`;
  }).join('');
  root.appendChild(el(`
    <div class="schedule-table-wrap">
      <table class="schedule-table">
        <thead><tr><th>항목</th><th>목표</th><th>달성</th><th>달성률</th><th>상태</th><th>실패/미달 원인</th><th>다음 조치</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
  `));
}

function renderPerformanceSnapshot(data) {
  const root = $('performance-snapshot');
  if (!root) return;
  root.innerHTML = '';
  let summary = data?.summary || [];
  if (!summary.length && data?.conversion_funnel_status) {
    const inv = data.conversion_funnel_status.inventory || {};
    const ready = data.conversion_funnel_status.ready_to_publish_by_format || {};
    const revised = data.conversion_funnel_status.revision_backlog_by_format || {};
    const obs = data.conversion_funnel_status.analytics_observability || {};
    summary = [
      { label: '누적 발행', value: inv.published_total ?? '-', note: `대기 reviewed ${inv.quality_reviewed_ready ?? 0} · 수정 revised ${inv.needs_revision ?? 0}` },
      { label: '즉시 발행 가능', value: `WP ${ready.wp ?? 0} / Shorts ${ready.shorts ?? 0} / Longform ${ready.longform ?? 0}`, note: '다음 publish 슬롯에서 소진 대상' },
      { label: '수정 백로그', value: `WP ${revised.wp ?? 0} / Longform ${revised.longform ?? 0}`, note: '품질 게이트 또는 구조 보강 필요' },
      { label: '전환 데이터', value: obs.has_revenue_metrics ? 'revenue linked' : 'revenue missing', note: `click ${obs.has_click_metrics ? 'ok' : 'missing'} · lead ${obs.has_lead_metrics ? 'ok' : 'missing'}` }
    ];
  }
  summary.forEach(item => {
    root.appendChild(el(`
      <article class="risk-item">
        <strong>${item.label}: ${item.value}</strong>
        <p>${item.note}</p>
      </article>
    `));
  });
  const funnel = data?.conversion_funnel || [];
  if (funnel.length) {
    root.appendChild(el('<div class="subhead">전환 퍼널 상태</div>'));
    funnel.forEach(stage => {
      const cls = stage.status === 'ok' ? 'ok' : (stage.status === 'partial' ? 'warn' : 'bad');
      root.appendChild(el(`
        <article class="risk-item">
          <strong>${stage.stage} · ${stage.metric}</strong>
          <p>${stage.next}</p>
          <div class="status-pill ${cls}">${stage.status}</div>
        </article>
      `));
    });
  }
}

function renderReportingStatus(data) {
  const root = $('reporting-status');
  if (!root) return;
  root.innerHTML = '';
  if (!data) return;
  const cls = data.status === 'ok' ? 'ok' : (data.status === 'watch' ? 'warn' : 'bad');
  root.appendChild(el(`
    <article class="risk-item">
      <strong>${data.delivery_mode || 'reporting'}</strong>
      <p>${data.current_route || '-'}</p>
      <p>${data.last_error_summary || '-'}</p>
      <div class="status-pill ${cls}">${data.status}</div>
    </article>
  `));
  (data.next_actions || []).forEach(a => root.appendChild(el(`
    <article class="risk-item">
      <strong>${a.name}</strong>
      <p>${a.detail}</p>
      <div class="status-pill ${a.status === 'in_use' ? 'ok' : 'warn'}">${a.status}</div>
    </article>
  `)));
}

function renderHermesFullFeaturePlan(data) {
  const root = $('hermes-full-feature-plan');
  if (!root) return;
  root.innerHTML = '';
  (data?.phases || []).forEach(p => {
    const cls = p.status === 'done' ? 'ok' : (p.status === 'in_progress' ? 'warn' : 'bad');
    root.appendChild(el(`
      <article class="risk-item">
        <strong>${p.phase}</strong>
        <p>${(p.items || []).join(' · ')}</p>
        <div class="status-pill ${cls}">${p.status}</div>
      </article>
    `));
  });
}

function renderRisks(items) {
  const root = $('risks');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    root.appendChild(el(`
      <article class="risk-item">
        <strong>${item.title}</strong>
        <p>${item.detail}</p>
        <div class="status-pill ${S[item.status] || 'warn'}">${item.status_label}</div>
      </article>
    `));
  });
}

function renderLlmStatus(llm) {
  const root = $('llm-status');
  if (!root) return;
  root.innerHTML = '';
  setText('llm-last-updated', llm?.updated || '-');

  const providers = llm?.providers || [];
  if (!providers.length) {
    root.appendChild(el('<article class="note-item"><strong>데이터 없음</strong><p>data/llm_status.json을 갱신하면 표시됩니다.</p></article>'));
    return;
  }

  providers.forEach(p => {
    const cls = p.status === 'ok' ? 'ok' : (p.status === 'warn' ? 'warn' : 'bad');
    root.appendChild(el(`
      <article class="risk-item">
        <strong>${p.name}</strong>
        <p>상태: ${p.status_label || p.status} · 최근 성공률: ${p.success_rate ?? '-'}% · 평균응답: ${p.avg_latency_sec ?? '-'}s</p>
        <p>최근 오류: ${p.last_error || '-'}</p>
        <div class="status-pill ${cls}">${p.status_label || p.status}</div>
      </article>
    `));
  });
}

function renderKpis(items) {
  const root = $('kpi-list');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    root.appendChild(el(`
      <article class="kpi-item">
        <div class="kpi-main"><strong>${item.value}</strong><span>${item.label}</span></div>
        <div class="kpi-side">${item.target}</div>
      </article>
    `));
  });
}

function renderQueue(items) {
  const root = $('content-queue');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    const score = item.score ? `<span class="badge">${item.score.average ?? '-'} / ${item.score.verdict ?? '-'}</span>` : '';
    root.appendChild(el(`
      <article class="queue-item">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <h3>${item.name}</h3>
          ${score}
        </div>
        <p>stage: ${item.stage} &middot; priority: ${item.priority}</p>
        <div class="status-pill ${S[item.status] || 'warn'}">${item.next_action || '-'}</div>
      </article>
    `));
  });
}

function renderTrends(trending) {
  const root = $('trend-keywords');
  const dateEl = $('trend-date');
  if (!root || !trending) return;
  if (dateEl) dateEl.textContent = trending.date || '-';
  root.innerHTML = '';
  (trending.all_keywords || []).forEach(kw => {
    root.appendChild(el(`<span class="tag">${kw}</span>`));
  });
}

function renderTrendSignals(trending) {
  const root = $('trend-signal-board');
  if (!root) return;
  root.innerHTML = '';
  const signals = trending?.top_signals || [];
  if (!signals.length) {
    root.appendChild(el('<article class="trend-row"><strong>데이터 없음</strong><p>trend_ingest.py daily 실행 후 표시됩니다.</p></article>'));
    return;
  }
  signals.slice(0, 12).forEach(sig => {
    const parts = sig.score_breakdown || {};
    const sentiment = Number(sig.sentiment || 0);
    const sentimentCls = sentiment > 0 ? 'ok' : (sentiment < 0 ? 'bad' : 'warn');
    root.appendChild(el(`
      <article class="trend-row">
        <div class="trend-main">
          <strong>${sig.keyword}</strong>
          <p>${sig.source || '-'} · ${sig.domain || '미분류'} · ${sig.channel || '-'}</p>
        </div>
        <div class="trend-score">${sig.score ?? '-'}</div>
        <div class="trend-metrics">
          <span>freq ${sig.frequency ?? 1}</span>
          <span>growth ${sig.growth_rate ?? 0}x</span>
          <span class="${sentimentCls}">sent ${sentiment}</span>
          <span>intent ${parts.intent_bonus ?? 0}</span>
        </div>
      </article>
    `));
  });
}

function renderNotes(items) {
  const root = $('notes');
  if (!root) return;
  root.innerHTML = '';
  (items || []).slice(0, 6).forEach(item => {
    root.appendChild(el(`
      <article class="note-item">
        <strong>${item.title}</strong>
        <p>${item.detail}</p>
      </article>
    `));
  });
}

function renderOpsSnapshot(status, drafts, quota) {
  const ops = status?.ops_snapshot || {};
  setText('ops-as-of', ops.as_of || status?.last_updated || '-');

  const summary = $('ops-summary');
  if (summary) {
    const q = ops.queue || drafts.by_state || {};
    const reviewed = q.reviewed?.total ?? drafts.reviewed ?? '-';
    const revised = q.revised?.total ?? drafts.revised ?? '-';
    const published = q.published?.total ?? drafts.published ?? '-';
    const ytUsed = quota?.used ?? ops.yt_quota?.used ?? 0;
    const ytUploads = quota?.uploads ?? ops.yt_quota?.uploads ?? 0;
    summary.innerHTML = [
      {label:'오늘 발행 증가', value: ops.today_published_delta || '-', detail: ops.today_publish_result || '' , cls:'ok'},
      {label:'남은 reviewed', value: reviewed, detail:`WP ${q.reviewed?.wp ?? 0} / Shorts ${q.reviewed?.shorts ?? 0} / Longform ${q.reviewed?.longform ?? 0}`, cls: reviewed ? 'warn' : 'ok'},
      {label:'수정 필요', value: revised, detail:`WP ${q.revised?.wp ?? 0} / Longform ${q.revised?.longform ?? 0}`, cls: revised ? 'warn' : 'ok'},
      {label:'누적 published', value: published, detail:`WP ${q.published?.wp ?? 0} / Shorts ${q.published?.shorts ?? 0} / Longform ${q.published?.longform ?? 0}`, cls:'ok'},
      {label:'YT quota', value:`${ytUsed}/10000`, detail:`오늘 uploads ${ytUploads} · Shorts cap 4`, cls: ytUsed > 8000 ? 'bad' : 'ok'},
      {label:'실행 중 프로세스', value: ops.running_processes || 'unknown', detail:'publish/renderer 병목 감시 대상', cls: ops.running_processes === 'none confirmed after cleanup' ? 'ok' : 'warn'},
    ].map(x => `<article class="ops-tile ${x.cls}"><span>${x.label}</span><strong>${x.value}</strong><p>${x.detail}</p></article>`).join('');
  }

  const matrix = $('queue-matrix');
  if (matrix) {
    const q = ops.queue || drafts.by_state || {};
    const rows = ['wp','shorts','longform'].map(type => {
      const label = type === 'wp' ? 'WordPress' : (type === 'shorts' ? 'Shorts' : 'Longform');
      return `<tr><th>${label}</th><td>${q.pending?.[type] ?? 0}</td><td>${q.reviewed?.[type] ?? 0}</td><td>${q.revised?.[type] ?? 0}</td><td>${q.published?.[type] ?? 0}</td><td>${q.rejected?.[type] ?? 0}</td></tr>`;
    }).join('');
    matrix.innerHTML = `<table class="ops-table"><thead><tr><th>포맷</th><th>Pending</th><th>Reviewed</th><th>Revised</th><th>Published</th><th>Rejected</th></tr></thead><tbody>${rows}</tbody></table>`;
  }
}

function renderBottleneckBoard(items) {
  const root = $('bottleneck-board');
  if (!root) return;
  root.innerHTML = '';
  let list = [];
  if (Array.isArray(items)) {
    list = items;
  } else if (items && typeof items === 'object') {
    list = Object.entries(items).map(([key, value]) => ({ area: key, ...(value || {}) }));
  }
  list.forEach(item => {
    const cls = item.status === 'ok' ? 'ok' : (item.status === 'blocked' ? 'bad' : 'warn');
    const area = item.area || item.name || item.title || '-';
    const summary = item.summary || item.detail || item.description || item.root_cause || '-';
    const next = item.next || item.next_action || '';
    const current = item.current_backend_url ? `<br><small>backend: ${item.current_backend_url}</small>` : '';
    const gateway = item.stable_gateway_url ? `<br><small>gateway: ${item.stable_gateway_url}</small>` : '';
    root.appendChild(el(`<article class="bottleneck-item ${cls}"><strong>${area}</strong><p>${summary}${next ? `<br><span class="muted">다음: ${next}</span>` : ''}${current}${gateway}</p><div class="status-pill ${cls}">${item.status || 'watch'}</div></article>`));
  });
}

function renderDailySchedule(items) {
  const root = $('daily-schedule');
  if (!root) return;
  const rows = (items || []).map(item => {
    const target = item.target || item.purpose || item.description || '-';
    const next = item.next || item.next_run || '-';
    return `<tr><td class="time-cell">${item.time}</td><td><strong>${item.job}</strong><br><span>${target}</span></td><td>${item.guard || '-'}</td><td>${next}</td></tr>`;
  }).join('');
  root.innerHTML = `<table class="ops-table schedule-table"><thead><tr><th>시간</th><th>작업</th><th>병목 방지</th><th>다음 실행</th></tr></thead><tbody>${rows}</tbody></table>`;
}

/* ─── PIPELINE TAB ─── */

function renderPipeline(drafts) {
  const root = $('pipeline-flow');
  if (!root) return;
  const stages = [
    { label: 'Pending', count: drafts.pending, color: 'var(--accent)' },
    { label: 'Reviewed', count: drafts.reviewed, color: 'var(--ok)' },
    { label: 'Revised', count: drafts.revised, color: 'var(--warn)' },
    { label: 'Rejected', count: drafts.rejected, color: 'var(--bad)' },
    { label: 'Published', count: drafts.published, color: 'var(--ok)' },
    { label: 'Failed', count: drafts.failed, color: 'var(--bad)' },
  ];
  root.innerHTML = '';
  stages.forEach((s, i) => {
    if (i > 0) root.appendChild(el(`<span class="pipe-arrow">→</span>`));
    const stage = el(`<div class="pipe-stage"><div class="count" style="color:${s.color}">${s.count}</div><div class="label">${s.label}</div></div>`);
    root.appendChild(stage);
  });
}

function renderPublishBySite(published) {
  const root = $('publish-by-site');
  if (!root) return;
  const sites = {};
  published.forEach(f => {
    const m = f.match(/wp-(\w+)/);
    if (m) sites[m[1]] = (sites[m[1]] || 0) + 1;
  });
  const max = Math.max(...Object.values(sites), 1);
  root.innerHTML = '<div class="bar-chart">' +
    Object.entries(sites).sort((a,b) => b[1]-a[1]).map(([k,v]) =>
      `<div class="bar-row"><div class="bar-label">${k}</div><div class="bar-track"><div class="bar-fill c-wp" style="width:${v/max*100}%">${v}</div></div></div>`
    ).join('') + '</div>';
}

function renderPublishByType(published) {
  const root = $('publish-by-type');
  if (!root) return;
  const types = { wp: 0, shorts: 0, longform: 0 };
  published.forEach(f => {
    if (f.includes('wp-')) types.wp++;
    else if (f.includes('shorts')) types.shorts++;
    else if (f.includes('longform')) types.longform++;
  });
  const max = Math.max(...Object.values(types), 1);
  const colors = { wp: 'c-wp', shorts: 'c-shorts', longform: 'c-longform' };
  root.innerHTML = '<div class="bar-chart">' +
    Object.entries(types).map(([k,v]) =>
      `<div class="bar-row"><div class="bar-label">${k}</div><div class="bar-track"><div class="bar-fill ${colors[k]}" style="width:${v/max*100}%">${v}</div></div></div>`
    ).join('') + '</div>';
}

function renderRecentPublished(published) {
  const root = $('recent-published');
  if (!root) return;
  root.innerHTML = '';
  published.slice(-20).reverse().forEach(f => {
    const name = f.replace('.md', '');
    const parts = name.split('_');
    const date = parts[0] || '';
    const target = parts[1] || '';
    const topic = parts.slice(2).join(' ') || name;
    root.appendChild(el(`
      <div class="recent-item">
        <span class="ri-target">${target}</span>
        <span class="ri-topic" title="${topic}">${topic}</span>
        <span class="ri-date">${date}</span>
      </div>
    `));
  });
}

/* ─── CHANNELS TAB ─── */

function renderChannels(routing) {
  const root = $('channel-grid');
  if (!root || !routing) return;
  root.innerHTML = '';

  // WP sites
  Object.entries(routing.wp_sites || {}).forEach(([id, cfg]) => {
    root.appendChild(el(`
      <div class="channel-card">
        <div class="ch-icon">W</div>
        <div class="ch-name">${id}</div>
        <div class="ch-theme">${cfg.topic}</div>
        <div class="ch-meta">daily: ${cfg.daily_count} &middot; series: ${(cfg.series_master||[]).length}</div>
      </div>
    `));
  });

  // YT channels
  Object.entries(routing.yt_channels || {}).forEach(([id, cfg]) => {
    root.appendChild(el(`
      <div class="channel-card">
        <div class="ch-icon">YT</div>
        <div class="ch-name">${cfg.channel_name || id}</div>
        <div class="ch-theme">${cfg.theme}</div>
        <div class="ch-meta">shorts: ${cfg.shorts_hour}h &middot; longform: ${cfg.longform_hour}h</div>
      </div>
    `));
  });
}

function renderYtQuotaDetail(quota) {
  const root = $('yt-quota-detail');
  if (!root || !quota) return;
  const limit = 10000;
  const used = quota.used || 0;
  const pct = Math.round(used / limit * 100);
  root.innerHTML = `
    <div style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
        <span>사용: ${used.toLocaleString()}</span>
        <span>한도: ${limit.toLocaleString()}</span>
      </div>
      <div class="bar-track"><div class="bar-fill ${pct > 80 ? 'c-shorts' : 'c-wp'}" style="width:${pct}%">${pct}%</div></div>
    </div>
    <div style="font-size:12px;color:var(--muted)">업로드: ${quota.uploads || 0}건 (${quota.date || '-'})</div>
    <div style="margin-top:10px">
      ${(quota.history || []).map(h => `<div style="font-size:11px;color:var(--muted);margin:2px 0">${h.label} (${h.cost})</div>`).join('')}
    </div>
  `;
}

function renderCadence(items) {
  const root = $('weekly-cadence');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    root.appendChild(el(`
      <article class="note-item">
        <strong>${item.day} — ${item.focus}</strong>
        <p>${item.deliverable}</p>
      </article>
    `));
  });
}

/* ─── KEYWORDS TAB ─── */

function renderBank(bank, trending) {
  ['unpre', 'untab', 'skewese'].forEach(site => {
    const root = $(`bank-${site}`);
    if (!root) return;
    const sb = bank[site] || {};
    const pending = sb.pending || [];
    const used = sb.used || [];
    root.innerHTML = `
      <div class="bank-section">
        <div class="bank-title">Pending (${pending.length})</div>
        ${pending.map(kw => `<div class="bank-item">${kw}</div>`).join('')}
      </div>
      <div class="bank-section">
        <div class="bank-title">Used (${used.length})</div>
        ${used.slice(-5).reverse().map(kw => `<div class="bank-item used">${kw}</div>`).join('')}
      </div>
    `;
  });

  // YT shorts pool
  const ytRoot = $('yt-topic-pools');
  if (ytRoot && bank.yt_shorts) {
    ytRoot.innerHTML = Object.entries(bank.yt_shorts).map(([ch, topics]) => `
      <div class="bank-section">
        <div class="bank-title">${ch} (${topics.length})</div>
        ${topics.map(t => `<div class="bank-item">${t}</div>`).join('')}
      </div>
    `).join('');
  }

  // Seasonal
  const seasonRoot = $('seasonal-keywords');
  if (seasonRoot && trending) {
    seasonRoot.innerHTML = '';
    (trending.seasonal || []).forEach(kw => {
      seasonRoot.appendChild(el(`<span class="tag">${kw}</span>`));
    });
  }
}

/* ─── OFFERS TAB ─── */

function renderOffers(offers, links) {
  const root = $('offer-status');
  if (!root) return;

  let rows = '';
  const wpLinks = links?.wp_links || {};

  Object.entries(offers?.wp_offers || {}).forEach(([siteId, site]) => {
    const siteLinks = wpLinks[siteId] || {};
    ['primary_offer', 'secondary_offer', 'lead_magnet', 'service_offer'].forEach(key => {
      const offer = site[key];
      if (!offer) return;
      // find matching link
      const typeMap = { coupang_affiliate: '[COUPANG_LINK]', linkprice_affiliate: '[LINKPRICE_LINK]', affiliate: '[AFFILIATE_LINK]', lead_capture: '[LEAD_FORM_LINK]', service_inquiry: '[SERVICE_LINK]' };
      const placeholder = typeMap[offer.type] || '';
      const url = siteLinks[placeholder] || '';
      const isOk = url && !url.startsWith('TODO');

      rows += `<tr>
        <td>${siteId}</td>
        <td>${offer.name}</td>
        <td>${offer.type}</td>
        <td>${offer.cta_action}</td>
        <td class="${isOk ? 'link-ok' : 'link-todo'}">${isOk ? 'OK' : 'TODO'}</td>
      </tr>`;
    });
  });

  root.innerHTML = `
    <table class="offer-table">
      <thead><tr><th>Site</th><th>Offer</th><th>Type</th><th>CTA</th><th>Link</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

function renderPaths(items) {
  const root = $('revenue-paths');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    root.appendChild(el(`
      <article class="path-item">
        <strong>${item.name}</strong>
        <p>${item.description}</p>
        <div class="status-pill ${S[item.status] || 'warn'}">${item.status_label}</div>
      </article>
    `));
  });
}

function renderFunnel(items) {
  const root = $('funnel');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    root.appendChild(el(`
      <article class="funnel-step">
        <h3>${item.step}</h3>
        <p>${item.detail}</p>
      </article>
    `));
  });
}

/* ─── LOGS TAB ─── */

function renderRules(items) {
  const root = $('rules');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => root.appendChild(el(`<li>${item}</li>`)));
}

function renderFocus(items) {
  const root = $('focus-grid');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    root.appendChild(el(`
      <article class="focus-item">
        <h3>${item.title}</h3>
        <p>${item.description}</p>
      </article>
    `));
  });
}

function renderMonthly(items) {
  const root = $('monthly-review');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    root.appendChild(el(`
      <article class="note-item">
        <strong>${item.bucket}</strong>
        <p>${item.detail}</p>
      </article>
    `));
  });
}

function renderPillars(items) {
  const root = $('pillars');
  if (!root) return;
  root.innerHTML = '';
  (items || []).forEach(item => {
    const tags = (item.series || []).map(t => `<span class="tag">${t}</span>`).join('');
    root.appendChild(el(`
      <article class="pillar-item">
        <h3>${item.name}</h3>
        <p>${item.description}</p>
        <div class="pillar-tags">${tags}</div>
      </article>
    `));
  });
}

/* ─── DRAFT SCANNER ─── */
// We can't list files via fetch, so we use a generated manifest
// For now, count from status.json active_work or use hardcoded scan

async function scanDrafts() {
  const d = await loadJSON('draft_manifest.json');
  return d || { pending: '?', reviewed: '?', revised: '?', rejected: '?', published: '?', failed: '?', publishedFiles: [] };
}

/* ─── MAIN RENDER LOOP ─── */

async function render() {
  try {
    const [status, routing, quota, trending, bank, offers, links, drafts, llm, featureUsage, performance, reportingStatus, fullFeaturePlan, dailyGoal, skillUsage] = await Promise.all([
      loadJSON('status.json'),
      loadJSON('routing.json'),
      loadJSON('yt_quota.json'),
      loadJSON('trending.json'),
      loadJSON('keyword_bank.json'),
      loadJSON('offers.json'),
      loadJSON('link_registry.json'),
      scanDrafts(),
      loadJSON('llm_status.json'),
      loadJSON('hermes_feature_usage.json'),
      loadJSON('performance_snapshot.json'),
      loadJSON('reporting_status.json'),
      loadJSON('hermes_full_feature_plan.json'),
      loadJSON('daily_goal_status.json'),
      loadJSON('hermes_skill_usage_status.json'),
    ]);

    if (!status) { setText('system-status', 'OFFLINE'); return; }

    // Header
    setText('dashboard-subtitle', status.subtitle);
    setText('last-updated', status.last_updated);
    const statusEl = $('system-status');
    if (statusEl) {
      statusEl.textContent = status.system_status;
      statusEl.style.color = `var(--${S[status.system_status] || 'warn'})`;
    }
    const statusCard = $('status-card');
    if (statusCard) statusCard.style.borderColor = `var(--${S[status.system_status] || 'warn'})`;

    // Overview
    renderStats(status, drafts);
    renderYtQuota(quota);
    renderOpsSnapshot(status, drafts, quota);
    renderDailyGoalStatus(dailyGoal || status.daily_goal_status);
    renderBottleneckBoard(status.bottleneck_board);
    renderDailySchedule(status.daily_schedule);
    renderHermesFeatureUsage(skillUsage || featureUsage || status.hermes_feature_usage);
    renderPerformanceSnapshot(performance || status.performance_snapshot);
    renderReportingStatus(reportingStatus || status.reporting_status);
    renderHermesFullFeaturePlan(fullFeaturePlan || status.hermes_full_feature_plan);
    renderTasks(status.active_work);
    renderRisks(status.risks);
    renderLlmStatus(llm);
    renderKpis(status.kpis);
    renderQueue(status.content_queue);
    renderTrends(trending);
    renderTrendSignals(trending);
    renderNotes(status.notes);

    // Pipeline
    renderPipeline(drafts);
    renderPublishBySite(drafts.publishedFiles || []);
    renderPublishByType(drafts.publishedFiles || []);
    renderRecentPublished(drafts.publishedFiles || []);

    // Channels
    renderChannels(routing);
    renderYtQuotaDetail(quota);
    renderCadence(status.weekly_cadence);

    // Keywords
    if (bank) renderBank(bank, trending);

    // Offers
    renderOffers(offers, links);
    renderPaths(status.revenue_paths);
    renderFunnel(status.funnel);

    // Logs
    renderRules(status.rules);
    renderFocus(status.focus_areas);
    renderMonthly(status.monthly_review);
    renderPillars(status.pillars);

  } catch (e) {
    console.error(e);
    setText('system-status', 'ERROR');
  }
}

render();
setInterval(render, 5000);
