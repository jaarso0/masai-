"""masai CLI — Multi-Agent Software AI."""

import asyncio
from collections import defaultdict

import typer
from rich.console import Console
from rich.table import Table

from core.runner import start

app = typer.Typer(
    name="masai",
    help="Multi-Agent Software AI — generate full-stack projects from natural language.",
    add_completion=False,
)
console = Console()


@app.command()
def build(
    spec: str = typer.Argument(..., help="Project description in natural language"),
) -> None:
    """Generate a full-stack project from a natural language description."""
    console.print("\n[bold blue]masai[/bold blue] — Multi-Agent Software AI\n")
    asyncio.run(start(spec))


@app.command()
def memory() -> None:
    """Show all stored architectural decisions."""
    from memory.store import list_all_decisions

    decisions = list_all_decisions()

    if not decisions:
        console.print("[yellow]No decisions stored yet.[/yellow]")
        return

    # Group by agent name
    grouped: dict[str, list[dict]] = defaultdict(list)
    for d in decisions:
        grouped[d["agent"]].append(d)

    for agent_name, agent_decisions in grouped.items():
        table = Table(title=f"Agent: {agent_name}", show_lines=True)
        table.add_column("Decision", style="white", ratio=3)
        table.add_column("Timestamp", style="dim", ratio=1)

        for d in agent_decisions:
            table.add_row(d["decision"], d["timestamp"])

        console.print(table)
        console.print()


if __name__ == "__main__":
    app()
