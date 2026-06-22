# Telegram AI Bot

A Telegram bot that forwards your messages to an LLM and sends the reply back. Send a message, get an AI answer — no extra apps, no setup on the user side.

The bot has a sarcastic personality: correct and useful, but delivered with dry wit. Replies in whatever language you write in. (changable)

## How it works

**Direct message (private chat):**
1. User sends a text message
2. Bot shows a "Thinking..." animation immediately
3. As the LLM generates tokens, the bot streams them live into the chat draft
4. Once done, the full reply is pinned as a permanent message
5. Replies longer than 4096 chars are split into blocks — each block streams and pins independently

**Group mention (guest mode):**
1. User @mentions the bot in a group it's not a member of
2. Bot sends a single complete reply (no streaming — Telegram's guest API is one-shot only)
3. Replies are truncated to 4096 chars if the LLM generates more

Each message is answered independently — no conversation history is stored.

## Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12 |
| Telegram | python-telegram-bot 22.8 (polling) |
| LLM layer | LiteLLM 1.88.1 |
| Default model | OpenAI `gpt-4o-mini` |
| Container | Docker (`python:3.12-slim`) |
| CI/CD | GitHub Actions → GHCR → Linux VPS |

## Requirements

- A Telegram Bot token (from @BotFather)
- An OpenAI API key (or any LiteLLM-compatible provider key)
- Docker (for production) or Python 3.12+ (for local dev)

## Configuration

All config is via environment variables:

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | — | Token from BotFather |
| `LLM_API_KEY` | Yes | — | API key for the LLM provider |
| `LLM_MODEL` | No | `gpt-4o-mini` | LiteLLM model string |
| `ALLOWED_USER_IDS` | No | *(all users)* | Comma-separated Telegram user IDs; if set, all others are rejected |

Create a `.env` file for local use:

```
TELEGRAM_BOT_TOKEN=your-token-here
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
# ALLOWED_USER_IDS=123456789,987654321
```

## Running locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
python -m bot
```

## Running with Docker

```bash
docker compose up --build
```

The `compose.yaml` reads from `.env` and restarts the bot automatically (`restart: unless-stopped`).

## Deployment (Linux VPS)

The GitHub Actions workflow builds the image, pushes it to GHCR, then SSHs into the server and pulls the new image.

**Secrets required in GitHub:**

| Secret | Value |
|--------|-------|
| `SERVER_HOST` | VPS IP or hostname |
| `SERVER_USER` | SSH username |
| `SERVER_SSH_KEY` | ED25519 private key |

**On the server:**

```bash
mkdir ~/telegram-ai-bot && cd ~/telegram-ai-bot
# place .env and compose.yaml here
docker compose up -d
```

After that, every push to `main` that passes CI automatically deploys.

## Development

```bash
ruff check .        # lint
ruff format .       # format
mypy bot/           # type check
pytest              # tests
```

## Project structure

```
bot/
  config.py        # env var loading; fails fast at boot if required vars are missing
  handlers.py      # Telegram message and command handlers
  openai_client.py # LiteLLM call wrappers (complete + complete_stream)
  prompts.py       # system prompt, /start and /help text
  main.py          # app wiring and polling loop
tests/
Dockerfile
compose.yaml
```

## Switching LLM providers

LiteLLM handles provider routing. To switch from OpenAI, update `.env`:

```
# Anthropic
LLM_MODEL=anthropic/claude-3-5-haiku-20241022
LLM_API_KEY=sk-ant-...

# Gemini
LLM_MODEL=gemini/gemini-1.5-flash
LLM_API_KEY=AIza...

# Ollama (local)
LLM_MODEL=ollama/llama3.1:8b
LLM_API_KEY=ollama

# Cloudflare Workers AI
LLM_MODEL=cloudflare/@cf/meta/llama-3.1-8b-instruct
LLM_API_KEY=your-cloudflare-api-token
CLOUDFLARE_ACCOUNT_ID=your-account-id
```
