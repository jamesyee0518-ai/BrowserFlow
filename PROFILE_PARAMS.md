# Profile 参数详解

本文档详细介绍 CloakBrowser-Manager 中每个浏览器 Profile 的参数含义、作用及配置建议。

---

## 基础设置（Basic）

### name

- **类型**：字符串（必填）
- **说明**：Profile 的名称，用于在管理界面中识别和区分不同的配置文件
- **示例**：`Amazon Seller #1`、`Google Ads - US`、`Social Media - JP`
- **建议**：使用有意义的命名，包含用途和地区信息，方便管理多个账号

### platform

- **类型**：枚举，可选值 `windows` / `macos` / `linux`
- **默认值**：`windows`
- **说明**：伪装的操作系统平台。CloakBrowser 会根据此值生成匹配的浏览器指纹特征
- **作用**：
  - `windows`：模拟 Windows 浏览器，生成 Windows 特有的 GPU 渲染器字符串、字体列表等
  - `macos`：模拟 macOS 浏览器，在 macOS 主机上运行时会使用原生 Mac 指纹，避免跨平台不一致
  - `linux`：模拟 Linux 浏览器
- **建议**：大多数场景选择 `windows`（市场份额最大，最不容易引起怀疑）。如果在 macOS 主机上运行且需要高度一致性，选择 `macos`

### fingerprint_seed

- **类型**：整数（可选）
- **默认值**：自动随机生成（10000-99999）
- **说明**：指纹种子，是生成整个浏览器指纹身份的核心参数。不同的 seed 产生完全不同的指纹，相同的 seed 始终产生相同的指纹
- **作用**：seed 通过 CloakBrowser 的 C++ 源码补丁，确定性生成以下指纹信号：
  - Canvas 指纹（2D 绘图像素差异）
  - WebGL 指纹（3D 渲染器信息和渲染结果）
  - Audio 指纹（音频处理微小差异）
  - GPU 供应商和渲染器型号
  - 硬件并发数（CPU 线程数）
  - 设备内存大小
  - 屏幕分辨率
  - 字体列表
- **关键特性**：
  - **确定性**：相同 seed + 相同平台 = 完全相同的指纹，重启后指纹不变
  - **唯一性**：不同 seed = 完全不同的设备身份，平台无法关联
- **建议**：通常保持自动生成即可。如需在另一台机器上复现相同的指纹身份，手动指定相同的 seed 值

---

## 网络设置（Network）

### proxy

- **类型**：字符串（可选）
- **格式**：`http://user:pass@host:port` 或 `socks5://user:pass@host:port` 或 `host:port` 或 `host:port:user:pass`
- **默认值**：无（直连）
- **说明**：该 Profile 使用的代理服务器。每个 Profile 应使用不同地区的代理 IP，确保 IP 地址与指纹身份匹配
- **支持的协议**：
  - HTTP/HTTPS：`http://user:pass@proxy.example.com:8080`
  - SOCKS5：`socks5://user:pass@proxy.example.com:1080`
  - 简写格式：`192.168.1.1:8080:user:pass`（自动转换为标准格式）
- **建议**：
  - 每个账号使用独立的代理 IP，避免多账号共享同一 IP
  - 选择住宅代理（Residential Proxy）而非数据中心代理，更不容易被识别
  - 代理 IP 所在地区应与 timezone 和 locale 设置一致

### timezone

- **类型**：字符串（可选）
- **格式**：IANA 时区标识
- **默认值**：无（使用系统时区）
- **说明**：浏览器报告的时区。通过 `--fingerprint-timezone` 参数注入，在 Chromium 渲染进程层面设置，而非通过 CDP 模拟（CDP 模拟可被检测）
- **示例**：`America/New_York`、`Europe/London`、`Asia/Tokyo`、`Asia/Shanghai`
- **建议**：必须与代理 IP 所在地区一致。例如使用美国纽约的代理 IP，应设置 `America/New_York`。开启 GeoIP 可自动匹配

### locale

- **类型**：字符串（可选）
- **格式**：BCP 47 语言标签
- **默认值**：无（使用系统语言）
- **说明**：浏览器报告的语言/区域设置。通过 `--lang` 和 `--fingerprint-locale` 参数注入，影响 `navigator.language`、`Accept-Language` 请求头等
- **示例**：`en-US`（美式英语）、`zh-CN`（简体中文）、`ja-JP`（日语）、`en-GB`（英式英语）
- **建议**：必须与代理 IP 地区和 timezone 匹配。例如美国代理应使用 `en-US`，英国代理应使用 `en-GB`

### geoip

