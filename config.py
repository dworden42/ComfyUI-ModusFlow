import json
import os

# The directory where this config.py file is located
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE_PATH = os.path.join(BASE_DIR, 'config.json')

# Default configuration
DEFAULT_CONFIG = {
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_timeout": 120,
    "civitai_api_key": "",
    "prompts_save_directory": "",  # Empty string means use default: BASE_DIR/saved_prompts
    "base_model_definitions": [
        {"type": "flux", "keywords": ["flux", "flux1.5", "flux1.d", "chroma", "flux.1-schnell"]},
        {"type": "sdxl", "keywords": ["sdxl", "sd_xl"]},
        {"type": "pony", "keywords": ["pony"]},
        {"type": "sd15", "keywords": ["sd_v1", "v1-5", "sd15"]},
        {"type": "sd35", "keywords": ["sd_v3", "v3-5", "sd35"]}
    ]
}

def get_config():
    """
    Loads configuration from environment variables or a JSON file.
    Environment variables take precedence.
    """
    config = DEFAULT_CONFIG.copy()

    # 1. Load from config.json if it exists
    if os.path.exists(CONFIG_FILE_PATH):
        try:
            with open(CONFIG_FILE_PATH, 'r') as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, TypeError) as e:
            print(f"[ModusFlow Config] Error loading config.json: {e}. Using defaults.")

    # 2. Override with environment variables
    if 'MODUSFLOW_OLLAMA_URL' in os.environ:
        config['ollama_url'] = os.environ['MODUSFLOW_OLLAMA_URL']
    if 'MODUSFLOW_OLLAMA_TIMEOUT' in os.environ:
        try:
            config['ollama_timeout'] = int(os.environ['MODUSFLOW_OLLAMA_TIMEOUT'])
            print(f"[ModusFlow Config] Loaded Ollama timeout from environment variable: {config['ollama_timeout']}s")
        except ValueError:
            print("[ModusFlow Config] Invalid MODUSFLOW_OLLAMA_TIMEOUT value; must be an integer. Using default.")
    if 'MODUSFLOW_CIVITAI_API_KEY' in os.environ:
        config['civitai_api_key'] = os.environ['MODUSFLOW_CIVITAI_API_KEY']
        print("[ModusFlow Config] Loaded Civitai API key from environment variable.")

    return config

# Load config once on startup
settings = get_config()

def get_prompt(prompt_name: str, default_text: str = "") -> str:
    """
    Loads a prompt from the 'prompts' directory.
    """
    prompt_path = os.path.join(BASE_DIR, 'prompts', f"{prompt_name}.txt")
    if os.path.exists(prompt_path):
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read().strip()
        except Exception as e:
            print(f"[ModusFlow Config] Error loading prompt '{prompt_name}': {e}")
    return default_text

def save_config(new_config: dict):
    """
    Saves the provided configuration dictionary to config.json.
    Also updates the live 'settings' object.
    """
    global settings
    try:
        with open(CONFIG_FILE_PATH, 'w') as f:
            json.dump(new_config, f, indent=4)
        settings.update(new_config)
        print(f"[ModusFlow Config] Successfully saved configuration to {CONFIG_FILE_PATH}")
        return True
    except Exception as e:
        print(f"[ModusFlow Config] Error saving config.json: {e}")
        return False
