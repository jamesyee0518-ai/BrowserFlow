# CloakBrowser Detection Test 使用说明

## 一、概述

CloakBrowser Detection Test 是一个浏览器指纹检测与隐身验证工具，部署在云服务器上后，可用于检验 CloakBrowser 的反检测效果。支持批量记录多个 Profile 的测试结果并横向对比。

---

## 二、部署

### 方式一：Python 启动（推荐）

1. 将 `detection-test/` 文件夹上传到 Windows Server
2. 双击 `start.bat`
3. 访问 `http://服务器IP:8088`

### 方式二：IIS 部署

1. 右键 `install_iis.bat` → 以管理员身份运行
2. 访问 `http://服务器IP:8088`

### 端口说明

| 页面 | 地址 |
|------|------|
| 检测页面 | `http://服务器IP:8088` |
| 结果对比 | `http://服务器IP:8088/results.html` |
| API 接口 | `http://服务器IP:8088/api/results` |

---

## 三、检测项目说明

### 3.1 自动化检测（🤖）

| 检测项 | 说明 | CloakBrowser 应对 |
|--------|------|-------------------|
| navigator.webdriver | 检测浏览器是否标记为自动化工具 | 返回 undefined（通过） |
| CDP Debug Port | 检测 Chrome DevTools Protocol 调试端口是否暴露 | 端口不对外暴露（通过） |
| Automation Frameworks | 检测 ChromeDriver、Selenium、Playwright、Puppeteer 等框架注入的全局变量 | 无这些变量（通过） |
| window.chrome | 检测 Chrome 特有对象是否存在 | 正常存在（通过） |
| chrome.runtime | 缺失可能表示无头模式 | 正常存在（通过） |
| Notification Permission | 无头 Chrome 会自动拒绝通知权限 | 正常行为（通过） |

### 3.2 Canvas 指纹（🎨）

| 检测项 | 说明 |
|--------|------|
| Canvas Hash | 通过 2D Canvas 绘制图形和文字，生成唯一哈希值。不同设备/驱动的渲染结果微小差异构成指纹 |

CloakBrowser 通过 `--fingerprint=seed` 参数修改 Canvas 渲染结果，不同 seed 产生不同哈希。

### 3.3 WebGL 指纹（🖥️）

| 检测项 | 说明 | 风险判定 |
|--------|------|----------|
| GPU Vendor | GPU 供应商名称 | 显示 SwiftShader → 失败（无头模式标志） |
| GPU Renderer | GPU 渲染器型号 | 显示 SwiftShader/llvmpipe → 失败 |
| Rendering Mode | 硬件/软件渲染 | 软件渲染 → 失败 |
| Extensions Count | WebGL 扩展数量 | 信息参考 |

### 3.4 Audio 指纹（🔊）

| 检测项 | 说明 |
|--------|------|
| Audio Hash | 通过 AudioContext 处理音频信号生成哈希值 |
| Sample Rate | 音频采样率，通常为 44100Hz 或 48000Hz |

### 3.5 字体检测（🔤）

| 检测项 | 说明 |
|--------|------|
| Detected Fonts | 通过测量文字宽度差异枚举已安装字体 |
| CJK Fonts | 中日韩字体检测，影响地区判断 |

### 3.6 硬件信息（💻）

| 检测项 | 说明 |
|--------|------|
| Hardware Concurrency | CPU 逻辑核心数 |
| Device Memory | 设备内存大小 |
| Screen Resolution | 屏幕分辨率 |
| Pixel Ratio | 设备像素比 |
| Touch Support | 触控支持 |
| Network Type | 网络连接类型 |

### 3.7 网络身份（🌐）

| 检测项 | 说明 | 风险判定 |
|--------|------|----------|
| Timezone | 浏览器报告的时区 | 应与代理 IP 地区一致 |
| Language | 浏览器语言设置 | 应与代理 IP 地区匹配 |
| User Agent | 浏览器标识字符串 | 应与 platform 一致 |
| UA/Platform Consistency | UA 声称的操作系统与 navigator.platform 是否一致 | 不一致 → 失败 |
| WebRTC Local IPs | WebRTC 泄露的真实内网 IP | 泄露 → 警告 |