- **类型**：布尔值
- **默认值**：`false`
- **说明**：开启后自动根据代理 IP 的出口地址检测并设置 timezone 和 locale。首次使用时会下载约 70MB 的 GeoLite2-City 数据库
- **作用**：
  - 自动解析代理 IP 的出口地址
  - 自动设置匹配的 timezone 和 locale
  - 附带获取出口 IP 用于 WebRTC IP 伪装
  - 手动设置的 timezone/locale 优先级高于 GeoIP 自动检测结果
- **建议**：如果不确定代理 IP 的地理位置，开启此选项可自动匹配。如果已手动设置 timezone 和 locale，GeoIP 仍可用于 WebRTC IP 伪装

---

## 硬件设置（Hardware）

### screen_width / screen_height

- **类型**：整数
- **默认值**：`1920` / `1080`
- **说明**：模拟的屏幕分辨率。通过 `--fingerprint-screen-width` 和 `--fingerprint-screen-height` 参数注入，影响 `screen.width`、`screen.height`、`window.outerWidth`、`window.outerHeight` 等属性
- **预设选项**：
  - 1920 × 1080（Full HD）— 最常见
  - 2560 × 1440（QHD）
  - 1366 × 768（HD）— 笔记本常见
  - 1440 × 900
  - 1536 × 864
  - 1280 × 720（720p）
- **建议**：使用常见分辨率，避免过于特殊。1920×1080 是最安全的选择。浏览器视口高度会自动减去约 133px（Chrome UI 占用）

### hardware_concurrency

- **类型**：整数（可选）
- **默认值**：自动（由 fingerprint seed 生成）
- **说明**：模拟的 CPU 逻辑核心数，影响 `navigator.hardwareConcurrency` 的返回值
- **常见值**：4、8、12、16
- **建议**：通常保持自动即可（由 seed 确定性生成）。如需手动指定，选择常见值如 8 或 12

### gpu_vendor

- **类型**：字符串（可选）
- **默认值**：自动（由 fingerprint seed 生成）
- **说明**：模拟的 GPU 供应商，影响 WebGL 的 `UNMASKED_VENDOR_WEBGL` 返回值
- **预设选项**：
  - `Google Inc. (NVIDIA)` — NVIDIA 显卡
  - `Google Inc. (AMD)` — AMD 显卡
  - `Google Inc. (Intel)` — Intel 集成显卡
  - `Google Inc. (Apple)` — Apple 芯片
- **建议**：保持自动或使用预设。如果手动填写，确保与 platform 匹配（macOS 应使用 Apple GPU）

### gpu_renderer

- **类型**：字符串（可选）
- **默认值**：自动（由 fingerprint seed 生成）
- **说明**：模拟的 GPU 渲染器型号，影响 WebGL 的 `UNMASKED_RENDERER_WEBGL` 返回值
- **预设选项**：
  - NVIDIA GeForce RTX 3070 / RTX 4070
  - AMD Radeon RX 6800 XT
  - Intel UHD Graphics 770
  - Apple M3
- **建议**：保持自动或使用预设。gpu_vendor 和 gpu_renderer 必须配套使用（NVIDIA 供应商对应 NVIDIA 渲染器）

---

## 行为设置（Behavior）

### humanize

- **类型**：布尔值
- **默认值**：`false`
- **说明**：开启后为浏览器操作注入类人行为模式，使鼠标移动、键盘输入和滚动行为更像真人操作，而非机器脚本
- **作用**：
  - **鼠标**：曲线移动（非直线）、微弱抖动、偶尔过冲后修正、点击前有瞄准延迟
  - **键盘**：随机打字速度、偶尔停顿、2% 概率打错字后修正、Shift 键有按下/释放延迟
  - **滚动**：加速-匀速-减速曲线、偶尔过冲后回滚、滚动前有预移动延迟
- **建议**：如果通过 Playwright/Puppeteer 自动化操作浏览器，建议开启以降低被行为分析检测的风险。纯手动操作（通过 VNC）时无需开启

### human_preset

- **类型**：枚举，可选值 `default` / `careful`
- **默认值**：`default`
- **说明**：humanize 的预设模式，仅在 humanize 开启时生效
- **区别**：
  - `default`：正常人类速度，打字延迟 70ms±40ms，鼠标移动较快
  - `careful`：更慢更谨慎，打字延迟 100ms±50ms，鼠标移动更精确，操作间有额外空闲停顿
- **建议**：大多数场景使用 `default`。如果目标网站有严格的行为分析（如金融类网站），使用 `careful`

### headless

- **类型**：布尔值
- **默认值**：`false`
- **说明**：是否以无头模式运行浏览器。无头模式下浏览器没有可见窗口，仅通过 API 控制
- **作用**：
  - `false`（默认）：浏览器在 VNC 虚拟显示器上运行，可通过 noVNC 在网页中实时查看和操作
  - `true`：浏览器在后台运行，不显示窗口，节省资源但无法通过 VNC 查看
