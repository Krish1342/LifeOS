import os
import sys
import subprocess
import time
import webbrowser
import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

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
    pass


@cli.command()
def keygen():
    """Generate a secure 32-byte AES-256-GCM encryption key."""
    from lifeos.shared.crypto import TokenEncryption
    new_key = TokenEncryption.generate_key_b64()
    console.print(f"[bold green]Generated AES-256-GCM Key:[/bold green] {new_key}")
    console.print("Add this to your [bold].env[/bold] as [cyan]LIFEOS_ENCRYPTION_KEY=[/cyan]" + new_key)


@cli.command()
@click.argument("service", type=click.Choice(["calendar", "email", "drive"]))
def connect(service: str):
    """Initiate OAuth authorization for a Google service."""
    service_map = {
        "calendar": "google_calendar",
        "email": "gmail",
        "drive": "google_drive"
    }
    target_service = service_map[service]
    url = f"http://127.0.0.1:8000/oauth/connect/{target_service}"
    console.print(f"[bold cyan]Opening browser for {service.capitalize()} authorization...[/bold cyan]")
    console.print(f"URL: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        console.print(f"Please open this link in your browser: {url}")


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


if __name__ == "__main__":
    cli()
