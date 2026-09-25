from .modules.ollama_prompt_refiner_node import OllamaPromptRefinerNode
from .modules.ollama_text_refiner_node import OllamaTextRefinerNode
from .modules.image_for_prompting_node import ModusFlowImageForPromptingNode
from .modules.modusflow_utils import get_ollama_models
from .modules.batch_ksampler_node import ModusFlowBatchKSampler
from .modules.lora_loader_node import ModusFlowLoraLoader
from .modules.upscaler_node import ModusFlowUpscaler
from .modules.ksampler_node import ModusFlowKSampler
from .modules.model_loader_node import ModusFlowModelLoader
from .modules.multi_clip_text_encode_node import ModusFlowMultiCLIPTextEncode
from .modules.show_text_node import ModusFlowShowText
from .modules.text_editor_node import ModusFlowTextEditor
from .modules.image_gallery_node import ModusFlowImageGallery
from .modules.latent_preset_node import ModusFlowLatentPreset
from .modules.save_audio_node import ModusFlowSaveAudio
from .modules.save_image_node import ModusFlowSaveImage
from .modules.ace_step_audio_node import ModusFlowAceStepAudio
from .modules.allinone_detailer_node import ModusFlowDetailerSlot, ModusFlowAllInOneDetailer
from .modules.conditioning_concat_node import ModusFlowConditioningConcat
from .modules.restormer_node import ModusFlowRestormer
import server
from aiohttp import web
import folder_paths
from urllib.parse import quote
from .config import settings, save_config
import safetensors.torch
import hashlib
import requests
import json
import os
import re
from PIL import Image
from PIL.PngImagePlugin import PngInfo

