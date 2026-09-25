import json
import os
import io
import base64
import torch
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
import folder_paths
import re
import requests
from .modusflow_utils import get_ollama_models, sanitize_llm_output
from ..config import settings, get_prompt

class ModusFlowImageForPromptingNode:
    @classmethod
    def INPUT_TYPES(s):
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

        return {
            "required": {
                "image_or_folder": (all_items if all_items else ["--no items found--"], {"image_upload": True}),
                "prompt_source": (["metadata_first", "force_description"], {"default": "metadata_first"}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 64}),
                "override_dimensions": (["off", "on"], {"default": "off"}),
                "width": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "height": ("INT", {"default": 1024, "min": 64, "max": 8192, "step": 8}),
                "image_usage": (["vision_guidance", "pose_reference"], {"default": "vision_guidance"}),
                "description_guidance": ("STRING", {
                    "multiline": True, 
                    "default": "Describe this image in detail for a text-to-image prompt.",
                    "dynamicPrompts": False
                }),
                "model": (get_ollama_models(settings.get('ollama_url', 'http://127.0.0.1:11434')),),
                "description_system_prompt": ("STRING", {
                    "multiline": True,
                    "default": get_prompt("description_system_prompt", "You are an expert image analyst..."),
                    "dynamicPrompts": False
                }),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1, "display": "slider"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "seed_priority": (["found_seed", "node_seed"], {"default": "found_seed"}),
            },
            "optional": {
                "image": ("IMAGE",),
            },
        }

    CATEGORY = "ModusFlow/Refine"
    RETURN_TYPES = ("IMAGE", "STRING", "STRING", "STRING", "INT", "LATENT", "INT", "INT")
    RETURN_NAMES = ("image", "image_usage", "positive_prompt", "negative_prompt", "seed", "latent", "width", "height")
    FUNCTION = "load_and_process_image"

    def _find_prompts_from_workflow(self, workflow_data):
        """More robustly find positive and negative prompts by checking common node types and widget names."""
        positive_prompt, negative_prompt = "", ""

        if not isinstance(workflow_data, dict) or "nodes" not in workflow_data:
            return "", ""

        nodes = workflow_data.get('nodes', [])

        text_node_types = ["CLIPTextEncode", "OllamaPromptRefiner", "ttN text", "SeargeText", "PrimitiveNode", "TextInput_"]

        positive_candidates = []
        negative_candidates = []

        for node in nodes:
            node_type = node.get("type")
            if node_type not in text_node_types:
                continue

            node_title = node.get("title", "").lower()
            widgets = node.get("widgets_values", [])

            # Heuristic: find the longest string in the widgets_values list, as it's the most likely candidate for the prompt.
            longest_string_in_widget = ""
            if widgets and isinstance(widgets, list):
                for w_val in widgets:
                    if isinstance(w_val, str) and len(w_val) > len(longest_string_in_widget):
                        longest_string_in_widget = w_val
            
            if not longest_string_in_widget:
                continue

            prompt_text = longest_string_in_widget

            is_negative_candidate = "negative" in node_title

            # A node is positive if its title suggests it, or if it's a type that's almost always a positive prompt holder and not explicitly negative.
            is_positive_candidate = "positive" in node_title or \
                                    (node_type in ["CLIPTextEncode", "TextInput_", "ttN text", "PrimitiveNode"] and not is_negative_candidate)

            if is_positive_candidate:
                positive_candidates.append((node.get('id', 'N/A'), node_title, prompt_text))
            if is_negative_candidate:
                negative_candidates.append((node.get('id', 'N/A'), node_title, prompt_text))

        # Heuristic: from all the candidates, pick the one with the longest text.
        if positive_candidates:
            best_candidate = max(positive_candidates, key=lambda item: len(item[2]))
            node_id, node_title, raw_positive_prompt = best_candidate
            positive_prompt = ' '.join(raw_positive_prompt.splitlines()).strip()
        if negative_candidates:
            best_candidate = max(negative_candidates, key=lambda item: len(item[2]))
            node_id, node_title, raw_negative_prompt = best_candidate
            negative_prompt = ' '.join(raw_negative_prompt.splitlines()).strip()
            
        return positive_prompt, negative_prompt

    def _find_seed_from_workflow(self, workflow_data):
        """More robustly find a seed by checking common sampler nodes."""
        if not isinstance(workflow_data, dict) or "nodes" not in workflow_data:
            return None

        nodes = {str(node['id']): node for node in workflow_data.get('nodes', [])}
        sampler_node_types = ["KSampler", "KSamplerAdvanced", "UltimateSDUpscale", "FaceDetailer"]

        for node in nodes.values():
            if node.get("type") in sampler_node_types:
                widgets = node.get("widgets_values", [])
                if isinstance(widgets, list):
                    # Find a widget that is an integer, likely the seed.
                    # This is a heuristic but better than the previous specific checks.
                    for i, val in enumerate(widgets):
                        if isinstance(val, int) and val > 0:
                            # Check if the next widget is a control string
                            if i + 1 < len(widgets) and widgets[i+1] in ["randomize", "increment", "decrement", "fixed"]:
                                return val

        return None

    def _extract_metadata(self, pil_image):
        """Extracts prompts and seed from image metadata."""
        metadata = pil_image.info or {}
        workflow_str = metadata.get('workflow') or metadata.get('prompt')
        
        if not isinstance(workflow_str, str):
            return "", "", None
            
        try:
            workflow_data = json.loads(workflow_str)
            positive_prompt, negative_prompt = self._find_prompts_from_workflow(workflow_data)
            found_seed = self._find_seed_from_workflow(workflow_data)
            return positive_prompt, negative_prompt, found_seed
        except json.JSONDecodeError:
            pass
        except Exception as e:
            pass

        return "", "", None

    def _create_placeholder_image(self, text="Image not found", width=512, height=512, batch_size=1):
        """Creates a black placeholder image with text."""
        img = Image.new('RGB', (width, height), color='black')
        draw = ImageDraw.Draw(img)
        
        # Try to load a font, fallback to default
        try:
            font = ImageFont.truetype("arial.ttf", 40)
        except IOError:
            try:
                # For linux, try a common path
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
            except IOError:
                font = ImageFont.load_default()

        # Center the text, trying modern and falling back to older methods
        try:
            # Modern Pillow versions with anchor support
            draw.text((width / 2, height / 2), text, fill="white", font=font, anchor="mm")
        except TypeError:
            # Fallback for older Pillow versions
            try:
                bbox = draw.textbbox((0, 0), text, font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                position = ((width - text_width) / 2, (height - text_height) / 2)
            except AttributeError:
                # Even older Pillow versions
                text_width, text_height = draw.textsize(text, font=font)
                position = ((width - text_width) / 2, (height - text_height) / 2)
            draw.text(position, text, fill="white", font=font)

        img_for_tensor = np.array(img).astype(np.float32) / 255.0
        img_tensor = torch.from_numpy(img_for_tensor)[None,]
        img_out = img_tensor.repeat(batch_size, 1, 1, 1)
        
        latent = torch.zeros([batch_size, 4, height // 8, width // 8])
        latent_out = {"samples": latent, "width": width, "height": height}
        return img_out, latent_out

    def _describe_image_with_ollama(self, pil_image, ollama_url, model, description_system_prompt, description_guidance, temperature, seed):
        """Generates a description for an image using a multimodal Ollama model."""
        try:
            buffered = io.BytesIO()
            pil_image.convert("RGB").save(buffered, format="PNG")
            img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
            api_url = f"{ollama_url}/api/chat"
            user_content = description_guidance if description_guidance and description_guidance.strip() else "Describe this image."
            user_message = {"role": "user", "content": user_content, "images": [img_base64]}
            payload = {
                "model": model,
                "messages": [{"role": "system", "content": description_system_prompt}, user_message],
                "stream": False,
                "options": {"temperature": temperature, "seed": seed}
            }

            timeout_val = settings.get('ollama_timeout', 120)
            response = requests.post(api_url, json=payload, timeout=timeout_val)
            response.raise_for_status()
            response_data = response.json()

            if "error" in response_data:
                return ""

            api_response = response_data.get("message", {}).get("content", "").strip()
            if api_response:
                description = sanitize_llm_output(api_response)
                return description
        except requests.exceptions.RequestException as e:
            pass
        except Exception as e:
            pass

        return ""

    def _process_single_image(self, pil_image, batch_size, image_usage, prompt_source, description_guidance, model, description_system_prompt, temperature, seed, seed_priority, override_dimensions, width, height, original_tensor=None):
        """Unified processing logic for a single image, from file or tensor."""
        ollama_url = settings.get('ollama_url')
        img_width, img_height = pil_image.size

        latent_width = width if override_dimensions == "on" else img_width
        latent_height = height if override_dimensions == "on" else img_height
        
        # --- Metadata and Prompt Logic ---
        positive_prompt, negative_prompt, found_seed = self._extract_metadata(pil_image)

        if prompt_source == "force_description":
            positive_prompt = "" # Clear any found prompt

        # --- Seed Logic ---
        final_seed = seed
        if seed_priority == "found_seed" and found_seed is not None:
            final_seed = found_seed

        # --- Description Logic ---
        if not positive_prompt and model and not model.startswith("ollama-not-running"):
            positive_prompt = self._describe_image_with_ollama(
                pil_image, ollama_url, model, description_system_prompt, 
                description_guidance, temperature, final_seed
            )

        # --- Tensor Creation ---
        if original_tensor is not None:
            img_tensor = original_tensor
        else:
            img_for_tensor = pil_image.convert("RGB")
            img_for_tensor = np.array(img_for_tensor).astype(np.float32) / 255.0
            img_tensor = torch.from_numpy(img_for_tensor)[None,]
        
        img_out = img_tensor.repeat(batch_size, 1, 1, 1)
        latent = torch.zeros([batch_size, 4, latent_height // 8, latent_width // 8], device=img_out.device)
        latent_out = {"samples": latent, "width": latent_width, "height": latent_height}
        return (img_out, image_usage, positive_prompt, negative_prompt, final_seed, latent_out, latent_out["width"], latent_out["height"])

    def _handle_tensor_input(self, image, image_usage, seed, batch_size, prompt_source, description_guidance, model, description_system_prompt, temperature, seed_priority, override_dimensions, width, height):
        """Handles logic when an image tensor is provided directly to the input."""
        if image.shape[0] > 1:
            img_out = image
            final_batch_size = image.shape[0]
            _, img_height, img_width, _ = img_out.shape
            latent_width = width if override_dimensions == "on" else img_width
            latent_height = height if override_dimensions == "on" else img_height
            latent = torch.zeros([final_batch_size, 4, latent_height // 8, latent_width // 8], device=img_out.device)
            latent_out = {"samples": latent, "width": latent_width, "height": latent_height}
            return (img_out, image_usage, "", "", seed, latent_out, latent_out["width"], latent_out["height"])

        i = 255. * image[0].cpu().numpy()
        pil_image = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))

        return self._process_single_image(pil_image, batch_size, image_usage, prompt_source, description_guidance, model, description_system_prompt, temperature, seed, seed_priority, override_dimensions, width, height, original_tensor=image)

    def _handle_folder_input(self, folder_name, image_usage, seed, override_dimensions, width, height):
        """Handles logic for loading a batch of images from a folder."""
        image_dir = os.path.join(folder_paths.get_input_directory(), folder_name)

        if not os.path.isdir(image_dir):
            latent_width = width if override_dimensions == "on" else 512
            latent_height = height if override_dimensions == "on" else 512
            img_out, latent_out = self._create_placeholder_image(text=f"Folder not found:\n{folder_name}", width=latent_width, height=latent_height, batch_size=1)
            return (img_out, image_usage, "", "", seed, latent_out, latent_out["width"], latent_out["height"])

        image_paths = []
        for f in sorted(os.listdir(image_dir)):
            if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp', '.bmp')):
                image_paths.append(os.path.join(image_dir, f))

        if not image_paths:
            latent_width = width if override_dimensions == "on" else 512
            latent_height = height if override_dimensions == "on" else 512
            img_out, latent_out = self._create_placeholder_image(text=f"No images in\n{folder_name}", width=latent_width, height=latent_height, batch_size=1)
            return (img_out, image_usage, "", "", seed, latent_out, latent_out["width"], latent_out["height"])

        # Determine target dimensions for resizing and latent creation
        try:
            with Image.open(image_paths[0]) as first_img:
                first_img_width, first_img_height = first_img.size
        except Exception as e:
            first_img_width, first_img_height = 512, 512

        if override_dimensions == "on":
            target_width, target_height = width, height
        else:
            target_width, target_height = first_img_width, first_img_height
        
        image_tensors = []
        for path in image_paths:
            try:
                with Image.open(path) as i:
                    i = ImageOps.exif_transpose(i).convert("RGB")
                    if i.size != (target_width, target_height):
                        i = i.resize((target_width, target_height), Image.LANCZOS)
                    
                    image_np = np.array(i).astype(np.float32) / 255.0
                    image_tensors.append(torch.from_numpy(image_np))
            except Exception as e:
                pass
        
        if not image_tensors:
            img_out, latent_out = self._create_placeholder_image(text=f"Failed to load any images\nfrom {folder_name}", width=target_width, height=target_height, batch_size=1)
            return (img_out, image_usage, "", "", seed, latent_out, latent_out["width"], latent_out["height"])

        img_out = torch.stack(image_tensors)
        
        folder_batch_size = img_out.shape[0]
        latent = torch.zeros([folder_batch_size, 4, target_height // 8, target_width // 8])
        latent_out = {"samples": latent, "width": target_width, "height": target_height}
        return (img_out, image_usage, "", "", seed, latent_out, latent_out["width"], latent_out["height"])

    def load_and_process_image(self, image_or_folder, prompt_source, batch_size, override_dimensions, width, height, image_usage, description_guidance, model, description_system_prompt, temperature, seed, seed_priority, image=None):
        ollama_url = settings.get('ollama_url')

        if image is None and (image_or_folder is None or image_or_folder == "--no items found--"):
            latent_width = width if override_dimensions == "on" else 512
            latent_height = height if override_dimensions == "on" else 512
            img_out, latent_out = self._create_placeholder_image(text="No image provided", width=latent_width, height=latent_height, batch_size=batch_size)
            return (img_out, image_usage, "", "", seed, latent_out, latent_out["width"], latent_out["height"])

        if image is not None:
            return self._handle_tensor_input(image, image_usage, seed, batch_size, prompt_source, description_guidance, model, description_system_prompt, temperature, seed_priority, override_dimensions, width, height)
        elif image_or_folder.startswith("[FOLDER] "):
            folder_name = image_or_folder.replace("[FOLDER] ", "").strip()
            return self._handle_folder_input(folder_name, image_usage, seed, override_dimensions, width, height)
        else:
            image_filename = image_or_folder
            image_path = folder_paths.get_annotated_filepath(image_filename)
            if not os.path.exists(image_path):
                latent_width = width if override_dimensions == "on" else 512
                latent_height = height if override_dimensions == "on" else 512
                img_out, latent_out = self._create_placeholder_image(text="Image not found", width=latent_width, height=latent_height, batch_size=batch_size)
                return (img_out, image_usage, "", "", seed, latent_out, latent_out["width"], latent_out["height"])

            pil_image = Image.open(image_path)
            pil_image = ImageOps.exif_transpose(pil_image)
            
            return self._process_single_image(pil_image, batch_size, image_usage, prompt_source, description_guidance, model, description_system_prompt, temperature, seed, seed_priority, override_dimensions, width, height, original_tensor=None)
