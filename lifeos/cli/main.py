import os
import sys
import subprocess
import time
import click
import httpx
from rich.console import Console
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
    pass


@cli.command()
def keygen():
    """Generate a secure 32-byte AES-256-GCM encryption key."""
    from lifeos.shared.crypto import TokenEncryption
    new_key = TokenEncryption.generate_key_b64()
    console.print(f"[bold green]Generated AES-256-GCM Key:[/bold green] {new_key}")
    console.print("Add this to your [bold].env[/bold] as [cyan]LIFEOS_ENCRYPTION_KEY=[/cyan]" + new_key)


@cli.command()
def up():
    """Start all 6 LifeOS agents as local FastAPI services."""
    console.print("[bold cyan]🚀 Starting LifeOS Agent Cluster...[/bold cyan]")
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
            console.print(f"  [green]✓[/green] Started {name} Agent on port [bold]{port}[/bold]")

        console.print("\n[bold green]All agents started successfully.[/bold green] Press Ctrl+C to stop.\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Stopping agents...[/yellow]")
        for name, p, _ in processes:
            p.terminate()
            p.wait()
        console.print("[green]All agents stopped.[/green]")


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
def run(command_text: str):
    """Execute a natural-language command through the Orchestrator."""
    url = "http://127.0.0.1:8000/api/command"
    console.print(f"[bold cyan]Dispatching instruction:[/bold cyan] '{command_text}'...")
    try:
        resp = httpx.post(url, json={"command": command_text}, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()
        console.print(f"[bold green]Status:[/bold green] {data.get('status')}")
        console.print(f"[bold]Agents Contacted:[/bold] {', '.join(data.get('agents_contacted', []))}")
        console.print("\n[bold]Results:[/bold]")
        console.print_json(data=data.get("results"))
    except Exception as e:
        console.print(f"[red]Execution failed: {e}[/red]")


if __name__ == "__main__":
    cli()
