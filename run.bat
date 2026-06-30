@echo off
echo Starting LegacyLens...
if not exist .venv (
    echo Creating virtual environment...
    uv venv .venv --python 3.11
    uv pip install -e ".[dev]" --python .venv\Scripts\python.exe
    uv pip install openai --python .venv\Scripts\python.exe
)
set PYTHONPATH=src
set PYTHONUTF8=1
.venv\Scripts\streamlit.exe run streamlit/app.py
