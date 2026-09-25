# Batch KSampler

Simplified KSampler for batch processing workflows.

## Overview

The Batch KSampler is a streamlined sampler node designed for batch workflows. It exposes the core sampling parameters without pipe support or denoise control, sampling at full strength (denoise = 1.0). It lives in the **ModusFlow/Batching** category.

## Features

- **Core Sampling Parameters**: model, seed, steps, cfg, sampler, scheduler, conditioning, and latent
- **Batch Compatible**: Processes batched latents as a standard LATENT input
- **No Pipe Overhead**: Direct inputs only — no pipe wiring required

## Inputs

### Required

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| model | MODEL | — | Diffusion model |
| latent_image | LATENT | — | Input latent to denoise |
| seed | INT | 0 | Random seed for generation |
| steps | INT | 20 | Number of sampling steps |
| cfg | FLOAT | 7.0 | Classifier-free guidance scale |
| sampler_name | COMBO | euler | Sampling algorithm |
| scheduler | COMBO | normal | Noise schedule |
| positive_conditioning | CONDITIONING | — | Positive conditioning |
| negative_conditioning | CONDITIONING | — | Negative conditioning |

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| latent | LATENT | Denoised latent |

## Notes

- Denoising strength is fixed at **1.0** (full denoise). For img2img or inpainting workflows, use the ModusFlow KSampler which exposes a `denoise` parameter.
- The sampler and scheduler lists are a curated subset of all ComfyUI samplers/schedulers. Use the ModusFlow KSampler for access to the full list.

## Typical Workflow

```
Model Loader → model ──────────────────┐
Latent Preset → latent_image ──────────┤
CLIP Text Encode → positive_conditioning┤──▶ Batch KSampler → latent → VAE Decode
CLIP Text Encode → negative_conditioning┘
```

## Usage Patterns

### Batch Processing
```
Base seed: 12345
Batch size: 5

Image 0: seed = 12345 + 0 = 12345
Image 1: seed = 12345 + 1 = 12346
Image 2: seed = 12345 + 2 = 12347
Image 3: seed = 12345 + 3 = 12348
Image 4: seed = 12345 + 4 = 12349
```

### Without Iterator
```
If batch_index is not connected:
- Acts like standard KSampler
- Uses base seed directly
```

## Tips

- **Fixed Base Seed**: Use consistent base seed for reproducible batch variations
- **Random Batches**: Use random base seed for varied batch results
- **Iterator Required**: Connect Image Iterator's batch_index for proper batch operation
- **Seed Range**: Ensure base seed + batch size doesn't overflow INT range

## Troubleshooting

- **Same image repeated**: Ensure batch_index is connected from Image Iterator
- **Unexpected seeds**: Verify batch_index starts at 0 and increments correctly
- **Iterator sync issues**: Check Image Iterator configuration matches batch size
