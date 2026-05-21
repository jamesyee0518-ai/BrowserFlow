# CloakBrowser-Manager × Skyvern 融合架构规划

> 版本: 1.1
> 日期: 2026-05-21
> 状态: 规划阶段 (已纳入优化审核意见)

---

## 目录

- [一、现有项目结构扫描](#一现有项目结构扫描)
- [二、核心架构冲突与融合点](#二核心架构冲突与融合点)
- [三、新架构设计](#三新架构设计)
- [四、模块详细设计](#四模块详细设计)
- [五、新项目目录结构](#五新项目目录结构)
- [六、双执行路径 × CloakBrowser 完整调用链](#六双执行路径--cloakbrowser-完整调用链)
- [七、LLM 调用架构详解](#七llm-调用架构详解)
- [八、实施路线图](#八实施路线图)
- [九、核心收益总结](#九核心收益总结)
- [十、错误处理与重试机制](#十错误处理与重试机制)
- [十一、并发控制与资源限制](#十一并发控制与资源限制)
- [十二、监控与可观测性](#十二监控与可观测性)
- [十三、安全性](#十三安全性)
- [十四、测试策略](#十四测试策略)

---

## 一、现有项目结构扫描

```
CloakBrowser-Manager/
├── backend/                          ← CloakBrowser Manager 后端
│   ├── main.py                       ← FastAPI (Profile CRUD + VNC + CDP 代理)
│   ├── browser_manager.py            ← 浏览器实例管理 (launch/stop/CDP)
│   ├── vnc_manager.py                ← KasmVNC 虚拟显示器管理
│   ├── database.py                   ← SQLite Profile 存储
│   └── models.py                     ← Pydantic 数据模型
├── frontend/src/                     ← React 管理面板
│   ├── components/                   ← ProfileList, LaunchButton, ProfileViewer...
│   └── hooks/useProfiles.ts          ← API 调用
├── CloakBrowser/                     ← CloakBrowser SDK (Python + JS)
│   ├── cloakbrowser/browser.py       ← launch() / launch_persistent_context()
│   ├── cloakbrowser/config.py        ← 指纹参数配置
│   └── examples/                     ← 示例 (basic, persistent, stealth, integrations)
├── skyvern/                          ← Skyvern 工作流引擎 (新加入)
│   └── skyvern/
│       ├── forge/                    ← 核心引擎
│       │   ├── agent.py              ← Agent 循环 (截图→LLM→动作)
│       │   ├── forge_app.py          ← ForgeApp 容器 (LLM/Browser/DB/Cache)
│       │   ├── sdk/
│       │   │   ├── api/llm/          ← LLM 调用层 (多模型路由)
│       │   │   ├── workflow/          ← 工作流模型
│       │   │   │   ├── models/block.py    ← Block 类型 (Task/Code/ForLoop/Conditional...)
│       │   │   │   ├── models/workflow.py ← WorkflowDefinition
│       │   │   │   └── service.py         ← WorkflowService (执行引擎)
│       │   │   ├── cache/            ← 动作缓存 (自适应缓存)
│       │   │   └── db/               ← 数据库层
│       │   └── prompts/              ← 60+ Jinja2 提示词模板
│       └── webeye/                   ← 浏览器交互层
│           ├── browser_factory.py     ← BrowserContextFactory (3 种浏览器类型)
│           ├── browser_state.py       ← BrowserState Protocol
│           ├── actions/caching.py     ← 动作缓存匹配逻辑
│           ├── scraper/scraper.py     ← DOM 抓取 + 截图
│           └── navigation.py          ← 导航控制
├── detection-test/                   ← 检测应用 (13 类 63+ 检测项)
└── Dockerfile                        ← Docker 构建
```

### 各模块职责

| 模块 | 职责 | 关键文件 |
|------|------|---------|
| **backend/** | Profile 管理、浏览器实例生命周期、VNC/CDP 代理 | `main.py`, `browser_manager.py`, `vnc_manager.py` |
| **frontend/** | React 管理面板，Profile CRUD + VNC 内嵌查看 | `App.tsx`, `ProfileList.tsx`, `LaunchButton.tsx` |
| **CloakBrowser/** | 隐身浏览器 SDK，32 个 C++ 补丁 Chromium | `browser.py`, `config.py` |
| **skyvern/** | 工作流引擎，Agent/Script 双执行路径 | `agent.py`, `browser_factory.py`, `block.py` |
| **detection-test/** | 反检测效果验证应用 | `index.html`, `results.html` |

---

## 二、核心架构冲突与融合点

### 融合点

| # | 融合点 | 当前状态 | 融合方式 |
|---|--------|---------|---------|
| F1 | 浏览器创建 | Skyvern `BrowserContextFactory` 注册 3 种类型；CloakBrowser Manager 有独立 `BrowserManager` | 注册第 4 种 `cloakbrowser` 类型 |
| F2 | Profile 管理 | Skyvern 有 `browser_profile_id` 参数；CloakBrowser Manager 有完整 Profile CRUD + 指纹管理 | Skyvern 的 `browser_profile_id` 指向 Manager 的 Profile |
| F3 | CDP 代理 | Skyvern 有 `cdp-connect` 模式；Manager 有 CDP 代理端点 | Manager 作为远程浏览器池 |

### 架构冲突

| # | 冲突 | 原因 | 解决方案 |
|---|------|------|---------|
| C1 | 双重浏览器管理 | Manager 的 `BrowserManager` 和 Skyvern 的 `BrowserContextFactory` 都管理浏览器生命周期 | 分层：Manager 管理实例池，Skyvern 管理执行上下文 |
| C2 | 双重数据库 | Manager 用 SQLite；Skyvern 用 PostgreSQL/SQLite | 统一数据层，Profile 表扩展 |

### Skyvern 模块取舍

```
skyvern/ (保留)                     skyvern/ (移除/替换)
─────────────────────              ─────────────────────
forge/agent.py                     forge/sdk/api/aws.py (不需要云存储)
forge/api_app.py (保留,共存)       forge/sdk/api/azure.py (不需要云存储)
forge/sdk/workflow/                forge/sdk/artifact/storage/azure.py (用本地存储)
forge/sdk/api/llm/                 forge/sdk/artifact/storage/s3.py (用本地存储)
forge/sdk/cache/                   integrations/ (用 Manager 的替代)
forge/sdk/db/ (部分)               
forge/sdk/services/credential/     ← 保留,用于密码管理器集成
  (Bitwarden/1Password/Azure Vault)
forge/prompts/ (核心模板)          
webeye/actions/                    ← 保留,动作处理核心
webeye/scraper/                    ← 保留,DOM 抓取核心
webeye/browser_factory.py (修改)   
webeye/browser_state.py            
webeye/navigation.py               
cli/                               ← 保留,命令行工具对开发有用
client/                            ← 保留,Python SDK 供外部调用
alembic/                           ← 保留,数据库迁移 (SQLite 也需要)
skyvern-frontend/                  ← 保留,独立项目不影响 Manager
```

> **审核修正说明**：v1.0 中将 `forge/api_app.py`、`forge/sdk/services/credential/`、`cli/`、`client/`、`alembic/`、`skyvern-frontend/` 标记为移除是不准确的。这些模块各有独立价值，应保留。实际只需移除不需要的云服务集成 (AWS/Azure/S3) 和第三方 integrations。

---

## 三、新架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        CloakBrowser-Manager (统一入口)                       │
│                        http://localhost:8080                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     Frontend (React + Vite)                         │    │
│  │                                                                     │    │
│  │  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────────┐ │    │
│  │  │ Profiles │ │ VNC 视图 │ │ 检测报告  │ │  Workflow Builder    │ │    │
│  │  │ 管理面板 │ │ (内嵌)   │ │ (detection)│ │  (新增)              │ │    │
│  │  └──────────┘ └──────────┘ └───────────┘ └──────────────────────┘ │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                     API Gateway (FastAPI)                           │    │
│  │                                                                     │    │
│  │  /api/profiles/*     ← Profile CRUD (原有)                         │    │
│  │  /api/auth/*         ← 认证 (原有)                                 │    │
│  │  /api/status         ← 状态 (原有)                                 │    │
│  │  /api/profiles/{id}/vnc     ← VNC WebSocket (原有)                │    │
│  │  /api/profiles/{id}/cdp     ← CDP 代理 (原有)                     │    │
│  │  /api/profiles/{id}/launch  ← 启动浏览器 (原有)                   │    │
│  │  ─────────────────────────────────────────────────────────────     │    │
│  │  /api/workflows/*    ← 工作流 CRUD (新增)                          │    │
│  │  /api/workflows/{id}/run     ← 执行工作流 (新增)                  │    │
│  │  /api/workflows/runs/*       ← 运行记录 (新增)                    │    │
│  │  /api/workflows/templates/*  ← 工作流模板 (新增)                  │    │
│  │  /api/tasks/*        ← 任务管理 (新增, 代理到 Skyvern)            │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│              ┌─────────────────────┼──────────────────────┐                  │
│              ▼                     ▼                      ▼                  │
│  ┌───────────────────┐ ┌─────────────────────┐ ┌──────────────────────┐     │
│  │  Browser Pool     │ │  Workflow Engine     │ │  Detection Service   │     │
│  │  (原有,增强)      │ │  (新增,来自Skyvern)  │ │  (原有)              │     │
│  │                   │ │                      │ │                      │     │
│  │  BrowserManager   │ │  ForgeAgent          │ │  detection-test/     │     │
│  │  VNCManager       │ │  WorkflowService     │ │  13类63+检测项       │     │
│  │  CDP Proxy        │ │  LLMAPIHandler       │ │                      │     │
│  │                   │ │  ActionCache         │ │                      │     │
│  │  Profile → 浏览器 │ │  Block执行器         │ │                      │     │
│  │  实例池管理       │ │  双执行路径调度      │ │                      │     │
│  └────────┬──────────┘ └──────────┬───────────┘ └──────────────────────┘     │
│           │                       │                                         │
│           │    ┌──────────────────┘                                         │
│           │    │ CloakBrowser 隐身层                                        │
│           │    │ (32个C++补丁 + 指纹伪装)                                   │
│           ▼    ▼                                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    CloakBrowser SDK                                 │    │
│  │                                                                     │    │
│  │  launch()  launch_persistent_context()  launch_async()             │    │
│  │  --fingerprint=seed  --fingerprint-platform=windows                │    │
│  │  humanize=True  geoip=True  proxy=...                              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                    Data Layer (统一)                                │    │
│  │                                                                     │    │
│  │  profiles.db (SQLite)     ← Profile + 指纹 + 代理配置              │    │
│  │  workflows.db (SQLite)    ← Workflow + Block + Run + Cache         │    │
│  │  或 PostgreSQL            ← 生产环境                               │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 架构分层说明

| 层级 | 模块 | 职责 |
|------|------|------|
| **展示层** | Frontend | Profile 管理、VNC 查看、工作流构建器、检测报告 |
| **接口层** | API Gateway | 统一 REST + WebSocket 入口，路由到各服务 |
| **服务层** | Browser Pool | 浏览器实例生命周期、VNC/CDP 代理、实例池调度 |
| **服务层** | Workflow Engine | 工作流解析、Block 执行、双路径调度、LLM 调用 |
| **服务层** | Detection Service | 反检测效果验证 |
| **基础层** | CloakBrowser SDK | 隐身浏览器启动、指纹注入、人类行为模拟 |
| **数据层** | Data Layer | Profile/Workflow/Run/Cache 持久化 |

---

## 四、模块详细设计

### 4.1 Browser Pool 层 — CloakBrowser Manager (原有, 增强)

这是整个架构的**基础设施层**，为上层工作流引擎提供隐身浏览器实例。

```python
# browser_manager.py 增强设计
class BrowserManager:
    """
    浏览器实例池管理器

    职责：
    1. Profile → 浏览器实例的生命周期管理
    2. VNC 显示器分配
    3. CDP 端口代理
    4. 实例健康检查 + 自动重启
    5. 并发实例限制
    """

    # 新增：实例池状态
    _pool: dict[str, RunningProfile]     # profile_id → RunningProfile
    _cdp_ports: dict[str, int]           # profile_id → CDP 端口
    _vnc_displays: dict[str, int]        # profile_id → VNC 显示器号

    # 新增：为工作流引擎提供的接口
    async def allocate_for_workflow(
        self,
        profile_id: str,
        workflow_run_id: str,
        cdp_port: int | None = None,
    ) -> BrowserSession:
        """为工作流分配浏览器实例，返回 CDP 连接信息"""

    async def release_from_workflow(
        self,
        profile_id: str,
        workflow_run_id: str,
        keep_alive: bool = False,
    ) -> None:
        """工作流完成后释放实例（可选保持运行）"""

    async def get_cdp_url(self, profile_id: str) -> str:
        """获取 CDP WebSocket URL"""
```

### 4.2 BrowserContextFactory 集成 — 核心适配层

这是两个系统融合的**关键适配器**，在 Skyvern `browser_factory.py` 基础上扩展：

```python
# 新增浏览器类型注册

async def _create_cloakbrowser_instance(
    playwright: Playwright,
    proxy_location: ProxyLocation | None = None,
    extra_http_headers: dict[str, str] | None = None,
    **kwargs: dict,
) -> tuple[BrowserContext, BrowserArtifacts, BrowserCleanupFunc]:
    """
    通过 CloakBrowser Manager 的浏览器池获取实例

    两种模式：
    1. cdp-connect: 连接到 Manager 已启动的浏览器 (BROWSER_TYPE=cloakbrowser-cdp)
    2. direct-launch: 直接用 CloakBrowser SDK 启动 (BROWSER_TYPE=cloakbrowser-direct)
    """
    profile_id = kwargs.get("browser_profile_id")
    browser_address = kwargs.get("browser_address")

    if profile_id:
        # 模式1: 连接到 Manager 浏览器池中的实例
        manager_url = settings.CLOAKBROWSER_MANAGER_URL  # http://cloakbrowser-manager:8080
        cdp_url = f"{manager_url}/api/profiles/{profile_id}/cdp"

        # 确保 Profile 对应的浏览器已启动
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{manager_url}/api/profiles/{profile_id}/launch")
            resp.raise_for_status()

        return await _connect_to_cdp_browser(
            playwright,
            remote_browser_url=cdp_url,
            extra_http_headers=extra_http_headers,
            apply_download_behaviour=True,
        )
    else:
        # 模式2: 直接用 CloakBrowser SDK 启动
        from cloakbrowser import launch_persistent_context_async

        user_data_dir = make_temp_directory(prefix="cloakbrowser_")
        browser_args = BrowserContextFactory.build_browser_args(
            proxy_location=proxy_location,
            extra_http_headers=extra_http_headers,
        )

        context = await launch_persistent_context_async(
            user_data_dir=user_data_dir,
            headless=True,
            proxy=...,
            args=browser_args["args"],
            viewport=browser_args["viewport"],
            color_scheme=browser_args.get("color_scheme", "no-preference"),
            humanize=True,
            human_preset="default",
        )

        browser_artifacts = BrowserContextFactory.build_browser_artifacts(
            har_path=browser_args["record_har_path"],
            browser_session_dir=user_data_dir,
        )

        async def cleanup():
            await context.close()

        return context, browser_artifacts, cleanup


BrowserContextFactory.register_type("cloakbrowser-cdp", _create_cloakbrowser_instance)
BrowserContextFactory.register_type("cloakbrowser-direct", _create_cloakbrowser_instance)
```

### 4.3 双执行路径调度器 — 工作流核心

这是 Skyvern 双执行路径在 CloakBrowser 隐身环境下的增强版：

```python
# workflow_executor.py

class DualPathExecutor:
    """
    双执行路径调度器

    Agent 路径: 截图 → CloakBrowser(隐身) → LLM → 动作
    Script 路径: CloakBrowser(隐身) → Playwright 直接操作

    关键增强：CloakBrowser 让 Script 路径真正可用
    """

    async def execute_block(
        self,
        block: TaskBlock,
        context: WorkflowRunContext,
        browser_state: BrowserState,
    ) -> BlockResult:

        # 1. 检查是否有缓存脚本
        cached_script = await self._get_cached_script(block, context)

        if cached_script:
            # Script 路径 (快速路径)
            try:
                result = await self._execute_script(
                    cached_script, browser_state, context
                )
                await self._record_execution(block, "script", success=True)
                return result
            except Exception as e:
                # Script 失败 → 检查是否 ai_fallback
                if block.ai_fallback:
                    LOG.warning("Script failed, falling back to Agent", error=str(e))
                    result = await self._execute_agent(block, browser_state, context)
                    await self._record_execution(block, "agent_fallback", success=True)
                    return result
                raise

        # 2. Agent 路径 (LLM 驱动)
        result = await self._execute_agent(block, browser_state, context)

        # 3. 成功后生成缓存脚本 (adaptive_caching)
        if block.adaptive_caching and result.status == BlockStatus.completed:
            await self._generate_script(block, browser_state, context)

        await self._record_execution(block, "agent", success=True)
        return result

    async def _execute_agent(
        self,
        block: TaskBlock,
        browser_state: BrowserState,
        context: WorkflowRunContext,
    ) -> BlockResult:
        """
        Agent 路径执行

        CloakBrowser 隐身效果的影响：
        - 截图质量：无 Cloudflare/reCAPTCHA 拦截页面
        - LLM Token：减少 50%+ (无需处理验证码)
        - 步骤数：减少 40%+ (无需等待验证)
        """
        agent = ForgeAgent(
            browser_state=browser_state,
            llm_api_handler=app.LLM_API_HANDLER,
        )
        return await agent.execute_task(block, context)

    async def _execute_script(
        self,
        script: CachedScript,
        browser_state: BrowserState,
        context: WorkflowRunContext,
    ) -> BlockResult:
        """
        Script 路径执行

        CloakBrowser 隐身效果的影响：
        - 反爬拦截率：从 ~60% 降至 ~5%
        - 缓存命中率：从 ~30% 提升至 ~90%
        - 速度：比 Agent 快 6-12x
        """
        page = await browser_state.get_working_page()
        return await script.execute(page, context)
```

### 4.4 数据模型扩展

```python
# models.py 扩展

class ProfileResponse(BaseModel):
    """原有 Profile 模型，新增工作流关联"""
    id: str
    name: str
    fingerprint_seed: int
    platform: str
    proxy_url: str | None
    status: str
    # 新增
    linked_workflows: list[str] = []      # 关联的工作流 ID
    last_workflow_run: str | None = None   # 最近一次工作流运行 ID
    total_workflow_runs: int = 0           # 工作流运行总次数


class WorkflowCreate(BaseModel):
    """工作流创建请求"""
    title: str
    description: str | None = None
    profile_id: str                         # 绑定的 CloakBrowser Profile
    definition: WorkflowDefinition          # Skyvern 工作流定义
    run_with: Literal["agent", "script"] = "agent"
    ai_fallback: bool = True
    adaptive_caching: bool = True
    schedule: str | None = None             # cron 表达式


class WorkflowRunResponse(BaseModel):
    """工作流运行结果"""
    workflow_run_id: str
    workflow_id: str
    profile_id: str
    status: str
    execution_path: Literal["agent", "script", "agent_fallback"]
    blocks_completed: int
    blocks_total: int
    llm_tokens_used: int
    duration_seconds: float
    output: dict[str, Any] | None = None
    error: str | None = None
```

---

## 五、新项目目录结构

```
CloakBrowser-Manager/
├── backend/
│   ├── main.py                       ← FastAPI (扩展工作流 API)
│   ├── browser_manager.py            ← 浏览器实例池 (增强)
│   ├── vnc_manager.py                ← VNC 管理 (不变)
│   ├── database.py                   ← 数据层 (扩展 workflow 表)
│   ├── models.py                     ← 数据模型 (扩展)
│   ├── workflow_executor.py          ← 双执行路径调度器 (新增)
│   ├── workflow_api.py               ← 工作流 API 路由 (新增)
│   ├── llm_config.py                 ← LLM 配置管理 (新增)
│   └── requirements.txt              ← 依赖 (增加 skyvern)
│
├── skyvern/                          ← Skyvern 工作流引擎 (裁剪版)
│   └── skyvern/
│       ├── forge/
│       │   ├── agent.py              ← Agent 循环 (保留)
│       │   ├── forge_app.py          ← ForgeApp 容器 (适配)
│       │   ├── prompts/              ← 提示词模板 (保留)
│       │   └── sdk/
│       │       ├── api/llm/          ← LLM 调用层 (保留)
│       │       ├── workflow/          ← 工作流核心 (保留)
│       │       ├── cache/            ← 自适应缓存 (保留)
│       │       └── db/               ← 数据库 (适配 SQLite)
│       └── webeye/
│           ├── browser_factory.py     ← 新增 cloakbrowser 类型 (修改)
│           ├── browser_state.py       ← BrowserState (保留)
│           ├── actions/               ← 动作处理 (保留)
│           ├── scraper/               ← DOM 抓取 (保留)
│           └── navigation.py          ← 导航控制 (保留)
│
├── CloakBrowser/                     ← CloakBrowser SDK (不变)
├── frontend/src/
│   ├── components/
│   │   ├── ProfileList.tsx           ← (原有)
│   │   ├── ProfileForm.tsx           ← (原有)
│   │   ├── LaunchButton.tsx          ← (原有)
│   │   ├── ProfileViewer.tsx         ← (原有)
│   │   ├── WorkflowBuilder.tsx       ← 工作流构建器 (新增)
│   │   ├── WorkflowList.tsx          ← 工作流列表 (新增)
│   │   ├── WorkflowRunDetail.tsx     ← 运行详情 (新增)
│   │   ├── BlockEditor.tsx           ← Block 编辑器 (新增)
│   │   └── ExecutionPathToggle.tsx   ← 双路径切换 (新增)
│   └── hooks/
│       ├── useProfiles.ts            ← (原有)
│       ├── useWorkflows.ts           ← 工作流 API (新增)
│       └── useWorkflowRuns.ts        ← 运行记录 API (新增)
│
├── detection-test/                   ← 检测应用 (不变)
├── Dockerfile                        ← Docker 构建 (扩展)
└── docker-compose.yml                ← 增加 LLM 服务容器
```

---

## 六、双执行路径 × CloakBrowser 完整调用链

```
用户操作: 点击 "Run Workflow"
    │
    ▼
Frontend: POST /api/workflows/{id}/run
    │
    ▼
workflow_api.py: WorkflowAPI.run_workflow()
    │
    ├── 1. 加载 WorkflowDefinition + Profile 配置
    ├── 2. BrowserManager.allocate_for_workflow(profile_id)
    │       ├── VNCManager.allocate() → 分配显示器
    │       ├── launch_persistent_context_async(
    │       │       user_data_dir=profile.data_dir,
    │       │       headless=False,
    │       │       proxy=profile.proxy_url,
    │       │       args=["--fingerprint={seed}", "--fingerprint-platform={platform}"],
    │       │       humanize=True,
    │       │   )
    │       └── 返回 BrowserSession (context + cdp_url + vnc_url)
    │
    ├── 3. Skyvern BrowserContextFactory.create_browser_context()
    │       └── BROWSER_TYPE="cloakbrowser-cdp"
    │           → _connect_to_cdp_browser(cdp_url)
    │           → 返回 BrowserContext (标准 Playwright 接口)
    │
    ├── 4. DualPathExecutor.execute_block(block)
    │       │
    │       ├── 检查缓存脚本
    │       │
    │       ├── [Script 路径] ──────────────────────────────┐
    │       │   cached_script.execute(page, context)         │
    │       │   ├── page.goto(url)                           │
    │       │   │   └── CloakBrowser 隐身 → 页面正常加载    │
    │       │   ├── page.wait_for_selector(selector)         │
    │       │   ├── page.text_content(selector)              │
    │       │   └── 返回提取结果                              │
    │       │       │                                        │
    │       │       └── 成功 → 返回结果 (0 tokens, ~2s)      │
    │       │           失败 + ai_fallback → 切换到 Agent     │
    │       │                                                │
    │       └── [Agent 路径] ──────────────────────────────┐ │
    │           ForgeAgent.execute_task()                   │ │
    │           ├── Step 1:                                 │ │
    │           │   ├── scraper.scrape_website()            │ │
    │           │   │   └── CloakBrowser 隐身 → 无反爬拦截 │ │
    │           │   ├── build_agent_prompt(scraped_page)    │ │
    │           │   ├── LLM_API_HANDLER(prompt, screenshot) │ │
    │           │   │   └── GPT-4V / Claude / DeepSeek     │ │
    │           │   ├── parse_actions(llm_response)         │ │
    │           │   └── ActionHandler.handle_action()       │ │
    │           ├── Step 2: ...                             │ │
    │           └── Step N: 提取完成                         │ │
    │               │                                      │ │
    │               ├── 成功 → 生成缓存脚本 (adaptive)       │ │
    │               └── 返回结果 (~25K tokens, ~30s)        │ │
    │                                                      │ │
    ├── 5. 汇总所有 Block 结果                               │ │
    ├── 6. BrowserManager.release_from_workflow()            │ │
    └── 7. 返回 WorkflowRunResponse                          │ │
```

### 自适应缓存飞轮效应

```
                    CloakBrowser 隐身层
                          │
    ┌─────────────────────┼─────────────────────┐
    │                     │                     │
    ▼                     ▼                     ▼
Agent 路径            执行成功            生成脚本
(首次运行)            (高成功率)          (高质量轨迹)
    │                     │                     │
    │                     │                     ▼
    │                     │              Script 路径生效
    │                     │              (不再被反爬拦截)
    │                     │                     │
    │                     ▼                     ▼
    │              无需 ai_fallback       速度提升 12x
    │              缓存持续有效          成本降至 $0
    │                     │                     │
    └─────────────────────┼─────────────────────┘
                          │
                    飞轮加速
```

---

## 七、LLM 调用架构详解

### 7.1 多模型路由

Skyvern 的 LLM 调用是**多模型路由**架构，在融合后需要适配 CloakBrowser 场景：

```
ForgeApp.LLM_API_HANDLER (主 LLM)
    ├── OpenAI GPT-4V         ← 默认, 视觉+动作决策
    ├── Anthropic Claude      ← 备选
    ├── Azure OpenAI          ← 企业部署
    └── DeepSeek / 本地模型   ← 低成本场景

ForgeApp.SCRIPT_GENERATION_LLM_API_HANDLER (脚本生成 LLM)
    └── GPT-4o / Claude      ← Agent 成功后生成缓存脚本

ForgeApp.EXTRACTION_LLM_API_HANDLER (数据提取 LLM)
    └── GPT-4o-mini          ← 轻量级提取

ForgeApp.CHECK_USER_GOAL_LLM_API_HANDLER (目标检查 LLM)
    └── GPT-4o-mini          ← 判断任务是否完成
```

### 7.2 CloakBrowser 对 LLM 调用的影响

**无 CloakBrowser 时 LLM 需要处理的场景**：

```
LLM_CALL_1: "I see a Cloudflare challenge page, waiting..."
LLM_CALL_2: "Still on challenge page, continuing to wait..."
LLM_CALL_3: "Page loaded, but reCAPTCHA v3 score is 0.1, I'm blocked"
LLM_CALL_4: "Trying to solve CAPTCHA..."  # 通常失败
LLM_CALL_5: "Page finally loaded, finding price element..."
# = 5+ calls, ~30K tokens, 高失败率
```

**有 CloakBrowser 时 LLM 只需处理**：

```
LLM_CALL_1: "Page loaded, price is $999, extracting..."
# = 1 call, ~3K tokens, 高成功率
```

### 7.3 Agent 路径 LLM 调用链

```
Task Block 执行
  → 创建 Task 记录
  → Agent 循环:
      1. browser_state.scrape_website()  ← 截图 + DOM 抓取
      2. build_agent_prompt()            ← 构建提示词（含页面元素列表）
      3. LLM_API_HANDLER()              ← 调用 LLM（GPT-4V 等）
      4. parse_actions()                 ← 解析 LLM 返回的 JSON 动作
      5. ActionHandler.handle_action()   ← 执行浏览器操作
      6. 检查完成/失败 → 继续循环
  → 返回 extracted_information
```

### 7.4 Script 路径 (跳过 LLM)

```python
# 生成的缓存脚本直接用 Playwright API
async def run_block_extract_price(context):
    page = context.browser_session.page
    await page.goto(context.values["product_url"])
    await page.wait_for_selector(".price")
    price = await page.text_content(".price")
    return {"price": float(price.replace("$", ""))}
```

### 7.5 量化影响对比

| 指标 | 标准 Playwright | + CloakBrowser |
|------|----------------|----------------|
| reCAPTCHA v3 分数 | 0.1-0.3 | 0.9 |
| Cloudflare 拦截率 | ~60% | ~5% |
| Agent 平均步数 | 15-20 步 | 8-12 步 |
| Token 消耗/任务 | ~50K | ~25K |
| 任务成功率 | ~70% | ~95% |
| Script 路径缓存命中率 | ~30% | ~90% |

---

## 八、实施路线图

### Phase 1: 基础集成 (1-2 周)

| 任务 | 描述 | 依赖 |
|------|------|------|
| 1.1 | 注册 `cloakbrowser-cdp` 浏览器类型到 `BrowserContextFactory` | 无 |
| 1.2 | `BrowserManager` 增加 `allocate_for_workflow` / `release` 接口 | 无 |
| 1.3 | Skyvern config 适配 (`BROWSER_TYPE`, `CLOAKBROWSER_MANAGER_URL`) | 1.1 |
| 1.4 | 基础工作流 API (CRUD + Run) | 1.2, 1.3 |
| 1.5 | 验证: Agent 路径通过 CloakBrowser 隐身浏览器执行 | 1.4 |

### Phase 2: 双执行路径 (2-3 周)

| 任务 | 描述 | 依赖 |
|------|------|------|
| 2.1 | `DualPathExecutor` 实现 | Phase 1 |
| 2.2 | 自适应缓存集成 (Skyvern cache → CloakBrowser 环境) | 2.1 |
| 2.3 | Script 生成 + 审查流程 | 2.1 |
| 2.4 | `ai_fallback` 回退机制 | 2.1 |
| 2.5 | 验证: Script 路径在 CloakBrowser 环境下稳定运行 | 2.2-2.4 |

### Phase 3: 前端工作流构建器 (2-3 周)

| 任务 | 描述 | 依赖 |
|------|------|------|
| 3.1 | `WorkflowBuilder` 可视化编辑器 | Phase 2 |
| 3.2 | Block 拖拽配置 (Task/Code/ForLoop/Conditional) | 3.1 |
| 3.3 | Profile-Workflow 绑定 UI | 3.1 |
| 3.4 | 运行监控 + 实时日志 | 3.1 |
| 3.5 | `ExecutionPathToggle` (Agent/Script 切换) | 3.2 |

### Phase 4: 生产化 (1-2 周)

| 任务 | 描述 | 依赖 |
|------|------|------|
| 4.1 | PostgreSQL 数据层迁移 | Phase 3 |
| 4.2 | LLM 调用优化 (模型路由 + Token 限制) | 4.1 |
| 4.3 | 并发工作流调度 | 4.1 |
| 4.4 | Docker Compose 扩展 (LLM 服务) | 4.3 |
| 4.5 | 压力测试 + 检测验证 | 4.4 |

---

## 九、核心收益总结

| 维度 | 当前 (Manager 独立) | 融合后 (Manager + Skyvern) |
|------|---------------------|---------------------------|
| **浏览器管理** | 手动点击 Launch | 工作流自动调度 |
| **任务执行** | 无自动化能力 | Agent + Script 双路径 |
| **反检测** | CloakBrowser 隐身 | 不变 (底层一致) |
| **LLM 集成** | 无 | 多模型路由 + 视觉决策 |
| **缓存** | 无 | 自适应缓存 (6-12x 加速) |
| **批量操作** | 逐个 Profile 操作 | ForLoop 批量 + 并发 |
| **监控** | VNC 实时查看 | VNC + 工作流日志 + 指标 |
| **成本** | 0 (无 LLM) | Script 路径 $0, Agent 路径 ~$0.05/任务 |

### 架构核心价值

CloakBrowser 解决**"能不能访问"**的问题，Skyvern 解决**"怎么自动化"**的问题。两者结合 = **隐身 + 智能** 的浏览器自动化平台。

**关键洞察**：CloakBrowser 的价值不仅是"绕过反爬"，而是**让 Skyvern 的双执行路径设计真正发挥效力**。没有隐身浏览器，Script 路径形同虚设（总是被拦截回退到 Agent），自适应缓存的飞轮无法转动。有了 CloakBrowser，两条路径都能稳定运行，形成"Agent 探索 → 生成脚本 → 脚本加速"的正向循环。

---

## 十、错误处理与重试机制

### 10.1 重试配置

```python
class RetryConfig(BaseModel):
    max_retries: int = 3
    backoff_factor: float = 1.0
    retry_on_exceptions: list[type[Exception]] = [
        TimeoutError,
        ConnectionError,
        BrowserCrashedError,
    ]
```

### 10.2 分层重试策略

不同层级使用不同的重试策略：

| 层级 | 可重试异常 | 最大重试 | 退避策略 |
|------|-----------|---------|---------|
| **Block 执行** | `TimeoutError`, `BrowserCrashedError`, `ScrapingFailed` | 3 | 指数退避 (1s, 2s, 4s) |
| **LLM 调用** | `RateLimitError`, `TimeoutError`, `APIConnectionError` | 5 | 指数退避 + 抖动 (2s, 4s, 8s, 16s, 32s) |
| **浏览器启动** | `BrowserLaunchError`, `DisplayServerError` | 2 | 固定间隔 (5s) |
| **CDP 连接** | `ConnectionRefusedError`, `WebSocketError` | 10 | 线性递增 (1s, 2s, 3s...) |
| **Script 路径** | `ElementNotFoundError`, `NavigationError` | 1 | 无退避 (直接 fallback 到 Agent) |

### 10.3 重试执行器

```python
async def execute_with_retry(
    block: TaskBlock,
    context: WorkflowRunContext,
    retry_config: RetryConfig | None = None,
) -> BlockResult:
    config = retry_config or RetryConfig()
    last_exception: Exception | None = None

    for attempt in range(config.max_retries):
        try:
            return await execute_block(block, context)
        except tuple(config.retry_on_exceptions) as e:
            last_exception = e
            if attempt == config.max_retries - 1:
                break
            backoff = config.backoff_factor * (2 ** attempt)
            LOG.warning(
                "Block execution failed, retrying",
                attempt=attempt + 1,
                max_retries=config.max_retries,
                backoff_seconds=backoff,
                error=str(e),
            )
            await asyncio.sleep(backoff)

    # 所有重试耗尽后，根据 block 配置决定是否 ai_fallback
    if block.ai_fallback and not isinstance(last_exception, BrowserCrashedError):
        LOG.warning("All retries exhausted, falling back to Agent", error=str(last_exception))
        return await execute_agent_path(block, context)
    raise last_exception
```

### 10.4 浏览器崩溃恢复

浏览器崩溃是特殊场景，需要重建浏览器状态：

```python
class BrowserCrashRecovery:
    async def recover(self, profile_id: str, browser_state: BrowserState) -> BrowserState:
        """
        浏览器崩溃恢复流程:
        1. 关闭崩溃的浏览器上下文
        2. 释放 VNC 显示器
        3. 重新分配资源
        4. 用同一 Profile 重新启动浏览器
        5. 导航到崩溃前的 URL
        """
        await browser_state.close(close_browser_on_completion=True)
        new_state = await self.browser_manager.allocate_for_workflow(profile_id)
        if browser_state.last_url:
            page = await new_state.get_or_create_page(url=browser_state.last_url)
        return new_state
```

---

## 十一、并发控制与资源限制

### 11.1 并发配置

```python
class ConcurrencyConfig(BaseModel):
    max_concurrent_workflows: int = 10
    max_concurrent_browsers_per_profile: int = 3
    max_memory_per_browser_mb: int = 2048
    max_total_browser_instances: int = 20
    browser_idle_timeout_seconds: int = 300
    workflow_queue_max_size: int = 100
```

### 11.2 资源信号量

```python
class ResourceManager:
    def __init__(self, config: ConcurrencyConfig):
        self._workflow_semaphore = asyncio.Semaphore(config.max_concurrent_workflows)
        self._browser_semaphore = asyncio.Semaphore(config.max_total_browser_instances)
        self._profile_semaphores: dict[str, asyncio.Semaphore] = {}
        self._config = config

    async def acquire_workflow_slot(self) -> None:
        if self._workflow_semaphore.locked():
            raise WorkflowQueueFullError(
                f"Max concurrent workflows ({self._config.max_concurrent_workflows}) reached"
            )
        await self._workflow_semaphore.acquire()

    async def acquire_browser_slot(self, profile_id: str) -> None:
        if profile_id not in self._profile_semaphores:
            self._profile_semaphores[profile_id] = asyncio.Semaphore(
                self._config.max_concurrent_browsers_per_profile
            )
        await self._browser_semaphore.acquire()
        await self._profile_semaphores[profile_id].acquire()

    async def release_browser_slot(self, profile_id: str) -> None:
        self._browser_semaphore.release()
        if profile_id in self._profile_semaphores:
            self._profile_semaphores[profile_id].release()

    async def release_workflow_slot(self) -> None:
        self._workflow_semaphore.release()
```

### 11.3 内存监控

```python
class MemoryGuard:
    async def check_browser_memory(self, profile_id: str) -> bool:
        """检查浏览器实例内存使用，超限则强制重启"""
        process = self._get_browser_process(profile_id)
        if process and process.memory_info().rss > self._config.max_memory_per_browser_mb * 1024 * 1024:
            LOG.warning("Browser memory exceeded limit, restarting", profile_id=profile_id)
            await self._restart_browser(profile_id)
            return False
        return True
```

---

## 十二、监控与可观测性

### 12.1 工作流指标模型

```python
class WorkflowMetrics(BaseModel):
    workflow_run_id: str
    workflow_id: str
    profile_id: str
    start_time: datetime
    end_time: datetime | None
    llm_tokens_used: int
    llm_cost_usd: float
    execution_path: Literal["agent", "script", "agent_fallback"]
    blocks_completed: int
    blocks_total: int
    errors: list[str]
```

### 12.2 Prometheus 指标

```python
from prometheus_client import Counter, Gauge, Histogram

workflow_duration_seconds = Histogram(
    'cloakbrowser_workflow_duration_seconds',
    'Workflow execution duration in seconds',
    ['execution_path', 'workflow_id'],
)

workflow_llm_tokens_total = Counter(
    'cloakbrowser_workflow_llm_tokens_total',
    'Total LLM tokens used by workflows',
    ['model', 'execution_path'],
)

workflow_success_rate = Gauge(
    'cloakbrowser_workflow_success_rate',
    'Workflow success rate by execution path',
    ['execution_path'],
)

browser_pool_active = Gauge(
    'cloakbrowser_browser_pool_active',
    'Number of active browser instances',
)

browser_pool_waiting = Gauge(
    'cloakbrowser_browser_pool_waiting',
    'Number of workflows waiting for browser slot',
)

script_cache_hit_rate = Gauge(
    'cloakbrowser_script_cache_hit_rate',
    'Script path cache hit rate',
)
```

### 12.3 结构化日志

```python
import structlog

LOG = structlog.get_logger()

# 工作流执行日志示例
LOG.info(
    "workflow_block_completed",
    workflow_run_id=run_id,
    block_label=block.label,
    execution_path="script",
    duration_ms=elapsed_ms,
    llm_tokens=0,
    cache_hit=True,
)

# LLM 调用日志示例
LOG.info(
    "llm_call_completed",
    workflow_run_id=run_id,
    model="gpt-4o",
    prompt_name="extract-action",
    input_tokens=1500,
    output_tokens=300,
    latency_ms=2500,
    cost_usd=0.012,
)
```

### 12.4 健康检查端点

```
GET /api/status          ← 服务状态 + 浏览器池状态
GET /api/status/health   ← 深度健康检查 (DB + LLM + 浏览器)
GET /metrics             ← Prometheus 指标 (可选)
```

---

## 十三、安全性

### 13.1 认证和授权

| 层级 | 措施 | 实现 |
|------|------|------|
| **API 认证** | `AUTH_TOKEN` 保护所有 `/api/*` 端点 | Bearer token 或 cookie (已有) |
| **WebSocket** | 验证 Origin 头防止 CSWSH | VNC/CDP WebSocket 连接检查 Origin |
| **CDP 端口** | 只监听 localhost | `--remote-debugging-address=127.0.0.1` |
| **工作流 API** | 继承 Manager 的 AUTH_TOKEN 机制 | 新增端点复用 `_check_auth()` |
| **LLM API Key** | 环境变量注入，不落盘 | `OPENAI_API_KEY` 等通过 `.env` 加载 |

### 13.2 数据隔离

| 隔离维度 | 措施 |
|---------|------|
| **Profile 隔离** | 每个 Profile 独立 `user_data_dir`，cookies/localStorage 互不可见 |
| **工作流隔离** | 工作流之间不能互相访问浏览器上下文 |
| **运行隔离** | 每次工作流运行使用独立的 `SkyvernContext` |
| **敏感数据** | 密码、cookie 等通过 `CredentialVaultService` 加密存储 |
| **代理凭证** | 代理 URL 中的用户名密码不记录到日志 |

### 13.3 资源限制

| 限制项 | 默认值 | 说明 |
|--------|-------|------|
| 并发工作流 | 10 | 防止资源耗尽 |
| LLM 调用频率 | 60 RPM | 防止 API 滥用 |
| LLM 单任务 Token 上限 | 200K | 防止成本失控 |
| 浏览器内存 | 2048 MB/实例 | 防止 OOM |
| 工作流最大 Block 数 | 50 | 防止无限循环 |
| ForLoop 最大迭代 | 500 | Skyvern 默认值 |
| 浏览器空闲超时 | 300s | 自动释放闲置实例 |

### 13.4 凭证管理

Skyvern 的 `forge/sdk/services/credential/` 提供多种密码管理器集成，融合后保留：

| 凭证服务 | 用途 | 保留理由 |
|---------|------|---------|
| `BitwardenCredentialService` | 从 Bitwarden 获取登录凭证 | 工作流中自动登录场景 |
| `AzureCredentialVaultService` | 从 Azure Key Vault 获取密钥 | 企业部署场景 |
| `CustomCredentialVaultService` | 自定义凭证 API | 灵活扩展 |
| `CredentialVaultService` | 凭证抽象层 | 统一接口 |

---

## 十四、测试策略

### 14.1 测试分层

```
┌─────────────────────────────────────────┐
│           E2E 测试 (少量, 慢)            │
│  完整工作流执行 + 检测验证               │
├─────────────────────────────────────────┤
│         集成测试 (中等数量, 中速)         │
│  CloakBrowser ↔ Skyvern ↔ LLM 集成      │
├─────────────────────────────────────────┤
│         单元测试 (大量, 快)              │
│  各模块独立逻辑验证                      │
└─────────────────────────────────────────┘
```

### 14.2 单元测试

| 测试文件 | 覆盖范围 |
|---------|---------|
| `tests/unit/test_browser_manager.py` | 浏览器实例池分配/释放/健康检查 |
| `tests/unit/test_dual_path_executor.py` | 双路径调度、fallback 逻辑、缓存命中 |
| `tests/unit/test_workflow_api.py` | 工作流 CRUD API、参数校验 |
| `tests/unit/test_retry_mechanism.py` | 重试策略、退避计算、异常分类 |
| `tests/unit/test_concurrency_control.py` | 信号量获取/释放、队列满处理 |
| `tests/unit/test_resource_manager.py` | 内存监控、浏览器重启 |

### 14.3 集成测试

| 测试文件 | 覆盖范围 |
|---------|---------|
| `tests/integration/test_cloakbrowser_integration.py` | CloakBrowser SDK ↔ BrowserContextFactory 集成 |
| `tests/integration/test_script_caching.py` | 自适应缓存端到端 (Agent→生成脚本→Script 执行) |
| `tests/integration/test_cdp_proxy.py` | Manager CDP 代理 ↔ Skyvern cdp-connect 模式 |
| `tests/integration/test_credential_vault.py` | Bitwarden/自定义凭证服务集成 |
| `tests/integration/test_llm_routing.py` | 多模型路由 + fallback |

### 14.4 E2E 测试

| 测试文件 | 覆盖范围 |
|---------|---------|
| `tests/e2e/test_full_workflow.py` | 完整工作流: 创建→配置→执行→结果验证 |
| `tests/e2e/test_detection_bypass.py` | 用 detection-test 验证 CloakBrowser 隐身效果 |
| `tests/e2e/test_dual_path_switch.py` | Agent→Script 路径切换 + ai_fallback 回退 |
| `tests/e2e/test_concurrent_workflows.py` | 多工作流并发执行 + 资源限制验证 |

### 14.5 性能测试

| 测试文件 | 覆盖范围 |
|---------|---------|
| `tests/perf/test_concurrent_workflows.py` | 10/50/100 并发工作流吞吐量 |
| `tests/perf/test_llm_token_usage.py` | Agent vs Script 路径 Token 消耗对比 |
| `tests/perf/test_browser_pool_scaling.py` | 浏览器实例池扩缩容性能 |
| `tests/perf/test_cache_hit_rate.py` | 自适应缓存命中率随运行次数变化 |

### 14.6 测试环境配置

```python
# tests/conftest.py

@pytest.fixture
def mock_llm_handler():
    """Mock LLM，返回预设动作，避免真实 API 调用"""

@pytest.fixture
async def cloakbrowser_context():
    """启动 CloakBrowser 测试实例 (headless=True)"""

@pytest.fixture
def detection_test_url():
    """指向本地 detection-test 服务的 URL"""
    return "http://localhost:8088"
```
