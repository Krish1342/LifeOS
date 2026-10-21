import subprocess
import sys
import time
import webbrowser

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

AGENTS = [
    ("Orchestrator", "lifeos.agents.orchestrator.main:app", 8000),
    ("Calendar", "lifeos.agents.calendar.main:app", 8001),
    ("Email", "lifeos.agents.email.main:app", 8002),
    ("File", "lifeos.agents.file.main:app", 8003),
    ("Task", "lifeos.agents.task.main:app", 8004),
    ("Notification", "lifeos.agents.notification.main:app", 8005),
]


@click.group()
def cli():
    """LifeOS - Personal AI Operations Layer."""


@cli.command()
def doctor():
    """Run system diagnostics across all LifeOS subsystems."""
    import asyncio

    from lifeos.cli.doctor import run_diagnostics
    asyncio.run(run_diagnostics())


@cli.command()
def keygen():
    """Generate a secure 32-byte AES-256-GCM encryption key."""
    from lifeos.shared.crypto import TokenEncryption
    new_key = TokenEncryption.generate_key_b64()
    console.print(f"[bold green]Generated AES-256-GCM Key:[/bold green] {new_key}")
    console.print("Add this to your [bold].env[/bold] as [cyan]LIFEOS_ENCRYPTION_KEY=[/cyan]" + new_key)


