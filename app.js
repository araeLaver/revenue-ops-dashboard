const statusClass = {
  healthy: 'ok',
  watch: 'warn',
  blocked: 'bad',
  done: 'ok',
};

function el(html) {
  const template = document.createElement('template');
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

function setText(id, value) {
  const node = document.getElementById(id);
  if (node) node.textContent = value ?? '-';
}

function renderFocus(items) {
  const root = document.getElementById('focus-grid');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="focus-item">
        <h3>${item.title}</h3>
        <p>${item.description}</p>
      </article>
    `));
  });
}

function renderKpis(items) {
  const root = document.getElementById('kpi-list');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="kpi-item">
        <div class="kpi-main">
          <strong>${item.value}</strong>
          <span>${item.label}</span>
        </div>
        <div class="kpi-side">${item.target}</div>
      </article>
    `));
  });
}

function renderPaths(items) {
  const root = document.getElementById('revenue-paths');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="path-item">
        <strong>${item.name}</strong>
        <p>${item.description}</p>
        <div class="status-pill ${statusClass[item.status] || 'warn'}">${item.status_label}</div>
      </article>
    `));
  });
}

function renderFunnel(items) {
  const root = document.getElementById('funnel');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="funnel-step">
        <h3>${item.step}</h3>
        <p>${item.detail}</p>
      </article>
    `));
  });
}

function renderPillars(items) {
  const root = document.getElementById('pillars');
  root.innerHTML = '';
  items.forEach(item => {
    const tags = item.series.map(tag => `<span class="tag">${tag}</span>`).join('');
    root.appendChild(el(`
      <article class="pillar-item">
        <h3>${item.name}</h3>
        <p>${item.description}</p>
        <div class="pillar-tags">${tags}</div>
      </article>
    `));
  });
}

function renderTasks(items) {
  const root = document.getElementById('active-work');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="task-item" data-status="${item.status}">
        <h3>${item.title}</h3>
        <p>${item.detail}</p>
        <div class="status-pill ${statusClass[item.status] || 'warn'}">${item.status_label}</div>
      </article>
    `));
  });
}

function renderRules(items) {
  const root = document.getElementById('rules');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`<li>${item}</li>`));
  });
}

function renderRisks(items) {
  const root = document.getElementById('risks');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="risk-item">
        <strong>${item.title}</strong>
        <p>${item.detail}</p>
        <div class="status-pill ${statusClass[item.status] || 'warn'}">${item.status_label}</div>
      </article>
    `));
  });
}

function renderNotes(items) {
  const root = document.getElementById('notes');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="note-item">
        <strong>${item.title}</strong>
        <p>${item.detail}</p>
      </article>
    `));
  });
}

function renderCadence(items) {
  const root = document.getElementById('weekly-cadence');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="note-item">
        <strong>${item.day} — ${item.focus}</strong>
        <p>${item.deliverable}</p>
      </article>
    `));
  });
}

function renderMonthly(items) {
  const root = document.getElementById('monthly-review');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="note-item">
        <strong>${item.bucket}</strong>
        <p>${item.detail}</p>
      </article>
    `));
  });
}

function renderQueue(items) {
  const root = document.getElementById('content-queue');
  root.innerHTML = '';
  items.forEach(item => {
    root.appendChild(el(`
      <article class="pillar-item">
        <h3>${item.name}</h3>
        <p>단계: ${item.stage}</p>
        <p>우선순위: ${item.priority}</p>
        <div class="status-pill ${statusClass[item.status] || 'warn'}">${item.next_action}</div>
      </article>
    `));
  });
}

async function loadStatus() {
  const res = await fetch(`data/status.json?t=${Date.now()}`);
  if (!res.ok) throw new Error(`Failed to load status: ${res.status}`);
  return res.json();
}

async function render() {
  try {
    const data = await loadStatus();
    setText('dashboard-title', data.title);
    setText('dashboard-subtitle', data.subtitle);
    setText('last-updated', data.last_updated);
    setText('system-status', data.system_status);
    setText('primary-goal', data.primary_goal);

    renderFocus(data.focus_areas || []);
    renderKpis(data.kpis || []);
    renderPaths(data.revenue_paths || []);
    renderFunnel(data.funnel || []);
    renderPillars(data.pillars || []);
    renderTasks(data.active_work || []);
    renderRules(data.rules || []);
    renderRisks(data.risks || []);
    renderCadence(data.weekly_cadence || []);
    renderMonthly(data.monthly_review || []);
    renderQueue(data.content_queue || []);
    renderNotes(data.notes || []);
  } catch (error) {
    console.error(error);
    setText('system-status', '데이터 로드 실패');
  }
}

render();
setInterval(render, 3000);
