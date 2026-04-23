"""Docs agent — generates project documentation."""

from agents.base import BaseAgent
from core.models import AgentContext, AgentOutput, Task
from memory.store import search_decisions

SYSTEM_PROMPT = (
    "You are a technical writer and senior engineer. You write clear, "
    "complete documentation that a junior developer could follow to run "
    "the project from scratch. You always include prerequisites, "
    "setup steps, environment variables, API endpoint reference, "
    "and architecture overview."
)


class DocsAgent(BaseAgent):
    """Generates README, API docs, and architecture docs."""

    async def run(
        self,
        task: Task,
        backend_output: AgentOutput,
        frontend_output: AgentOutput,
        devops_output: AgentOutput,
        context: AgentContext,
    ) -> AgentOutput:
        """Generate documentation files based on all previous agent outputs."""
        memory_context = search_decisions(task.description)

        # Build a summary of all outputs for the docs agent
        backend_summary = (
            f"Backend notes: {backend_output.notes}\n"
            f"Backend files: {', '.join(f.filename for f in backend_output.files)}\n"
        )
        frontend_summary = (
            f"Frontend notes: {frontend_output.notes}\n"
            f"Frontend files: {', '.join(f.filename for f in frontend_output.files)}\n"
        )
        devops_summary = (
            f"DevOps notes: {devops_output.notes}\n"
            f"DevOps files: {', '.join(f.filename for f in devops_output.files)}\n"
        )

        # Include backend code (especially routers) so docs agent can document API endpoints
        backend_code = ""
        for f in backend_output.files:
            if f.filename.endswith(".py"):
                backend_code += f"--- {f.filename} ---\n{f.code}\n\n"

        memory_section = ""
        if memory_context:
            memory_section = f"Context from memory:\n{memory_context}\n\n"
        context_section = ""
        if task.context:
            context_section = f"Additional context:\n{task.context}\n\n"

        decisions_text = "\n".join(f"- {d}" for d in context.all_decisions) if context.all_decisions else "- None recorded"
        qa_issues_text = "\n".join(context.qa_issues) if context.qa_issues else "None"

        user_prompt = (
            f"Task: {task.name}\n"
            f"Description: {task.description}\n\n"
            f"{memory_section}"
            f"{context_section}"
            f"Project components:\n{backend_summary}\n{frontend_summary}\n{devops_summary}\n"
            f"Backend code for API reference:\n{backend_code}\n"
            f"Architectural decisions made during this build:\n{decisions_text}\n\n"
            f"API endpoints (for API docs section):\n{context.backend_api_contract}\n\n"
            f"QA findings (document as known issues if any):\n{qa_issues_text}\n\n"
            f"Revision cycles completed: {context.revision_count}\n\n"
            "Generate complete project documentation. You MUST generate at minimum:\n"
            "- README.md (setup instructions, how to run, environment variables, "
            "architecture overview, Architecture Decisions section)\n"
            "- docs/api.md (every API endpoint with method, path, request body, response shape)\n"
            "- docs/architecture.md (component overview, data flow diagram in text, decisions made)\n\n"
            "Rules:\n"
            "- All documentation must be complete — no placeholders or TODOs.\n"
            "- README must include prerequisites, installation, running locally, and running with Docker.\n"
            "- README MUST include an 'Architecture Decisions' section listing every decision.\n"
            "- API docs must document every single endpoint from the backend.\n"
            "- Architecture docs must explain the data flow between frontend, backend, and any databases.\n"
            "- Include at least 3 decisions in the 'decisions' list.\n"
            "- Provide a 'notes' summary of the documentation coverage.\n"
        )

        result: AgentOutput = await self.call(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=AgentOutput,
        )

        # Save decisions to memory
        self.save_to_memory(result.decisions, agent_name="docs")

        return result

