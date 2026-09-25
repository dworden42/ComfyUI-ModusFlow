# Model Loader

All-in-one loader for diffusion models, CLIPs, and VAE with UNet, checkpoint, and DualCLIP support.

## Overview

The Model Loader consolidates model loading into a single node. It supports UNet-only models, full checkpoints, up to 4 individual CLIPs, a DualCLIPLoader path for models like Flux/SDXL/ACE, and a standalone VAE loader. All outputs are available individually plus a pipe for downstream nodes.

## Features

- **UNet + Checkpoint**: Load a standalone UNet or a full checkpoint (checkpoint takes priority for the model)
- **Dual CLIP Loader**: Load two CLIPs together via ComfyUI's `DualCLIPLoader` (required for Flux, ACE Step 1.5, SDXL, etc.)
- **Up to 4 Individual CLIPs**: Each with its own type and device setting
- **Weight Dtype Control**: Load the UNet in fp8, fp16, fp32, bf16, or default
- **CLIP Skip**: Apply layer skipping to all loaded CLIPs simultaneously
- **T5 Tokenizer Settings**: Configure `min_length` and `min_padding` for T5-based encoders
- **Pipe Output**: Emits `(model, clip_merged, vae, None, None)` for downstream pipe nodes

## Inputs

### Diffusion Model
- **unet_name** (COMBO): UNet model file, or "None" to skip
- **weight_dtype** (COMBO): Load precision — `default`, `fp8_e4m3fn`, `fp8_e5m2`, `fp16`, `fp32`, `bf16`

### Dual CLIP Loader
- **use_dual_clip_loader** (BOOLEAN): When true, loads clip1 + clip2 together via `DualCLIPLoader` (default: false)
- **dual_clip_type** (COMBO): Model architecture for DualCLIPLoader — `sdxl`, `sd3`, `flux`, `ace`, `hunyuan_video`, `hidream`, and more

### Individual CLIPs (×4)
- **clip1_name / clip2_name / clip3_name / clip4_name** (COMBO): CLIP file, or "disabled" to skip
- **clip1_type / clip2_type / clip3_type / clip4_type** (COMBO): CLIP model type — `stable_diffusion`, `sd3`, `flux`, `wan`, `ace`, and more
- **clip1_device / clip2_device / clip3_device / clip4_device** (COMBO): Device — `auto`, `cpu`, `cuda`, `cuda:0`, `cuda:1`

### CLIP Skip
- **clip_skip** (INT): Layer skip applied to all CLIPs (0 = disabled, −1 to −24 = skip from end)

### Checkpoint
- **checkpoint_name** (COMBO): Checkpoint file, or "None" to skip
- **use_checkpoint_clip** (BOOLEAN): When true, uses the checkpoint's embedded CLIP as clip1 (default: false)

### VAE
- **vae_name** (COMBO): VAE file, or "None" to use checkpoint's VAE

### T5 Tokenizer
- **t5_min_length** (INT): Minimum token sequence length for T5 encoders (default: 256)
- **t5_min_padding** (INT): Minimum padding tokens for T5 encoders (default: 0)

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| model | MODEL | Loaded diffusion model |
| clip_merged | CLIP | Primary/merged CLIP (used by Ollama Prompt Refiner and similar nodes) |
| clip1 | CLIP | Individual CLIP 1 output |
| clip2 | CLIP | Individual CLIP 2 output |
| clip3 | CLIP | Individual CLIP 3 output |
| clip4 | CLIP | Individual CLIP 4 output |
| vae | VAE | Loaded VAE |
| pipe | PIPE | `(model, clip_merged, vae, None, None)` for pipe-based workflows |

## Loading Priority

1. **Model**: Checkpoint model first; if not loaded, UNet is tried
2. **CLIP**: `use_dual_clip_loader` path first (when enabled); otherwise individual CLIPs; checkpoint CLIP used only when `use_checkpoint_clip = true`
3. **VAE**: Explicit `vae_name` first; falls back to checkpoint VAE when `vae_name = "None"`

## Usage Patterns

### Flux / ACE Step 1.5
```
unet_name: <flux unet>
weight_dtype: fp8_e4m3fn
use_dual_clip_loader: true
dual_clip_type: flux   (or "ace" for ACE Step)
clip1_name: <clip_l.safetensors>
clip2_name: <t5xxl.safetensors>
vae_name: <vae.safetensors>
```

### SDXL Checkpoint
```
checkpoint_name: <sdxl_base.safetensors>
use_checkpoint_clip: true
vae_name: None   (uses checkpoint VAE)
```

### SD 1.5 with Custom VAE
```
checkpoint_name: <model.safetensors>
use_checkpoint_clip: true
vae_name: vae-ft-mse.safetensors
```

### Multi-CLIP Manual Setup
```
unet_name: <unet>
clip1_name: <clip_l>, clip1_type: stable_diffusion
clip2_name: <clip_g>, clip2_type: stable_diffusion
vae_name: <vae>
```

## Tips

- **Dual CLIP Loader vs individual CLIPs**: Use `use_dual_clip_loader` for Flux, ACE, and SDXL — these models require both CLIPs to be loaded together. Individual CLIPs are for manual multi-CLIP setups
- **clip_merged output**: This is the best output to use for single-CLIP workflows and for pipe connections
- **Individual clip1–4 outputs**: Wire these into Multi-CLIP Text Encode for per-CLIP prompting
- **T5 settings**: Only apply to CLIPs that expose a T5 tokenizer with `set_parameters` — safe to leave at defaults for non-T5 models
- **CLIP skip**: Typically used with SD 1.5 models; -1 or -2 is common; 0 disables it

## Troubleshooting

- **"No model loaded"**: Specify either `checkpoint_name` or `unet_name`
- **"No CLIP loaded"**: Enable `use_checkpoint_clip`, set `use_dual_clip_loader`, or enable at least one `clipN_name`
- **DualCLIPLoader error**: Verify both clip1 and clip2 names are set (not "disabled") when `use_dual_clip_loader = true`
- **VRAM errors on load**: Try `weight_dtype: fp8_e4m3fn` or `fp16` for the UNet
