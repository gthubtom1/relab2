# 流量抓包与代理逆向手册 (Traffic & Proxy Manual)

> 本文档记录本机专有抓包代理、根证书路径、中间人脚本及 SSL Pinning 绕过流水线。
> 当任务涉及 HTTP/HTTPS/WebSocket 抓包、API 动态签名还原、移动端/客户端加解密时按需查阅。

## 1. 中间人代理工具链 (Mitmproxy)
- **监听端点**: `127.0.0.1:8080`
- **根证书安装路径**（在当前用户目录下，随用户而变，**不要写死用户名**）:
  - Windows/Android 导入证书: `%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.cer`（POSIX：`~/.mitmproxy/mitmproxy-ca-cert.cer`）
  - PKCS#12 浏览器证书包: `%USERPROFILE%\.mitmproxy\mitmproxy-ca-cert.p12`
  - 没生成过就先起一次 `mitmproxy`（`mitmdump`/`mitmweb` 首次运行自动签发），再回上一级目录找。
- **无头命令行启动**:
  `mitmdump -p 8080 -s <addon_script.py>`
- **Web UI 抓包审查**:
  `mitmweb -p 8080 --web-port 8081`

## 2. 报文抓包与备用工具
> 下面三个都**不写死路径**，先探测：`(Get-Command <id> -ErrorAction SilentlyContinue).Source` → 无值再按候选目录逐个 `Test-Path`（id = `wireshark` / `tshark` / `Fiddler`）。

- **Wireshark**: `resolve wireshark` → `path`（便携版可能在 `…\WiresharkPortable64\App\Wireshark\Wireshark.exe`）
- **TShark 命令行抓包**: `resolve tshark` → `path`（便携版 tshark 与 Wireshark.exe 常不在同一目录，各查各的）
  - 快速过滤模板: `tshark.exe -i 1 -Y "http.request || websocket" -T fields -e http.host -e http.request.uri`
- **Fiddler Classic**: `resolve Fiddler` → 取 `path` **所在目录**下的 `Fiddler.exe`（监听 `127.0.0.1:8888`）。
  注册表可能把 `uninst.exe` 当作锚点绑定，`path` 字段指向它时不要直接去跑那个文件。
- **任一 resolve 返回 `path: None`** = 本机没装/没探到，明确报缺口，不要编一个盘符路径凑数。

## 3. mitmproxy Addon 动态拦截模板
```python
from mitmproxy import http

class Interceptor:
    def request(self, flow: http.HTTPFlow) -> None:
        if "target-domain.com" in flow.request.pretty_url:
            # 读取或修改参数并重算签名
            pass

    def response(self, flow: http.HTTPFlow) -> None:
        if "target-domain.com" in flow.request.pretty_url:
            # 捕获加密响应并输出
            pass

addons = [Interceptor()]
```

## 4. 客户端 SSL Pinning 突破 (Frida 方案)
- 检测机制: 客户端握手失败、网络中断但代理无报错时，自动判定为证书绑定 (SSL Pinning)。
- Frida 启动命令:
  `frida -U -f <package_name> -l ssl_unpinning.js --no-pause`
