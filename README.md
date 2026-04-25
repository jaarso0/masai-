# masai — Multi-Agent Software AI

A CLI tool that uses multiple AI agents (powered by Google Gemini) to collaboratively generate complete full-stack projects from a natural language description.

## How It Works

```
masai build "create a todo app with login and React frontend"
```

The system decomposes your spec into tasks and runs specialized agents:

1. **Orchestrator** — Breaks down the spec into detailed tasks
2. **Backend Agent** — Generates a FastAPI backend
3. **Frontend Agent** — Generates a React + Vite frontend
4. **QA Agent** — Reviews code for bugs, security issues, and inconsistencies
5. **DevOps Agent** — Generates Docker, docker-compose, and CI/CD configs
6. **Docs Agent** — Generates README, API docs, and architecture docs

Backend and Frontend agents run in **parallel**. QA reviews the output and can request up to 2 revision cycles. All agents share a **persistent memory** (ChromaDB) to stay aligned across runs.

## Prerequisitesfdfd

- Python 3.11+

## Setup

1. **Clone and install dependencies:**

```bash
cd masai
pip install poetry
poetry install
```

2. **Set your API key** in `.env`:

```
GROQ_API_KEY=your_actual_key_here
```

## Usage

### Generate a project

```bash
masai build "create a todo app with login and React frontend"
```

Output is saved to `output/<project_name>/`.

### View stored decisions

```bash
masai memory
```

## Project Structure

```
masai/
├── main.py              ← CLI entry point
├── agents/              ← All specialist agents
│   ├── base.py          ← BaseAgent with Gemini + instructor
│   ├── orchestrator.py  ← Decomposes spec into tasks
│   ├── backend.py       ← FastAPI backend generator
│   ├── frontend.py      ← React + Vite frontend generator
│   ├── qa.py            ← Code reviewer with revision cycles
│   ├── devops.py        ← Docker / CI config generator
│   └── docs.py          ← Documentation generator
├── core/
│   ├── models.py        ← Pydantic v2 data models
│   └── runner.py        ← Pipeline orchestration
├── memory/
│   └── store.py         ← ChromaDB persistent memory
└── output/              ← Generated projects go here
```

## Tech Stack

- **google-generativeai** — Gemini API
- **instructor** — Structured outputs from Gemini
- **pydantic v2** — Data models
- **asyncio** — Parallel agent execution
- **chromadb** — Persistent vector memory
- **typer** — CLI framework
- **rich** — Terminal UI
