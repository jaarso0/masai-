"""Core runner — orchestrates the v3 parallel multi-agent pipeline."""

import asyncio
import os
import time
import traceback

from rich.columns import Columns
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from agents.backend import BackendAgent
from agents.devops import DevOpsAgent
from agents.docs import DocsAgent
from agents.frontend import FrontendAgent
from agents.orchestrator import OrchestratorAgent
from agents.qa import QAAgent
from core.models import AgentContext, AgentOutput, RevisionRequest, FileOutput, Task
from memory.store import save_decision, search_decisions

orchestrator = OrchestratorAgent()
backend_agent = BackendAgent()
frontend_agent = FrontendAgent()
qa_agent = QAAgent()
devops_agent = DevOpsAgent()
docs_agent = DocsAgent()

console = Console()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DISPLAY HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _show_communication(sender: str, receiver: str, message: str,
                        details: list[str] | None = None) -> None:
    header = f"[bold cyan]{sender}[/bold cyan] → [bold magenta]{receiver}[/bold magenta]"
    body = f"[white]{message}[/white]"
    if details:
        body += "\n" + "\n".join(f"  [dim]• {d}[/dim]" for d in details[:8])
        if len(details) > 8:
            body += f"\n  [dim]  ... and {len(details) - 8} more[/dim]"
    console.print(Panel(body, title=header, border_style="blue", padding=(0, 1)))


def _show_context_update(field: str, value: str) -> None:
    console.print(f"  [dim]Context updated:[/dim] [bold]{field}[/bold] [dim]← {value}[/dim]")


def _show_memory_panel(memory_context: str) -> None:
    if memory_context:
        console.print(Panel(
            f"[dim]{memory_context}[/dim]",
            title="[bold green] Shared Memory (loaded from ChromaDB)[/bold green]",
            border_style="green",
            padding=(0, 1),
        ))
    else:
        console.print("  [dim]No past decisions found in memory[/dim]")


def _show_context_snapshot(context: AgentContext) -> None:
    table = Table(
        title="Shared Context Snapshot",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
        padding=(0, 1),
    )
    table.add_column("Field", style="bold", width=22)
    table.add_column("Value", style="white")

    table.add_row("backend_notes", (context.backend_notes[:80] + "…") if len(context.backend_notes) > 80 else context.backend_notes or "—")
    table.add_row("api_contract", f"{len(context.backend_api_contract.splitlines())} endpoints" if context.backend_api_contract else "—")
    table.add_row("frontend_notes", (context.frontend_notes[:80] + "…") if len(context.frontend_notes) > 80 else context.frontend_notes or "—")
    table.add_row("decisions", f"{len(context.all_decisions)} recorded")
    table.add_row("qa_approved", "Yes" if context.qa_approved else "Not yet")
    table.add_row("revision_count", str(context.revision_count))

    console.print(table)


def _normalize_task_keys(tasks: dict, spec: str) -> dict:
    """Remap LLM-generated key variants to canonical keys."""
    canonical = ["backend", "frontend", "qa", "devops", "docs"]
    normalized = {}

    for key, task in tasks.items():
        lower = key.lower().replace(" ", "_").replace("-", "_")
        matched = False
        for canon in canonical:
            if canon in lower:
                normalized[canon] = task
                matched = True
                break
        if not matched:
            normalized[key] = task

    for canon in canonical:
        if canon not in normalized:
            normalized[canon] = Task(
                name=f"{canon} task",
                description=f"Generate {canon} component for: {spec}",
            )

    return normalized


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LIVE SIDE-BY-SIDE PARALLEL DISPLAY
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _make_agent_panel(name: str, status: str, detail: str = "",
                      color: str = "cyan") -> Panel:
    """Create a single agent status panel."""
    if status == "running":
        icon = "[yellow]⟳[/yellow]"
        border = "yellow"
        body = f"{icon} [yellow]Running...[/yellow]"
    elif status == "done":
        icon = "[green]✓[/green]"
        border = "green"
        body = f"{icon} [green]Complete[/green]"
        if detail:
            body += f"\n[dim]{detail}[/dim]"
    else:  # error
        icon = "[red]✗[/red]"
        border = "red"
        body = f"{icon} [red]Failed[/red]\n[dim]{detail}[/dim]"

    return Panel(
        body,
        title=f"[bold {color}]{name}[/bold {color}]",
        border_style=border,
        width=38,
        height=6,
        padding=(1, 2),
    )


