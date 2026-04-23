"""DevOps agent — generates Docker, CI/CD configs."""

from agents.base import BaseAgent
from core.models import AgentOutput, Task

SYSTEM_PROMPT = (
    "You are a DevOps engineer. Write production-ready Docker and CI configs. "
    "Use specific version tags, multi-stage Dockerfiles. No placeholders.\n"
    "IMPORTANT: The 'code' field in each file must contain the raw, ready-to-save "
    "file content — NOT JSON-escaped, NOT wrapped in quotes. Write it exactly as "
    "it should appear in the actual file."
)


class DevOpsAgent(BaseAgent):
    """Generates Docker, docker-compose, and CI/CD configs."""

    async def run(
        self,
        task: Task,
        backend_output: AgentOutput | None = None,
        frontend_output: AgentOutput | None = None,
    ) -> AgentOutput:
        context_lines = [f"Task: {task.name}\n{task.description}\n"]

        if backend_output:
            context_lines.append(
                f"Backend: {', '.join(f.filename for f in backend_output.files)}"
            )
        if frontend_output:
            context_lines.append(
                f"Frontend: {', '.join(f.filename for f in frontend_output.files)}"
            )

        user_prompt = (
            "\n".join(context_lines) + "\n\n"
            "Generate: Dockerfile (multi-stage), docker-compose.yml (volumes, "
            "healthchecks), .github/workflows/ci.yml, .dockerignore."
        )

        result: AgentOutput = await self.call(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=AgentOutput,
        )

        self.save_to_memory(result.decisions, agent_name="devops")
        return result

