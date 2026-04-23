"""Orchestrator agent — decomposes a project spec into tasks."""

from agents.base import BaseAgent
from core.models import TaskList

VALID_AGENTS = {"backend", "frontend", "qa", "devops", "docs"}

SYSTEM_PROMPT = (
    "You are a software architect. Analyze the project spec and decide which "
    "specialist agents are actually needed. Not every project requires all agents.\n\n"
    "Available agents:\n"
    "  - backend: For server-side logic, APIs, databases, authentication, etc.\n"
    "  - frontend: For UI/UX, HTML/CSS/JS, React, templates, static pages, etc.\n"
    "  - qa: For testing strategies, test files, quality checks.\n"
    "  - devops: For Docker, CI/CD, deployment configs, cloud infrastructure.\n"
    "  - docs: For documentation, READMEs, API docs.\n\n"
    "Guidelines for deciding which agents to include:\n"
    "  - A simple static HTML/CSS page only needs 'frontend' and 'docs'.\n"
    "  - A frontend-only project (no server) does NOT need 'backend' or 'devops'.\n"
    "  - A small script or single-file project does NOT need 'devops'.\n"
    "  - Only include 'devops' if the project genuinely needs containerisation, "
    "CI/CD, or cloud deployment.\n"
    "  - Only include 'backend' if there is actual server-side logic required.\n"
    "  - Only include 'qa' if the project is complex enough to benefit from tests.\n"
    "  - Always include 'docs'.\n\n"
    "Be specific and detailed in each task description."
)


class OrchestratorAgent(BaseAgent):
    """Breaks a raw user spec into a TaskList."""

    async def run(self, spec: str) -> TaskList:
        user_prompt = (
            f"Spec: {spec}\n\n"
            "Decide which agents are needed for this project. Only include agents "
            "that are truly necessary — do NOT include agents just for the sake of it.\n"
            "Set 'required_agents' to a list of the agent keys you chose.\n"
            "Then create tasks ONLY for those agents.\n"
            "Generate a snake_case project_name. Each task needs a name and "
            "description (2-3 sentences min)."
        )

        task_list: TaskList = await self.call(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=TaskList,
        )

        # Ensure required_agents only contains valid keys and matches tasks
        task_list.required_agents = [
            a for a in task_list.required_agents if a in VALID_AGENTS
        ]

        self.save_to_memory(
            [
                f"Project '{task_list.project_name}': {task_list.project_description}",
                f"Required agents: {', '.join(task_list.required_agents)}",
            ],
            agent_name="orchestrator",
        )

        return task_list
