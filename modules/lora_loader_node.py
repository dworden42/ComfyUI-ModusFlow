import torch
import folder_paths
import os
import json
from nodes import LoraLoader as CoreLoraLoader
from ..config import settings

class ModusFlowLoraLoader:
    @staticmethod
    def find_lora_path(lora_name: str, lora_paths: list[str]) -> str | None:
        """Finds a LoRA path from a given name, trying multiple case-insensitive strategies for robustness."""
        lora_name_norm = lora_name.strip().replace('\\', '/')
        lora_name_lower = lora_name_norm.lower()

        # Strategy 1: Case-insensitive exact match
        for p in lora_paths:
            if p.lower().replace('\\', '/') == lora_name_lower:
                return p

        # Strategy 2: Case-insensitive basename match
        lora_basename_lower = os.path.basename(lora_name_lower)
        for p in lora_paths:
            if os.path.basename(p.lower().replace('\\', '/')) == lora_basename_lower:
                return p

        # Strategy 3: Case-insensitive basename match without extension
        lora_basename_no_ext_lower = os.path.splitext(lora_basename_lower)[0]
        for p in lora_paths:
            p_basename_no_ext_lower = os.path.splitext(os.path.basename(p.lower().replace('\\', '/')))[0]
            if p_basename_no_ext_lower == lora_basename_no_ext_lower:
                return p

        return None

    @classmethod
    def INPUT_TYPES(cls):
        # Get base model types from config for the validation dropdown.
        try:
            # Add a "None" option for no validation
            base_model_types = ["None"] 
            definitions = settings.get("base_model_definitions", [])
            # Extract the 'type' from each definition dictionary
            base_model_types.extend([d.get("type") for d in definitions if d.get("type")])
            if len(base_model_types) == 1: # Only "None" is present
                 base_model_types.append("<no definitions in config>")
        except Exception as e:
            base_model_types = ["None", "<error loading definitions>"]

        return {
            "required": {
                # This hidden widget stores the state of the advanced list, managed by JS
                "lora_stack": ("STRING", {"default": "[]", "multiline": True, "hidden": True}),
                # This widget is for the UI to help validate LoRAs against a base model.
                "base_model_name": (base_model_types,),
            },
            "optional": {
                "pipe": ("PIPE",),
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                # Seed is a passthrough and should not have a widget.
                "seed": ("INT", {"forceInput": True}),
                # This widget is for the UI only, to filter the LoRA list.
                "lora_filter": ("STRING", {"default": "", "multiline": False}),
                # This widget holds the API key, making it part of the workflow.
                "civitai_api_key": ("STRING", {"default": "", "multiline": False, "hidden": True}),
            }
        }

    RETURN_TYPES = ("MODEL", "CLIP", "CONDITIONING", "CONDITIONING", "INT", "PIPE")
    RETURN_NAMES = ("model", "clip", "positive", "negative", "seed", "pipe")
    FUNCTION = "load_loras"
    CATEGORY = "ModusFlow/Loaders"

    def load_loras(self, lora_stack, base_model_name, pipe=None, model=None, clip=None, positive=None, negative=None, lora_filter="", seed=0, civitai_api_key=""):
        # Extract from pipe if provided (individual inputs override pipe)
        if pipe is not None:
            # Pipe format: (model, clip, vae, positive, negative)
            model = model if model is not None else (pipe[0] if len(pipe) > 0 else None)
            clip = clip if clip is not None else (pipe[1] if len(pipe) > 1 else None)
            vae = pipe[2] if len(pipe) > 2 else None
            positive = positive if positive is not None else (pipe[3] if len(pipe) > 3 else positive)
            negative = negative if negative is not None else (pipe[4] if len(pipe) > 4 else negative)
        else:
            vae = None
        
        # Validate that we have model and clip
        if model is None or clip is None:
            raise ValueError("MODEL and CLIP are required (provide via pipe or individual inputs)")
        
        # base_model_name is only used by the UI for validation and is not used in the execution logic here.
        lora_loader = CoreLoraLoader()
        lora_paths = folder_paths.get_filename_list("loras")

        try:
            lora_items = json.loads(lora_stack)
            if not isinstance(lora_items, list):
                lora_items = []
        except (json.JSONDecodeError, TypeError):
            lora_items = []

        enabled_loras = [item for item in lora_items if item.get("enabled", False)]

        if not enabled_loras:
            # Ensure conditioning outputs are valid lists, not None, to prevent crashes.
            if positive is None: positive = []
            if negative is None: negative = []
            # Create output pipe
            output_pipe = (model, clip, vae, positive, negative)
            return (model, clip, positive, negative, seed, output_pipe)

        loaded_lora_count = 0

        for item in enabled_loras:
            lora_name = item.get("name")
            if not lora_name:
                continue

            lora_file = self.find_lora_path(lora_name, lora_paths)
            if lora_file:
                strength = item.get("strength", 1.0)
                
                if strength == 0:
                    continue

                try:
                    model, clip = lora_loader.load_lora(model, clip, lora_file, strength, strength)
                    loaded_lora_count += 1
                except Exception as e:
                    pass
            else:
                pass
        

        # Ensure conditioning outputs are valid lists, not None, to prevent crashes.
        if positive is None: positive = []
        if negative is None: negative = []
        
        # Create output pipe
        output_pipe = (model, clip, vae, positive, negative)
        return (model, clip, positive, negative, seed, output_pipe)

NODE_CLASS_MAPPINGS = {
    "ModusFlowLoraLoader": ModusFlowLoraLoader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModusFlowLoraLoader": "ModusFlow LoRA Loader"
}
