# net-checker

一个带 Web 面板的代理访问测试工具，用来确认当前代理是否能访问 TMDB、Google、GitHub、Docker Hub，以及你自己添加的网页 URL，并展示访问耗时。

既可以直接在本机用 Python 运行，也可以放进 Docker 里测试容器内的代理访问情况。

适合这些场景：

- 本地快速确认代理能不能访问指定网页
- 容器设置了代理后，确认代理是否生效
- 对比不同目标的访问耗时
- 周期性测试几个常用站点或自定义服务
- 测试 `host.docker.internal` 代理端口是否能从容器访问

## 功能

- 首页展示代理访问测试结果和耗时
- 设置页启用/关闭代理，不需要重启服务
- 设置页修改默认测试目标
- 设置页添加、删除、启用、禁用自定义目标
- 支持自动刷新
- 配置持久化到 `CONFIG_PATH` 指定的 JSON 文件
- 后端统一使用 Python Web/API 实现

## 项目结构

```text
app.py                  # 启动入口
net_checker/env.py      # .env 和运行参数
net_checker/config.py   # 配置默认值、校验、读写
net_checker/checks.py   # curl 代理访问测试逻辑
net_checker/server.py   # API 路由和静态文件服务
static/index.html       # 首页测试结果
static/settings.html    # 设置页
static/common.js        # 前端通用工具
static/home.js          # 首页逻辑
static/settings.js      # 设置页逻辑
static/style.css        # 页面样式和主题
```

默认测试目标：

| 名称 | URL |
| --- | --- |
| TMDB | `https://api.themoviedb.org/3/configuration` |
| Google | `https://www.google.com/generate_204` |
| GitHub | `https://github.com/` |
| Docker Hub | `https://registry-1.docker.io/v2/` |

只要 curl 成功拿到 HTTP 响应，就表示代理访问链路是通的。`401`、`403` 这类状态码通常表示网站拒绝未授权请求，但仍说明代理已经访问到了对方服务。

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

首页只展示“开始测试”和测试结果。测试会使用设置页保存的代理和目标。测试完成后会在标题区显示本次总耗时；如果有失败目标，会出现醒目的“重新测试失败项”按钮。黑色 / 白色主题可以在设置页切换。

点击首页右上角“设置”进入：

```text
http://127.0.0.1:8080/settings.html
```

### 代理设置

在设置页的“测试设置”里：

1. 勾选“启用代理”
2. 填写代理地址
3. 点击“保存配置”

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

### 测试目标

每个目标包含：

- 启用：是否参与测试
- 名称：页面展示名称
- URL / 域名：可以写完整 URL，也可以只写域名

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

表示首页每 60 秒按保存的配置检测一次。

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
| 目标 | 测试目标名称和 URL |
| 结果 | 代理是否成功拿到 HTTP 响应 |
| 状态码 | 实际 HTTP 状态码；`401` / `403` 也表示已经访问到对方服务，只是被拒绝授权或禁止访问 |
| 耗时 | curl 本次测试总耗时，按秒显示。默认先用 HEAD 请求，不跟随跳转；HEAD 失败时再回退到 GET |
| 失败原因 | 仅失败时显示更易读的失败说明；成功时留空 |

状态含义：

- `OK`：curl 成功完成请求，并拿到 HTTP 响应，表示代理能访问到该目标
- `FAIL`：curl 执行失败，例如连接失败、TLS 握手失败、超时、代理不可用等；失败原因会用中文说明显示在结果表里

如果存在失败目标，首页会显示“重新测试失败项”按钮，只重新测试失败的目标，不重复测试已经成功的目标。

## 关于代理和 DNS

首页的判断以 curl 是否通过代理拿到第一个 HTTP 响应为准，不再用 DNS 结果决定成功或失败。测试会优先使用 HEAD 请求，不跟随跳转，只验证首个响应；如果 HEAD 执行失败，再自动回退到 GET 请求。

HTTP 请求使用 `curl`，如果页面启用了代理，会通过：

```bash
curl --proxy <proxy-url>
```

执行。

因此：

- HTTP 测试会走页面配置的代理
- 远端 IP 如果显示 `127.0.0.1` 或 `host.docker.internal`，通常表示 curl 连接到的是本机代理
- 如果你使用 `socks5h://`，curl 的域名解析会交给 SOCKS 代理端处理

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

`data/config.json` 是本地运行时配置，可能包含代理账号密码，默认不提交到 Git。仓库里提供了安全示例：

```text
data/config.example.json
```

删除 `data/config.json` 并重启服务，会按程序内置默认配置重新生成。

## 安全提醒

这个工具允许在页面输入任意 URL 和代理地址，本质上适合个人本机或可信内网使用。不要直接暴露到公网。默认 `.env` / `docker-compose.yml` 已经只监听 `127.0.0.1:8080`。