### 3.8 浏览器特性（🔍）

| 检测项 | 说明 |
|--------|------|
| Cookies Enabled | Cookie 是否可用 |
| Plugins Count | 浏览器插件数量，0 个可能表示无头模式 |
| Battery API | 电池信息，无头模式通常不可用 |
| Voices Count | 语音合成声音数量 |

### 3.9 存储检测（💾）

| 检测项 | 说明 |
|--------|------|
| localStorage | 本地存储是否可用 |
| sessionStorage | 会话存储是否可用 |
| IndexedDB | 索引数据库是否可用 |

### 3.10 高级检测（🔬）

| 检测项 | 说明 |
|--------|------|
| ClientRects Hash | 元素客户端矩形哈希，受字体渲染影响 |
| CSS Media Queries | 用户偏好设置（深色模式、减少动画等） |
| Error Stack Trace | 错误堆栈跟踪，可能暴露框架内部信息 |

### 3.11 CAPTCHA 验证码测试（🔐）

| 检测项 | 说明 | 判定逻辑 |
|--------|------|----------|
| reCAPTCHA v3 | 加载 Google reCAPTCHA v3 SDK 并获取 token | 成功获取 token → 通过 |
| hCaptcha | 加载 hCaptcha SDK | SDK 加载成功 → 通过 |
| Cloudflare Turnstile | 加载 Cloudflare Turnstile SDK | SDK 加载成功 → 通过 |

> **注意**：CAPTCHA 测试使用公开测试密钥，仅验证 SDK 是否能正常加载和执行。实际的验证评分（如 reCAPTCHA 的 0-1 分数）需要在服务端验证。如果浏览器指纹被识别为可疑，CAPTCHA 服务端可能会给出低分或弹出交互式验证。

### 3.12 人机交互测试（👤）

| 测试项 | 说明 | 判定逻辑 |
|--------|------|----------|
| 🧩 滑块验证 | 拖动滑块到随机目标位置（70%-85%） | 鼠标移动事件 > 5 且耗时 > 300ms → 人类行为 |
| 🔢 点击序列 | 按升序点击 1-9 九个数字 | 平均点击间隔 > 200ms 且总耗时 > 2s → 人类行为 |
| ⌨️ 打字测试 | 输入屏幕显示的随机英文单词 | 平均按键间隔 > 60ms 且方差 > 200 → 人类行为 |
| 🎯 拖拽匹配 | 将 3 个标签拖到对应目标位置 | 全部匹配 → 通过 |

---

## 四、评分体系

### 综合评分

```
评分 = 通过数 / (通过数 + 警告数 + 失败数) × 100
```

| 评分 | 等级 | 含义 |
|------|------|------|
| 90-100 | 🟢 优秀 | 隐身效果出色，大部分检测通过 |
| 70-89 | 🟡 良好 | 有少量信号暴露，但不影响大多数场景 |
| 50-69 | 🟠 一般 | 明显检测信号暴露，可能被高级反检测系统识别 |
| 0-49 | 🔴 较差 | 多个检测信号暴露，浏览器身份可被识别 |

### 关键指标

以下指标如果失败，几乎一定会被检测到：

- ❌ `navigator.webdriver = true` → 最直接的自动化标志
- ❌ GPU Renderer 显示 SwiftShader → 无头模式铁证
- ❌ UA/Platform 不一致 → 伪装配置错误
- ❌ WebRTC 泄露真实 IP → 代理失效

---

## 五、使用流程

### 步骤 1：建立基线

用普通 Chrome 浏览器打开检测页面，记录评分和各项结果作为基线参考。

### 步骤 2：逐个测试 CloakBrowser Profile

