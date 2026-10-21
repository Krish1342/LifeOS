import os

import httpx
from rich.console import Console
from rich.table import Table

from lifeos.shared.crypto.encryption import TokenEncryption
from lifeos.shared.db.mongo import MongoDB
from lifeos.shared.http.client import ScopedHTTPClient, SecurityError

console = Console()


async def run_diagnostics() -> bool:
    """Runs system diagnostics across all LifeOS subsystems."""
    table = Table(title="LifeOS System Diagnostics")
    table.add_column("Subsystem", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    all_passed = True

    # 1. Encryption Key
    try:
        crypto = TokenEncryption()
        test_val = "diagnostic_token_payload"
        enc = crypto.encrypt(test_val)
        dec = crypto.decrypt(enc)
        if dec == test_val:
            table.add_row("AES-256 Encryption", "[green]PASS[/green]", "Key verified, GCM roundtrip valid")
        else:
            table.add_row("AES-256 Encryption", "[red]FAIL[/red]", "Decryption mismatch")
            all_passed = False
    except Exception as e:
        table.add_row("AES-256 Encryption", "[red]FAIL[/red]", str(e))
        all_passed = False

    # 2. MongoDB Database
    try:
        client = MongoDB.get_client()
        await client.admin.command("ping")
        db_name = MongoDB.get_db_name()
        table.add_row("MongoDB Database", "[green]PASS[/green]", f"Connected to '{db_name}'")
    except Exception as e:
        table.add_row("MongoDB Database", "[yellow]DEGRADED[/yellow]", f"Running in-memory fallback ({e})")

    # 3. HTTP Sandboxing Boundary
    try:
        sandbox = ScopedHTTPClient(allowed_hosts=["www.googleapis.com"])
        sandbox._verify_host("https://www.googleapis.com/calendar/v3/events")
        blocked = False
        try:
            sandbox._verify_host("https://unauthorized-domain.com")
        except SecurityError:
            blocked = True
        if blocked:
            table.add_row("Outbound Sandbox", "[green]PASS[/green]", "Domain allowlist enforced")
        else:
            table.add_row("Outbound Sandbox", "[red]FAIL[/red]", "Unauthorized domain was not blocked")
            all_passed = False
    except Exception as e:
        table.add_row("Outbound Sandbox", "[red]FAIL[/red]", str(e))
        all_passed = False

    # 4. Local Ollama LLM
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(f"{ollama_url}/api/tags")
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                table.add_row("Local LLM (Ollama)", "[green]PASS[/green]", f"Online, {len(models)} models available")
            else:
                table.add_row("Local LLM (Ollama)", "[yellow]OFFLINE[/yellow]", f"HTTP {resp.status_code}")
    except Exception:
        table.add_row("Local LLM (Ollama)", "[yellow]OFFLINE[/yellow]", f"Cannot connect to {ollama_url}")

    # 5. Agent Cluster Reachability
    ports = [
        ("Orchestrator", 8000),
        ("Calendar", 8001),
        ("Email", 8002),
        ("File", 8003),
        ("Task", 8004),
        ("Notification", 8005)
    ]
    online_count = 0
    async with httpx.AsyncClient(timeout=0.5) as client:
        for name, port in ports:
            try:
                resp = await client.get(f"http://127.0.0.1:{port}/health")
                if resp.status_code == 200:
                    online_count += 1
            except Exception:
                pass

    if online_count == len(ports):
        table.add_row("Agent Cluster", "[green]PASS[/green]", "All 6 agents active")
    elif online_count > 0:
        table.add_row("Agent Cluster", "[yellow]PARTIAL[/yellow]", f"{online_count}/{len(ports)} agents online")
    else:
        table.add_row("Agent Cluster", "[yellow]STANDBY[/yellow]", "No active daemon processes (start with 'lifeos up')")

    console.print(table)
    return all_passed
