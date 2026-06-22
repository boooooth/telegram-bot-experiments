<!-- GSD:project-start source:PROJECT.md -->

## Project

**Telegram AI Bot**

A public Telegram bot that acts as a general-purpose AI assistant. A user sends a text message, the bot forwards it to the OpenAI (ChatGPT) API, and the reply is sent straight back in the chat. It's for anyone on Telegram who wants quick AI answers without leaving the app.

**Core Value:** Send a message in Telegram, get a useful LLM reply back — reliably, 24/7.

### Constraints

- **Architecture**: Bot calls an LLM provider (OpenAI by default) via LiteLLM — model and API key configurable via `LLM_MODEL` and `LLM_API_KEY` env vars.
- **Packaging**: Docker-containerized so the same image runs locally and on the server.
- **Hosting**: Linux VPS using polling — no public URL, HTTPS, or domain required.
- **Delivery**: CI/CD via GitHub Actions deploying to the server on push to `main`.
- **Dependencies**: Telegram Bot API token; LLM API key (OpenAI by default).
- **Cost**: Public access + no usage caps = unbounded LLM spend risk; accepted for v1.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->

## Technology Stack

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12 (3.10+ required) | Implementation language | User already has Python 3.12/3.14 installed and prior polling-bot experience. Python is the dominant ecosystem for both Telegram bots and LLM SDKs — official, mature, first-party SDKs exist for OpenAI, Anthropic, and the Telegram Bot API. 3.12 is the sweet spot in 2026: fully supported by every dependency below, broad wheel availability, and a stable `slim` Docker image. (3.13/3.14 work too, but 3.12 has the widest battle-tested support.) |
| python-telegram-bot (PTB) | 22.7 | Telegram Bot API wrapper + polling loop | The de-facto standard async Telegram library. Built-in `Application.run_polling()` is exactly the locked delivery model — no domain/TLS needed. Handles long-polling, retries, graceful shutdown (SIGTERM/SIGINT, important for Docker), and update dispatch out of the box. Pure-async (asyncio), actively maintained, requires Python 3.10+. |
| LiteLLM | pinned | LLM call layer | Provides a unified async interface to LLM providers. The bot uses LiteLLM to call OpenAI (`gpt-4o-mini` by default) via `litellm.acompletion`. Switching providers is a config change (`LLM_MODEL`, `LLM_API_KEY`), not a code change. Pinned to a specific version for reproducible builds. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| python-dotenv | 1.x (latest) | Load `.env` in local dev | Local/dev parity only. Read `TELEGRAM_BOT_TOKEN`, `LLM_API_KEY`, `LLM_MODEL` from a `.env` file locally; in the container these come from real env vars / Docker `--env-file`. Keep it a dev convenience, not a runtime dependency for config. |
| (stdlib) `logging` | builtin | Structured logging | No third-party logging lib needed for v1. Use stdlib `logging` at INFO, log incoming chat IDs (not message bodies, for privacy/cost-debugging) and LLM errors. PTB integrates with it natively. |
| (stdlib) `asyncio` | builtin | Concurrency | PTB and LiteLLM are async; the LLM call site should be `async` (`litellm.acompletion`). No extra concurrency lib required. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Lint + format | Single fast tool replacing flake8 + black + isort. Add a minimal `ruff.toml`; run in CI before the build step. |
| Docker + docker compose | Packaging & dev/prod parity | Same image runs locally and on the server. A one-service `compose.yaml` on the server makes the deploy step (`docker compose pull && up -d`) trivial and gives you `restart: unless-stopped` for 24/7 uptime. |
| GitHub Actions | CI/CD | Build image, push to GHCR, SSH to server, pull + restart. See workflow sketch below. |

## Installation

# Core (pin in requirements.txt or pyproject)

# Dev dependencies

## LLM Call Structure (LiteLLM → OpenAI by default)

v1 calls LiteLLM from a small, self-contained module (`openai_client.py`) — **no `LLMProvider` Protocol, no factory, no `llm/` package of providers.** The handler builds a one-shot prompt, calls `litellm.acompletion` with the configured model and API key, and returns the text. LiteLLM is pinned to a specific version for reproducible builds. Provider is OpenAI by default; switching is a config change (`LLM_MODEL`, `LLM_API_KEY` env vars), not a code change.

## Docker Base Image

- `slim` gives glibc compatibility (prebuilt wheels for httpx/cryptography "just work"), active security patches, and a ~40MB base — the documented default choice for Python apps in 2026.
- `PYTHONUNBUFFERED=1` so logs reach Docker/journald immediately.
- Rely on PTB's built-in signal handling for graceful shutdown; pair with `restart: unless-stopped` in compose for 24/7 uptime.

## GitHub Actions → Linux VPS (push to `main`)

