# LifeOS

Personal operations layer coordinating everyday services (Google Calendar, Gmail, Google Drive, Microsoft 365, Tasks, Slack) via Google's Agent2Agent (A2A) protocol.

## Architecture

LifeOS uses a multi-agent spin-off pattern:
- **Orchestrator Agent** (`:8000`): Decomposes natural-language user commands, coordinates domain agents over A2A, manages write confirmation gates, and serves the Web Dashboard.
- **Calendar Agent** (`:8001`): Manages Google Calendar and Outlook Calendar read/write operations.
- **Email Agent** (`:8002`): Handles Gmail and Outlook message listing, local summarization, and action item extraction.
- **File Agent** (`:8003`): Manages Google Drive file listing, renaming, moving, and folder organization.
- **Task Agent** (`:8004`): Manages the internal task board in MongoDB Atlas (`tasks` collection).
- **Notification Agent** (`:8005`): Delivers notifications and confirmation requests to Slack channels/DMs.

All inter-agent communication uses Google's **A2A protocol** (JSON-RPC 2.0).

## Security & Zero-Cost Architecture
- **Zero private user data to cloud LLMs**: All private email bodies, event details, and file metadata are processed locally using Ollama (`llama3.1:8b-instruct-q4_K_M` or `phi3:mini`). Zero cloud AI bills.
- **Authentication & OAuth via Clerk**: Uses Clerk Free Tier (10,000 monthly active users, no credit card required) for session JWT validation and external Google/Microsoft OAuth token synchronization.
- **Database**: MongoDB Atlas M0 Free Tier (512 MB, 500 connections, no credit card required, no inactivity auto-pausing) or local MongoDB instance.
- **Per-agent token scoping**: Domain agents only hold credentials for their authorized service.
- **Outbound HTTP sandboxing**: `ScopedHTTPClient` enforces domain allowlisting per agent process.
- **AES-256-GCM encryption at rest**: OAuth access and refresh tokens are encrypted at application level before writing to MongoDB.
- **100% Free**: Operates entirely within permanent free tiers; no paid subscriptions or credit cards required.

## Setup & Running

### 1. Installation
```bash
uv venv
.\.venv\Scripts\activate
uv pip install -e ".[dev]"
```

### 2. Environment Configuration
```bash
cp .env.example .env
lifeos keygen  # Generate and copy LIFEOS_ENCRYPTION_KEY to .env

# Verify and initialize MongoDB collections and indexes
python scripts/init_mongo.py

# Run system diagnostic checks
lifeos doctor
```

### 3. Launching the Agent Cluster
```bash
# Start all 6 agents as local services
lifeos up

# Verify connectivity across all agents
lifeos health
```

### 4. Interfaces

#### Web Dashboard
Open `http://localhost:8000` in your browser for the Web UI:
- Natural-language command console
- Visual A2A agent dispatch pipeline
- Action confirmation dialog for write operations
- Interactive Task Board connected to MongoDB

#### CLI
```bash
# Execute natural language command
lifeos run "Summarize my week"

# Execute with interactive write confirmation
lifeos run "Create tasks from my unread emails"

# Auto-approve write operations (non-interactive)
lifeos run "Block focus time tomorrow morning" --yes

# OAuth connection
lifeos connect calendar
lifeos connect email
lifeos connect drive
```

#### Docker Deployment
```bash
docker-compose up --build
```

## API Reference

| Endpoint | Method | Description |
|---|---|---|
| `GET /` | `GET` | Serves Web Dashboard UI |
| `POST /api/command` | `POST` | Dispatches natural-language command |
| `POST /api/confirm` | `POST` | Approves or rejects pending write operations |
| `GET /api/command/stream` | `GET` | SSE stream for live command progress |
| `GET /api/tasks` | `GET` | Fetches open tasks from Task Agent |
| `POST /api/tasks/{task_id}/toggle` | `POST` | Toggles task completion |
| `GET /api/schedules` | `GET` | Lists automated recurring workflows |
| `POST /api/schedules` | `POST` | Schedules a recurring command |
| `DELETE /api/schedules/{id}` | `DELETE` | Deletes a scheduled job |
| `POST /api/agents/register` | `POST` | Dynamically registers an A2A agent card |
| `GET /api/audit` | `GET` | Fetches execution audit records |
| `GET /api/privacy/status` | `GET` | Audits zero-cloud-leakage compliance |
| `GET /api/health/all` | `GET` | Health checks all domain agents |

## Testing
```bash
pytest -v
```
