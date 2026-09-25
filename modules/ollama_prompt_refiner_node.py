import requests
import json
import re
import torch
import numpy as np
from PIL import Image, ImageOps
import io
import base64
import os
import folder_paths
import comfy.sd
from ..config import settings, get_prompt
from .modusflow_utils import get_ollama_models, sanitize_llm_output

class OllamaPromptRefinerNode:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "refiner_status": (["enabled", "bypassed"], {"default": "enabled"}),
                "mode": (["refine", "generate"],),
                "text_input": ("STRING", {"multiline": True, "default": "A beautiful painting of a cat"}),
                "negative_prompt": ("STRING", {"multiline": True, "default": ""}),
                "prepend_positive": ("STRING", {"multiline": True, "default": ""}),
                "prepend_negative": ("STRING", {"multiline": True, "default": ""}),
                "positive_embeddings": ("STRING", {"multiline": True, "default": ""}),
                "negative_embeddings": ("STRING", {"multiline": True, "default": ""}),
                "ollama_model": (get_ollama_models(settings.get('ollama_url')),),
                "refine_mode_system_prompt": ("STRING", {
                    "multiline": True,
                    "default": get_prompt("refine_mode_system_prompt", "You are an expert prompt engineer...")
                }),
                "generate_mode_system_prompt": ("STRING", {
                    "multiline": True,
                    "default": get_prompt("generate_mode_system_prompt", "You are an expert prompt engineer...")
                }),
                "pose_reference_system_prompt": ("STRING", {
                    "multiline": True,
                    "default": get_prompt("pose_reference_system_prompt", "You are an expert prompt engineer...")
                }),
                "temperature": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 2.0, "step": 0.1, "display": "slider"}),
                "max_tokens": ("INT", {"default": 200, "min": 50, "max": 4096, "step": 1, "display": "number"}),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "use_flux_guidance": (["enabled", "disabled"], {"default": "enabled"}),
                "flux_guidance": ("FLOAT", {"default": 3.5, "min": 0.0, "max": 100.0, "step": 0.1, "display": "slider"}),
            },
            "optional": {
                "pipe": ("PIPE",),
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "positive_conditioning": ("CONDITIONING",),
                "negative_conditioning": ("CONDITIONING",),
                "width": ("INT", {"default": 1024, "min": 32, "max": 4096, "step": 1, "display": "number"}),
                "height": ("INT", {"default": 1024, "min": 32, "max": 4096, "step": 1, "display": "number"}),
                "use_image_dimensions": (["defined", "original_image"], {"default": "defined"}),
                "image_usage": (["vision_guidance", "pose_reference"], {"default": "vision_guidance"}),
                "seed_override": ("INT", {"default": -1, "min": -1, "max": 0xffffffffffffffff}),
                "image": ("IMAGE",),
                "latent": ("LATENT",),
            },
        }

    RETURN_TYPES = ("MODEL", "CONDITIONING", "CONDITIONING", "STRING", "STRING", "CLIP", "IMAGE", "INT", "LATENT", "INT", "INT", "PIPE")
    RETURN_NAMES = ("model", "positive", "negative", "refined_prompt", "negative_prompt", "clip", "image", "seed", "latent", "width", "height", "pipe")
    FUNCTION = "refine_prompt"
    CATEGORY = "ModusFlow/Refine"

    def refine_prompt(self, 
                      refiner_status, 
                      mode, 
                      text_input, 
                      negative_prompt, 
                      prepend_positive, 
                      prepend_negative, 
                      positive_embeddings, 
                      negative_embeddings, 
                      ollama_model, 
                      refine_mode_system_prompt, 
                      generate_mode_system_prompt, 
                      pose_reference_system_prompt, 
                      temperature, 
                      max_tokens, 
                      seed,
                      use_flux_guidance,
                      flux_guidance,
                      pipe=None, model=None, clip=None,
                      positive_conditioning=None, negative_conditioning=None,
                      width=1024, height=1024, use_image_dimensions="defined", image_usage="vision_guidance",
                      seed_override=-1, image=None, latent=None):
        
        # Extract from pipe or use individual inputs
        vae = None  # Initialize VAE
        if pipe is not None:
            # Pipe format: (model, clip, vae, positive, negative)
            model = model if model is not None else (pipe[0] if len(pipe) > 0 else None)
            clip = clip if clip is not None else (pipe[1] if len(pipe) > 1 else None)
            vae = pipe[2] if len(pipe) > 2 else None  # Extract VAE from pipe for passthrough
        
        # Stub classes for safe fallback
        class StubModel:
            def get_model_object(self, name):
                return None
        class StubClip:
            pass
        
        # Validate that we have model and clip - use stubs if missing to prevent validation failure
        if model is None:
            model = StubModel()
        if clip is None:
            clip = StubClip()
        # Use latent image input if provided, else create new
        try:
            # Initialize variables
            positive, negative = [], []
            final_positive_text, final_negative_text = "", ""
            latent_out = latent

            # Corrected latent dimension logic
            latent_width = width
            latent_height = height

            if latent is not None and "samples" in latent:
                latent_width = latent.get("width", latent_width)
                latent_height = latent.get("height", latent_height)
                # Force image dimensions to match latent
                if image is not None:
                    # ComfyUI image tensors are (B, H, W, C). F.interpolate expects (B, C, H, W).
                    if image.shape[1] != latent_height or image.shape[2] != latent_width:
                        import torch.nn.functional as F
                        # Permute to (B, C, H, W) for interpolation
                        image_permuted = image.permute(0, 3, 1, 2)
                        # Interpolate
                        image_resized = F.interpolate(image_permuted, size=(latent_height, latent_width), mode="bilinear", align_corners=False)
                        # Permute back to (B, H, W, C)
                        image = image_resized.permute(0, 2, 3, 1)
            else:
                if use_image_dimensions == "original_image" and image is not None:
                    latent_width, latent_height = image.shape[2], image.shape[1]

                try:
                    import comfy.model_management
                    device = comfy.model_management.intermediate_device()
                except ImportError:
                    device = None
                latent_img = torch.zeros([1, 4, latent_height // 8, latent_width // 8], device=device)
                latent_out = {"samples": latent_img, "width": latent_width, "height": latent_height}

            ollama_url = settings.get('ollama_url')
            final_seed = seed
            if seed_override is not None and seed_override != -1:
                final_seed = seed_override

            final_image_usage = image_usage
            if final_image_usage not in ["vision_guidance", "pose_reference"]:
                final_image_usage = "vision_guidance"

            if refiner_status == "enabled":
                if ollama_model.startswith("ollama-not-running") or ollama_model.startswith("ollama-no-models-found"):
                    pass
                else:
                    if image is not None and final_image_usage == 'pose_reference':
                        system_prompt = pose_reference_system_prompt
                        log_action = "Generating prompt with pose reference"
                    elif mode == "refine":
                        system_prompt = refine_mode_system_prompt
                        log_action = "Refining prompt"
                    else:
                        system_prompt = generate_mode_system_prompt
                        log_action = "Generating prompt"

                    try:
                        img_base64 = None
                        if image is not None:
                            # Validate image tensor shape before processing
                            if len(image.shape) == 4 and image.shape[3] in [3, 4]:
                                i = 255. * image[0].cpu().numpy()
                                img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
                                buffered = io.BytesIO()
                                img.save(buffered, format="PNG")
                                img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')

                        api_url = f"{ollama_url}/api/chat"
                        user_message = {"role": "user", "content": text_input}
                        if img_base64:
                            user_message["images"] = [img_base64]

                        payload = {
                            "model": ollama_model,
                            "messages": [{"role": "system", "content": system_prompt}, user_message],
                            "stream": False,
                            "options": {"temperature": temperature, "num_predict": max_tokens, "seed": final_seed}
                        }

                        timeout_val = settings.get('ollama_timeout', 120)
                        response = requests.post(api_url, json=payload, timeout=timeout_val)
                        response.raise_for_status()
                        response_data = response.json()
                    
                        if "error" in response_data:
                            pass
                        else:
                            api_response = response_data.get("message", {}).get("content", "").strip()
                            if api_response:
                                text_input = sanitize_llm_output(api_response)

                    except requests.exceptions.RequestException as e:
                        pass
                    except Exception as e:
                        pass

            # Check if conditioning inputs are provided - if so, bypass text encoding
            use_positive_conditioning = positive_conditioning is not None
            use_negative_conditioning = negative_conditioning is not None
            
            if use_positive_conditioning:
                positive = positive_conditioning
                # Try to extract prompt text from conditioning metadata if available
                final_positive_text = ""
                if isinstance(positive_conditioning, list) and len(positive_conditioning) > 0:
                    cond_data = positive_conditioning[0]
                    if isinstance(cond_data, list) and len(cond_data) > 1 and isinstance(cond_data[1], dict):
                        final_positive_text = cond_data[1].get("prompt_text", "")
            else:
                # Build positive text from text inputs
                positive_parts = []
                if prepend_positive and prepend_positive.strip():
                    positive_parts.append(prepend_positive.strip())
                if text_input and text_input.strip():
                    positive_parts.append(text_input.strip())
                if positive_embeddings and positive_embeddings.strip():
                    positive_parts.append(positive_embeddings.strip())
                final_positive_text = ", ".join(filter(None, positive_parts))

            if use_negative_conditioning:
                negative = negative_conditioning
                # Try to extract prompt text from conditioning metadata if available
                final_negative_text = ""
                if isinstance(negative_conditioning, list) and len(negative_conditioning) > 0:
                    cond_data = negative_conditioning[0]
                    if isinstance(cond_data, list) and len(cond_data) > 1 and isinstance(cond_data[1], dict):
                        final_negative_text = cond_data[1].get("prompt_text", "")
            else:
                # Build negative text from text inputs
                negative_parts = []
                if prepend_negative and prepend_negative.strip():
                    negative_parts.append(prepend_negative.strip())
                if negative_prompt and negative_prompt.strip():
                    negative_parts.append(negative_prompt.strip())
                if negative_embeddings and negative_embeddings.strip():
                    negative_parts.append(negative_embeddings.strip())
                final_negative_text = ", ".join(filter(None, negative_parts))
            
            # Tokenize and encode only if clip is available and conditioning not provided
            if clip:
                is_flux_clip = hasattr(clip, 'clip_type') and clip.clip_type == comfy.sd.CLIPType.FLUX

                # Encode positive if not provided as conditioning
                if not use_positive_conditioning:
                    if is_flux_clip:
                        # FLUX models use a T5 text encoder and don't use pooled_output.
                        tokens = clip.tokenize(final_positive_text)
                        cond = clip.encode_from_tokens(tokens)
                        
                        # Apply Flux Guidance if enabled
                        if use_flux_guidance == "enabled":
                            positive = [[cond, {"guidance": flux_guidance, "prompt_text": final_positive_text}]]
                        else:
                            positive = [[cond, {"prompt_text": final_positive_text}]]
                    else:
                        # Default behavior for SDXL and other models that use pooled_output.
                        tokens = clip.tokenize(final_positive_text)
                        cond, pooled = clip.encode_from_tokens(tokens, return_pooled=True)
                        positive = [[cond, {"pooled_output": pooled, "prompt_text": final_positive_text}]]
                
                # Encode negative if not provided as conditioning
                if not use_negative_conditioning:
                    if is_flux_clip:
                        negative_tokens = clip.tokenize(final_negative_text)
                        neg_cond = clip.encode_from_tokens(negative_tokens)
                        
                        # Apply Flux Guidance if enabled
                        if use_flux_guidance == "enabled":
                            negative = [[neg_cond, {"guidance": flux_guidance, "prompt_text": final_negative_text}]]
                        else:
                            negative = [[neg_cond, {"prompt_text": final_negative_text}]]
                    else:
                        negative_tokens = clip.tokenize(final_negative_text)
                        neg_cond, neg_pooled = clip.encode_from_tokens(negative_tokens, return_pooled=True)
                        negative = [[neg_cond, {"pooled_output": neg_pooled, "prompt_text": final_negative_text}]]

            # Final guard: ensure model and clip are valid, and latent is well-formed
            if model is None or not hasattr(model, 'get_model_object'):
                model = StubModel()
            if clip is None:
                clip = StubClip()
            # Ensure latent dict is valid and tensor shape matches metadata
            def make_valid_latent(latent_obj, w, h):
                if not isinstance(latent_obj, dict):
                    latent_img = torch.zeros([1, 4, h // 8, w // 8])
                    return {"samples": latent_img, "width": w, "height": h}
                if "samples" not in latent_obj or not isinstance(latent_obj["samples"], torch.Tensor):
                    latent_obj["samples"] = torch.zeros([1, 4, h // 8, w // 8])
                latent_obj.setdefault("width", w)
                latent_obj.setdefault("height", h)
                s = latent_obj["samples"]
                expected_h, expected_w = latent_obj["height"] // 8, latent_obj["width"] // 8
                if s.shape[-2:] != (expected_h, expected_w):
                    latent_obj["samples"] = torch.zeros([s.shape[0], s.shape[1], expected_h, expected_w])
                return latent_obj

            latent_out = make_valid_latent(latent_out, latent_width, latent_height)
            refined_prompt = final_positive_text
            negative_prompt = final_negative_text
            image = image if image is not None else torch.zeros([1, 3, 8, 8])
            seed = seed if seed is not None else 0
            # Create output pipe (passthrough VAE from input pipe)
            output_pipe = (model, clip, vae, positive, negative)
            
            return (model, positive, negative, refined_prompt, negative_prompt, clip, image, seed, latent_out, latent_out["width"], latent_out["height"], output_pipe)
        except Exception as e:
            # Always return explicit safe defaults, never reference possibly undefined variables
            stub_model = StubModel()
            stub_clip = StubClip()
            error_pipe = (stub_model, stub_clip, None, [], [])  # Include pipe in error return
            return (stub_model, [], [], "", "", stub_clip, torch.zeros([1, 3, 8, 8]), 0, {"samples": torch.zeros([1, 4, 8, 8]), "width": 64, "height": 64}, 64, 64, error_pipe)
