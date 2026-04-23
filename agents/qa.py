"""QA agent — reviews backend and frontend code as a system."""

import asyncio

from agents.base import BaseAgent
from core.models import (Task, AgentContext, AgentOutput,
                         QAFeedback, APIContract)


class QAAgent(BaseAgent):
    """Reviews backend and frontend code, producing QAFeedback."""

    async def review(self,
                     task: Task,
                     context: AgentContext,
                     backend_output: AgentOutput,
                     frontend_output: AgentOutput,
                     api_contract: APIContract) -> QAFeedback:

        backend_files_summary = "\n".join([
            f"=== {f.filename} ===\n{f.code}"
            for f in backend_output.files
        ])

        frontend_files_summary = "\n".join([
            f"=== {f.filename} ===\n{f.code}"
            for f in frontend_output.files
        ])

        system_prompt = (
            "You are a strict senior QA engineer and security reviewer. "
            "You review backend and frontend as a system.\n\n"
            "Check for ALL of the following:\n"
            "1. API contract violations — frontend calling endpoints that "
            "don't exist in the backend\n"
            "2. Data shape mismatches — frontend expects fields backend "
            "doesn't return\n"
            "3. Auth inconsistencies — frontend sends auth differently than "
            "backend expects\n"
            "4. Missing error handling — unhandled promise rejections, "
            "unhandled exceptions, missing try/catch\n"
            "5. Security issues — hardcoded secrets, missing input "
            "validation, unprotected routes, SQL injection risks\n"
            "6. Incomplete code — any TODO, placeholder, or '...' in files\n"
            "7. Broken imports — importing files or modules that don't exist\n\n"
            "For each issue specify:\n"
            "- Owner: 'backend' or 'frontend' at the START of the string\n"
            "- Filename\n"
            "- Exact problem\n"
            "- Exact fix required\n\n"
            "Format each issue exactly like:\n"
            "'backend: routers/auth.py — /login returns 200 on bad password, "
            "should return 401 with message field'\n\n"
            "If you find NO issues, set approved=True and issues=[]."
        )

        user_prompt = (
            "Review this full-stack project.\n\n"
            f"API Contract (source of truth):\n"
            + "\n".join(api_contract.endpoints) + "\n"
            f"Auth: {api_contract.auth_method}\n\n"
            f"BACKEND CODE:\n{backend_files_summary}\n\n"
            f"FRONTEND CODE:\n{frontend_files_summary}\n\n"
            f"This is revision cycle {context.revision_count}.\n"
            + ("This code has already been revised once — be thorough."
               if context.revision_count > 0 else "")
        )

        feedback: QAFeedback = await self.call(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model=QAFeedback,
        )
        return feedback

    def split_feedback(self,
                       feedback: QAFeedback) -> tuple[list[str], list[str]]:
        """
        Split issues into backend_issues and frontend_issues.
        Each issue string starts with 'backend:' or 'frontend:'.
        Anything that doesn't match defaults to backend.
        """
        backend_issues = []
        frontend_issues = []

        for issue in feedback.issues:
            lower = issue.lower()
            if lower.startswith("frontend"):
                frontend_issues.append(issue)
            else:
                backend_issues.append(issue)

        return backend_issues, frontend_issues
