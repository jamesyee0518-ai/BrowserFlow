# CloakBrowser-Manager × Skyvern 分阶段开发计划

> 版本: 1.0
> 日期: 2026-05-21
> 基于: ARCHITECTURE.md v1.1
> 状态: Phase 1 已完成

---

## 总览

| 阶段 | 名称 | 周期 | 核心目标 | 状态 |
|------|------|------|---------|------|
| P0 | 现有基线验证 | 1 周 | 确保现有 Manager 功能不受影响 | ✅ 已完成 |
| P1 | 基础集成 | 2 周 | 工作流 API + 浏览器池接口 + Skyvern 适配 | ✅ 已完成 |
| P2 | 双执行路径 | 3 周 | Agent/Script 双路径 + 自适应缓存 + 回退 | 🔲 待开始 |
| P3 | 前端工作流 | 3 周 | 可视化构建器 + 运行监控 + 双路径切换 | 🔲 待开始 |
| P4 | 生产化加固 | 2 周 | 并发控制 + 监控 + 安全 + 性能优化 | 🔲 待开始 |
| P5 | 端到端验证 | 1 周 | 全链路测试 + 压力测试 + 部署验证 | 🔲 待开始 |

**总工期**: 约 12 周

---

## P0: 现有基线验证

> 目标: 确保融合开发不会破坏 Manager 已有功能

### 任务清单

| 编号 | 任务 | 优先级 | 预计工时 |
|------|------|--------|---------|
| P0-01 | Docker 构建验证: `docker compose up --build` 成功 | 高 | 2h |
| P0-02 | Profile CRUD 全流程: 创建/编辑/删除/列表 | 高 | 1h |
| P0-03 | Launch 浏览器: Profile 启动 + VNC 连接 + CDP 代理 | 高 | 2h |
| P0-04 | 前端构建: `npm run build` 无错误 | 高 | 1h |
| P0-05 | 检测应用: detection-test 13 类检测项正常运行 | 中 | 1h |
| P0-06 | 数据库迁移: 新增 workflow 表后原有 profile 表不受影响 | 高 | 1h |

### 验收标准

| 编号 | 验收标准 | 验证方法 |
|------|---------|---------|
| AC-P0-01 | Docker 镜像构建成功，容器启动后 `GET /api/status` 返回 200 | `docker compose up --build && curl localhost:8080/api/status` |
| AC-P0-02 | Profile CRUD 全部 200: POST 创建、GET 列表、PUT 更新、DELETE 删除 | curl 逐一测试 |
| AC-P0-03 | Launch 浏览器后 VNC WebSocket 可连接，CDP `/json/version` 返回浏览器信息 | 浏览器打开 VNC + curl CDP 端点 |
| AC-P0-04 | `npm run build` 零错误零警告 | 终端输出确认 |
| AC-P0-05 | detection-test 页面加载无 JS 报错，13 类检测项全部显示结果 | 浏览器 Console 无红字 |
| AC-P0-06 | 新增 workflows/workflow_runs 表后，原有 profiles 表数据完整 | `sqlite3 profiles.db "SELECT count(*) FROM profiles"` 数量不变 |

---

## P1: 基础集成 ✅

> 目标: 建立工作流 API 骨架，浏览器池支持工作流调度，Skyvern 适配层可注册

### 任务清单

