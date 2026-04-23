"""Pydantic v2 data models for the masai multi-agent system."""

from pydantic import BaseModel, Field


class Task(BaseModel):
    """A single task assigned to a specialist agent."""
    name: str
    description: str
    context: str = ""  # memory injected before agent runs


class TaskList(BaseModel):
    """The orchestrator's output: a full project decomposition."""
    project_name: str
    project_description: str
    required_agents: list[str] = Field(
        description="List of agent keys that are actually needed for this project. "
        "Possible values: backend, frontend, qa, devops, docs."
    )
    tasks: dict[str, Task]  # only keys listed in required_agents


class FileOutput(BaseModel):
    """A single generated file with its path and content."""
    filename: str  # e.g. "app.py", "src/App.jsx"
    code: str  # full file content


class AgentOutput(BaseModel):
    """Output from any specialist agent."""
    agent_name: str
    files: list[FileOutput]
    decisions: list[str]  # architectural choices made
    notes: str  # summary for next agent


class QAFeedback(BaseModel):
    """Output from the QA agent."""
    approved: bool
    issues: list[str]  # list of specific problems found
    revised_files: list[FileOutput]  # fixed files if approved=False


class AgentContext(BaseModel):
    """
    Shared context object passed through the entire pipeline.
    Created once in runner.py and mutated as each agent completes.
    Later agents see everything earlier agents produced.
    """
    project_name: str
    project_description: str
    memory_decisions: str = ""        # from ChromaDB at build start
    backend_notes: str = ""           # set after backend runs
    backend_api_contract: str = ""    # newline-separated endpoint list
    frontend_notes: str = ""          # set after frontend runs
    frontend_api_needs: str = ""      # endpoints frontend expects
    qa_issues: list[str] = []         # issues QA found this cycle
    qa_approved: bool = False         # whether QA signed off
    revision_count: int = 0           # how many QA cycles completed
    all_decisions: list[str] = []     # every decision by every agent


class RevisionRequest(BaseModel):
    """
    QA sends this to Backend or Frontend when issues are found.
    Contains only what that specific agent needs to fix.
    """
    target_agent: str                 # "backend" or "frontend"
    issues: list[str]                 # specific problems to fix
    files_to_revise: list[str]        # filenames that need changes
    instructions: str                 # plain english fix instructions


class APIContract(BaseModel):
    """
    Backend publishes this after generating code.
    Frontend consumes it so it knows exactly what endpoints exist.
    """
    endpoints: list[str]
    # format each as: "POST /api/auth/login" or "GET /api/todos/{id}"
    base_url: str = "http://localhost:8000"
    auth_method: str                  # "JWT", "session", or "none"
    notes: str                        # anything frontend should know
