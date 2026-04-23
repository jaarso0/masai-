# masai — Reference Guide

## Setup

```bash
# 1. Clone & install
cd masai
pip install groq instructor pydantic chromadb typer rich python-dotenv

# 2. Environment
# Create .env in project root:
GROQ_API_KEY=your_key_here

# 3. Run
python main.py build "your project description"
python main.py memory   # view stored decisions
```

## Project Structure

```
masai/
├── main.py              # CLI entry point (typer)
├── core/
│   ├── models.py        # All Pydantic models
│   └── runner.py        # Pipeline orchestration (v3)
├── agents/
│   ├── base.py          # BaseAgent — Groq + instructor (JSON mode)
│   ├── orchestrator.py  # Decomposes spec → TaskList
│   ├── backend.py       # Backend code + APIContract
│   ├── frontend.py      # Two-phase: UI shell → API wiring
│   ├── qa.py            # Reviews system, sends RevisionRequests
│   ├── devops.py        # Docker, CI/CD configs
│   └── docs.py          # README, API docs
├── memory/
│   └── store.py         # ChromaDB read/write (persists to .masai_memory/)
└── output/              # Generated projects land here
```

## Pipeline (v3)

```
Orchestrator
     │
     ▼
┌─────────┐  ┌─────────────┐
│ Backend │  │ Frontend P1  │   ← asyncio.gather (parallel)
└────┬────┘  └──────┬───────┘
     │ APIContract   │ UI shell
     ▼               ▼
     └──► Frontend P2 ◄──┘     ← wires fetch() using contract
              │
              ▼
         QA Review (max 2 cycles)
          │          │
     RevisionReq  RevisionReq   ← sent to backend/frontend if issues
          │          │
          ▼          ▼
     ┌────────┐  ┌──────┐
     │ DevOps │  │ Docs │      ← asyncio.gather (parallel)
     └────────┘  └──────┘
              │
              ▼
        Write to output/
```

## Data Models (`core/models.py`)

| Model | Purpose |
|-------|---------|
| `Task` | Single agent assignment (name + description) |
| `TaskList` | Orchestrator output: project name, required agents, task map |
| `AgentOutput` | Any agent's return: files, decisions, notes |
| `AgentContext` | Shared state passed through pipeline — mutated by each agent |
| `APIContract` | Backend → Frontend: endpoints, base_url, auth_method |
| `RevisionRequest` | QA → Agent: issues to fix, instructions |
| `QAFeedback` | QA result: approved bool + issue list |

## Key Contracts

### BaseAgent (`agents/base.py`)

All agents extend `BaseAgent`. It provides:

```python
self.client    # instructor.from_groq(..., mode=instructor.Mode.JSON)
self.model     # "llama-3.3-70b-versatile"
self.max_tokens # 8096

await self.call(system_prompt, user_prompt, response_model)  # → Pydantic model
self.save_to_memory(decisions, agent_name)                    # → ChromaDB
```

### AgentContext Flow

Created in `runner.py`, passed to every agent. Each agent reads what it needs and writes back:

```
Orchestrator  →  context.project_name, project_description
Backend       →  context.backend_notes, backend_api_contract, all_decisions
Frontend      →  context.frontend_notes, all_decisions
QA            →  context.qa_issues, qa_approved, revision_count
```

### Frontend Two-Phase Split

```python
# Phase 1 — runs parallel with backend (no API dependency)
run_phase1(task, context) → AgentOutput  # UI shell, components, routing

# Phase 2 — runs after backend finishes (needs APIContract)
run_phase2(task, context, api_contract, phase1_output) → AgentOutput  # wires fetch()
```

## Adding a New Agent

1. Create `agents/your_agent.py`:

```python
from agents.base import BaseAgent
from core.models import AgentOutput, Task, AgentContext

class YourAgent(BaseAgent):
    async def run(self, task: Task, context: AgentContext) -> AgentOutput:
        result = await self.call(
            system_prompt="...",
            user_prompt=f"Project: {context.project_description}\nTask: {task.description}",
            response_model=AgentOutput,
        )
        self.save_to_memory(result.decisions, "your_agent")
        return result
```

2. Register in `core/runner.py`:
   - Import and instantiate at top
   - Add the key to `_normalize_task_keys()` canonical list
   - Add the call in the pipeline (sequential or inside `asyncio.gather`)

3. Add the key to `VALID_AGENTS` in `agents/orchestrator.py`

## Memory System

- **Store**: ChromaDB with persistent client at `.masai_memory/`
- **Write**: `save_decision(agent_name, decision)` — called by each agent
- **Read**: `search_decisions(query)` — semantic search, loaded at build start into `AgentContext.memory_decisions`
- **View**: `python main.py memory` — lists all stored decisions grouped by agent

## Error Handling

- All agent calls retry once after 10s on failure (`base.py`)
- Revision calls (QA loop) are wrapped in try/except — failures keep original code
- DevOps and Docs calls are wrapped in try/except — failures produce empty output
- Task key normalization handles any LLM key format ("Backend", "backend_api" → "backend")