| 编号 | 任务 | 优先级 | 预计工时 | 状态 |
|------|------|--------|---------|------|
| P1-01 | 创建 `llm_config.py`: 多模型配置管理 | 高 | 4h | ✅ |
| P1-02 | 创建 `workflow_executor.py`: 双执行路径调度器骨架 | 高 | 8h | ✅ |
| P1-03 | 创建 `workflow_api.py`: 工作流 REST API | 高 | 6h | ✅ |
| P1-04 | 创建 `skyvern_adapter.py`: 注册 cloakbrowser-cdp/direct 类型 | 高 | 6h | ✅ |
| P1-05 | 扩展 `models.py`: WorkflowCreate/Response/RunResponse | 高 | 2h | ✅ |
| P1-06 | 扩展 `database.py`: workflows + workflow_runs 表 + CRUD | 高 | 4h | ✅ |
| P1-07 | 扩展 `browser_manager.py`: allocate_for_workflow/release | 高 | 4h | ✅ |
| P1-08 | 修改 `main.py`: 注册 workflow 路由 + lifespan 注册适配器 | 高 | 2h | ✅ |
| P1-09 | 更新 `requirements.txt`: 增加 playwright 依赖 | 中 | 0.5h | ✅ |
| P1-10 | 语法验证 + 数据库 CRUD 验证 | 高 | 2h | ✅ |

### 验收标准

| 编号 | 验收标准 | 验证方法 | 状态 |
|------|---------|---------|------|
| AC-P1-01 | 8 个 Python 文件语法检查零错误 | `python3 -c "import ast; ast.parse(open(f).read())"` | ✅ |
| AC-P1-02 | Workflow CRUD: 创建/查询/列表/更新/删除全部 200 | curl 测试各端点 | ✅ |
| AC-P1-03 | Workflow Run CRUD: 创建/查询/更新全部 200 | curl 测试各端点 | ✅ |
| AC-P1-04 | LLM 配置从环境变量正确加载 | `LLMConfig.get().primary.model == "gpt-4o"` | ✅ |
| AC-P1-05 | `skyvern_adapter.register_cloakbrowser_types()` 不报错 (Skyvern 未安装时优雅降级) | 调用后无异常抛出 | ✅ |
| AC-P1-06 | `allocate_for_workflow` 复用已运行的 Profile 实例 | 同一 profile_id 二次调用返回同一 RunningProfile | ✅ |
| AC-P1-07 | `release_from_workflow` keep_alive=True 时浏览器不停止 | 调用后 profile 状态仍为 running | ✅ |

### 已知遗留

| 编号 | 遗留项 | 优先级 | 计划解决阶段 |
|------|--------|--------|------------|
| P1-L01 | `workflow_executor._execute_agent_path` 中 ForgeAgent 调用为占位实现 | 高 | P2 |
| P1-L02 | `workflow_executor._execute_script_path` 为空壳 | 高 | P2 |
| P1-L03 | Workflow API 未做参数校验 (definition 结构验证) | 中 | P2 |
| P1-L04 | 前端无工作流 UI | 高 | P3 |

---

## P2: 双执行路径

> 目标: 实现 Agent 路径 (LLM 驱动) 和 Script 路径 (确定性脚本) 的完整执行逻辑，含自适应缓存和 ai_fallback 回退

### 任务清单

| 编号 | 任务 | 优先级 | 预计工时 | 依赖 |
|------|------|--------|---------|------|
| P2-01 | Skyvern ForgeAgent 适配: 接入 Manager 的浏览器上下文 | 高 | 16h | P1 |
| P2-02 | Agent 路径完整实现: 截图→LLM→动作解析→执行循环 | 高 | 24h | P2-01 |
| P2-03 | LLM 调用层实现: OpenAI/Claude/DeepSeek 多模型路由 | 高 | 12h | P2-02 |
| P2-04 | Script 路径实现: 缓存脚本的加载和执行 | 高 | 8h | P2-01 |
| P2-05 | 自适应缓存: Agent 成功后自动生成缓存脚本 | 高 | 16h | P2-02, P2-04 |
| P2-06 | ai_fallback 回退: Script 失败自动切换到 Agent | 高 | 8h | P2-02, P2-04 |
| P2-07 | 错误处理: 分层重试策略 + 浏览器崩溃恢复 | 高 | 12h | P2-02 |
| P2-08 | Workflow Definition 校验: Block 结构验证 + 参数类型检查 | 中 | 6h | P1 |
| P2-09 | Code Block 执行: 安全沙箱 + 沙箱变量注入 | 中 | 8h | P1 |
| P2-10 | ForLoop/Conditional Block 执行 | 中 | 12h | P2-09 |
| P2-11 | 集成测试: Agent 路径 + Script 路径 + fallback | 高 | 8h | P2-06 |