@server.PromptServer.instance.routes.get("/modusflow/refresh_ollama_models")
async def refresh_ollama_models(request):
    """API endpoint to force a refresh of the Ollama models list."""
    ollama_url = settings.get('ollama_url')
    try:
        # Call the utility function directly with force_refresh=True
        models = get_ollama_models(ollama_url, force_refresh=True)
        return web.json_response({"success": True, "data": models})
    except Exception as e:
        msg = f"API Error refreshing Ollama models: {e}"
        print(f"[ModusFlow] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.get("/modusflow/gallery/list")
async def gallery_list(request):
    """API endpoint to list folders and images in the output directory."""
    try:
        subpath = request.query.get("path", "").strip()
        sort_by = request.query.get("sort", "name").strip()
        output_dir = folder_paths.get_output_directory()
        
        # Build the full path
        if subpath:
            full_path = os.path.join(output_dir, subpath)
        else:
            full_path = output_dir
            
        # Security check: ensure we're still within output directory
        full_path = os.path.normpath(full_path)
        output_dir_norm = os.path.normpath(output_dir)
        if not full_path.startswith(output_dir_norm):
            return web.json_response({"success": False, "message": "Invalid path"})
        
        if not os.path.isdir(full_path):
            return web.json_response({"success": False, "message": "Directory not found"})
        
        folders = []
        images = []
        folder_stats = {}
        image_stats = {}
        
        try:
            items = os.listdir(full_path)
            
            for item in items:
                item_path = os.path.join(full_path, item)
                try:
                    stat = os.stat(item_path)
                    
                    if os.path.isdir(item_path):
                        folders.append(item)
                        folder_stats[item] = {
                            'modified': stat.st_mtime,
                            'created': stat.st_ctime
                        }
                    elif os.path.isfile(item_path):
                        # Check if it's an image file
                        if item.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                            images.append(item)
                            image_stats[item] = {
                                'modified': stat.st_mtime,
                                'created': stat.st_ctime,
                                'size': stat.st_size
                            }
                except (OSError, PermissionError):
                    continue
                    
        except PermissionError:
            return web.json_response({"success": False, "message": "Permission denied"})
        
        return web.json_response({
            "success": True, 
            "data": {
                "folders": folders,
                "images": images,
                "folderStats": folder_stats,
                "imageStats": image_stats
            }
        })
    except Exception as e:
        msg = f"API Error listing gallery: {e}"
        print(f"[ModusFlow Gallery] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.get("/modusflow/gallery/metadata")
async def gallery_metadata(request):
    """API endpoint to get metadata from an image file."""
    try:
        filename = request.query.get("filename", "").strip()
        subpath = request.query.get("path", "").strip()
        
        if not filename:
            return web.json_response({"success": False, "message": "No filename provided"})
        
        output_dir = folder_paths.get_output_directory()
        
        # Build the full path
        if subpath:
            full_path = os.path.join(output_dir, subpath, filename)
        else:
            full_path = os.path.join(output_dir, filename)
        
        # Security check: ensure we're still within output directory
        full_path = os.path.normpath(full_path)
        output_dir_norm = os.path.normpath(output_dir)
        if not full_path.startswith(output_dir_norm):
            return web.json_response({"success": False, "message": "Invalid path"})
        
        if not os.path.isfile(full_path):
            return web.json_response({"success": False, "message": "File not found"})
        
        metadata = {}
        
        try:
            # Try to read PNG metadata
            if full_path.lower().endswith('.png'):
                with Image.open(full_path) as img:
                    # Get PNG text chunks
                    png_info = img.info
                    
                    # Common ComfyUI metadata fields
                    if 'prompt' in png_info:
                        try:
                            metadata['prompt'] = json.loads(png_info['prompt'])
                        except:
                            metadata['prompt'] = png_info['prompt']
                    
                    if 'workflow' in png_info:
                        try:
                            metadata['workflow'] = json.loads(png_info['workflow'])
                        except:
                            metadata['workflow'] = png_info['workflow']
                    
                    # Include other text chunks
                    for key, value in png_info.items():
                        if key not in ['prompt', 'workflow'] and isinstance(value, str):
                            try:
                                # Try to parse as JSON
                                metadata[key] = json.loads(value)
                            except:
                                metadata[key] = value
                    
                    # Add basic image info
                    metadata['_image_info'] = {
                        'format': img.format,
                        'mode': img.mode,
                        'size': img.size,
                        'width': img.width,
                        'height': img.height
                    }
            else:
                # For non-PNG images, just get basic info
                with Image.open(full_path) as img:
                    metadata['_image_info'] = {
                        'format': img.format,
                        'mode': img.mode,
                        'size': img.size,
                        'width': img.width,
                        'height': img.height
                    }
                    
                    # Try to get EXIF data
                    if hasattr(img, '_getexif') and img._getexif():
                        metadata['exif'] = img._getexif()
        
        except Exception as e:
            print(f"[ModusFlow Gallery] Error reading metadata from {filename}: {e}")
            return web.json_response({"success": False, "message": f"Error reading metadata: {str(e)}"})
        
        # Add file info
        file_stat = os.stat(full_path)
        metadata['_file_info'] = {
            'filename': filename,
            'size_bytes': file_stat.st_size,
            'size_mb': round(file_stat.st_size / (1024 * 1024), 2),
            'modified': file_stat.st_mtime,
            'created': file_stat.st_ctime
        }
        
        return web.json_response({"success": True, "metadata": metadata})
    except Exception as e:
        msg = f"API Error getting metadata: {e}"
        print(f"[ModusFlow Gallery] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.get("/modusflow/refresh_input_files")
async def refresh_input_files(request):
    """API endpoint to get an updated list of images and folders from the input directory."""
    try:
        input_dir = folder_paths.get_input_directory()
        all_items = []
        if os.path.isdir(input_dir):
            folder_items = []
            file_items = []
            for dirpath, dirnames, filenames in os.walk(input_dir, topdown=True):
                dirnames.sort()
                filenames.sort()
                for dirname in dirnames:
                    relative_path = os.path.relpath(os.path.join(dirpath, dirname), input_dir)
                    folder_items.append(f"[FOLDER] {relative_path.replace(os.sep, '/')}")
                for filename in filenames:
                    if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                        relative_path = os.path.relpath(os.path.join(dirpath, filename), input_dir)
                        file_items.append(relative_path.replace(os.sep, '/'))
            all_items = folder_items + file_items

        if not all_items:
            all_items.append("--no items found--")
        return web.json_response({"success": True, "data": all_items})
    except Exception as e:
        msg = f"API Error refreshing input file list: {e}"
        print(f"[ModusFlow] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.get("/modusflow/get_loras")
async def get_loras(request):
    """API endpoint to get a list of all available LoRA models."""
    try:
        lora_list = sorted(folder_paths.get_filename_list("loras"))
        return web.json_response({"success": True, "data": lora_list})
    except Exception as e:
        msg = f"API Error getting LoRA list: {e}"
        print(f"[ModusFlow LoRA Loader] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.post("/modusflow/save_civitai_key")
async def save_civitai_key_endpoint(request):
    """API endpoint to save the Civitai API key to the config file."""
    try:
        data = await request.json()
        api_key = data.get("api_key", "")

        current_config = settings.copy()
        current_config["civitai_api_key"] = api_key

        if save_config(current_config):
            return web.json_response({"success": True, "message": "API key saved successfully."})
        else:
            msg = "Failed to write to config file. Check permissions."
            print(f"[ModusFlow] {msg}")
            return web.json_response({"success": False, "message": msg})
    except Exception as e:
        msg = f"Error saving Civitai API key: {e}"
        print(f"[ModusFlow] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.get("/modusflow/get_config")
async def get_config_endpoint(request):
    """API endpoint to get the current ModusFlow configuration."""
    try:
        from .config import settings, DEFAULT_CONFIG
        config_data = {
            "ollama_url": settings.get("ollama_url", DEFAULT_CONFIG.get("ollama_url", "http://127.0.0.1:11434")),
            "ollama_timeout": settings.get("ollama_timeout", DEFAULT_CONFIG.get("ollama_timeout", 120)),
            "civitai_api_key": settings.get("civitai_api_key", ""),
            "prompts_save_directory": settings.get("prompts_save_directory", ""),
        }
        return web.json_response({"success": True, "data": config_data})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

@server.PromptServer.instance.routes.post("/modusflow/save_config")
async def save_config_endpoint(request):
    """API endpoint to update ModusFlow configuration fields."""
    try:
        data = await request.json()
        from .config import settings, save_config

        current_config = settings.copy()
        for key in ("ollama_url", "ollama_timeout", "civitai_api_key", "prompts_save_directory"):
            if key in data:
                val = data[key]
                if key == "ollama_timeout":
                    try:
                        val = int(val)
                    except (ValueError, TypeError):
                        val = 120
                elif isinstance(val, str):
                    val = val.strip()
                current_config[key] = val

        if save_config(current_config):
            return web.json_response({"success": True, "message": "Configuration saved successfully."})
        else:
            return web.json_response({"success": False, "message": "Failed to write configuration file."})
    except Exception as e:
        return web.json_response({"success": False, "message": str(e)})

@server.PromptServer.instance.routes.post("/modusflow/save_prompt")
async def save_prompt_endpoint(request):
    """API endpoint to save a text prompt to a JSON file."""
    try:
        data = await request.json()
        filename = data.get("filename", "").strip()
        category = data.get("category", "").strip()
        positive = data.get("positive", "")
        negative = data.get("negative", "")

        if not filename:
            return web.json_response({"success": False, "message": "Filename cannot be empty."})

        # Sanitize filename to prevent directory traversal
        filename = os.path.basename(filename)
        # Strip legacy .txt extension and ensure .json
        if filename.endswith('.txt'):
            filename = filename[:-4]
        if not filename.endswith('.json'):
            filename += '.json'

        # Get the prompts save directory from config
        from .config import settings, BASE_DIR
        prompts_dir = settings.get('prompts_save_directory', '').strip()
        if not prompts_dir:
            prompts_dir = os.path.join(BASE_DIR, 'saved_prompts')

        # Create directory if it doesn't exist
        os.makedirs(prompts_dir, exist_ok=True)

        # Save as JSON
        file_path = os.path.join(prompts_dir, filename)
        prompt_data = {"category": category, "positive": positive, "negative": negative}
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(prompt_data, f, ensure_ascii=False, indent=2)

        print(f"[ModusFlow TextEditor] Saved prompt to: {file_path}")
        return web.json_response({"success": True, "message": f"Prompt saved as {filename}"})
    except Exception as e:
        msg = f"Error saving prompt: {e}"
        print(f"[ModusFlow TextEditor] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.post("/modusflow/load_prompt")
async def load_prompt_endpoint(request):
    """API endpoint to load a text prompt from a JSON file."""
    try:
        data = await request.json()
        filename = data.get("filename", "").strip()

        if not filename:
            return web.json_response({"success": False, "message": "Filename cannot be empty."})

        # Sanitize filename to prevent directory traversal
        filename = os.path.basename(filename)

        # Get the prompts save directory from config
        from .config import settings, BASE_DIR
        prompts_dir = settings.get('prompts_save_directory', '').strip()
        if not prompts_dir:
            prompts_dir = os.path.join(BASE_DIR, 'saved_prompts')

        file_path = os.path.join(prompts_dir, filename)
        if not os.path.exists(file_path):
            return web.json_response({"success": False, "message": f"File '{filename}' not found."})

        with open(file_path, 'r', encoding='utf-8') as f:
            prompt_data = json.load(f)

        print(f"[ModusFlow TextEditor] Loaded prompt from: {file_path}")
        return web.json_response({
            "success": True,
            "data": {
                "category": prompt_data.get("category", ""),
                "positive": prompt_data.get("positive", ""),
                "negative": prompt_data.get("negative", ""),
            }
        })
    except Exception as e:
        msg = f"Error loading prompt: {e}"
        print(f"[ModusFlow TextEditor] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.get("/modusflow/list_prompts")
async def list_prompts_endpoint(request):
    """API endpoint to list all saved prompts with their category metadata."""
    try:
        # Get the prompts save directory from config
        from .config import settings, BASE_DIR
        prompts_dir = settings.get('prompts_save_directory', '').strip()
        if not prompts_dir:
            prompts_dir = os.path.join(BASE_DIR, 'saved_prompts')

        # Create directory if it doesn't exist
        os.makedirs(prompts_dir, exist_ok=True)

        prompts = []
        if os.path.isdir(prompts_dir):
            for filename in sorted(f for f in os.listdir(prompts_dir) if f.endswith('.json')):
                category = ""
                try:
                    file_path = os.path.join(prompts_dir, filename)
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    category = data.get('category', '') or ''
                except Exception:
                    pass
                prompts.append({"filename": filename, "category": category})

        return web.json_response({"success": True, "data": prompts})
    except Exception as e:
        msg = f"Error listing prompts: {e}"
        print(f"[ModusFlow TextEditor] {msg}")
        return web.json_response({"success": False, "message": msg})

def _get_songs_dir():
    """Return the songs save directory, creating it if needed."""
    from .config import settings, BASE_DIR
    songs_dir = settings.get("songs_save_directory", "").strip()
    if not songs_dir:
        songs_dir = os.path.join(BASE_DIR, "saved_songs")
    os.makedirs(songs_dir, exist_ok=True)
    return songs_dir

@server.PromptServer.instance.routes.get("/modusflow/ace_audio/list")
async def ace_audio_list(request):
    """API endpoint to list all saved song files."""
    try:
        songs_dir = _get_songs_dir()
        files = sorted(f for f in os.listdir(songs_dir) if f.endswith(".json"))
        return web.json_response({"success": True, "data": files})
    except Exception as e:
        msg = f"Error listing songs: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.post("/modusflow/ace_audio/save")
async def ace_audio_save(request):
    """API endpoint to save tags and lyrics as a JSON song file."""
    try:
        data = await request.json()
        filename = data.get("filename", "").strip()
        title = data.get("title", "")
        tags = data.get("tags", "")
        lyrics = data.get("lyrics", "")

        if not filename:
            return web.json_response({"success": False, "message": "Filename cannot be empty."})

        filename = os.path.basename(filename)
        if not filename.endswith(".json"):
            filename += ".json"

        songs_dir = _get_songs_dir()
        file_path = os.path.join(songs_dir, filename)

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({"title": title, "tags": tags, "lyrics": lyrics}, f, ensure_ascii=False, indent=2)

        print(f"[ModusFlow AceStepAudio] Saved song to: {file_path}")
        return web.json_response({"success": True, "message": f"Song saved as {filename}"})
    except Exception as e:
        msg = f"Error saving song: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.post("/modusflow/ace_audio/load")
async def ace_audio_load(request):
    """API endpoint to load tags and lyrics from a JSON song file."""
    try:
        data = await request.json()
        filename = data.get("filename", "").strip()

        if not filename:
            return web.json_response({"success": False, "message": "Filename cannot be empty."})

        filename = os.path.basename(filename)
        songs_dir = _get_songs_dir()
        file_path = os.path.join(songs_dir, filename)

        if not os.path.exists(file_path):
            return web.json_response({"success": False, "message": f"Song file '{filename}' not found."})

        with open(file_path, "r", encoding="utf-8") as f:
            song_data = json.load(f)

        return web.json_response({"success": True, "data": song_data})
    except Exception as e:
        msg = f"Error loading song: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

# ── Individual tags routes ────────────────────────────────────────────────────

@server.PromptServer.instance.routes.get("/modusflow/ace_audio/list_tags")
async def ace_audio_list_tags(request):
    """API endpoint to list all saved tags files."""
    try:
        tags_dir = os.path.join(_get_songs_dir(), "tags")
        os.makedirs(tags_dir, exist_ok=True)
        files = sorted(f for f in os.listdir(tags_dir) if f.endswith(".txt"))
        return web.json_response({"success": True, "data": files})
    except Exception as e:
        msg = f"Error listing tags: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.post("/modusflow/ace_audio/save_tags")
async def ace_audio_save_tags(request):
    """API endpoint to save tags as a .txt file."""
    try:
        data = await request.json()
        filename = data.get("filename", "").strip()
        tags = data.get("tags", "")
        if not filename:
            return web.json_response({"success": False, "message": "Filename cannot be empty."})
        filename = os.path.basename(filename)
        if not filename.endswith(".txt"):
            filename += ".txt"
        tags_dir = os.path.join(_get_songs_dir(), "tags")
        os.makedirs(tags_dir, exist_ok=True)
        with open(os.path.join(tags_dir, filename), "w", encoding="utf-8") as f:
            f.write(tags)
        print(f"[ModusFlow AceStepAudio] Saved tags: {filename}")
        return web.json_response({"success": True, "message": f"Tags saved as {filename}"})
    except Exception as e:
        msg = f"Error saving tags: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.post("/modusflow/ace_audio/load_tags")
async def ace_audio_load_tags(request):
    """API endpoint to load tags from a .txt file."""
    try:
        data = await request.json()
        filename = os.path.basename(data.get("filename", "").strip())
        if not filename:
            return web.json_response({"success": False, "message": "Filename cannot be empty."})
        tags_dir = os.path.join(_get_songs_dir(), "tags")
        file_path = os.path.join(tags_dir, filename)
        if not os.path.exists(file_path):
            return web.json_response({"success": False, "message": f"Tags file '{filename}' not found."})
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return web.json_response({"success": True, "data": content})
    except Exception as e:
        msg = f"Error loading tags: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

# ── Individual lyrics routes ──────────────────────────────────────────────────

@server.PromptServer.instance.routes.get("/modusflow/ace_audio/list_lyrics")
async def ace_audio_list_lyrics(request):
    """API endpoint to list all saved lyrics files."""
    try:
        lyrics_dir = os.path.join(_get_songs_dir(), "lyrics")
        os.makedirs(lyrics_dir, exist_ok=True)
        files = sorted(f for f in os.listdir(lyrics_dir) if f.endswith(".txt"))
        return web.json_response({"success": True, "data": files})
    except Exception as e:
        msg = f"Error listing lyrics: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.post("/modusflow/ace_audio/save_lyrics")
async def ace_audio_save_lyrics(request):
    """API endpoint to save lyrics as a .txt file."""
    try:
        data = await request.json()
        filename = data.get("filename", "").strip()
        lyrics = data.get("lyrics", "")
        if not filename:
            return web.json_response({"success": False, "message": "Filename cannot be empty."})
        filename = os.path.basename(filename)
        if not filename.endswith(".txt"):
            filename += ".txt"
        lyrics_dir = os.path.join(_get_songs_dir(), "lyrics")
        os.makedirs(lyrics_dir, exist_ok=True)
        with open(os.path.join(lyrics_dir, filename), "w", encoding="utf-8") as f:
            f.write(lyrics)
        print(f"[ModusFlow AceStepAudio] Saved lyrics: {filename}")
        return web.json_response({"success": True, "message": f"Lyrics saved as {filename}"})
    except Exception as e:
        msg = f"Error saving lyrics: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

@server.PromptServer.instance.routes.post("/modusflow/ace_audio/load_lyrics")
async def ace_audio_load_lyrics(request):
    """API endpoint to load lyrics from a .txt file."""
    try:
        data = await request.json()
        filename = os.path.basename(data.get("filename", "").strip())
        if not filename:
            return web.json_response({"success": False, "message": "Filename cannot be empty."})
        lyrics_dir = os.path.join(_get_songs_dir(), "lyrics")
        file_path = os.path.join(lyrics_dir, filename)
        if not os.path.exists(file_path):
            return web.json_response({"success": False, "message": f"Lyrics file '{filename}' not found."})
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return web.json_response({"success": True, "data": content})
    except Exception as e:
        msg = f"Error loading lyrics: {e}"
        print(f"[ModusFlow AceStepAudio] {msg}")
        return web.json_response({"success": False, "message": msg})

def calculate_sha256(file_path, chunk_size=1024*1024):
    """Calculates the SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            sha256.update(data)
    return sha256.hexdigest().upper()

def _get_model_type(name: str, definitions: list) -> str:
    """A simple heuristic to determine the general type of a model file or metadata string based on definitions."""
    if not name or not isinstance(name, str):
        return 'unknown'
    
    lower_name = name.lower()
    
    for definition in definitions:
        model_type = definition.get("type")
        if not model_type:
            continue
        for keyword in definition.get("keywords", []):
            if keyword.lower() in lower_name:
                return model_type
    
    return re.split(r'[\s._-]', lower_name)[0] or 'unknown'

@server.PromptServer.instance.routes.get("/modusflow/get_lora_civitai_info")
async def get_lora_civitai_info(request):
    """API endpoint to get LoRA info from Civitai by file hash."""
    lora_name = request.query.get("name")
    api_key_from_request = request.query.get("api_key")
    if not lora_name:
        return web.json_response({"success": False, "message": "LoRA name not provided"})

    try:
        # Use ComfyUI's built-in file resolver which is more reliable.
        # Use the same logic as the node itself to find the LoRA file path.
        lora_paths_list = folder_paths.get_filename_list("loras")
        lora_file_relative = ModusFlowLoraLoader.find_lora_path(lora_name, lora_paths_list)

        if not lora_file_relative:
            msg = f"LoRA file not found for: {lora_name}"
            print(f"[ModusFlow LoRA Loader] Civitai Info: {msg}")
            return web.json_response({"success": False, "message": msg})

        lora_path = folder_paths.get_full_path("loras", lora_file_relative)
        if not lora_path or not os.path.exists(lora_path):
            msg = f"LoRA file path could not be resolved for: {lora_file_relative}"
            print(f"[ModusFlow LoRA Loader] Civitai Info: {msg}")
            return web.json_response({"success": False, "message": msg})

        file_hash = calculate_sha256(lora_path)
        civitai_api_url = f"https://civitai.com/api/v1/model-versions/by-hash/{file_hash}"

        headers = {}
        # Prioritize API key from the request, fall back to config file.
        api_key = api_key_from_request or settings.get("civitai_api_key")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        response = requests.get(civitai_api_url, timeout=15, headers=headers)

        if response.status_code == 404:
            return web.json_response({"success": False, "message": "Model not found on Civitai with this hash."})

        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict):
            print(f"[ModusFlow LoRA Loader] Civitai API did not return a JSON object for hash: {file_hash}")
            return web.json_response({"success": False, "message": "Invalid response from Civitai API (not a JSON object)."})

        model_data = data.get("model", {})
        # Ensure model_data is a dictionary, default to empty if it's None or something else
        if not isinstance(model_data, dict):
            print(f"[ModusFlow LoRA Loader] Civitai API returned a non-dict 'model' field for hash: {file_hash}. Response: {data}")
            model_data = {} # Default to empty dict to prevent errors
        
        # More robustly check for model_id, preferring the top-level one.
        # This avoids issues with falsy values like 0.
        model_id = data.get("modelId")
        if model_id is None:
            model_id = model_data.get("id")

        if model_id is None:
            print(f"[ModusFlow LoRA Loader] Civitai API returned a response without a model ID for hash: {file_hash}")
            return web.json_response({"success": False, "message": "Model found, but the Civitai API response was missing a model ID. Check console for details."})

        info = {
            "modelId": model_id,
            "modelName": model_data.get("name"),
            "creator": model_data.get("creator", {}).get("username"),
            "trainedWords": data.get("trainedWords", []),
            "description": model_data.get("description"),
            "images": [img.get("url") for img in data.get("images", []) if img.get("url")]
        }
        return web.json_response({"success": True, "data": info})
    except requests.exceptions.RequestException as e:
        return web.json_response({"success": False, "message": f"Failed to connect to Civitai: {e}"})
    except Exception as e:
        return web.json_response({"success": False, "message": f"An unexpected error occurred: {e}"})

@server.PromptServer.instance.routes.get("/modusflow/get_lora_metadata")
async def get_lora_metadata(request):
    """API endpoint to get metadata and a preview image from a specific LoRA file."""
    lora_name = request.query.get("name")
    base_model_name = request.query.get("base_model_name")
    if not lora_name:
        return web.json_response({"success": False, "message": "LoRA name not provided"})

    try:
        # Use the same logic as the node itself to find the LoRA file path.
        lora_paths_list = folder_paths.get_filename_list("loras")
        lora_file_relative = ModusFlowLoraLoader.find_lora_path(lora_name, lora_paths_list)

        if not lora_file_relative:
            msg = f"LoRA file not found for: {lora_name}"
            print(f"[ModusFlow LoRA Loader] Local Metadata: {msg}")
            return web.json_response({"success": False, "message": msg})

        lora_path = folder_paths.get_full_path("loras", lora_file_relative)
        if not lora_path or not os.path.exists(lora_path):
            msg = f"LoRA file path could not be resolved for: {lora_file_relative}"
            print(f"[ModusFlow LoRA Loader] Local Metadata: {msg}")
            return web.json_response({"success": False, "message": msg})

        # --- Extract Safetensors Metadata ---
        metadata = {}
        if lora_path.lower().endswith(".safetensors"):
            with safetensors.safe_open(lora_path, framework="pt", device="cpu") as f:
                metadata = f.metadata() or {}
        else:
            print(f"[ModusFlow LoRA Loader] Skipped metadata check for non-safetensors file: {lora_name}")

        parsed_metadata = {}
        for key, value in metadata.items():
            try:
                parsed_metadata[key] = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                parsed_metadata[key] = value

        if not parsed_metadata:
            print(f"[ModusFlow LoRA Loader] No metadata found in LoRA file: {lora_name}")

        # --- Find Preview Image ---
        preview_image_url = None

        # Priority 1: Check for embedded preview image in metadata (case-insensitive)
        if metadata:
            found_key = None
            # Search for standard preview keys, case-insensitively
            for key in metadata.keys():
                if key.lower() in ["ss_preview_image", "ss_preview"]:
                    found_key = key
                    break
            
            if found_key:
                base64_image = metadata[found_key]
                # Ensure we have a non-empty string before processing
                if base64_image and isinstance(base64_image, str):
                    if not base64_image.startswith('data:image'):
                        preview_image_url = f"data:image/png;base64,{base64_image}"
                    else:
                        preview_image_url = base64_image

        # Priority 2: Fallback to finding an external file if no embedded one was found
        if not preview_image_url:
            lora_file_relative_no_ext, _ = os.path.splitext(lora_file_relative)
            for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                potential_preview_relative = lora_file_relative_no_ext + ext
                full_preview_path = folder_paths.get_full_path("loras", potential_preview_relative)
                if full_preview_path and os.path.exists(full_preview_path):
                    # Correctly split the path into subfolder and filename for the /view endpoint
                    subfolder, filename = os.path.split(potential_preview_relative)
                    preview_image_url = f"/view?filename={quote(filename)}&type=loras&subfolder={quote(subfolder)}"
                    break

        # --- Perform Validation ---
        validation = {"status": "unknown", "message": "Validation not performed."}
        if base_model_name and base_model_name != "None":
            lora_base_model_str = parsed_metadata.get("ss_base_model_version") or parsed_metadata.get("modelspec.architecture") or ""
            if not lora_base_model_str:
                validation = {"status": "unknown", "message": "No base model specified in LoRA metadata."}
            else:
                definitions = settings.get("base_model_definitions", [])
                lora_type = _get_model_type(lora_base_model_str, definitions)
                base_model_type = _get_model_type(base_model_name, definitions)

                if lora_type != 'unknown' and base_model_type != 'unknown' and lora_type != base_model_type:
                    validation = {
                        "status": "incompatible",
                        "message": f"Warning: LoRA base model ('{lora_type}') may not match selected base model ('{base_model_type}')."
                    }
                else:
                    validation = {
                        "status": "compatible",
                        "message": f"LoRA base model ('{lora_type}') appears compatible with selected base model ('{base_model_type}')."
                    }

        # --- Combine and Return ---
        final_data = {
            "local_metadata": parsed_metadata,
            "preview_image_url": preview_image_url,
            "validation": validation
        }
        return web.json_response({"success": True, "data": final_data})
    except Exception as e:
        print(f"[ModusFlow LoRA Loader] Error reading metadata for '{lora_name}': {e}")
        return web.json_response({"success": False, "message": f"Could not read metadata. File may be corrupted or not a valid safetensors file. Error: {e}"})

NODE_CLASS_MAPPINGS = {
    "OllamaPromptRefiner": OllamaPromptRefinerNode,
    "ImageForPrompting": ModusFlowImageForPromptingNode,
    "ModusFlowBatchKSampler": ModusFlowBatchKSampler,
    "ModusFlowLoraLoader": ModusFlowLoraLoader,
    "ModusFlowUpscaler": ModusFlowUpscaler,
    "ModusFlowKSampler": ModusFlowKSampler,
    "ModusFlowModelLoader": ModusFlowModelLoader,
    "ModusFlowMultiCLIPTextEncode": ModusFlowMultiCLIPTextEncode,
    "ModusFlowShowText": ModusFlowShowText,
    "ModusFlowTextEditor": ModusFlowTextEditor,
    "ModusFlowImageGallery": ModusFlowImageGallery,
    "ModusFlowLatentPreset": ModusFlowLatentPreset,
    "ModusFlowSaveAudio": ModusFlowSaveAudio,
    "ModusFlowAceStepAudio": ModusFlowAceStepAudio,
    "OllamaTextRefiner": OllamaTextRefinerNode,
    "ModusFlowSaveImage": ModusFlowSaveImage,
    "ModusFlowDetailerSlot": ModusFlowDetailerSlot,
    "ModusFlowAllInOneDetailer": ModusFlowAllInOneDetailer,
    "ModusFlowConditioningConcat": ModusFlowConditioningConcat,
    "ModusFlowRestormer": ModusFlowRestormer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "OllamaPromptRefiner": "ModusFlow Ollama Prompt Refiner",
    "ImageForPrompting": "ModusFlow Image For Prompting",
    "ModusFlowBatchKSampler": "ModusFlow Batch KSampler",
    "ModusFlowLoraLoader": "ModusFlow LoRA Loader",
    "ModusFlowUpscaler": "ModusFlow Upscaler",
    "ModusFlowKSampler": "ModusFlow KSampler",
    "ModusFlowModelLoader": "ModusFlow Model Loader",
    "ModusFlowMultiCLIPTextEncode": "ModusFlow Multi-CLIP Text Encode",
    "ModusFlowShowText": "ModusFlow ShowText",
    "ModusFlowTextEditor": "ModusFlow Text Editor",
    "ModusFlowImageGallery": "ModusFlow Image Gallery",
    "ModusFlowLatentPreset": "ModusFlow Latent Preset",
    "ModusFlowSaveAudio": "ModusFlow Save Audio",
    "ModusFlowAceStepAudio": "ModusFlow ACE Step Audio 1.5",
    "OllamaTextRefiner": "ModusFlow Ollama Text Refiner",
    "ModusFlowSaveImage": "ModusFlow Save Image",
    "ModusFlowDetailerSlot": "ModusFlow Detailer Slot",
    "ModusFlowAllInOneDetailer": "ModusFlow All-in-One Detailer",
    "ModusFlowConditioningConcat": "ModusFlow Conditioning Concat",
    "ModusFlowRestormer": "ModusFlow Restormer",
}

WEB_DIRECTORY = "./web"

print("✅ ModusFlow Ollama Prompt Refiner: Custom node loaded.")