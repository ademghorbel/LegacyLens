# src/agent/nodes/fortran_node/config.py

FORTRAN_SUMMARIZER_CONFIG = {
    "model": "deepseek/deepseek-chat-v3-0324",
    "temperature": 0.5,
    "max_tokens": 800,
    "api_base": "https://openrouter.ai/api/v1",
    "api_key_env": "OPENROUTER_API_KEY"
}

TECHNICAL_SUMMARIZER_CONFIG = {
    "model": "deepseek/deepseek-chat-v3-0324",
    "temperature": 0.1,
    "max_tokens": 1000,
    "api_base": "https://openrouter.ai/api/v1",
    "api_key_env": "OPENROUTER_API_KEY"
}

FUNCTIONALITY_DESCRIPTION_CONFIG = {
    "model": "deepseek/deepseek-chat-v3-0324",
    "temperature": 0.3,  # Lower for concise and factual summaries
    "max_tokens": 120,
    "api_base": "https://openrouter.ai/api/v1",
    "api_key_env": "OPENROUTER_API_KEY"
}