- **Registry: GHCR (`ghcr.io`)** — free for the repo, authenticated with the built-in `GITHUB_TOKEN`, no extra cloud-specific container registry billing. The server pulls with a read-only PAT/`GITHUB_TOKEN`.
- **SSH: `appleboy/ssh-action@v1`** — the standard action for "run these commands on my server." Use an **ED25519** deploy key (RSA is rejected on some modern sshd configs).
- Secrets needed: `SERVER_HOST`, `SERVER_USER`, `SERVER_SSH_KEY`. Provider/API keys live in an `.env` file on the server referenced by `compose.yaml` (never baked into the image).

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| python-telegram-bot 22.7 | aiogram 3.x | aiogram is excellent and slightly more modern in API; choose it if you prefer its router/filter style. PTB wins here on the user's prior familiarity and `run_polling()` simplicity. Either is a defensible standard. |
| python-telegram-bot 22.7 | pyTelegramBotAPI (telebot) | Simpler but largely sync; weaker fit for async LLM calls. Use only for trivial sync scripts. |
| LiteLLM (OpenAI default) | Direct `openai` SDK | Use the direct `openai` SDK only if you never need to switch providers and want one fewer dependency. LiteLLM is used here because it enables provider flexibility via config (`LLM_MODEL`, `LLM_API_KEY`) without code changes. |
| GHCR | Cloud-specific container registry | Use a provider registry if you want registry and server in one vendor/VPC or hit GHCR rate/visibility limits. GHCR is cheaper and simpler for a single private repo. |
| `appleboy/ssh-action` + compose | Managed platform (PaaS) | A managed platform removes server management but costs more and was explicitly declined in favor of a Linux VPS with full control. |
| `python:3.12-slim` | `python:3.12-alpine` | Alpine only if image size is critical AND you have no glibc-only wheels. For Python it routinely breaks/recompiles wheels (musl libc) — not worth it here. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Webhook mode / Flask/FastAPI front | Requires public URL, TLS, domain; contradicts locked polling decision | PTB `Application.run_polling()` |
| `python:3.12-alpine` | musl libc breaks/recompiles many Python wheels; slow, fragile builds | `python:3.12-slim` |
| Conversation/history storage (Redis, DB) | One-shot replies are locked scope; adds infra | Stateless handler; no persistence |
| Pinning `httpx` yourself | All three SDKs bring a compatible `httpx`; manual pins cause resolver conflicts | Let SDKs manage it transitively |
| Baking API keys into the Docker image | Leaks secrets into image layers/registry | `.env` on server via compose `env_file`; GH Actions secrets for SSH only |
| `latest` floating Python tag in Dockerfile | Non-reproducible builds | Pin `python:3.12-slim` |

## Stack Patterns by Variant

- LiteLLM is already in use — switching providers (e.g. Anthropic, Gemini) is a config change: update `LLM_MODEL` and `LLM_API_KEY`. No code changes required.
- Add PTB's `[rate-limiter]` extra (aiolimiter) and/or a per-user throttle in the handler. Out of scope for v1 but the cleanest place to add it is the handler layer, not the OpenAI call site.
- Switch to webhook mode — PTB supports it via the `[webhooks]` extra (tornado), but this then requires the domain/TLS the project deliberately avoided.

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| python-telegram-bot 22.7 | Python 3.10–3.14 | Async; needs 3.10+. 3.12 recommended. |
| LiteLLM (pinned) | Python 3.8+ | Async via `litellm.acompletion`; pulls in `openai` as a transitive dep — do not pin `openai` separately. |
| PTB + LiteLLM | shared `httpx`/`anyio` | Both depend on `httpx`; do not pin `httpx` manually to avoid resolver conflicts. |
| docker/build-push-action | docker/login-action@v3 | v6 is current-stable and widely used; v7 + login-action@v4 also released in 2026. Either works; v6/v3 are the conservative, documented pairing. |

## Sources

- https://pypi.org/pypi/python-telegram-bot/json — confirmed v22.7, Python 3.10+, available extras (HIGH)
- https://pypi.org/pypi/openai/json — confirmed v2.41.1, Python 3.9–3.14 (HIGH)
- https://docs.python-telegram-bot.org/ — `Application.run_polling()` behavior, signal handling (HIGH)
- https://pythonspeed.com/articles/base-image-python-docker-images/ — slim vs alpine vs distroless guidance, Feb 2026 (MEDIUM-HIGH, cross-checked)
- https://oneuptime.com/blog/post/2026-02-08-how-to-choose-the-right-docker-base-image-for-your-application/view — base image selection (MEDIUM, cross-checked)
- https://www.digitalocean.com/community/questions/github-action-to-deploy-docker-image-from-github-packages — GHCR + appleboy/ssh-action deploy pattern (MEDIUM, cross-checked)
- https://github.com/docker/build-push-action — current action versions v6/v7 (MEDIUM)

<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:

- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
