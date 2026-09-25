import requests
import re
from ..config import settings

_ollama_models = []
_fetched_from_url = None

def get_ollama_models(ollama_url, force_refresh=False):
    global _ollama_models
    global _fetched_from_url

    if not force_refresh and _ollama_models and _fetched_from_url == ollama_url:
        return _ollama_models

    _fetched_from_url = ollama_url
    try:
        timeout_val = settings.get('ollama_timeout', 120)
        response = requests.get(f"{ollama_url}/api/tags", timeout=timeout_val)
        response.raise_for_status()
        models_data = response.json().get("models", [])
        _ollama_models = sorted([model["name"] for model in models_data])
        if not _ollama_models:
            _ollama_models = ["ollama-no-models-found"]
    except requests.exceptions.RequestException as e:
        _ollama_models = ["ollama-not-running"]
    except Exception as e:
        # Catch any other unexpected errors (e.g., JSON decode, attribute errors)
        _ollama_models = ["ollama-not-running"]
    return _ollama_models

def sanitize_llm_output(text: str) -> str:
    sanitized_text = text.strip()
    if sanitized_text.startswith("```") and sanitized_text.endswith("```"):
        sanitized_text = sanitized_text[3:-3].strip()
    if (sanitized_text.startswith('"') and sanitized_text.endswith('"')) or \
       (sanitized_text.startswith("'") and sanitized_text.endswith("'")):
        sanitized_text = sanitized_text[1:-1].strip()
    sanitized_text = re.sub(r'^[^:\n]*prompt[^:\n]*:\s*', '', sanitized_text, count=1, flags=re.IGNORECASE).strip()
    return sanitized_text