1. 打开 CloakBrowser-Manager 管理界面
2. 创建或选择一个 Profile
3. 启动该 Profile 的浏览器
4. 在浏览器中打开 `http://服务器IP:8088`
5. 等待自动检测完成
6. 完成人机交互测试（滑块、点击、打字、拖拽）
7. 在顶部输入 Profile 名称（如 `Profile-A (seed=12345)`）
8. 点击 **"提交结果"**

### 步骤 3：对比结果

1. 重复步骤 2 测试所有 Profile
2. 点击 **"查看对比"** 进入结果对比页面
3. 查看汇总表和指纹差异对比

### 指纹差异对比解读

对比页面中，多个 Profile 的关键指纹值并排展示：

- **灰色文字** = 所有 Profile 值相同（指纹未隔离，需关注）
- **黄色高亮** = Profile 之间值不同（指纹隔离有效）

**重点关注**：
- Canvas Hash — 不同 Profile 应该不同
- Audio Hash — 不同 Profile 应该不同
- GPU Renderer — 不同 Profile 应该不同
- Screen Resolution — 可以相同
- Timezone/Language — 取决于代理配置

---

## 六、常见问题

### Q: CAPTCHA 测试显示 "Script blocked"？

A: 说明浏览器或网络阻止了 CAPTCHA SDK 的加载。可能原因：
- 网络无法访问 Google/hCaptcha/Cloudflare 的 CDN
- 浏览器扩展（如广告拦截器）阻止了脚本加载
- 代理设置导致境外 CDN 无法访问

### Q: 人机交互测试判定为 "robotic"？

A: 说明操作节奏过于均匀和快速，被判定为机器行为。CloakBrowser 的 `humanize` 功能可以在自动化操作时模拟人类节奏。手动操作时，尝试放慢速度、增加停顿。

### Q: 多个 Profile 的 Canvas Hash 相同？

A: 如果 seed 不同但 Canvas Hash 相同，可能是：
- CloakBrowser 的指纹补丁未生效
- 浏览器缓存了旧的渲染结果
- 使用了相同的 seed

### Q: 评分很高但网站仍然能识别我？

A: 本检测工具覆盖了主要的指纹信号，但实际网站可能使用更复杂的检测技术（如 TLS 指纹、HTTP/2 指纹、鼠标轨迹分析等）。评分高说明基础隐身效果好，但不保证通过所有检测。

---

## 七、文件结构

```
detection-test/
├── server.py        Python 后端服务器（API + 静态文件）
├── index.html       检测页面（12 类检测 + CAPTCHA + 交互测试）
├── results.html     结果对比页面（汇总表 + 指纹差异 + 详情）
├── web.config       IIS 配置文件
├── start.bat        Python 一键启动脚本
└── install_iis.bat  IIS 自动部署脚本
```

### API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/results` | 获取所有测试结果 |
| POST | `/api/results` | 提交一条测试结果 |
| DELETE | `/api/results/:id` | 删除指定测试结果 |

### 提交数据格式

```json
{
  "profile_name": "Profile-A (seed=12345)",
  "score": 85,
  "summary": { "pass": 17, "warn": 2, "fail": 1 },
  "categories": [
    {
      "category": "Automation Detection",
      "items": [
        { "key": "navigator.webdriver", "val": "undefined", "cls": "pass" }
      ]
    }
  ],
  "captcha_results": {
    "recaptcha": { "status": "pass", "detail": "Token received" },
    "hcaptcha": { "status": "pass", "detail": "SDK loaded" },
    "turnstile": { "status": "warn", "detail": "Script blocked" }
  },
  "interaction_results": {
    "slider": { "status": "pass", "events": 42, "time": 1200 },
    "clickseq": { "status": "pass", "totalTime": 4500, "avgInterval": 500 },
    "typing": { "status": "pass", "totalTime": 3000, "avgInterval": 150, "variance": 800 },
    "dragdrop": { "status": "pass" }
  }
}
```
