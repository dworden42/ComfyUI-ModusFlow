import os
import sys
import torch
from nodes import CLIPTextEncode

class ModusFlowTextEditor:
    """
    A resizable text editor node with save/load functionality.
    Allows editing positive and negative prompts with both input and output connections.
    Provides ability to save and load text prompts from a configurable directory as JSON files.
    """

    @classmethod
    def INPUT_TYPES(cls):
        # Get saved prompts for dropdown
        saved_prompts = cls.get_saved_prompts()
        
        return {
            "required": {
                "positive": ("STRING", {"default": "", "multiline": True}),
                "negative": ("STRING", {"default": "", "multiline": True}),
                "saved_prompt": (saved_prompts, {"default": saved_prompts[0] if saved_prompts else ""}),
            },
            "optional": {
                "positive_input": ("STRING", {"forceInput": True}),
                "negative_input": ("STRING", {"forceInput": True}),
                "positive_embedding": ("STRING", {"forceInput": True}),
                "negative_embedding": ("STRING", {"forceInput": True}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }
    
    @classmethod
    def get_saved_prompts(cls):
        """Get list of saved prompts from the configured directory."""
        try:
            from ..config import settings, BASE_DIR
            prompts_dir = settings.get('prompts_save_directory', '').strip()
            if not prompts_dir:
                prompts_dir = os.path.join(BASE_DIR, 'saved_prompts')
            
            if os.path.isdir(prompts_dir):
                files = [f for f in os.listdir(prompts_dir) if f.endswith('.json')]
                files.sort()
                if files:
                    return ["--select prompt--"] + files
        except Exception as e:
            print(f"[ModusFlow TextEditor] Error loading prompts list: {e}")
        
        return ["--no prompts found--"]

    RETURN_TYPES = ("STRING", "STRING",)
    RETURN_NAMES = ("positive", "negative",)
    FUNCTION = "process_text"
    OUTPUT_NODE = False
    CATEGORY = "ModusFlow/Utilities"

    def process_text(self, positive, negative, saved_prompt, positive_input=None, negative_input=None, positive_embedding=None, negative_embedding=None, unique_id=None, extra_pnginfo=None):
        """Process positive and negative text inputs and return them as outputs."""
        # If connected inputs are provided, they take precedence over widget values
        output_positive = positive_input if positive_input is not None else positive
        output_negative = negative_input if negative_input is not None else negative

        # Append embeddings to respective outputs
        if positive_embedding is not None and positive_embedding.strip():
            output_positive = f"{output_positive}, {positive_embedding}".strip(", ")
        if negative_embedding is not None and negative_embedding.strip():
            output_negative = f"{output_negative}, {negative_embedding}".strip(", ")

        # Update the node's widget values in the workflow metadata if available
        if unique_id is not None and extra_pnginfo is not None:
            if isinstance(extra_pnginfo, dict) and "workflow" in extra_pnginfo:
                workflow = extra_pnginfo["workflow"]
                node = next(
                    (x for x in workflow["nodes"] if str(x["id"]) == str(unique_id)),
                    None,
                )
                if node:
                    node["widgets_values"] = [output_positive, output_negative, saved_prompt]

        return (output_positive, output_negative,)
