
<h3 align="center">BrowserFlow — Anti-Detect Browser Manager + Workflow Automation</h3>

<p align="center">
Create isolated browser profiles with unique fingerprints, then automate them<br>
with LLM-driven agents or deterministic scripts — all from one self-hosted dashboard.
</p>

<p align="center">
<a href="https://github.com/jamesyee0518-ai/BrowserFlow"><img src="https://img.shields.io/badge/repo-BrowserFlow-blue?logo=github" alt="GitHub"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue" alt="License"></a>
<img src="https://img.shields.io/badge/python-3.12-blue?logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/react-19-blue?logo=react&logoColor=white" alt="React">
</p>

---

## What is BrowserFlow?

BrowserFlow combines two capabilities in one platform:

1. **Anti-Detect Browser Manager** — Create and manage isolated browser profiles, each with a unique device fingerprint. Powered by [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) (32 source-level C++ patches to Chromium), each profile appears as a completely different computer to websites.

2. **Workflow Automation Engine** — Automate browser tasks using a dual execution path:
   - **Agent Path** (LLM-driven): Takes screenshots → sends to LLM → parses actions → executes via Playwright. Handles dynamic, unpredictable pages.
   - **Script Path** (deterministic): Runs cached Playwright scripts. Fast, cheap, and repeatable.
   - **Adaptive Caching**: Successful agent runs automatically generate scripts, so next time the script path runs first.
   - **AI Fallback**: If a script fails, it automatically falls back to the agent path.

## Why Not Just Use a VPN?

A VPN only changes your IP. Incognito only clears cookies. Chrome profiles share the same hardware fingerprint. Platforms use 50+ signals to link your accounts — canvas, WebGL, audio, GPU, fonts, screen size, timezone.

Each BrowserFlow profile generates a completely different device identity. To the website, each profile looks like a different computer.

| Solution | What it changes | Accounts linked? |
|----------|----------------|-----------------|
| VPN | IP address only | Yes — same fingerprint |
| Incognito | Clears cookies | Yes — same fingerprint |
| Chrome profiles | Separate bookmarks/cookies | Yes — same hardware fingerprint |
| **BrowserFlow** | **Everything — full device identity per profile** | **No** |

## Quick Start

```bash
docker compose up --build
```

