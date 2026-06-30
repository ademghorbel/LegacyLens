# LegacyLens

> Multi-agent AI pipeline for legacy system modernisation — powered by LangGraph, LangChain, and Gemini.

Analyses COBOL, VB6, Fortran, and modern codebases. Produces functionality breakdowns, architecture diagrams, and an interactive chat to ask "how do we modernise this?"

## Features

- **Multi-agent pipeline** — orchestrator routes files to specialised nodes (COBOL / VB6 / Fortran / Generic)
- **GitHub-native** — paste a repo URL and get instant analysis
- **Interactive chat** — ask questions about the codebase after analysis
- **FastAPI** — REST endpoints for `/analyse` and `/chat`
- **Streamlit UI** — 4-tab interface with dark theme

## Quickstart

```bash
# 1. Copy env and fill in keys
cp .env.example .env

# 2. Install deps
pip install -e .

# 3. Run the web UI
streamlit run streamlit/app.py

# 4. Or run the API
uvicorn api.main:app --reload
```

## Architecture

```
Input (local path / GitHub URL / ZIP)
       │
       ▼
  Orchestrator (Gemini 2.5 Flash)
  ├── detects languages & frameworks
  └── routes files to:
       ├── COBOL node
       ├── VB6 node      → functionality extraction
       ├── Fortran node  → parser + human + tech summary
       └── Generic node
              │
              ▼
       Checker (loop until all files processed)
              │
              ▼
       Results + Chat (ask Gemini about the analysis)
```

## Stack

| Layer | Tech |
|-------|------|
| Orchestration | LangGraph |
| LLM | Google Gemini 2.0/2.5 Flash |
| UI | Streamlit |
| API | FastAPI |
| GitHub | GitPython |

## Environment variables

| Var | Required | Purpose |
|-----|----------|---------|
| `GOOGLE_API_KEY` | ✅ | Gemini API |
| `GITHUB_TOKEN` | Optional | Private repos |
| `OPENROUTER_API_KEY` | Optional | VB6 node alt LLM |