### 验收标准

| 编号 | 验收标准 | 验证方法 |
|------|---------|---------|
| AC-P2-01 | Agent 路径: 给定 URL 和提取目标，LLM 返回正确动作并执行成功 | 创建含 Task Block 的工作流，`POST /api/workflows/{id}/run` 返回 `status=completed` |
| AC-P2-02 | Agent 路径: LLM 调用日志记录 model/input_tokens/output_tokens/latency_ms | 查看日志输出包含 `llm_call_completed` 事件 |
| AC-P2-03 | Script 路径: 有缓存脚本时跳过 LLM 调用，直接 Playwright 操作 | 第二次运行同一工作流，`llm_tokens_used=0`，`execution_path=script` |
| AC-P2-04 | 自适应缓存: Agent 成功后自动生成脚本并持久化 | 首次运行后 `GET /api/workflows/{id}` 返回的 definition 包含 `cached_script` |
| AC-P2-05 | ai_fallback: Script 失败后自动回退到 Agent，`execution_path=agent_fallback` | 手动注入错误脚本，运行后验证回退 |
| AC-P2-06 | 重试: Block 执行超时后重试最多 3 次，指数退避 | Mock 超时场景，验证重试次数和间隔 |
| AC-P2-07 | 浏览器崩溃恢复: 崩溃后自动重启浏览器并继续执行 | 手动 kill 浏览器进程，验证工作流不中断 |
| AC-P2-08 | Code Block: 安全执行 Python 代码，返回结果注入上下文 | 创建含 Code Block 的工作流，验证输出 |
| AC-P2-09 | ForLoop Block: 遍历列表，每个元素执行子 Block | 创建含 ForLoop 的工作流，验证迭代执行 |
| AC-P2-10 | Conditional Block: 条件判断，满足时执行子 Block | 创建含 Conditional 的工作流，验证分支 |
| AC-P2-11 | 集成测试通过: Agent/Script/Fallback 三种路径各至少 1 个测试用例 | `pytest tests/integration/ -v` 全绿 |

### 关键风险

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Skyvern ForgeAgent 依赖链复杂，适配工作量大 | P2 延期 | 先实现简化版 Agent (直接调用 LLM API)，后续再接入 ForgeAgent |
| LLM API 不稳定/超时 | Agent 路径失败率 | 实现多模型 fallback (OpenAI→Claude→DeepSeek) |
| 自适应缓存生成的脚本质量低 | Script 路径命中率低 | 生成后人工审核机制，低质量脚本不缓存 |

---

## P3: 前端工作流构建器

> 目标: 提供可视化工作流编辑、运行监控、双路径切换的前端界面

### 任务清单

| 编号 | 任务 | 优先级 | 预计工时 | 依赖 |
|------|------|--------|---------|------|
| P3-01 | `useWorkflows.ts` Hook: 工作流 CRUD + 运行 API | 高 | 4h | P1 |
| P3-02 | `useWorkflowRuns.ts` Hook: 运行记录查询 API | 高 | 3h | P1 |
| P3-03 | `WorkflowList.tsx`: 工作流列表 + 状态标签 + 快捷操作 | 高 | 8h | P3-01 |
| P3-04 | `WorkflowBuilder.tsx`: 可视化工作流编辑器 | 高 | 24h | P3-01 |
| P3-05 | `BlockEditor.tsx`: Block 类型选择 + 参数配置表单 | 高 | 16h | P3-04 |
| P3-06 | `ExecutionPathToggle.tsx`: Agent/Script 模式切换 | 中 | 6h | P3-04 |
| P3-07 | Profile-Workflow 绑定: 选择 Profile + 预览指纹参数 | 高 | 8h | P3-04 |
| P3-08 | `WorkflowRunDetail.tsx`: 运行详情 + Block 执行时间线 + 日志 | 高 | 12h | P3-02 |
| P3-09 | 运行监控: 实时状态轮询 + 进度条 + 错误提示 | 中 | 8h | P3-08 |
| P3-10 | 工作流模板: 预置常用模板 (价格监控/表单填写/数据抓取) | 低 | 8h | P3-04 |
| P3-11 | 前端构建验证: `npm run build` 零错误 | 高 | 2h | P3-ALL |

