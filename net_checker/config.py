import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse


DEFAULT_CONFIG = {
    "proxy": {
        "enabled": False,
        "url": "http://127.0.0.1:7890",
    },
    "timeout": 10,
    "autoRefresh": 0,
    "targets": [
        {
            "name": "TMDB",
            "url": "https://api.themoviedb.org",
            "enabled": True
        },
        {
            "name": "Google",
            "url": "https://www.google.com",
            "enabled": True
        },
        {
            "name": "GitHub",
            "url": "https://github.com/",
            "enabled": True
        },
        {
            "name": "DockerHub",
            "url": "https://hub.docker.com/",
            "enabled": True
        }
    ],
}


def clone_default_config():
    return json.loads(json.dumps(DEFAULT_CONFIG))


def normalize_url(value):
    url = str(value or "").strip()
    if not url:
        raise ValueError("URL 不能为空")
    if "://" not in url:
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("目标 URL 只支持 http/https")
    if not parsed.hostname:
        raise ValueError("目标 URL 缺少域名")
    return url


def normalize_proxy(proxy):
    proxy = proxy if isinstance(proxy, dict) else {}
    enabled = bool(proxy.get("enabled", False))
    url = str(proxy.get("url", "")).strip()
    if enabled:
        if not url:
            raise ValueError("启用代理时必须填写代理地址")
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https", "socks4", "socks4a", "socks5", "socks5h"}:
            raise ValueError("代理只支持 http/https/socks4/socks5")
        if not parsed.hostname:
            raise ValueError("代理地址缺少主机名")
    return {"enabled": enabled, "url": url}


def normalize_config(config):
    config = config if isinstance(config, dict) else {}
    proxy = normalize_proxy(config.get("proxy"))

    try:
        timeout = int(config.get("timeout", 10))
    except (TypeError, ValueError):
        timeout = 10
    timeout = min(max(timeout, 1), 120)

    try:
        auto_refresh = int(config.get("autoRefresh", 0) or 0)
    except (TypeError, ValueError):
        auto_refresh = 0
    auto_refresh = min(max(auto_refresh, 0), 3600)

    targets = []
    raw_targets = config.get("targets") if isinstance(config.get("targets"), list) else []
    if len(raw_targets) > 100:
        raise ValueError("目标数量不能超过 100 个")

    for index, target in enumerate(raw_targets, start=1):
        if not isinstance(target, dict):
            continue
        url = normalize_url(target.get("url"))
        parsed = urlparse(url)
        name = str(target.get("name") or parsed.hostname or f"Target {index}").strip()
        targets.append(
            {
                "name": name[:80],
                "url": url,
                "enabled": bool(target.get("enabled", True)),
            }
        )

    if not targets:
        targets = clone_default_config()["targets"]

    return {
        "proxy": proxy,
        "timeout": timeout,
        "autoRefresh": auto_refresh,
        "targets": targets,
    }


def ensure_config(config_path):
    config_path = Path(config_path)
    if config_path.exists():
        return
    config_path.parent.mkdir(parents=True, exist_ok=True)
    save_config(config_path, clone_default_config())


def load_config(config_path):
    config_path = Path(config_path)
    ensure_config(config_path)
    try:
        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return normalize_config(data)
    except Exception:
        return clone_default_config()


def save_config(config_path, config):
    config_path = Path(config_path)
    config = normalize_config(config)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="config.", suffix=".json", dir=str(config_path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(config, file, ensure_ascii=False, indent=2)
            file.write("\n")
        os.replace(tmp_name, config_path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return config
