(() => {
  const {
    $,
    showToast,
    setStatus,
    requestJson,
  } = window.NetChecker;

  const state = {
    config: null,
  };

  const targetsBody = $('#targetsBody');

  function createTargetRow(target = {}) {
    const template = $('#targetRowTemplate');
    const row = template.content.firstElementChild.cloneNode(true);
    row.querySelector('.target-enabled').checked = target.enabled !== false;
    row.querySelector('.target-name').value = target.name || '';
    row.querySelector('.target-url').value = target.url || '';
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
      };
    });

    if (!targets.length) throw new Error('至少需要一个测试目标');

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

  async function loadConfig() {
    setStatus('配置加载中...');
    const config = await requestJson('/api/config');
    renderConfig(config);
    setStatus('配置已加载');
  }

  async function saveConfig() {
    const config = collectConfig();
    const data = await requestJson('/api/config', {
      method: 'PUT',
      body: JSON.stringify(config),
    });
    renderConfig(data.config);
    setStatus('配置已保存');
    showToast('配置已保存，首页会使用新配置测试');
  }

  async function resetConfig() {
    if (!confirm('确定要恢复默认配置吗？当前页面配置会被覆盖。')) return;
    const data = await requestJson('/api/reset', { method: 'POST' });
    renderConfig(data.config);
    setStatus('已恢复默认配置');
    showToast('已恢复默认配置');
  }

  $('#addTargetBtn').addEventListener('click', () => {
    targetsBody.appendChild(createTargetRow({
      enabled: true,
      name: 'Custom',
      url: 'https://example.com/',
    }));
  });

  $('#saveBtn').addEventListener('click', async () => {
    try {
      await saveConfig();
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

  loadConfig().catch((error) => {
    setStatus('配置加载失败');
    showToast(error.message, 'error');
  });
})();
