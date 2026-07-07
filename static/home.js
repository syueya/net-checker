(() => {
  const {
    $,
    showToast,
    setStatus,
    badge,
    formatTime,
    requestJson,
    escapeHtml,
  } = window.NetChecker;

  const state = {
    config: null,
    autoTimer: null,
    running: false,
    results: [],
  };

  const resultsBody = $('#resultsBody');
  const retryFailedBtn = $('#retryFailedBtn');

  function failedResults() {
    return state.results.filter((item) => item.status === 'FAIL');
  }

  function updateRetryButton() {
    const hasFailed = failedResults().length > 0;
    retryFailedBtn.classList.toggle('hidden', !hasFailed);
    retryFailedBtn.disabled = state.running || !hasFailed;
  }

  function setRunning(running, label = '开始测试') {
    state.running = running;
    $('#runBtn').disabled = running;
    $('#runBtn').textContent = running ? '测试中...' : '开始测试';
    retryFailedBtn.disabled = running || failedResults().length === 0;
    retryFailedBtn.textContent = running && label === '重新测试失败项' ? '重试中...' : '↻ 重试失败项';
  }

  function setFinishedStatus(message, durationMs) {
    setStatus(durationMs ? `${message}，用时 ${formatTime(durationMs)}` : message);
  }

  function resultKey(item) {
    return `${item.name}\n${item.url}`;
  }

  function codeBadge(code) {
    const value = Number(code || 0);
    if (!value) return '<span class="code-badge empty-code">-</span>';
    const group = `${Math.floor(value / 100)}xx`;
    return `<span class="code-badge code-${group}">${value}</span>`;
  }

  function mergeRetryResults(results) {
    const retryMap = new Map(results.map((item) => [resultKey(item), item]));
    state.results = state.results.map((item) => retryMap.get(resultKey(item)) || item);
  }

  function renderResults(results = state.results) {
    state.results = results;
    resultsBody.innerHTML = '';

    state.results.forEach((item) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td><strong>${escapeHtml(item.name)}</strong><div class="url">${escapeHtml(item.url)}</div></td>
        <td>${badge(item.status)}</td>
        <td>${codeBadge(item.http?.code)}</td>
        <td>${formatTime(item.http?.timing?.totalMs ?? item.http?.timeMs)}</td>
        <td><div class="note">${item.status === 'FAIL' ? escapeHtml(item.http?.error || '访问失败') : ''}</div></td>
      `;
      resultsBody.appendChild(row);
    });

    $('#emptyResult').classList.toggle('hidden', state.results.length > 0);
    $('#resultWrap').classList.toggle('hidden', state.results.length === 0);
    updateRetryButton();
  }

  async function runCheck() {
    if (state.running) return;
    setRunning(true);
    setStatus('测试中...');
    try {
      const payload = await requestJson('/api/check', { method: 'POST' });
      renderResults(payload.results || []);
      setFinishedStatus('测试完成', payload.summary?.durationMs);
    } catch (error) {
      setStatus('测试失败');
      showToast(error.message, 'error');
    } finally {
      setRunning(false);
      updateRetryButton();
    }
  }

  async function retryFailed() {
    if (state.running) return;
    const failed = failedResults();
    if (!failed.length) return;

    setRunning(true, '重新测试失败项');
    setStatus('正在重新测试失败项...');
    try {
      const payload = await requestJson('/api/check', {
        method: 'POST',
        body: JSON.stringify({
          proxy: state.config?.proxy,
          timeout: state.config?.timeout,
          autoRefresh: state.config?.autoRefresh,
          targets: failed.map((item) => ({
            name: item.name,
            url: item.url,
            enabled: true,
          })),
        }),
      });
      mergeRetryResults(payload.results || []);
      renderResults();
      setFinishedStatus('重试完成', payload.summary?.durationMs);
    } catch (error) {
      setStatus('重试失败');
      showToast(error.message, 'error');
    } finally {
      setRunning(false);
      updateRetryButton();
    }
  }

  function setupAutoRefresh() {
    if (state.autoTimer) {
      clearInterval(state.autoTimer);
      state.autoTimer = null;
    }

    const seconds = Number(state.config?.autoRefresh || 0);
    if (seconds > 0) {
      state.autoTimer = setInterval(() => {
        if (!state.running) runCheck();
      }, seconds * 1000);
      setStatus(`配置已加载，自动刷新 ${seconds} 秒`);
    } else {
      setStatus('配置已加载');
    }
  }

  async function loadConfig() {
    setStatus('配置加载中...');
    state.config = await requestJson('/api/config');
    setupAutoRefresh();
  }

  $('#runBtn').addEventListener('click', runCheck);
  retryFailedBtn.addEventListener('click', retryFailed);
  loadConfig().catch((error) => {
    setStatus('配置加载失败');
    showToast(error.message, 'error');
  });
})();
