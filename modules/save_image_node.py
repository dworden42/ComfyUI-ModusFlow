"""
ModusFlow Save Image Node

Save images with variable filename support:
  %date%      -> YYYY-MM-DD
  %time%      -> HH-MM-SS
  %datetime%  -> YYYY-MM-DD_HH-MM-SS
  %year%  %month%  %day%  %hour%  %minute%  %second%
  %seed%      -> seed value (optional input)
  %width%     -> image width in pixels
  %height%    -> image height in pixels
  %batch_num% -> batch index

Formats: png (lossless), jpeg, webp
embed_metadata: enabled = workflow/prompt embedded; disabled = clean file with no metadata
"""

import os
import json
import numpy as np
from PIL import Image
from PIL.PngImagePlugin import PngInfo

import folder_paths
from .save_audio_node import _expand_shorthand_vars

try:
    import torch
    _has_torch = True
except ImportError:
    _has_torch = False


def _build_workflow_xmp(workflow_data):
    escaped = json.dumps(workflow_data).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (
        '<?xpacket begin="\xef\xbb\xbf" id="W5M0MpCehiHzreSzNTczkc9d"?>'
        '<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        '<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{escaped}</rdf:li></rdf:Alt></dc:description>'
        '</rdf:Description></rdf:RDF></x:xmpmeta>'
        '<?xpacket end="w"?>'
    ).encode("utf-8")


class ModusFlowSaveImage:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "images": ("IMAGE",),
                "filename_prefix": ("STRING", {"default": "images/%date%/ComfyUI_%seed%"}),
                "format": (["png", "jpeg", "webp"], {"default": "png"}),
                "quality": ("INT", {"default": 95, "min": 1, "max": 100, "step": 1, "display": "slider"}),
                "embed_metadata": (["enabled", "disabled"], {"default": "enabled"}),
                "clean_vram": ("BOOLEAN", {"default": False, "label_on": "Clean VRAM", "label_off": "Keep VRAM"}),
            },
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_images"
    OUTPUT_NODE = True
    CATEGORY = "ModusFlow/Utilities"

    def save_images(self, images, filename_prefix, format, quality, embed_metadata="enabled", clean_vram=False, seed=None, prompt=None, extra_pnginfo=None):
        output_dir = folder_paths.get_output_directory()
        results = []

        for batch_number, image_tensor in enumerate(images):
            # Convert tensor (H, W, C) float [0,1] -> uint8
            i = 255.0 * image_tensor.cpu().numpy()
            img = Image.fromarray(np.clip(i, 0, 255).astype(np.uint8))
            w, h = img.size

            # Expand variables — width/height substituted after expansion
            prefix = _expand_shorthand_vars(filename_prefix, seed=seed)
            prefix = prefix.replace("%width%", str(w)).replace("%height%", str(h))
            prefix = prefix.replace("%batch_num%", str(batch_number))

            full_output_folder, filename, counter, subfolder, _ = folder_paths.get_save_image_path(
                prefix, output_dir, w, h
            )

            ext = format
            file = f"{filename}_{counter:05}_.{ext}"
            output_path = os.path.join(full_output_folder, file)

            should_embed = embed_metadata == "enabled"

            if format == "png":
                metadata = None
                if should_embed:
                    metadata = PngInfo()
                    if prompt is not None:
                        metadata.add_text("prompt", json.dumps(prompt))
                    if extra_pnginfo is not None:
                        for k, v in extra_pnginfo.items():
                            metadata.add_text(k, json.dumps(v))
                img.save(output_path, pnginfo=metadata, compress_level=4)

            elif format == "jpeg":
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                if should_embed and (prompt is not None or extra_pnginfo is not None):
                    workflow_data = {}
                    if prompt is not None:
                        workflow_data["prompt"] = prompt
                    if extra_pnginfo is not None:
                        workflow_data.update(extra_pnginfo)
                    exif = Image.Exif()
                    exif[0x010e] = json.dumps(workflow_data)  # ImageDescription tag
                    img.save(output_path, quality=quality, optimize=True, exif=exif.tobytes())
                else:
                    img.save(output_path, quality=quality, optimize=True, exif=b"")

            elif format == "webp":
                if should_embed and (prompt is not None or extra_pnginfo is not None):
                    workflow_data = {}
                    if prompt is not None:
                        workflow_data["prompt"] = prompt
                    if extra_pnginfo is not None:
                        workflow_data.update(extra_pnginfo)
                    xmp = _build_workflow_xmp(workflow_data)
                    img.save(output_path, quality=quality, method=6, xmp=xmp)
                else:
                    img.save(output_path, quality=quality, method=6)

            print(f"[ModusFlow SaveImage] Saved: {output_path}")
            results.append({"filename": file, "subfolder": subfolder, "type": "output"})

        if clean_vram and _has_torch and torch.cuda.is_available():
            torch.cuda.empty_cache()
            print("[ModusFlow SaveImage] VRAM cache cleared.")

        return {"ui": {"images": results}}
