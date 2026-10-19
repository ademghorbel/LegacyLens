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
Input (local path / GitHub URL)
       │
       ▼
  Orchestrator
  ├── routes each file by extension (exact, no LLM call)
  └── one LLM call per project to detect frameworks
       │
       ├── COBOL node
       ├── VB6 node      → functionality extraction
       ├── Fortran node  → parser + human + tech summary
       └── Generic node  → structured analysis: role, layer, classes,
              │            functions, dependencies, design patterns
              ▼
       Checker (loop until every file is processed)
              │
              ▼
       Module aggregation → groups all analyses into business modules
              │             (tech stack, endpoints, entities; RFP format)
              ▼
       Results + Chat (ask about the analysis)
```

## Reliability

Every LLM call goes through `src/agent/llm.py`:

- **Timeouts** on every request, so a stuck call cannot freeze the pipeline.
- **Retries with exponential backoff** on 429 / 5xx / timeouts (4 attempts, 4s → 8s → 16s), which covers a per-minute quota window.
- **Shared rate limiter** across all nodes (`LLM_RPM`, default 8/min, under the free-tier limit).
- **Daily-quota fallback.** Free-tier quotas are per model (20 requests/day on `gemini-3.5-flash`). When one model runs out, calls move to the next model in `GEMINI_FALLBACK_MODELS`; when all are out, the remaining calls fail at once with a clear reason instead of each retrying.
- **One failing file never stops the run.** It is marked `error` with the cause, and the aggregation is built from the files that worked.
- The API maps failures to proper status codes: quota → 429, timeout → 504, bad key → 401.

## Stack

| Layer | Tech |
|-------|------|
| Orchestration | LangGraph |
| LLM | Google Gemini (3.5 Flash, Flash-Lite fallbacks), via LangChain |
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
| `GEMINI_MODEL` | Optional | Primary model (default `gemini-3.5-flash`) |
| `GEMINI_FALLBACK_MODELS` | Optional | Comma-separated models used when the primary hits its daily quota |
| `LLM_TIMEOUT` | Optional | Seconds per request (default 120) |
| `LLM_MAX_ATTEMPTS` | Optional | Tries per request on 429 / 5xx / timeout (default 4) |
| `LLM_RETRY_DELAY` | Optional | First backoff in seconds (default 4) |
| `LLM_RPM` | Optional | Requests per minute across all nodes (default 8) |

Copy `.env.example` to `.env` and fill in your own keys — never commit `.env`.

## Project structure

```
.
├── api/main.py              # FastAPI app (/analyse, /chat, /health)
├── streamlit/app.py         # Streamlit UI entrypoint
├── src/agent/               # LangGraph pipeline: orchestrator, language nodes, checker, aggregation
├── src/agent/llm.py         # Shared Gemini client: timeouts, retries, rate limit, quota fallback
├── src/agents/               # Standalone agent helpers (language identifier)
├── src/github_integration/  # Clone + analyse a GitHub repo by URL
├── examples/demo_project/   # Small VB6 / Fortran / Python sample
├── examples/ecommerce_project/  # Larger Python + React sample for the structured analyser
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

## Tests

```bash
pip install -e ".[dev]"
python -m pytest -q
```

The suite runs offline: a local fake Gemini server (`tests/fake_gemini.py`) stands in for the API, so the real google-genai SDK retry, backoff and timeout code is exercised without a key or quota. It covers retries, backoff timing, timeouts (sync and async), the daily-quota fallback chain, rate limiting, full pipeline runs on both example projects, partial failures, and the API error codes.

To run the real pipeline with your key: `python scripts/run_pipeline.py examples/ecommerce_project`.

## License

MIT — see [LICENSE](LICENSE).
