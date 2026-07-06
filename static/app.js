const state = {
  config: null,
  autoTimer: null,
  running: false,
};

const $ = (selector) => document.querySelector(selector);
const targetsBody = $('#targetsBody');
const resultsBody = $('#resultsBody');

function showToast(message, type = 'info') {
  const old = document.querySelector('.toast');
  if (old) old.remove();

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);
  setTimeout(() => toast.remove(), 3600);
}

function setStatus(message) {
  $('#statusText').textContent = message;
}

function badge(status) {
  const normalized = String(status || '').toLowerCase();
  return `<span class="badge ${normalized}">${status || '-'}</span>`;
}

function formatTime(value) {
  if (!value) return '-';
  return `${value} ms`;
}

function formatDate(value) {
  if (!value) return '未运行';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function expectedToText(expected) {
  return Array.isArray(expected) ? expected.join(',') : String(expected || '');
}

function parseExpected(text) {
  const values = String(text || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => {
      const code = Number(item);
      if (!Number.isInteger(code) || code < 100 || code > 599) {
        throw new Error(`无效 HTTP 状态码：${item}`);
      }
      return code;
    });
  return [...new Set(values.length ? values : [200, 204, 301, 302, 401, 403])];
}

function createTargetRow(target = {}) {
  const template = $('#targetRowTemplate');
  const row = template.content.firstElementChild.cloneNode(true);
  row.querySelector('.target-enabled').checked = target.enabled !== false;
  row.querySelector('.target-name').value = target.name || '';
  row.querySelector('.target-url').value = target.url || '';
  row.querySelector('.target-expected').value = expectedToText(target.expected || [200]);
  row.querySelector('.delete-row').addEventListener('click', () => row.remove());
  return row;
}

function renderConfig(config) {
  state.config = config;
  $('#proxyEnabled').checked = !!config.proxy?.enabled;
  $('#proxyUrl').value = config.proxy?.url || '';
  $('#timeout').value = config.timeout || 10;
  $('#autoRefresh').value = config.autoRefresh || 0;

  targetsBody.innerHTML = '';
  (config.targets || []).forEach((target) => targetsBody.appendChild(createTargetRow(target)));
  setupAutoRefresh();
}

function collectConfig() {
  const targets = [...targetsBody.querySelectorAll('tr')].map((row, index) => {
    const url = row.querySelector('.target-url').value.trim();
    const name = row.querySelector('.target-name').value.trim() || `Target ${index + 1}`;
    if (!url) throw new Error(`第 ${index + 1} 行 URL 不能为空`);
    return {
      enabled: row.querySelector('.target-enabled').checked,
      name,
      url,
      expected: parseExpected(row.querySelector('.target-expected').value),
    };
  });

  if (!targets.length) throw new Error('至少需要一个检测目标');

  const timeout = Number($('#timeout').value || 10);
  const autoRefresh = Number($('#autoRefresh').value || 0);
  if (!Number.isInteger(timeout) || timeout < 1 || timeout > 120) {
    throw new Error('请求超时需要在 1 到 120 秒之间');
  }
  if (!Number.isInteger(autoRefresh) || autoRefresh < 0 || autoRefresh > 3600) {
    throw new Error('自动刷新需要在 0 到 3600 秒之间');
  }

  return {
    proxy: {
      enabled: $('#proxyEnabled').checked,
      url: $('#proxyUrl').value.trim(),
    },
    timeout,
    autoRefresh,
    targets,
  };
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || `请求失败：${response.status}`);
  }
  return data;
}

async function loadConfig() {
  setStatus('配置加载中...');
  const config = await requestJson('/api/config');
  renderConfig(config);
  setStatus('配置已加载');
}

