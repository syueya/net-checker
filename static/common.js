(() => {
  function $(selector) {
    return document.querySelector(selector);
  }

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
    const statusText = $('#statusText');
    if (statusText) statusText.textContent = message;
  }

  function badge(status) {
    const normalized = String(status || '').toLowerCase();
    return `<span class="badge ${normalized}">${status || '-'}</span>`;
  }

  function formatTime(value) {
    if (value === null || value === undefined || value === '') return '-';
    return `${(Number(value) / 1000).toFixed(2)} s`;
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

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem('theme', theme);
    document.querySelectorAll('.theme-option').forEach((button) => {
      const active = button.dataset.themeChoice === theme;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
  }

  function initTheme() {
    const saved = localStorage.getItem('theme') || 'light';
    applyTheme(saved);
    document.querySelectorAll('.theme-option').forEach((button) => {
      button.addEventListener('click', () => {
        applyTheme(button.dataset.themeChoice || 'light');
      });
    });
  }

  window.NetChecker = {
    $,
    showToast,
    setStatus,
    badge,
    formatTime,
    requestJson,
    escapeHtml,
  };

  initTheme();
})();