### 验收标准

| 编号 | 验收标准 | 验证方法 |
|------|---------|---------|
| AC-P3-01 | 工作流列表页: 显示所有工作流，支持创建/删除/运行 | 浏览器操作验证 |
| AC-P3-02 | 工作流编辑器: 拖拽添加 Block，配置参数，保存成功 | 创建含 3 个 Block 的工作流并保存 |
| AC-P3-03 | Block 编辑器: Task/Code/ForLoop/Conditional 四种类型可配置 | 逐一添加验证 |
| AC-P3-04 | Profile 绑定: 下拉选择已有 Profile，显示指纹参数预览 | 绑定后运行工作流使用该 Profile |
| AC-P3-05 | 运行工作流: 点击运行按钮，状态从 pending→running→completed | 观察状态变化 |
| AC-P3-06 | 运行详情: 显示每个 Block 的执行路径/耗时/Token/输出 | 查看运行详情页 |
| AC-P3-07 | 双路径切换: 切换 Agent/Script 模式，运行后 `execution_path` 对应 | 切换后运行验证 |
| AC-P3-08 | 错误展示: 工作流失败时显示错误信息和失败 Block | 注入错误验证 |
| AC-P3-09 | `npm run build` 零错误 | 终端输出确认 |
| AC-P3-10 | 响应式: 管理面板在 1280px+ 宽度下正常显示 | 浏览器窗口调整验证 |

---

## P4: 生产化加固

> 目标: 并发控制、监控可观测性、安全加固、性能优化

### 任务清单

| 编号 | 任务 | 优先级 | 预计工时 | 依赖 |
|------|------|--------|---------|------|
| P4-01 | `ResourceManager`: 并发工作流信号量 + 浏览器实例限制 | 高 | 8h | P2 |
| P4-02 | `MemoryGuard`: 浏览器内存监控 + 超限重启 | 中 | 6h | P4-01 |
| P4-03 | Prometheus 指标: 6 个核心指标埋点 | 中 | 8h | P2 |
| P4-04 | 结构化日志: structlog 替换 print/logging | 中 | 6h | P2 |
| P4-05 | 健康检查: `/api/status/health` 深度检查 (DB+LLM+浏览器) | 高 | 4h | P4-03 |
| P4-06 | 安全加固: WebSocket Origin 校验 + CDP localhost 限制 | 高 | 6h | P1 |
| P4-07 | LLM Token 限制: 单任务上限 + 预算控制 | 中 | 4h | P2 |
| P4-08 | LLM 多模型 fallback: OpenAI→Claude→DeepSeek 自动切换 | 高 | 8h | P2 |
| P4-09 | Docker Compose 扩展: LLM 代理服务 + 资源限制配置 | 中 | 4h | P4-01 |
| P4-10 | PostgreSQL 适配: 数据层抽象 + 迁移脚本 | 低 | 12h | P2 |

### 验收标准