async function saveConfig(silent = false) {
  const config = collectConfig();
  const data = await requestJson('/api/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  });
  renderConfig(data.config);
  setStatus('配置已保存');
  if (!silent) showToast('配置已保存');
  return data.config;
}

function setRunning(running) {
  state.running = running;
  $('#runBtn').disabled = running;
  $('#runBtn').textContent = running ? '检测中...' : '运行检测';
}

function renderSummary(summary = {}) {
  $('#sumTotal').textContent = summary.total ?? 0;
  $('#sumOk').textContent = summary.ok ?? 0;
  $('#sumWarn').textContent = summary.warn ?? 0;
  $('#sumFail').textContent = summary.fail ?? 0;
  $('#lastChecked').textContent = formatDate(summary.checkedAt);
  $('#durationText').textContent = summary.durationMs ? `总耗时 ${summary.durationMs} ms` : '';
}

function resultNote(item) {
  const parts = [];
  if (item.http?.error) parts.push(item.http.error);
  if (item.dns?.error) parts.push(`DNS: ${item.dns.error}`);
  if (item.http?.effectiveUrl && item.http.effectiveUrl !== item.url) {
    parts.push(`Final: ${item.http.effectiveUrl}`);
  }
  if (!parts.length) parts.push(item.url);
  return parts.join(' | ');
}

function renderResults(payload) {
  renderSummary(payload.summary);
  resultsBody.innerHTML = '';

  (payload.results || []).forEach((item) => {
    const row = document.createElement('tr');
    const dnsAddress = item.dns?.addresses?.length ? `<div class="note">${item.dns.addresses.join(', ')}</div>` : '';
    row.innerHTML = `
      <td><strong>${escapeHtml(item.name)}</strong><div class="url">${escapeHtml(item.host || item.url)}</div></td>
      <td>${badge(item.status)}</td>
      <td>${badge(item.dns?.status || '-')} ${dnsAddress}</td>
      <td>${badge(item.http?.status || '-')}</td>
      <td>${item.http?.code || '-'}</td>
      <td>${formatTime(item.http?.timeMs)}</td>
      <td>${escapeHtml(item.http?.remoteIp || '-')}</td>
      <td><div class="note">${escapeHtml(resultNote(item))}</div></td>
    `;
    resultsBody.appendChild(row);
  });

  $('#emptyResult').classList.toggle('hidden', (payload.results || []).length > 0);
  $('#resultWrap').classList.toggle('hidden', !(payload.results || []).length);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

async function runCheck() {
  if (state.running) return;
  setRunning(true);
  setStatus('检测中...');
  try {
    const config = collectConfig();
    const payload = await requestJson('/api/check', {
      method: 'POST',
      body: JSON.stringify(config),
    });
    renderResults(payload);
    setStatus('检测完成');
  } catch (error) {
    setStatus('检测失败');
    showToast(error.message, 'error');
  } finally {
    setRunning(false);
  }
}

async function resetConfig() {
  if (!confirm('确定要恢复默认配置吗？当前页面配置会被覆盖。')) return;
  const data = await requestJson('/api/reset', { method: 'POST' });
  renderConfig(data.config);
  renderSummary();
  resultsBody.innerHTML = '';
  $('#emptyResult').classList.remove('hidden');
  $('#resultWrap').classList.add('hidden');
  showToast('已恢复默认配置');
  setStatus('已恢复默认配置');
}

function setupAutoRefresh() {
  if (state.autoTimer) {
    clearInterval(state.autoTimer);
    state.autoTimer = null;
  }

  const seconds = Number($('#autoRefresh').value || 0);
  if (seconds > 0) {
    state.autoTimer = setInterval(() => {
      if (!state.running) runCheck();
    }, seconds * 1000);
  }
}

function bindEvents() {
  $('#addTargetBtn').addEventListener('click', () => {
    targetsBody.appendChild(createTargetRow({
      enabled: true,
      name: 'Custom',
      url: 'https://example.com/',
      expected: [200, 204, 301, 302],
    }));
  });

  $('#runBtn').addEventListener('click', runCheck);
  $('#saveBtn').addEventListener('click', async () => {
    try {
      await saveConfig();
      setupAutoRefresh();
    } catch (error) {
      showToast(error.message, 'error');
    }
  });
  $('#resetBtn').addEventListener('click', async () => {
    try {
      await resetConfig();
    } catch (error) {
      showToast(error.message, 'error');
    }
  });
  $('#autoRefresh').addEventListener('change', setupAutoRefresh);
}

bindEvents();
loadConfig().catch((error) => {
  setStatus('配置加载失败');
  showToast(error.message, 'error');
});
