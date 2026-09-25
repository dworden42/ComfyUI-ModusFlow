# KSampler

Enhanced KSampler with pipe support, audio latent handling, and CUDNN control.

## Overview

The ModusFlow KSampler extends ComfyUI's standard KSampler with pipe input/output, passthrough outputs for all components, audio latent decoding, and CUDNN benchmark control.

## Features

- **Pipe Input/Output**: Accept and pass through a `(model, clip, vae, positive, negative)` pipe tuple
- **Full Passthrough Outputs**: Emits model, clip, vae, conditioning, and seed alongside the latent and decoded image
- **Audio Latent Support**: Detects audio latents and routes to audio output instead of image
- **CUDNN Control**: Toggle CUDNN benchmark for performance or VRAM tuning
- **Latent Operation**: Optional latent operation injected into the model's CFG loop

## Inputs

### Required
- **seed** (INT): Random seed for generation
- **steps** (INT): Number of sampling steps
- **cfg** (FLOAT): Classifier-free guidance scale
- **sampler_name** (COMBO): Sampling algorithm
- **scheduler** (COMBO): Noise schedule
- **denoise** (FLOAT): Denoising strength (0.0–1.0)
- **use_cudnn** (BOOLEAN): Enable CUDNN benchmark (default: true)

### Optional
- **pipe** (PIPE): Carries `(model, clip, vae, positive, negative)` — individual inputs override pipe values
- **model** (MODEL): Diffusion model
- **clip** (CLIP): CLIP model (passthrough only)
- **vae** (VAE): VAE for decoding
- **positive** (CONDITIONING): Positive conditioning
- **negative** (CONDITIONING): Negative conditioning
- **latent_image** (LATENT): Input latent to denoise
- **latent_operation** (LATENT_OPERATION): Optional operation injected into the CFG pre-step

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| latent | LATENT | Denoised latent samples |
| image | IMAGE | VAE-decoded image (None for audio latents) |
| audio | AUDIO | Decoded audio (None for image latents) |
| seed | INT | Seed passthrough |
| model | MODEL | Model passthrough |
| clip | CLIP | CLIP passthrough |
| vae | VAE | VAE passthrough |
| positive | CONDITIONING | Positive conditioning passthrough |
| negative | CONDITIONING | Negative conditioning passthrough |
| pipe | PIPE | `(model, clip, vae, positive, negative)` passthrough |

## CUDNN Benchmark

`use_cudnn = true` (default) enables CUDNN benchmark mode which auto-selects the fastest convolution algorithms.

**When to disable (`use_cudnn = false`)**:
- Low VRAM situations where the benchmark's memory overhead causes OOM
- Debugging determinism issues (benchmark introduces non-determinism)
- Single one-off generations where warmup cost is wasted

**When to keep enabled (default)**:
- Batch processing or repeated generations with same settings
- VRAM is not constrained

## Usage Patterns

### Via Pipe
```
Model Loader → pipe → KSampler
```

### Via Individual Inputs
```
Model Loader → model, vae → KSampler
CLIP Text Encode → positive, negative → KSampler
Latent Preset → latent_image → KSampler
```

### Audio Workflow
```
KSampler → audio → Save Audio
(image output will be None when latent type is "audio")
```

## Tips

- **Pipe priority**: individual inputs always override the pipe when both are connected
- **Seed**: wire the `seed` passthrough to downstream nodes (e.g. Save Image `%seed%`) to keep it in sync
- **CFG Scale**: typical range is 1.0–7.0 for Flux, 7–11 for SD/SDXL
- **Steps**: 20–30 steps sufficient for most models

## Troubleshooting

- **VRAM errors**: Set `use_cudnn = false`
- **Slow first generation with CUDNN on**: Normal — benchmark warmup runs once per session
- **audio output is None**: Expected for image latents; only populated when the latent type is `"audio"`
- **image output is None**: Expected for audio latents
