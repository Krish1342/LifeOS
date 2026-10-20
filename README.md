# LifeOS

> Personal AI operations layer coordinating everyday services (Calendar, Email, Drive, Tasks, Slack) via Google's Agent2Agent (A2A) protocol.

## Architecture

LifeOS is built with a multi-agent spin-off pattern:
- **Orchestrator Agent** (`:8000`) decomposes user requests and coordinates domain agents.
- **Calendar Agent** (`:8001`) manages Google Calendar read/write operations.
- **Email Agent** (`:8002`) handles Gmail interactions, summarization, and action-item extraction.
- **File Agent** (`:8003`) handles Google Drive organization, moving, and searching.
- **Task Agent** (`:8004`) maintains internal task tracking in Supabase Postgres.
- **Notification Agent** (`:8005`) delivers messages and alerts to Slack channels/DMs.

All agents communicate strictly over Google's **A2A protocol** (JSON-RPC 2.0).

## Hard Security Guarantees
- **No confidential user data to cloud LLMs**: All private email, file, and schedule operations run locally on Ollama (Llama 3.1 8B / Phi-3 mini).
- **Per-agent token scoping**: Domain agents hold only their specific service credentials.
- **Outbound HTTP sandboxing**: `ScopedHTTPClient` enforces domain whitelisting per agent.
- **Tokens encrypted at rest**: OAuth refresh tokens are encrypted using AES-256-GCM.
- **Free-tier cloud database**: State and audit trails persist in Supabase Postgres free tier.

## Getting Started

```bash
# 1. Setup virtual environment & dependencies
uv venv
.\.venv\Scripts\activate
uv pip install -e ".[dev]"

# 2. Configure environment variables
cp .env.example .env
lifeos keygen  # Generate and copy LIFEOS_ENCRYPTION_KEY to .env

# 3. Launch Agent Cluster
lifeos up

# 4. In another terminal, verify agent health
lifeos health

# 5. Dispatch a command
lifeos run "Summarize my week"
```
