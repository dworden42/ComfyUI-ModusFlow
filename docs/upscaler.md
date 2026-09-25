# Upscaler

Tiled upscaling with seam fixing and post-processing options.

## Overview

The Upscaler node provides high-quality image upscaling using tiled processing to handle large images efficiently, with built-in seam fixing and optional refinement.

## Features

- **Tiled Processing**: Handles large upscales without VRAM overflow
- **Seam Fixing**: Blends tile boundaries for seamless results
- **Multiple Models**: Supports all ESRGAN/RealESRGAN upscale models
- **Post-Processing**: Optional additional refinement pass
- **Memory Efficient**: Processes image in manageable chunks

## Inputs

### Required
- **image** (IMAGE): Input image to upscale
- **model** (MODEL): Model for optional refinement
- **vae** (VAE): VAE for encoding/decoding
- **upscale_model** (COMBO): ESRGAN/RealESRGAN model to use
- **positive** (CONDITIONING): Positive conditioning for refinement
- **negative** (CONDITIONING): Negative conditioning for refinement

### Upscale Parameters
- **rescale_factor** (FLOAT): Final size multiplier (default: 2.0)
- **steps** (INT): Refinement steps (default: 20)
- **cfg** (FLOAT): CFG scale for refinement (default: 8.0)
- **sampler_name** (COMBO): Sampler for refinement
- **scheduler** (COMBO): Scheduler for refinement
- **denoise** (FLOAT): Refinement strength (default: 0.2)
- **seed** (INT): Random seed for refinement

### Tiling Parameters
- **tile_size** (INT): Size of each tile (default: 512)
- **tile_overlap** (INT): Overlap between tiles (default: 64)
- **tile_batch_size** (INT): Tiles processed simultaneously (default: 4)

### Seam Fixing
- **seam_fix_mode** (COMBO): "None", "Band Pass", or "Half Tile"
- **seam_fix_denoise** (FLOAT): Seam fix strength (default: 0.35)
- **seam_fix_width** (INT): Width of seam fix area (default: 64)
- **seam_fix_mask_blur** (INT): Blur radius for seam masks (default: 16)

## Outputs

- **IMAGE**: Upscaled and refined image

## Workflow

1. **Initial Upscale**: ESRGAN/RealESRGAN model upscales image
2. **Tiled Processing**: Image divided into overlapping tiles
3. **Seam Fixing**: Blend tile boundaries if enabled
4. **Refinement**: Optional detail enhancement pass

## Upscale Models

### Recommended Models
- **RealESRGAN_x4plus**: General purpose, balanced quality
- **RealESRGAN_x4plus_anime**: Optimized for anime/illustrated content
- **ESRGAN_4x**: Good for photographs
- **4x-UltraSharp**: High detail preservation

Download models to: `ComfyUI/models/upscale_models/`

## Tiling Strategy

### Tile Size
- **256-512**: Faster, more VRAM efficient
- **512-1024**: Better quality, requires more VRAM
- **1024+**: Best quality, high VRAM requirement

### Tile Overlap
- **32-64**: Minimal overlap, faster (default: 64)
- **64-128**: Better seam blending
- **128+**: Smoothest blending, slower

### Batch Size
- **1-2**: Low VRAM systems
- **4-8**: Balanced (default: 4)
- **8+**: Fast processing, requires high VRAM

## Seam Fix Modes

### None
- No seam fixing
- Fastest
- May show tile boundaries

### Band Pass
- Frequency-based seam blending
- Good balance of quality and speed
- Recommended for most use cases

### Half Tile
- Processes tile overlap areas
- Highest quality seam removal
- Slower, uses more VRAM

## Usage Patterns

### Quick Upscale
```
rescale_factor: 2.0
tile_size: 512
seam_fix_mode: Band Pass
denoise: 0.2
```

### High Quality Upscale
```
rescale_factor: 4.0
tile_size: 1024
tile_overlap: 128
seam_fix_mode: Half Tile
denoise: 0.3
steps: 30
```

### Memory-Constrained
```
rescale_factor: 2.0
tile_size: 256
tile_overlap: 32
tile_batch_size: 1
seam_fix_mode: Band Pass
```

## Tips

- **VRAM Management**: Reduce tile_size and batch_size if running out of memory
- **Quality vs Speed**: Larger tiles and overlap = better quality but slower
- **Denoise**: Keep low (0.1-0.3) to preserve original image details
- **Model Selection**: Match upscale model to content type (anime vs photo)
- **Seam Fixing**: Always use at least Band Pass for tiled upscaling

## Troubleshooting

- **VRAM errors**: Reduce tile_size, tile_batch_size, or tile_overlap
- **Visible seams**: Increase tile_overlap or use Half Tile seam fix mode
- **Blurry result**: Reduce denoise value
- **Too sharp/artifacts**: Increase denoise value slightly
- **Slow processing**: Reduce tile_overlap, increase tile_batch_size