def _make_parallel_display(panels: list[Panel]) -> Columns:
    """Arrange panels side-by-side."""
    return Columns(panels, equal=True, expand=True)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN PIPELINE
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def start(spec: str):

    console.print("\n[bold blue]━━━ masai v3 ━━━[/bold blue] Parallel Multi-Agent Build\n")

    # ── STEP 1: ORCHESTRATE ───────────────────────
    with console.status("[bold green]Orchestrator decomposing spec..."):
        task_list = await orchestrator.run(spec)

    task_list.tasks = _normalize_task_keys(task_list.tasks, spec)

    console.print(f"[green]✓[/green] Project: [bold]{task_list.project_name}[/bold]")

    task_details = [f"{k}: {v.name}" for k, v in task_list.tasks.items()]
    _show_communication("Orchestrator", "All Agents",
                        f"Decomposed spec into {len(task_list.tasks)} tasks",
                        task_details)

    # ── STEP 2: SHARED CONTEXT ────────────────────
    memory_context = search_decisions(spec)
    context = AgentContext(
        project_name=task_list.project_name,
        project_description=task_list.project_description,
        memory_decisions=memory_context,
    )
    _show_memory_panel(memory_context)
    console.print()

    # ── STEP 3: PARALLEL — Backend + Frontend Phase 1 ──
    console.print(f"\n[bold cyan]{'━' * 50}[/bold cyan]")
    console.print(f"[bold cyan]  PARALLEL: Backend + Frontend Phase 1[/bold cyan]")
    console.print(f"[bold cyan]{'━' * 50}[/bold cyan]\n")

    # State trackers for the live display
    backend_status = {"state": "running", "detail": ""}
    frontend_p1_status = {"state": "running", "detail": ""}

    async def _run_backend(task, ctx):
        try:
            result = await backend_agent.run(task, ctx)
            out, contract = result
            backend_status["state"] = "done"
            backend_status["detail"] = f"{len(out.files)} files, {len(contract.endpoints)} endpoints"
            return result
        except Exception as e:
            backend_status["state"] = "error"
            backend_status["detail"] = str(e)[:60]
            raise

    async def _run_frontend_p1(task, ctx):
        try:
            result = await frontend_agent.run_phase1(task, ctx)
            frontend_p1_status["state"] = "done"
            frontend_p1_status["detail"] = f"{len(result.files)} UI components"
            return result
        except Exception as e:
            frontend_p1_status["state"] = "error"
            frontend_p1_status["detail"] = str(e)[:60]
            raise

    # Live side-by-side display
    with Live(console=console, refresh_per_second=2) as live:
        tasks = asyncio.gather(
            _run_backend(task_list.tasks["backend"], context),
            _run_frontend_p1(task_list.tasks["frontend"], context),
        )

        # Update display while tasks are running
        while not tasks.done():
            panels = [
                _make_agent_panel("Backend", backend_status["state"],
                                  backend_status["detail"], "blue"),
                _make_agent_panel("Frontend P1", frontend_p1_status["state"],
                                  frontend_p1_status["detail"], "magenta"),
            ]
            live.update(_make_parallel_display(panels))
            await asyncio.sleep(0.5)

        # Final update
        panels = [
            _make_agent_panel("Backend", backend_status["state"],
                              backend_status["detail"], "blue"),
            _make_agent_panel("Frontend P1", frontend_p1_status["state"],
                              frontend_p1_status["detail"], "magenta"),
        ]
        live.update(_make_parallel_display(panels))

    backend_result, frontend_phase1 = await tasks
    backend_out, api_contract = backend_result

    # Update context with backend results
    context.backend_notes = backend_out.notes
    context.backend_api_contract = "\n".join(api_contract.endpoints)
    context.all_decisions.extend(backend_out.decisions)
    context.all_decisions.extend(frontend_phase1.decisions)

    _show_context_update("backend_notes", (backend_out.notes[:60] + "…") if len(backend_out.notes) > 60 else backend_out.notes)
    _show_context_update("all_decisions", f"+{len(backend_out.decisions) + len(frontend_phase1.decisions)} decisions")

    # Show API contract handoff
    _show_communication("Backend", "Frontend Phase 2",
                        f"API Contract ready: {len(api_contract.endpoints)} endpoints, auth={api_contract.auth_method}",
                        api_contract.endpoints)

    await asyncio.sleep(1)

    # ── STEP 4: FRONTEND PHASE 2 — Wire API ──────
    console.print(f"\n[bold cyan]  Frontend Phase 2: Wiring API calls[/bold cyan]\n")

    with console.status("[bold green]Frontend wiring API integration..."):
        frontend_out = await frontend_agent.run_phase2(
            task_list.tasks["frontend"], context, api_contract, frontend_phase1
        )
    context.frontend_notes = frontend_out.notes
    context.all_decisions.extend(frontend_out.decisions)

    console.print(f"[green]✓[/green] Frontend P2: {len(frontend_out.files)} files with API integration")
    _show_context_update("frontend_notes", (frontend_out.notes[:60] + "…") if len(frontend_out.notes) > 60 else frontend_out.notes)

    # Show what's going to QA
    frontend_files = [f.filename for f in frontend_out.files]
    backend_files = [f.filename for f in backend_out.files]
    _show_communication("Frontend + Backend", "QA",
                        f"Sending {len(backend_files)} backend + {len(frontend_files)} frontend files for review",
                        backend_files + frontend_files)

    await asyncio.sleep(2)

    # ── STEP 5: QA LOOP ───────────────────────────
    for cycle in range(2):
        console.print(f"\n[bold yellow]{'━' * 40}[/bold yellow]")
        console.print(f"[bold yellow]  QA Review Cycle {cycle + 1}/2[/bold yellow]")
        console.print(f"[bold yellow]{'━' * 40}[/bold yellow]")

        with console.status("[yellow]QA reviewing full system..."):
            qa_feedback = await qa_agent.review(
                task_list.tasks["qa"], context,
                backend_out, frontend_out, api_contract
            )

        if qa_feedback.approved:
            context.qa_approved = True
            _show_communication("QA", "All Agents",
                                "All checks passed — code approved!", [])
            break

        backend_issues, frontend_issues = qa_agent.split_feedback(qa_feedback)
        context.qa_issues = qa_feedback.issues
        context.revision_count += 1

        _show_communication("QA", "Backend + Frontend",
                            f"Found {len(qa_feedback.issues)} issues — revision required",
                            qa_feedback.issues)

        if backend_issues:
            _show_communication("QA", "Backend",
                                f"Sending RevisionRequest with {len(backend_issues)} fixes",
                                backend_issues)
            revision = RevisionRequest(
                target_agent="backend",
                issues=backend_issues,
                files_to_revise=[],
                instructions=f"Fix the {len(backend_issues)} QA issues listed.",
            )
            try:
                with console.status("[yellow]Backend revising..."):
                    backend_out, api_contract = await backend_agent.revise(
                        task_list.tasks["backend"], context, revision
                    )
                context.backend_api_contract = "\n".join(api_contract.endpoints)
                console.print(f"  [green]✓[/green] Backend revised — {len(backend_out.files)} files updated")
            except Exception as e:
                console.print(f"  [red]![/red] Backend revision failed (keeping original): {type(e).__name__}")
            await asyncio.sleep(2)

        if frontend_issues:
            _show_communication("QA", "Frontend",
                                f"Sending RevisionRequest with {len(frontend_issues)} fixes",
                                frontend_issues)
            revision = RevisionRequest(
                target_agent="frontend",
                issues=frontend_issues,
                files_to_revise=[],
                instructions=f"Fix the {len(frontend_issues)} QA issues listed.",
            )
            try:
                with console.status("[yellow]Frontend revising..."):
                    frontend_out = await frontend_agent.revise(
                        task_list.tasks["frontend"], context,
                        api_contract, revision
                    )
                console.print(f"  [green]✓[/green] Frontend revised — {len(frontend_out.files)} files updated")
            except Exception as e:
                console.print(f"  [red]![/red] Frontend revision failed (keeping original): {type(e).__name__}")
            await asyncio.sleep(2)

        await asyncio.sleep(2)

    else:
        console.print("[yellow]![/yellow] Max QA cycles reached — proceeding")

    # Show context snapshot before final steps
    console.print()
    _show_context_snapshot(context)
    console.print()

    # ── STEP 6: PARALLEL — DevOps + Docs ──────────
    console.print(f"\n[bold cyan]{'━' * 50}[/bold cyan]")
    console.print(f"[bold cyan]  PARALLEL: DevOps + Docs[/bold cyan]")
    console.print(f"[bold cyan]{'━' * 50}[/bold cyan]\n")

    devops_status = {"state": "running", "detail": ""}
    docs_status = {"state": "running", "detail": ""}

    async def _run_devops(task, b_out, f_out):
        try:
            result = await devops_agent.run(task, b_out, f_out)
            devops_status["state"] = "done"
            devops_status["detail"] = f"{len(result.files)} config files"
            return result
        except Exception as e:
            devops_status["state"] = "error"
            devops_status["detail"] = type(e).__name__
            return AgentOutput(
                agent_name="devops", files=[], decisions=["DevOps skipped"], notes="skipped"
            )

    async def _run_docs(task, b_out, f_out, ctx):
        try:
            placeholder = AgentOutput(
                agent_name="devops", files=[], decisions=[], notes="parallel"
            )
            result = await docs_agent.run(task, b_out, f_out, placeholder, ctx)
            docs_status["state"] = "done"
            docs_status["detail"] = f"{len(result.files)} doc files"
            return result
        except Exception as e:
            docs_status["state"] = "error"
            docs_status["detail"] = type(e).__name__
            return AgentOutput(
                agent_name="docs", files=[], decisions=["Docs skipped"], notes="skipped"
            )

    with Live(console=console, refresh_per_second=2) as live:
        tasks2 = asyncio.gather(
            _run_devops(task_list.tasks["devops"], backend_out, frontend_out),
            _run_docs(task_list.tasks["docs"], backend_out, frontend_out, context),
        )

        while not tasks2.done():
            panels = [
                _make_agent_panel("DevOps", devops_status["state"],
                                  devops_status["detail"], "blue"),
                _make_agent_panel("Docs", docs_status["state"],
                                  docs_status["detail"], "magenta"),
            ]
            live.update(_make_parallel_display(panels))
            await asyncio.sleep(0.5)

        panels = [
            _make_agent_panel("DevOps", devops_status["state"],
                              devops_status["detail"], "blue"),
            _make_agent_panel("Docs", docs_status["state"],
                              docs_status["detail"], "magenta"),
        ]
        live.update(_make_parallel_display(panels))

    devops_out, docs_out = await tasks2

    # ── STEP 7: PERSIST MEMORY ────────────────────
    for decision in context.all_decisions:
        save_decision("build", decision)

    console.print(Panel(
        f"[green]{len(context.all_decisions)} decisions saved to ChromaDB[/green]\n"
        + "\n".join(f"  [dim]• {d}[/dim]" for d in context.all_decisions[:6])
        + (f"\n  [dim]  ... and {len(context.all_decisions) - 6} more[/dim]"
           if len(context.all_decisions) > 6 else ""),
        title="[bold green] Memory Persisted[/bold green]",
        border_style="green",
        padding=(0, 1),
    ))

    # ── STEP 8: WRITE OUTPUT ──────────────────────
    write_output(
        task_list.project_name,
        backend_out, frontend_out, devops_out, docs_out,
    )

    total = sum(
        len(o.files)
        for o in [backend_out, frontend_out, devops_out, docs_out]
    )

    console.print(f"""
[bold green]{'━' * 44}
  Build Complete!
{'━' * 44}[/bold green]

  Project    : [bold]{task_list.project_name}[/bold]
  Files      : {total} generated
  QA cycles  : {context.revision_count}
  QA status  : {"[green]Approved[/green]" if context.qa_approved else "[yellow]Max cycles reached[/yellow]"}
  Decisions  : {len(context.all_decisions)} saved to memory
  Output     : [bold]output/{task_list.project_name}/[/bold]
    """)


def write_output(project_name: str, *agent_outputs):
    """Write all files to output/{project_name}/"""
    base = f"output/{project_name}"
    for agent_out in agent_outputs:
        if agent_out.agent_name in ("backend", "frontend"):
            folder = f"{base}/{agent_out.agent_name}"
        else:
            folder = base
        for f in agent_out.files:
            path = os.path.join(folder, f.filename)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as fp:
                fp.write(f.code)
