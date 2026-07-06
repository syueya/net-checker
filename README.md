# net-checker

一个带 Web 面板的网络连通性检测工具，用来确认当前运行环境是否能访问 TMDB、Google、GitHub、Docker Hub，以及你自己添加的域名或 URL。

既可以直接在本机用 Python 运行，也可以放进 Docker 里检测容器网络。

适合这些场景：

- 本地快速确认代理、DNS、HTTP 访问是否正常
- 容器设置了代理后，确认代理是否生效
- 排查 Docker 容器内 DNS / HTTP 访问问题
- 周期性监测几个常用站点或自定义服务
- 测试 `host.docker.internal` 代理端口是否能从容器访问

## 功能

- Web 页面展示检测结果
- 页面上启用/关闭代理，不需要重启服务
- 页面上修改默认检测目标
- 页面上添加、删除、启用、禁用自定义目标
- 支持自定义期望 HTTP 状态码
- 支持自动刷新
- 配置持久化到 `CONFIG_PATH` 指定的 JSON 文件
- 后端统一使用 Python Web/API 实现

## 项目结构

```text
app.py                # 启动入口
net_checker/env.py    # .env 和运行参数
net_checker/config.py # 配置默认值、校验、读写
net_checker/checks.py # DNS / HTTP 检测逻辑
net_checker/server.py # API 路由和静态文件服务
static/               # 前端页面
```

默认检测目标：

| 名称 | URL | 视为正常的状态码 |
| --- | --- | --- |
| TMDB | `https://api.themoviedb.org/3/configuration` | `200,401` |
| Google | `https://www.google.com/generate_204` | `204` |
| GitHub | `https://github.com/` | `200,301,302` |
| Docker Hub | `https://registry-1.docker.io/v2/` | `200,401` |

> TMDB 和 Docker Hub 在没有凭据时返回 `401` 是正常的，说明网络已经连通。

## 环境配置

项目根目录提供 `.env`，本地 Python 和 Docker Compose 都会使用它作为默认配置。

默认内容类似：

```env
# Local Python defaults
HOST=127.0.0.1
PORT=8080
CONFIG_PATH=./data/config.json

# Docker Compose defaults
DOCKER_BIND_HOST=127.0.0.1
DOCKER_DATA_DIR=./data
DOCKER_CONFIG_PATH=/data/config.json
```

变量说明：

| 变量 | 用途 | 默认值 |
| --- | --- | --- |
| `HOST` | 本地 Python 运行时监听地址 | `127.0.0.1` |
| `PORT` | Web 服务端口，本地和 Docker Compose 共用 | `8080` |
| `CONFIG_PATH` | 本地 Python 运行时的配置文件路径 | `./data/config.json` |
| `DOCKER_BIND_HOST` | Docker 发布到宿主机的监听地址 | `127.0.0.1` |
| `DOCKER_DATA_DIR` | 宿主机数据目录 | `./data` |
| `DOCKER_CONFIG_PATH` | 容器内配置文件路径 | `/data/config.json` |

### `HOST`、`DOCKER_BIND_HOST` 和容器内监听地址

这几个地址控制的是不同层级：

- `HOST` 是程序进程自己的监听地址。本地直接运行 `python app.py` 时，它默认是 `127.0.0.1`，表示只允许本机访问。
- Docker Compose 运行时，容器里的程序必须监听 `0.0.0.0`，否则它只会监听容器自己的 loopback 地址，Docker 的端口映射可能无法从宿主机转发进来。因此 compose 里会固定传入 `HOST=0.0.0.0`，这个值属于容器内部实现，不再单独暴露成 `.env` 变量。
- `DOCKER_BIND_HOST` 控制的是 Docker 把端口发布到宿主机的哪个地址。默认 `127.0.0.1` 只允许宿主机自己访问；改成 `0.0.0.0` 才会绑定到宿主机所有网卡，让局域网里的其他设备也可能访问到。

所以，容器内的 `HOST=0.0.0.0` 不等于把服务暴露到公网。真正决定外部能不能访问的是 `ports` 里的宿主机绑定地址，也就是 `DOCKER_BIND_HOST`。

Python 后端启动时会自动读取项目根目录的 `.env`。如果系统环境变量里已经设置了同名变量，则系统环境变量优先，不会被 `.env` 覆盖。

## 启动

### 本地 Python

本地直接运行时，检测的是宿主机自己的网络环境。

```bash
cd net-checker
python app.py
```

然后打开：

```text
http://127.0.0.1:8080
```

如果你要测试本机代理，页面里的代理地址通常填写：

```text
http://127.0.0.1:7890
```

或：

```text
socks5h://127.0.0.1:7890
```

### docker compose

Docker 运行时，检测的是容器内的网络环境。

```bash
cd net-checker
docker compose up --build -d
```

然后打开：

