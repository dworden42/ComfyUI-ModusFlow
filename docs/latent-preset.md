# Latent Preset

Create a blank latent tensor with common resolution presets or manual dimensions.

## Overview
- Quickly generate empty latents sized for popular SDXL/selfie aspect ratios.
- Default preset: **1024x1024 (Square)**.
- Manual mode allows custom width/height.

## Inputs
- **resolution** (dropdown):
  - 1024x1024 (Square)
  - 832x1216 (Portrait)
  - 1216x832 (Landscape)
  - 960x1280 (Portrait)
  - 1280x960 (Landscape)
  - 768x1152 (Portrait)
  - 1152x768 (Landscape)
  - Manual
- **width** (INT): Used only when resolution = Manual. Default 1024.
- **height** (INT): Used only when resolution = Manual. Default 1024.
- **batch_size** (INT): Number of latents to create. Default 1.
- **latent_channels** (INT): Latent channel count (usually 4). Default 4.
- **downscale** (INT): VAE downscale factor (typically 8). Default 8.

## Outputs
- **latent** (LATENT): `{"samples": tensor, "width": W, "height": H}` sized to the selected resolution.

## Behavior
- Preset resolutions override width/height inputs.
- Latent spatial size is rounded **up** to the nearest multiple of `downscale`.

## Usage
- Use as a starting latent for samplers or pipelines that expect a LATENT input.
- Pair with VAE decode to produce a blank image canvas of the chosen size.

## Tips
- Keep `downscale` at 8 for SD/SDXL workflows unless you know you need a different factor.
- Choose portrait presets (e.g., 832x1216, 960x1280, 768x1152) for selfie-style generations.
- For custom sizes, set resolution to Manual and enter width/height; prefer multiples of 8 to avoid extra padding.