| 编号 | 验收标准 | 验证方法 |
|------|---------|---------|
| AC-P4-01 | 并发限制: 超过 `max_concurrent_workflows` 时新请求返回 429 | 并发 curl 测试 |
| AC-P4-02 | 浏览器限制: 超过 `max_total_browser_instances` 时排队等待 | 启动超限数量 Profile |
| AC-P4-03 | 内存监控: 浏览器 RSS 超过 2048MB 时自动重启 | 模拟内存泄漏场景 |
| AC-P4-04 | Prometheus: `curl /metrics` 返回 `cloakbrowser_workflow_duration_seconds` 等 6 个指标 | curl 验证 |
| AC-P4-05 | 结构化日志: 日志输出 JSON 格式，包含 workflow_run_id/block_label 等字段 | 查看日志输出 |
| AC-P4-06 | 健康检查: DB 异常/LLM 不可达/浏览器池满时返回 503 | 模拟故障验证 |
| AC-P4-07 | WebSocket 安全: 非 localhost Origin 的 VNC/CDP 连接被拒绝 | curl 带 Origin 头测试 |
| AC-P4-08 | CDP 安全: 远程主机无法访问 CDP 端口 | 远程 curl 验证 |
| AC-P4-09 | Token 限制: 单任务超过 200K Token 时自动终止 | 长对话场景验证 |
| AC-P4-10 | LLM fallback: OpenAI 不可用时自动切换到 Claude | Mock OpenAI 500 错误 |
| AC-P4-11 | Docker Compose: `docker compose up` 一键启动全部服务 | 完整构建验证 |

---

## P5: 端到端验证

> 目标: 全链路功能验证、压力测试、部署验证

### 任务清单

| 编号 | 任务 | 优先级 | 预计工时 | 依赖 |
|------|------|--------|---------|------|
| P5-01 | E2E 测试: 完整工作流 创建→配置→执行→结果验证 | 高 | 8h | P4 |
| P5-02 | E2E 测试: 双路径切换 Agent→Script→Fallback | 高 | 6h | P4 |
| P5-03 | E2E 测试: detection-test 验证 CloakBrowser 隐身效果 | 高 | 4h | P4 |
| P5-04 | 压力测试: 10 并发工作流吞吐量 | 高 | 8h | P4 |
| P5-05 | 压力测试: 50 并发工作流 + 资源限制验证 | 中 | 8h | P5-04 |
| P5-06 | Token 消耗对比: Agent vs Script 路径 | 中 | 4h | P5-01 |
| P5-07 | 缓存命中率测试: 自适应缓存随运行次数变化 | 中 | 4h | P5-01 |
| P5-08 | 部署验证: Docker 全量构建 + 容器启动 + 功能验证 | 高 | 4h | P5-04 |
| P5-09 | 文档更新: README + 使用指南 + API 文档 | 低 | 4h | P5-08 |
| P5-10 | 交付验收: 全部验收标准通过 | 高 | 4h | P5-ALL |

### 验收标准

| 编号 | 验收标准 | 验证方法 |
|------|---------|---------|
| AC-P5-01 | 完整工作流: 创建含 3 个 Block 的工作流，运行成功，结果正确 | 自动化 E2E 脚本 |
| AC-P5-02 | 双路径: 首次运行 Agent 路径，第二次 Script 路径，第三次 Script 失败 Fallback | 3 次运行验证 |
| AC-P5-03 | 隐身验证: CloakBrowser 通过 detection-test 13 类检测项，BrowserScan 评分 Normal | 检测报告截图 |
| AC-P5-04 | 10 并发: 10 个工作流同时运行，全部完成，无资源泄漏 | 并发测试脚本 |
| AC-P5-05 | 50 并发: 50 个工作流排队执行，资源限制生效，无 OOM | 压力测试脚本 |
| AC-P5-06 | Token 对比: Agent 路径 ~25K tokens，Script 路径 0 tokens | 日志统计 |
| AC-P5-07 | 缓存命中率: 第 2 次运行命中率 >80%，第 5 次 >95% | 运行记录统计 |
| AC-P5-08 | Docker 部署: `docker compose up --build` 一键部署成功，所有 API 可访问 | 完整部署流程 |
| AC-P5-09 | 文档完整: README 包含安装/配置/使用/架构 4 个章节 | 人工审核 |
| AC-P5-10 | 全部 AC 通过: P0-P5 所有验收标准 100% 通过 | 检查清单 |

