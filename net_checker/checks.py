import socket
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from .config import normalize_config


def dns_check(host):
    started = time.perf_counter()
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
        addresses = []
        for info in infos:
            address = info[4][0]
            if address not in addresses:
                addresses.append(address)
        return {
            "ok": True,
            "status": "OK",
            "addresses": addresses[:6],
            "timeMs": round((time.perf_counter() - started) * 1000),
            "error": "",
        }
    except Exception as exc:
        return {
            "ok": False,
            "status": "FAIL",
            "addresses": [],
            "timeMs": round((time.perf_counter() - started) * 1000),
            "error": str(exc),
        }


def parse_curl_meta(stdout):
    lines = stdout.splitlines()
    if "CURL_META_START" in lines:
        start = lines.index("CURL_META_START") + 1
        lines = lines[start:]
    return {
        "httpCode": int(lines[0]) if len(lines) > 0 and lines[0].isdigit() else 0,
        "timeTotal": float(lines[1]) if len(lines) > 1 and lines[1] else 0.0,
        "remoteIp": lines[2] if len(lines) > 2 else "",
        "effectiveUrl": lines[3] if len(lines) > 3 else "",
    }


def http_check(url, expected, timeout, proxy):
    command = [
        "curl",
        "-L",
        "-sS",
        "-o",
        "/dev/null",
        "--connect-timeout",
        str(timeout),
        "--max-time",
        str(timeout),
        "-w",
        "CURL_META_START\n%{http_code}\n%{time_total}\n%{remote_ip}\n%{url_effective}\n",
    ]

    if proxy.get("enabled") and proxy.get("url"):
        command.extend(["--proxy", proxy["url"]])

    command.append(url)

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout + 3,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "status": "FAIL",
            "code": 0,
            "timeMs": round((time.perf_counter() - started) * 1000),
            "remoteIp": "",
            "effectiveUrl": url,
            "error": "curl 执行超时",
        }
    except FileNotFoundError:
        return {
            "ok": False,
            "status": "FAIL",
            "code": 0,
            "timeMs": 0,
            "remoteIp": "",
            "effectiveUrl": url,
            "error": "容器内未找到 curl",
        }

    meta = parse_curl_meta(completed.stdout)
    code = meta["httpCode"]
    error = completed.stderr.strip().replace("\n", " ")

    if completed.returncode != 0:
        return {
            "ok": False,
            "status": "FAIL",
            "code": code,
            "timeMs": round((meta["timeTotal"] or (time.perf_counter() - started)) * 1000),
            "remoteIp": meta["remoteIp"],
            "effectiveUrl": meta["effectiveUrl"] or url,
            "error": error or f"curl exit {completed.returncode}",
        }

    matched = code in expected
    return {
        "ok": matched,
        "status": "OK" if matched else "WARN",
        "code": code,
        "timeMs": round(meta["timeTotal"] * 1000),
        "remoteIp": meta["remoteIp"],
        "effectiveUrl": meta["effectiveUrl"] or url,
        "error": "" if matched else f"状态码不在预期列表：{','.join(map(str, expected))}",
    }


def check_target(target, timeout, proxy):
    url = target["url"]
    parsed = urlparse(url)
    host = parsed.hostname or ""
    dns = dns_check(host)
    http = http_check(url, target["expected"], timeout, proxy)
    overall = "OK" if dns["ok"] and http["status"] == "OK" else http["status"]
    if not dns["ok"] and http["status"] == "OK":
        overall = "WARN"
    if http["status"] == "FAIL":
        overall = "FAIL"

    return {
        "name": target["name"],
        "url": url,
        "expected": target["expected"],
        "host": host,
        "dns": dns,
        "http": http,
        "status": overall,
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def run_checks(config):
    config = normalize_config(config)
    enabled_targets = [target for target in config["targets"] if target.get("enabled")]
    results = []
    started = time.perf_counter()

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(enabled_targets)))) as executor:
        future_map = {
            executor.submit(check_target, target, config["timeout"], config["proxy"]): target
            for target in enabled_targets
        }
        for future in as_completed(future_map):
            results.append(future.result())

    name_order = {target["name"] + target["url"]: index for index, target in enumerate(enabled_targets)}
    results.sort(key=lambda item: name_order.get(item["name"] + item["url"], 9999))

    summary = {
        "total": len(results),
        "ok": sum(1 for item in results if item["status"] == "OK"),
        "warn": sum(1 for item in results if item["status"] == "WARN"),
        "fail": sum(1 for item in results if item["status"] == "FAIL"),
        "durationMs": round((time.perf_counter() - started) * 1000),
        "checkedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    return {"summary": summary, "results": results}