- **建议**：需要通过 VNC 查看和手动操作浏览器时保持 `false`。纯自动化脚本操作时可设为 `true` 节省资源

### clipboard_sync

- **类型**：布尔值
- **默认值**：`true`
- **说明**：是否在 VNC 查看器中默认启用剪贴板同步。开启后可在本地电脑和 VNC 浏览器之间复制粘贴文本
- **建议**：保持开启。如需禁止剪贴板数据泄露可关闭

### auto_launch

- **类型**：布尔值
- **默认值**：`false`
- **说明**：是否在 Docker 容器启动时自动启动此 Profile 的浏览器。适合需要 7×24 运行的长期任务
- **建议**：需要持续运行的 Profile（如长期监控、自动化任务）设为 `true`。临时使用的 Profile 保持 `false`

### color_scheme

- **类型**：枚举（可选），可选值 `light` / `dark` / `no-preference`
- **默认值**：无（系统默认，通常为 `light`）
- **说明**：浏览器报告的颜色方案偏好，影响 `prefers-color-scheme` 媒体查询和 CSS 样式
- **建议**：保持默认即可。如需模拟深色模式用户，选择 `dark`

### user_agent

- **类型**：字符串（可选）
- **默认值**：自动（由 CloakBrowser 二进制文件根据 platform 和版本生成）
- **说明**：自定义 User-Agent 字符串。覆盖浏览器默认的 UA
- **建议**：通常保持自动即可，CloakBrowser 会生成与伪装平台匹配的真实 UA。仅在需要模拟特定浏览器版本时手动设置

---

## 标签（Tags）

### tags

- **类型**：对象数组，每项包含 `tag`（标签名）和 `color`（颜色，可选）
- **说明**：为 Profile 添加分类标签，方便在管理界面中筛选和分组
- **示例**：
  - `{"tag": "电商", "color": "#6366f1"}`
  - `{"tag": "美国", "color": "#22c55e"}`
  - `{"tag": "生产环境", "color": "#ef4444"}`
- **建议**：按用途、地区、重要性等维度添加标签，便于管理大量 Profile

---

## 启动参数（Launch Args）

### launch_args

- **类型**：字符串数组
- **默认值**：`[]`（空数组）
- **说明**：自定义 Chromium 命令行参数，在启动浏览器时传递。用于高级配置和扩展加载
- **常用参数**：
  - `--load-extension=/data/extensions/ublock` — 加载 Chrome 扩展
  - `--disable-features=SomeFeature` — 禁用特定 Chrome 功能
  - `--disable-web-security` — 禁用同源策略（开发调试用）
  - `--window-size=1280,720` — 设置窗口大小
- **建议**：仅在明确需要时添加。错误的参数可能导致浏览器行为异常或指纹检测失败

---

## 备注（Notes）

### notes

- **类型**：字符串（可选）
- **说明**：关于此 Profile 的自由文本备注，仅用于管理目的，不影响浏览器行为
- **示例**：`此账号用于亚马逊美国站运营，代理 IP 为洛杉矶住宅代理，2024年1月创建`
- **建议**：记录账号用途、代理来源、创建时间等信息，方便团队协作和后续维护

---

## 只读字段（系统生成，不可编辑）

以下字段由系统自动管理，无需手动设置：

| 字段 | 说明 |
|------|------|
| `id` | Profile 的唯一标识符（UUID），创建时自动生成 |
| `user_data_dir` | 浏览器数据目录路径，存储 cookies、localStorage、缓存等，自动分配 |
| `created_at` | 创建时间（UTC ISO 格式） |
| `updated_at` | 最后更新时间（UTC ISO 格式） |
| `status` | 当前状态：`running`（运行中）或 `stopped`（已停止） |
| `vnc_ws_port` | VNC WebSocket 端口（运行时分配） |
| `cdp_url` | CDP 调试协议地址（运行时分配），用于 Playwright/Puppeteer 连接 |

---

## 参数关联与一致性建议

各参数之间存在逻辑关联，配置不一致可能被检测：

```
proxy（美国 IP）→ timezone（America/New_York）→ locale（en-US）→ platform（windows）
proxy（日本 IP）→ timezone（Asia/Tokyo）→ locale（ja-JP）→ platform（windows）
proxy（英国 IP）→ timezone（Europe/London）→ locale（en-GB）→ platform（windows）
```

**核心原则**：所有参数必须讲述一个一致的故事——如果 IP 在美国，时区、语言、GPU 型号都应该是美国用户常见的配置。开启 GeoIP 可以自动保证 timezone 和 locale 与代理 IP 一致。