---

## 里程碑与交付物

| 里程碑 | 时间点 | 交付物 | 质量门禁 |
|--------|-------|--------|---------|
| **M1: 基线确认** | P0 完成后 | 基线测试报告 | P0 全部 AC 通过 |
| **M2: API 就绪** | P1 完成后 | 工作流 API + 数据库 + 适配器 | P1 全部 AC 通过 + 语法检查零错误 |
| **M3: 双路径可用** | P2 完成后 | Agent/Script 双执行路径 + 缓存 + 回退 | P2 全部 AC 通过 + 集成测试全绿 |
| **M4: UI 可用** | P3 完成后 | 前端工作流构建器 + 运行监控 | P3 全部 AC 通过 + `npm run build` 零错误 |
| **M5: 生产就绪** | P4 完成后 | 并发控制 + 监控 + 安全加固 | P4 全部 AC 通过 + Docker 部署验证 |
| **M6: 交付验收** | P5 完成后 | 全链路测试报告 + 部署文档 | P5 全部 AC 通过 |

---

## 质量门禁规则

每个阶段进入下一阶段前，必须满足以下条件：

### 代码质量

| 规则 | 标准 |
|------|------|
| Python 语法检查 | `ast.parse()` 零错误 |
| 前端构建 | `npm run build` 零错误 |
| 类型注解 | 所有新增函数 100% 类型注解 |
| 无硬编码密钥 | API Key / Token 不出现在源码中 |

### 功能质量

| 规则 | 标准 |
|------|------|
| 阶段 AC 通过率 | 100% |
| 回归测试 | 新增代码不破坏已有功能 |
| 错误处理 | 所有外部调用 (LLM/浏览器/网络) 有 try-except |
| 日志覆盖 | 关键路径有结构化日志 |

### 安全质量

| 规则 | 标准 |
|------|------|
| API 认证 | 新增端点继承 AUTH_TOKEN 机制 |
| 输入校验 | 所有 API 入参有 Pydantic 校验 |
| 资源限制 | 浏览器/工作流有并发上限 |
| 数据隔离 | 工作流之间不能互访浏览器上下文 |

---

## 风险登记

| 编号 | 风险 | 概率 | 影响 | 缓解措施 | 负责阶段 |
|------|------|------|------|---------|---------|
| R-01 | Skyvern ForgeAgent 依赖链复杂，适配困难 | 高 | P2 延期 2 周 | 实现简化版 Agent (直接 LLM API)，ForgeAgent 作为增强 | P2 |
| R-02 | LLM API 不稳定/限流 | 中 | Agent 路径失败 | 多模型 fallback + 重试 + 降级到 Script | P2 |
| R-03 | Docker 构建网络问题 (国内镜像) | 中 | 部署阻塞 | 使用 `docker.1ms.run` 镜像加速器 | P4 |
| R-04 | 自适应缓存脚本质量低 | 中 | Script 命中率低 | 人工审核机制 + 质量评分阈值 | P2 |
| R-05 | 浏览器内存泄漏 | 低 | OOM 崩溃 | MemoryGuard + 空闲超时自动释放 | P4 |
| R-06 | 前端工作流编辑器复杂度高 | 中 | P3 延期 | 先实现表单式编辑，后续迭代拖拽式 | P3 |

---

## 当前进度

```
P0 ████████████████████ 100% ✅
P1 ████████████████████ 100% ✅
P2 ░░░░░░░░░░░░░░░░░░░░   0% 🔲
P3 ░░░░░░░░░░░░░░░░░░░░   0% 🔲
P4 ░░░░░░░░░░░░░░░░░░░░   0% 🔲
P5 ░░░░░░░░░░░░░░░░░░░░   0% 🔲

总体进度: ██████░░░░░░░░░░░░░░ 18%
```