Open [http://localhost:8080](http://localhost:8080). Create a profile. Click Launch. Done.

Or run from source:

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8080

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

## Features

### Profile Management
- **Per-profile fingerprint** — seed, platform, GPU vendor/renderer, hardware concurrency, screen size
- **Per-profile proxy** — HTTP/HTTPS/SOCKS5 with authentication
- **Per-profile settings** — timezone, locale, user agent, color scheme, humanized input
- **One-click launch/stop** — each profile runs as an isolated CloakBrowser instance
- **Session persistence** — cookies, localStorage, and cache survive browser restarts
- **In-browser viewing** — interact with launched browsers via noVNC, directly in the web GUI
- **CDP access** — connect Playwright/Puppeteer to any running profile programmatically

### Workflow Automation
- **Visual workflow builder** — drag-and-drop block editor (Task, Code, ForLoop, Conditional)
- **Dual execution path** — Agent (LLM) or Script (deterministic), with adaptive switching
- **Multi-model LLM** — OpenAI, Anthropic, DeepSeek with automatic fallback
- **Adaptive caching** — agent success auto-generates cached scripts for future runs
- **AI fallback** — script failures automatically retry with the agent path
- **Retry with backoff** — 3 attempts with exponential backoff for transient errors
- **Workflow monitoring** — real-time run status, token usage, execution path, duration

### Production Hardening
- **Concurrency control** — semaphore-based workflow + browser instance limits
- **Memory guard** — monitors browser process memory, auto-restarts on limit breach
- **LLM budget** — per-task token limits + total USD budget cap
- **Rate limiting** — API and CDP endpoint rate limiting
- **Structured logging** — JSON format with key fields (set `LOG_FORMAT=json`)
- **Prometheus metrics** — `/metrics` endpoint with workflow duration, LLM tokens, browser pool stats
- **Deep health check** — `/api/status/health` checks DB, LLM config, browser pool, resources
- **Security** — WebSocket Origin validation, CDP localhost-only, optional auth token

## Architecture

```
BrowserFlow/
├── backend/
│   ├── main.py                  ← FastAPI app (Profile CRUD + VNC + CDP proxy)
│   ├── browser_manager.py       ← Browser instance lifecycle (launch/stop/allocate)
│   ├── vnc_manager.py           ← KasmVNC virtual display management
│   ├── workflow_executor.py     ← Dual-path executor (Agent + Script + Adaptive Cache)
│   ├── workflow_api.py          ← Workflow REST API (CRUD + Run)
│   ├── llm_config.py            ← Multi-model LLM configuration
│   ├── resource_manager.py      ← Concurrency control + LLM budget
│   ├── memory_guard.py          ← Browser memory monitoring + auto-restart
│   ├── metrics.py               ← Prometheus-compatible metrics collector
│   ├── rate_limiter.py          ← API + CDP rate limiting
│   ├── structured_logging.py    ← JSON structured logging
│   ├── skyvern_adapter.py       ← CloakBrowser browser type registration
│   ├── database.py              ← SQLite (profiles + workflows + workflow_runs)
│   └── models.py                ← Pydantic data models
├── frontend/src/
│   ├── components/
│   │   ├── ProfileList.tsx      ← Profile management UI
│   │   ├── ProfileForm.tsx      ← Profile editor
│   │   ├── ProfileViewer.tsx    ← VNC browser viewer
│   │   ├── WorkflowList.tsx     ← Workflow list with status + path icons
│   │   ├── WorkflowBuilder.tsx  ← Block editor (Task/Code/ForLoop/Conditional)
│   │   ├── WorkflowEditor.tsx   ← Workflow config (profile, mode, caching)
│   │   └── WorkflowRunDetail.tsx← Run details (path, tokens, duration)
│   ├── hooks/
│   │   ├── useProfiles.ts       ← Profile CRUD hook
│   │   ├── useWorkflows.ts      ← Workflow CRUD + Run hook
│   │   └── useWorkflowRuns.ts   ← Run history hook
│   └── lib/api.ts               ← API client + TypeScript types
├── detection-test/              ← Anti-detection test suite (13 categories, 63+ checks)
├── docker-compose.yml           ← Production Docker config with resource limits
├── Dockerfile                   ← Multi-stage build (Node → Python + KasmVNC)
└── entrypoint.sh                ← Container startup script
```

## Dual Execution Path

```
┌─────────────────────────────────────────────────────┐
│                   Workflow Block                     │
├─────────────────┬───────────────────────────────────┤
│  Cached Script? │         No → Agent Path           │
│  Yes ↓          │   Screenshot → LLM → Parse JSON  │
│  Script Path    │   → Execute Action → Loop         │
│  exec(sandbox)  │   → On success: generate script   │
│       │         │              ↓                     │
│  Success ✓      │         Cached Script ✓           │
│       │         │              │                     │
│  Fail → AI Fallback → Agent Path (retry)            │
└─────────────────┴───────────────────────────────────┘
```

- **First run**: Agent path (LLM-driven, ~5-30s per step)
- **Subsequent runs**: Script path (deterministic, <1s per step)
- **On script failure**: Automatically falls back to agent path
- **Adaptive caching**: Agent success → auto-generate script for next run

## Automation API

### CDP (Chrome DevTools Protocol)

Connect Playwright or Puppeteer to any running profile:

```python
from playwright.async_api import async_playwright

async with async_playwright() as pw:
    browser = await pw.chromium.connect_over_cdp(
        "http://localhost:8080/api/profiles/<profile-id>/cdp"
    )
    page = browser.contexts[0].pages[0]
    await page.goto("https://example.com")
```

### Workflow API

```bash
# Create a workflow
curl -X POST http://localhost:8080/api/workflows \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Login Test",
    "profile_id": "<profile-id>",
    "run_with": "agent",
    "ai_fallback": true,
    "adaptive_caching": true,
    "definition": {
      "blocks": [{
        "label": "Navigate & Login",
        "block_type": "task",
        "url": "https://example.com/login",
        "navigation_goal": "Login with credentials",
        "max_steps": 15
      }]
    }
  }'

# Run the workflow
curl -X POST http://localhost:8080/api/workflows/<workflow-id>/run

# Check run status
curl http://localhost:8080/api/workflow-runs/<run-id>
```

### Health Check & Metrics

```bash
# Deep health check
curl http://localhost:8080/api/status/health

# Prometheus metrics
curl http://localhost:8080/metrics
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AUTH_TOKEN` | (none) | API/UI authentication token |
| `LOG_FORMAT` | `text` | Logging format: `text` or `json` |
| `LOG_LEVEL` | `INFO` | Logging level |
| `MAX_CONCURRENT_WORKFLOWS` | `10` | Max parallel workflows |
| `MAX_TOTAL_BROWSERS` | `20` | Max browser instances |
| `MAX_MEMORY_PER_BROWSER_MB` | `2048` | Memory limit per browser |
| `MAX_LLM_TOKENS_PER_TASK` | `200000` | Token limit per workflow task |
| `MAX_LLM_BUDGET_USD` | `50.0` | Total LLM budget cap (USD) |
| `LLM_PROVIDER` | `openai` | Primary LLM provider |
| `LLM_MODEL` | `gpt-4o` | Primary LLM model |
| `LLM_API_KEY` | (none) | LLM API key |
| `LLM_BASE_URL` | (none) | Custom LLM API base URL |
| `RATE_LIMIT_RPM` | `60` | API rate limit (requests/min) |
| `CDP_RATE_LIMIT_RPM` | `30` | CDP endpoint rate limit |
| `MEMORY_CHECK_INTERVAL` | `30` | Memory check interval (seconds) |

### Docker Compose

```yaml
services:
  manager:
    build: .
    ports:
      - "127.0.0.1:8080:8080"
    environment:
      - AUTH_TOKEN=your-secret-token
      - LOG_FORMAT=json
      - MAX_CONCURRENT_WORKFLOWS=10
    deploy:
      resources:
        limits:
          memory: 4g
          cpus: "2.0"
    restart: unless-stopped
```

## Detection Test Suite

Included `detection-test/` provides a comprehensive anti-detection verification page with 13 categories and 63+ checks:

- Browser Fingerprint (Canvas, WebGL, Audio, Fonts)
- Hardware & Device (GPU, Screen, Concurrency)
- Network (IP, Proxy, DNS)
- Automation Detection (WebDriver, CDP, Headless)
- Human Interaction (reCAPTCHA, Turnstile, hCaptcha)
- TLS & Headers

Deploy on a Windows Server (IIS) or any HTTP server to test your profiles.

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.12) |
| Frontend | React 19 + Tailwind CSS + Vite |
| Browser Viewer | noVNC (WebSocket VNC client) |
| VNC Server | KasmVNC + Xvnc |
| Database | SQLite |
| Browser Engine | [CloakBrowser](https://github.com/CloakHQ/CloakBrowser) (stealth Chromium) |
| LLM | OpenAI / Anthropic / DeepSeek (with fallback) |
| Monitoring | Prometheus-compatible metrics |

## Requirements

- Docker 20.10+ (for containerized deployment)
- ~2 GB disk (Docker image + CloakBrowser binary)
- ~512 MB RAM per running browser profile
- LLM API key (for Agent path; Script path works without LLM)

## Authentication

By default, no authentication is required. Set `AUTH_TOKEN` to protect the UI and API:

```bash
docker run -p 8080:8080 -v cloakprofiles:/data -e AUTH_TOKEN=your-secret-token cloakhq/cloakbrowser-manager
```

When `AUTH_TOKEN` is set:
- The web UI shows a login page
- API consumers pass `Authorization: Bearer <token>`
- VNC WebSocket connections are authenticated via login cookie
- `/api/status` remains unauthenticated (for Docker healthcheck)

> **Note**: The auth token is transmitted in cleartext over HTTP. For internet-facing deployments, use a reverse proxy with HTTPS (Caddy, nginx, Traefik).

## Remote Access

The container binds to localhost only. To access remotely:

```bash
ssh -L 8080:localhost:8080 your-server
```

Then open `http://localhost:8080`.

## License

- **This application** (source code) — MIT. See [LICENSE](LICENSE).
- **CloakBrowser binary** (compiled Chromium) — free to use, no redistribution. See [BINARY-LICENSE.md](BINARY-LICENSE.md).

## Contributing

Contributions are welcome. Please [open an issue](https://github.com/jamesyee0518-ai/BrowserFlow/issues) first to discuss what you'd like to change.

## Links

- **CloakBrowser** — [github.com/CloakHQ/CloakBrowser](https://github.com/CloakHQ/CloakBrowser)
- **Bug reports** — [GitHub Issues](https://github.com/jamesyee0518-ai/BrowserFlow/issues)
