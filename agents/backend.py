"""Backend agent — generates FastAPI backend code."""

import asyncio

from agents.base import BaseAgent
from core.models import AgentContext, AgentOutput, APIContract, RevisionRequest, Task

SYSTEM_PROMPT = (
    "You are a backend engineer. Write complete, runnable FastAPI code. "
    "Include error handling, Pydantic models, CORS. No placeholders or TODOs.\n"
    "IMPORTANT: The 'code' field in each file must contain the raw, ready-to-save "
    "file content — NOT JSON-escaped, NOT wrapped in quotes. Write it exactly as "
    "it should appear in the actual file."
)

API_EXTRACT_SYSTEM = (
    "You are a technical architect. Extract a precise API contract "
    "from the backend code provided. List every HTTP endpoint with "
    "its exact method and path. Be exhaustive — the frontend team "
    "will use this list as their only reference."
)


class BackendAgent(BaseAgent):
    """Generates a complete FastAPI backend."""

    async def run(self, task: Task,
                  context: AgentContext) -> tuple[AgentOutput, APIContract]:
        user_prompt = (
            f"Project: {context.project_description}\n"
            f"Your task: {task.description}\n\n"
            + (f"Relevant past decisions:\n{context.memory_decisions}\n\n"
               if context.memory_decisions else "")
            + (f"QA issues to fix from previous cycle:\n"
               + "\n".join(context.qa_issues) + "\n\n"
               if context.qa_issues else "")
            + "Generate complete, production-ready FastAPI backend code.\n"
              "No placeholders. No TODOs. No '...' in any file."
        )

        output: AgentOutput = await self.call(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=AgentOutput,
        )

        # Extract API contract from generated code
        code_summary = str([
            f"{f.filename}: {f.code[:500]}" for f in output.files
        ])
        api_contract: APIContract = await self.call(
            system_prompt=API_EXTRACT_SYSTEM,
            user_prompt=f"Extract the API contract from this backend code:\n{code_summary}",
            response_model=APIContract,
        )

        self.save_to_memory(output.decisions, "backend")
        return (output, api_contract)

    async def revise(self,
                     task: Task,
                     context: AgentContext,
                     revision: RevisionRequest) -> tuple[AgentOutput, APIContract]:
        """
        Called when QA sends back issues.
        Fix ONLY what is listed. Return updated files.
        """
        issues_text = "\n".join(f"- {i}" for i in revision.issues[:5])

        user_prompt = (
            f"Fix these QA issues in the backend:\n{issues_text}\n\n"
            "Rules: Return ONLY changed files. Keep code minimal and clean. "
            "No placeholders. No TODOs. Use simple string literals."
        )

        output: AgentOutput = await self.call(
            system_prompt=(
                "You are a backend engineer applying targeted fixes. "
                "Return only the files that need changes. Keep code short and clean. "
                "IMPORTANT: The 'code' field must contain raw file content, not JSON-escaped strings."
            ),
            user_prompt=user_prompt,
            response_model=AgentOutput,
        )

        # Re-extract API contract from revised code
        api_contract: APIContract = await self.call(
            system_prompt="Extract a precise API contract listing every HTTP endpoint with method and path.",
            user_prompt=f"Backend files: {[f.filename for f in output.files]}",
            response_model=APIContract,
        )

        self.save_to_memory(
            [f"Revision {context.revision_count}: {i}" for i in revision.issues],
            "backend",
        )
        return (output, api_contract)
