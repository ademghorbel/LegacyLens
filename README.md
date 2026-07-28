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
| `LANGCHAIN_API_KEY` | Optional | LangSmith tracing |
| `LANGCHAIN_TRACING_V2` | Optional | Enable LangSmith tracing |
| `LANGCHAIN_PROJECT` | Optional | LangSmith project name |

Copy `.env.example` to `.env` and fill in your own keys — never commit `.env`.

## Project structure

```
.
├── api/main.py              # FastAPI app (/analyse, /chat, /health)
├── streamlit/app.py         # Streamlit UI entrypoint
├── src/agent/               # LangGraph pipeline: orchestrator, checker, language nodes
├── src/agents/               # Standalone agent helpers (language identifier)
├── src/github_integration/  # Clone + analyse a GitHub repo by URL
├── examples/demo_project/   # Sample COBOL/VB6/Fortran files for a quick test run
├── outputs/                 # Generated analysis artifacts (gitignored)
└── static/                  # Architecture diagrams (mermaid + png)
```

## API reference

### `POST /analyse`
Run the pipeline against a local path or a GitHub URL.

```json
{
  "project_path": "examples/demo_project",
  "github_url": null,
  "branch": null,
  "max_files": 20,
  "include_tests": false
}
```
Provide exactly one of `project_path` or `github_url`. Returns the pipeline's
final state: detected languages/frameworks and per-file functionality analyses.

### `POST /chat`
Ask a question about a previous `/analyse` result.

```json
{
  "message": "How would you modernise the payroll module?",
  "analysis_results": { "...": "the /analyse response" },
  "history": [{"role": "user", "content": "..."}]
}
```
Returns `{"reply": "..."}` from Gemini, grounded in the analysis context.

### `GET /health`
Liveness check — returns `{"status": "ok"}`.

## Try it on the bundled example

```bash
uvicorn api.main:app --reload
curl -X POST localhost:8000/analyse -H "Content-Type: application/json" \
  -d '{"project_path": "examples/demo_project", "max_files": 10}'
```

## License

MIT — see [LICENSE](LICENSE).
