import requests
from ..config import settings
from .modusflow_utils import get_ollama_models, sanitize_llm_output

DEFAULT_SYSTEM_PROMPT = (
    "You are an expert prompt engineer for AI image generation. "
    "Refine the user's prompt to be more descriptive, vivid, and effective. "
    "Output only the refined prompt text with no explanation, preamble, or quotes."
)

class OllamaTextRefinerNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "text": ("STRING", {"multiline": True, "default": "A beautiful painting of a cat"}),
                "ollama_model": (get_ollama_models(settings.get('ollama_url')),),
                "system_prompt": ("STRING", {
                    "multiline": True,
                    "default": DEFAULT_SYSTEM_PROMPT,
                }),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1, "display": "slider"}),
                "max_tokens": ("INT", {"default": 200, "min": 50, "max": 4096, "step": 1}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("refined_text",)
    FUNCTION = "refine_text"
    CATEGORY = "ModusFlow/Refine"

    def refine_text(self, text, ollama_model, system_prompt, temperature, max_tokens, seed):
        if ollama_model.startswith("ollama-not-running") or ollama_model.startswith("ollama-no-models-found"):
            print("[OllamaTextRefiner] Ollama unavailable, returning input unchanged.")
            return (text,)

        ollama_url = settings.get('ollama_url')
        api_url = f"{ollama_url}/api/chat"
        payload = {
            "model": ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens, "seed": seed},
        }

        try:
            timeout_val = settings.get('ollama_timeout', 120)
            response = requests.post(api_url, json=payload, timeout=timeout_val)
            response.raise_for_status()
            data = response.json()
            if "error" in data:
                print(f"[OllamaTextRefiner] API error: {data['error']}")
                return (text,)
            refined = data.get("message", {}).get("content", "").strip()
            if refined:
                return (sanitize_llm_output(refined),)
        except requests.exceptions.RequestException as e:
            print(f"[OllamaTextRefiner] Request failed: {e}")
        except Exception as e:
            print(f"[OllamaTextRefiner] Unexpected error: {e}")

        return (text,)
