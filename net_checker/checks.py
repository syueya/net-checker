import os
import subprocess
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .config import normalize_config


CURL_META_MARKER = "CURL_META_START"
CURL_WRITE_OUT = (
    f"{CURL_META_MARKER}\n"
    "%{http_code}\n"
    "%{time_connect}\n"
    "%{time_appconnect}\n"
    "%{time_starttransfer}\n"
    "%{time_total}\n"
    "%{remote_ip}\n"
    "%{url_effective}\n"
)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def to_ms(seconds):
    return round(seconds * 1000)


def empty_timing(total_ms=0):
    return {"connectMs": 0, "tlsMs": 0, "firstByteMs": 0, "totalMs": total_ms}


def parse_curl_meta(stdout):
    lines = stdout.splitlines()
    if CURL_META_MARKER in lines:
        lines = lines[lines.index(CURL_META_MARKER) + 1 :]
    return {
        "httpCode": int(lines[0]) if len(lines) > 0 and lines[0].isdigit() else 0,
        "timeConnect": float(lines[1]) if len(lines) > 1 and lines[1] else 0.0,
        "timeAppConnect": float(lines[2]) if len(lines) > 2 and lines[2] else 0.0,
        "timeStartTransfer": float(lines[3]) if len(lines) > 3 and lines[3] else 0.0,
        "timeTotal": float(lines[4]) if len(lines) > 4 and lines[4] else 0.0,
        "remoteIp": lines[5] if len(lines) > 5 else "",
        "effectiveUrl": lines[6] if len(lines) > 6 else "",
    }


def human_curl_error(returncode, error, timeout):
    messages = {
        5: "代理解析失败：无法解析代理地址",
        6: "域名解析失败：无法解析目标网站地址",
        7: "连接失败：无法连接到目标网站或代理服务",
        23: "本地写入失败：curl 无法写入响应内容",
        28: f"访问超时：{timeout} 秒内没有完成连接或响应",
        35: "TLS 握手失败：HTTPS 连接没有建立成功",
        52: "访问失败：目标没有返回有效响应",
        55: "发送请求失败：连接中断",
        56: "接收响应失败：连接中断",
        60: "证书校验失败：HTTPS 证书不被信任",
    }
    message = messages.get(returncode)
    if message:
        return message
    return error or f"curl 执行失败，退出码 {returncode}"


def make_curl_command(url, timeout, proxy, head=False, output_path=None):
    command = ["curl", "-sS"]
    if head:
        command.append("-I")
    elif output_path:
        command.extend(["-o", output_path])

    command.extend(["--connect-timeout", str(timeout), "--max-time", str(timeout), "-w", CURL_WRITE_OUT])

    if proxy.get("enabled") and proxy.get("url"):
        command.extend(["--proxy", proxy["url"]])

    command.append(url)
    return command


def run_curl(url, timeout, proxy, head=False):
    body_path = None
    if not head:
        body_fd, body_path = tempfile.mkstemp(prefix="net-checker-curl-", suffix=".body")
        os.close(body_fd)

    command = make_curl_command(url, timeout, proxy, head=head, output_path=body_path)
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
        total_ms = to_ms(time.perf_counter() - started)
        return {
            "returncode": 28,
            "code": 0,
            "timeMs": total_ms,
            "timing": empty_timing(total_ms),
            "remoteIp": "",
            "effectiveUrl": url,
            "error": f"访问超时：{timeout} 秒内没有完成连接或响应",
        }
    except FileNotFoundError:
        return {
            "returncode": 127,
            "code": 0,
            "timeMs": 0,
            "timing": empty_timing(),
            "remoteIp": "",
            "effectiveUrl": url,
            "error": "容器内未找到 curl",
        }
    finally:
        if body_path:
            try:
                os.unlink(body_path)
            except OSError:
                pass

    meta = parse_curl_meta(completed.stdout)
    total_ms = to_ms(meta["timeTotal"] or (time.perf_counter() - started))
    return {
        "returncode": completed.returncode,
        "code": meta["httpCode"],
        "timeMs": total_ms,
        "timing": {
            "connectMs": to_ms(meta["timeConnect"]),
            "tlsMs": to_ms(meta["timeAppConnect"]),
            "firstByteMs": to_ms(meta["timeStartTransfer"]),
            "totalMs": total_ms,
        },
        "remoteIp": meta["remoteIp"],
        "effectiveUrl": meta["effectiveUrl"] or url,
        "error": completed.stderr.strip().replace("\n", " "),
    }


def http_check(url, timeout, proxy):
    result = run_curl(url, timeout, proxy, head=True)
    if result["returncode"] != 0:
        result = run_curl(url, timeout, proxy, head=False)

    reached = result["returncode"] == 0 and result["code"] > 0
    return {
        "ok": reached,
        "status": "OK" if reached else "FAIL",
        "code": result["code"],
        "timeMs": result["timeMs"],
        "timing": result["timing"],
        "remoteIp": result["remoteIp"],
        "effectiveUrl": result["effectiveUrl"],
        "error": "" if reached else human_curl_error(result["returncode"], result["error"], timeout),
    }


def check_target(target, timeout, proxy):
    http = http_check(target["url"], timeout, proxy)
    return {
        "name": target["name"],
        "url": target["url"],
        "http": http,
        "status": http["status"],
        "checkedAt": now_iso(),
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
        "fail": sum(1 for item in results if item["status"] == "FAIL"),
        "durationMs": to_ms(time.perf_counter() - started),
        "checkedAt": now_iso(),
    }
    return {"summary": summary, "results": results}
