import torch


class ModusFlowLatentPreset:
    """Create a blank latent with common resolution presets or manual size."""

    @classmethod
    def INPUT_TYPES(cls):
        presets = [
            "1024x1024 (Square)",
            "832x1216 (Portrait)",
            "1216x832 (Landscape)",
            "960x1280 (Portrait)",
            "1280x960 (Landscape)",
            "768x1152 (Portrait)",
            "1152x768 (Landscape)",
            "Manual",
        ]

        return {
            "required": {
                "resolution": (presets, {"default": presets[0]}),
                "width": ("INT", {"default": 1024, "min": 64, "max": 4096, "step": 8}),
                "height": ("INT", {"default": 1024, "min": 64, "max": 4096, "step": 8}),
                "batch_size": ("INT", {"default": 1, "min": 1, "max": 64, "step": 1}),
                "latent_channels": ("INT", {"default": 4, "min": 1, "max": 16, "step": 1}),
                "downscale": ("INT", {"default": 8, "min": 1, "max": 32, "step": 1}),
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "create_latent"
    CATEGORY = "ModusFlow/Latent"

    def create_latent(self, resolution, width, height, batch_size, latent_channels, downscale):
        preset_map = {
            "1024x1024 (Square)": (1024, 1024),
            "832x1216 (Portrait)": (832, 1216),
            "1216x832 (Landscape)": (1216, 832),
            "960x1280 (Portrait)": (960, 1280),
            "1280x960 (Landscape)": (1280, 960),
            "768x1152 (Portrait)": (768, 1152),
            "1152x768 (Landscape)": (1152, 768),
        }

        if resolution != "Manual":
            width, height = preset_map.get(resolution, (1024, 1024))

        # Ensure latent spatial dims align to downscale factor (ceil to nearest multiple)
        latent_width = (width + downscale - 1) // downscale
        latent_height = (height + downscale - 1) // downscale

        latent = torch.zeros((batch_size, latent_channels, latent_height, latent_width))
        return ({"samples": latent, "width": width, "height": height},)