```text
http://127.0.0.1:8080
```

默认 compose 只绑定本机：

```yaml
ports:
  - "${DOCKER_BIND_HOST:-127.0.0.1}:${PORT:-8080}:${PORT:-8080}"
```

这个端口映射可以拆成：

```text
宿主机监听地址:宿主机端口:容器内端口
```

默认值等价于：

```text
127.0.0.1:8080:8080
```

也就是只有宿主机自己能通过 `http://127.0.0.1:8080` 访问。容器内部的服务虽然监听 `0.0.0.0:8080`，但外部访问范围仍然由宿主机这一侧的 `127.0.0.1` 限制，所以不会直接把这个可以请求任意 URL 的工具暴露到局域网或公网。

如果需要改端口，可以修改 `.env`：

```env
PORT=18080
```

如果确实要让局域网访问，可以修改：

```env
DOCKER_BIND_HOST=0.0.0.0
```

但不建议暴露到公网。

### docker run

不用 compose 时，也可以手动传入环境变量：

```bash
docker build -t net-checker .

docker run -d --name net-checker \
  --env-file .env \
  -e HOST=0.0.0.0 \
  -e CONFIG_PATH=/data/config.json \
  -p 127.0.0.1:8080:8080 \
  -v "$PWD/data:/data" \
  net-checker
```

访问：

```text
http://127.0.0.1:8080
```

## 页面使用

### 代理设置

在页面的“检测设置”里：

1. 勾选“启用代理”
2. 填写代理地址

本地 Python 运行时，如果代理在本机，通常使用：

```text
http://127.0.0.1:7890
```

Docker 运行时，Windows / macOS Docker Desktop 通常可以用：

```text
http://host.docker.internal:7890
```

也支持 curl 支持的代理协议，例如：

```text
socks5://host.docker.internal:7890
socks5h://host.docker.internal:7890
http://user:password@host.docker.internal:7890
```

Linux 下可按实际情况使用：

- 宿主机网关 IP
- `--network host`
- Docker Compose 的 `extra_hosts` 配置

### 检测目标

每个目标包含：

- 启用：是否参与检测
- 名称：页面展示名称
- URL / 域名：可以写完整 URL，也可以只写域名
- 期望状态码：逗号分隔，例如 `200,204,301,302,401`

如果只写域名：

```text
example.com
```

后端会自动按：

```text
https://example.com
```

处理。

### 自动刷新

“自动刷新”填 `0` 表示关闭。填大于 `0` 的数字表示按秒刷新，例如：

```text
60
```

表示每 60 秒检测一次。

## API 使用

除了 Web 页面，也可以直接调用 API 触发检测：

```bash
curl -X POST http://127.0.0.1:8080/api/check \
  -H 'Content-Type: application/json' \
  -d '{}'
```

查看当前配置：

```bash
curl http://127.0.0.1:8080/api/config
```

## 输出说明

结果表里会展示：

| 字段 | 说明 |
| --- | --- |
| 整体 | 综合 DNS 和 HTTP 的结果 |
| DNS | 当前运行环境的 DNS 解析是否成功 |
| HTTP | HTTP 请求是否成功且状态码是否符合预期 |
| 状态码 | 实际 HTTP 状态码 |
| 耗时 | HTTP 请求总耗时 |
| 远端 IP | curl 连接到的远端 IP |
| 说明 | 错误信息、跳转后的最终 URL 或原始 URL |

状态含义：

- `OK`：正常
- `WARN`：请求成功，但状态码不在预期列表内，或 HTTP 正常但 DNS 单独检测失败
- `FAIL`：请求失败，例如超时、连接失败、TLS 错误、代理不可用等

## 关于 DNS 和代理

DNS 检测使用当前运行环境自身的 DNS 解析能力：

- 本地 Python 运行时：使用宿主机 DNS
- Docker 运行时：使用容器内 DNS

HTTP 请求使用 `curl`，如果页面启用了代理，会通过：

```bash
curl --proxy <proxy-url>
```

执行。

因此：

- DNS 检测不走 HTTP 代理
- HTTP 检测会走页面配置的代理
- 如果你使用 `socks5h://`，curl 的域名解析会交给 SOCKS 代理端处理，但页面里的独立 DNS 检测仍然显示当前运行环境的 DNS 状态

## 配置文件

配置保存在 `CONFIG_PATH` 指定的位置。

本地 Python 默认：

```text
./data/config.json
```

Docker Compose 默认映射为：

```text
宿主机：./data/config.json
容器内：/data/config.json
```

删除这个文件并重启服务，会重新生成默认配置。

## 安全提醒

这个工具允许在页面输入任意 URL 和代理地址，本质上适合个人本机或可信内网使用。不要直接暴露到公网。默认 `.env` / `docker-compose.yml` 已经只监听 `127.0.0.1:8080`。