@cli.command()
@click.argument("service", type=click.Choice(["calendar", "email", "drive", "clerk"]))
@click.option("--user-id", default="default_user", help="User ID for Clerk token synchronization")
def connect(service: str, user_id: str):
    """Initiate OAuth authorization for a Google service or synchronize via Clerk."""
    if service == "clerk":
        try:
            resp = httpx.post(
                "http://127.0.0.1:8000/api/auth/clerk/sync-tokens",
                json={"user_id": user_id, "provider": "oauth_google"},
                timeout=10.0
            )
            data = resp.json()
            console.print(f"Clerk token sync: {data.get('message', data.get('status'))}")
        except Exception as e:
            console.print(f"[red]Error synchronizing from Clerk: {e}[/red]")
        return

    service_map = {
        "calendar": "google_calendar",
        "email": "gmail",
        "drive": "google_drive"
    }
    target_service = service_map[service]
    url = f"http://127.0.0.1:8000/oauth/connect/{target_service}"
    console.print(f"[bold cyan]Opening authorization for {service}...[/bold cyan]")
    console.print(f"URL: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        console.print(f"Open link in browser: {url}")


@cli.command()
def up():
    """Start all 6 LifeOS agents as local FastAPI services."""
    console.print("[bold]Starting LifeOS agent cluster...[/bold]")
    processes = []
    try:
        for name, app_str, port in AGENTS:
            cmd = [
                sys.executable,
                "-m",
                "uvicorn",
                app_str,
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--log-level",
                "warning",
            ]
            p = subprocess.Popen(cmd)
            processes.append((name, p, port))
            console.print(f"  Started {name.lower()} agent on port {port}")

        console.print("[green]All agents running.[/green] Press Ctrl+C to stop.\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\nStopping agents...")
        for name, p, _ in processes:
            p.terminate()
            p.wait()
        console.print("All agents stopped.")


@cli.command()
def health():
    """Check connectivity and Agent Cards across all 6 agents."""
    url = "http://127.0.0.1:8000/api/health/all"
    try:
        resp = httpx.get(url, timeout=5.0)
        data = resp.json()
        table = Table(title="LifeOS Agent Cluster Health")
        table.add_column("Agent", style="bold")
        table.add_column("Port")
        table.add_column("Status")
        table.add_column("Skills")

        table.add_row("Orchestrator", "8000", "[green]online[/green]", "execute_command")
        for agent_name, info in data.get("domain_agents", {}).items():
            status_str = f"[green]{info['status']}[/green]" if info.get("status") == "online" else f"[red]{info.get('status')}[/red]"
            skills_str = ", ".join(info.get("skills", [])) or "none"
            port = info.get("url", "").split(":")[-1]
            table.add_row(agent_name.capitalize(), port, status_str, skills_str)

        console.print(table)
    except Exception as e:
        console.print(f"[red]Error contacting Orchestrator at {url}: {e}[/red]")
        console.print("[dim]Make sure the cluster is running via 'lifeos up'[/dim]")


@cli.command()
@click.argument("command_text")
@click.option("--yes", "-y", is_flag=True, help="Auto-approve pending write operations without prompting")
def run(command_text: str, yes: bool):
    """Execute a natural-language command through the Orchestrator."""
    url = "http://127.0.0.1:8000/api/command"
    console.print(f"[bold cyan]Dispatching instruction:[/bold cyan] '{command_text}'...")
    try:
        resp = httpx.post(url, json={"command": command_text, "auto_confirm": yes}, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        # Check if write confirmation is required
        if data.get("status") == "confirmation_required":
            console.print("\n[bold yellow]Confirmation Required[/bold yellow]")
            console.print(Panel(data.get("prompt", "Please approve pending actions:"), title="Action Approval"))
            
            table = Table(title="Pending Actions")
            table.add_column("#", style="dim")
            table.add_column("Action", style="bold")
            table.add_column("Details")

            for idx, action in enumerate(data.get("pending_actions", []), 1):
                act_name = action.get("action", "unknown")
                details = ", ".join(f"{k}: {v}" for k, v in action.items() if k != "action")
                table.add_row(str(idx), act_name, details)
            console.print(table)

            approved = click.confirm("\nApprove execution?", default=True)
            conf_resp = httpx.post(
                "http://127.0.0.1:8000/api/confirm",
                json={
                    "confirmation_id": data["confirmation_id"],
                    "approved": approved
                },
                timeout=30.0
            )
            conf_resp.raise_for_status()
            conf_data = conf_resp.json()
            if approved:
                console.print(f"[green]Approved:[/green] {conf_data.get('message')}")
            else:
                console.print(f"[yellow]Canceled:[/yellow] {conf_data.get('message')}")
            return

        # Regular completed output
        console.print(f"[green]Status:[/green] {data.get('status')}")
        if "briefing" in data:
            console.print(Panel(data["briefing"], title="Briefing"))
        elif "results" in data:
            console.print_json(data=data.get("results"))
    except Exception as e:
        console.print(f"[red]Execution failed: {e}[/red]")


@cli.group()
def tasks():
    """Manage LifeOS task board."""


@tasks.command("list")
@click.option("--status", "-s", type=click.Choice(["all", "open", "completed"]), default="all")
@click.option("--priority", "-p", type=click.Choice(["all", "high", "medium", "low"]), default="all")
def list_tasks(status: str, priority: str):
    """List tasks with optional status and priority filtering."""
    url = "http://127.0.0.1:8000/api/tasks"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        items = data.get("tasks", []) if isinstance(data, dict) else data

        if status != "all":
            items = [t for t in items if t.get("status") == status]
        if priority != "all":
            items = [t for t in items if t.get("priority") == priority]

        if not items:
            console.print("No matching tasks found.")
            return

        table = Table(title="Tasks")
        table.add_column("ID", style="dim")
        table.add_column("Status")
        table.add_column("Priority")
        table.add_column("Title", style="bold")
        table.add_column("Due Date")

        for t in items:
            status_style = "green" if t.get("status") == "completed" else "yellow"
            status_str = f"[{status_style}]{t.get('status', 'open')}[/{status_style}]"
            table.add_row(
                str(t.get("task_id", t.get("id", "")))[:8],
                status_str,
                t.get("priority", "medium"),
                t.get("title", ""),
                str(t.get("due_date") or "None"),
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching tasks: {e}[/red]")


@tasks.command("toggle")
@click.argument("task_id")
def toggle_task(task_id: str):
    """Toggle a task status between open and completed."""
    url = f"http://127.0.0.1:8000/api/tasks/{task_id}/toggle"
    try:
        resp = httpx.post(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        console.print(f"Task updated. Status: {data.get('status')}")
    except Exception as e:
        console.print(f"[red]Error toggling task: {e}[/red]")


@cli.group()
def schedule():
    """Manage automated recurring workflows."""


@schedule.command("list")
def list_schedules():
    """List active scheduled jobs."""
    url = "http://127.0.0.1:8000/api/schedules"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        items = resp.json()
        if not items:
            console.print("No active schedules.")
            return

        table = Table(title="Schedules")
        table.add_column("ID", style="dim")
        table.add_column("Command", style="bold")
        table.add_column("Interval (s)")
        table.add_column("Active")
        table.add_column("Runs")
        table.add_column("Last Run")

        for s in items:
            active_str = "[green]yes[/green]" if s.get("is_active") else "[red]no[/red]"
            table.add_row(
                s.get("id", "")[:8],
                s.get("command", ""),
                str(s.get("interval_seconds", 0)),
                active_str,
                str(s.get("total_runs", 0)),
                str(s.get("last_run", "Never")),
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching schedules: {e}[/red]")


@schedule.command("add")
@click.argument("command_text")
@click.option("--interval", "-i", type=int, default=3600, help="Interval in seconds (default: 3600)")
def add_schedule(command_text: str, interval: int):
    """Add a recurring scheduled command."""
    url = "http://127.0.0.1:8000/api/schedules"
    try:
        resp = httpx.post(url, json={"command": command_text, "interval_seconds": interval}, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        console.print(f"Schedule registered. ID: {data.get('id')}")
    except Exception as e:
        console.print(f"[red]Error creating schedule: {e}[/red]")


@schedule.command("remove")
@click.argument("schedule_id")
def remove_schedule(schedule_id: str):
    """Remove a recurring scheduled command."""
    url = f"http://127.0.0.1:8000/api/schedules/{schedule_id}"
    try:
        resp = httpx.delete(url, timeout=5.0)
        resp.raise_for_status()
        console.print(f"Schedule {schedule_id} removed.")
    except Exception as e:
        console.print(f"[red]Error deleting schedule: {e}[/red]")


@cli.command()
def audit():
    """Inspect privacy audit logs and leak-detection metrics."""
    url = "http://127.0.0.1:8000/api/audit"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        table = Table(title="Privacy Audit Log")
        table.add_column("Timestamp", style="dim")
        table.add_column("Event")
        table.add_column("Agent")
        table.add_column("Destination")
        table.add_column("Status")

        for row in data.get("logs", []):
            table.add_row(
                str(row.get("timestamp", ""))[:19],
                row.get("event", ""),
                row.get("agent", ""),
                row.get("destination", "local"),
                row.get("status", "ok"),
            )
        console.print(table)
    except Exception as e:
        console.print(f"[red]Error fetching audit log: {e}[/red]")


@cli.command()
def privacy():
    """View outbound network privacy status and cloud compliance."""
    url = "http://127.0.0.1:8000/api/privacy/status"
    try:
        resp = httpx.get(url, timeout=5.0)
        resp.raise_for_status()
        data = resp.json()
        console.print(Panel(
            f"Cloud LLM Requests Blocked: {data.get('cloud_llm_requests_blocked', 0)}\n"
            f"Third-Party Transmissions: {data.get('third_party_transmissions', 0)}\n"
            f"Local Ollama Executions: {data.get('local_ollama_executions', 0)}\n"
            f"Zero-Leakage Compliance: {data.get('compliance_rate', '100%')}",
            title="Privacy Compliance Status"
        ))
    except Exception as e:
        console.print(f"[red]Error fetching privacy status: {e}[/red]")


if __name__ == "__main__":
    cli()
