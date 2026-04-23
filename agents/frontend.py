"""Frontend agent — generates React + Vite frontend code in two phases."""

import asyncio

from agents.base import BaseAgent
from core.models import AgentContext, AgentOutput, APIContract, RevisionRequest, Task

PHASE1_SYSTEM = (
    "You are a frontend engineer. Generate the UI shell: React components, "
    "pages, routing, layouts, and CSS. Do NOT make any API/fetch calls yet — "
    "use placeholder data or empty state for now.\n"
    "IMPORTANT: The 'code' field must contain raw file content, not JSON."
)

PHASE2_SYSTEM = (
    "You are a frontend engineer wiring up API integration. You receive:\n"
    "1. The UI components already built (phase 1 output)\n"
    "2. The backend API contract with exact endpoints\n\n"
    "Your job: add fetch() calls, auth headers, loading states, error "
    "handling. Use ONLY the endpoints listed in the API contract.\n"
    "Return the COMPLETE updated files (not diffs).\n"
    "IMPORTANT: The 'code' field must contain raw file content, not JSON."
)


class FrontendAgent(BaseAgent):
    """Generates a complete React+Vite frontend in two phases."""

    async def run_phase1(self, task: Task,
                         context: AgentContext) -> AgentOutput:
        """Phase 1: Generate UI shell — components, pages, routing.
        No API calls. Runs in parallel with backend."""
        user_prompt = (
            f"Project: {context.project_description}\n"
            f"Task: {task.description}\n\n"
            + (f"Relevant past decisions:\n{context.memory_decisions}\n\n"
               if context.memory_decisions else "")
            + "Generate a complete React + Vite UI shell:\n"
              "- All pages and components\n"
              "- Routing setup\n"
              "- CSS styling\n"
              "- Form layouts\n"
              "- Use placeholder data or empty arrays for now\n"
              "- Do NOT add any fetch() or API calls yet\n"
              "No placeholders. No TODOs."
        )

        result: AgentOutput = await self.call(
            system_prompt=PHASE1_SYSTEM,
            user_prompt=user_prompt,
            response_model=AgentOutput,
        )

        self.save_to_memory(result.decisions, "frontend_phase1")
        return result

    async def run_phase2(self, task: Task,
                         context: AgentContext,
                         api_contract: APIContract,
                         phase1_output: AgentOutput) -> AgentOutput:
        """Phase 2: Wire up API calls using the backend's contract.
        Runs after backend completes and APIContract is available."""
        phase1_files = "\n".join(
            f"--- {f.filename} ---\n{f.code[:300]}"
            for f in phase1_output.files
        )

        user_prompt = (
            f"Project: {context.project_description}\n\n"
            f"Phase 1 files already built:\n{phase1_files}\n\n"
            f"Backend API contract — use ONLY these endpoints:\n"
            f"Base URL: {api_contract.base_url}\n"
            f"Auth: {api_contract.auth_method}\n"
            f"Endpoints:\n"
            + "\n".join(api_contract.endpoints) + "\n\n"
            f"Notes: {api_contract.notes}\n\n"
            "Now wire up all fetch() calls, auth headers, loading/error "
            "states. Return the COMPLETE updated files."
        )

        result: AgentOutput = await self.call(
            system_prompt=PHASE2_SYSTEM,
            user_prompt=user_prompt,
            response_model=AgentOutput,
        )

        self.save_to_memory(result.decisions, "frontend_phase2")
        return result

    async def revise(self,
                     task: Task,
                     context: AgentContext,
                     api_contract: APIContract,
                     revision: RevisionRequest) -> AgentOutput:
        """Fix only the issues QA flagged for frontend."""
        issues_text = "\n".join(f"- {i}" for i in revision.issues[:5])
        endpoints_text = "\n".join(api_contract.endpoints[:10])

        user_prompt = (
            f"Fix these QA issues in the frontend:\n{issues_text}\n\n"
            f"API endpoints (do not change):\n{endpoints_text}\n\n"
            "Rules: Return ONLY changed files. Keep code minimal and clean. "
            "No placeholders. No TODOs."
        )

        output: AgentOutput = await self.call(
            system_prompt=(
                "You are a frontend engineer applying targeted fixes. "
                "Return only the files that need changes. Keep code short and clean. "
                "IMPORTANT: The 'code' field must contain raw file content, not JSON-escaped strings."
            ),
            user_prompt=user_prompt,
            response_model=AgentOutput,
        )

        self.save_to_memory(
            [f"Revision {context.revision_count}: {i}" for i in revision.issues],
            "frontend",
        )
        return output
