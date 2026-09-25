# LoRA Loader

Stack-based LoRA management with base model validation, Civitai integration, and pipe support.

## Overview

The ModusFlow LoRA Loader manages a JSON-based stack of LoRAs through an interactive UI. Multiple LoRAs can be enabled, reordered, and strength-adjusted in the node panel without rewiring. The node applies all enabled LoRAs in order to the model and CLIP, and passes everything through via pipe.

## Features

- **LoRA Stack UI**: Add, remove, reorder, and toggle individual LoRAs in the node's panel — all state is stored in a hidden `lora_stack` JSON field
- **Case-Insensitive Path Matching**: Finds LoRA files using three fallback strategies (exact, basename, basename without extension) — handles subdirectories and mixed-case filenames
- **Per-LoRA Strength**: Each entry in the stack has its own strength value; strength 0 skips the LoRA
- **Base Model Validation**: The `base_model_name` dropdown (populated from `config.json` definitions) lets the UI warn when a LoRA's metadata doesn't match the selected base model
- **Civitai Integration**: Preview images, training keywords, and model info are fetched from Civitai via the built-in API routes
- **Pipe Support**: Accepts and emits a `(model, clip, vae, positive, negative)` pipe — individual inputs override pipe values

## Inputs

### Required
- **lora_stack** (STRING, hidden): JSON array of LoRA entries managed by the node UI — do not wire manually
- **base_model_name** (COMBO): Base model type for validation (populated from `base_model_definitions` in `config.json`); does not affect execution

### Optional
- **pipe** (PIPE): Carries `(model, clip, vae, positive, negative)` — individual inputs override pipe
- **model** (MODEL): Model to apply LoRAs to
- **clip** (CLIP): CLIP to apply LoRAs to
- **positive** (CONDITIONING): Positive conditioning passthrough
- **negative** (CONDITIONING): Negative conditioning passthrough
- **seed** (INT): Seed passthrough (forceInput — must be wired, not typed)
- **lora_filter** (STRING): Text filter for the LoRA list in the UI panel; not used in execution
- **civitai_api_key** (STRING, hidden): Civitai API key stored in the workflow; overrides `config.json` key

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| model | MODEL | Model with all enabled LoRAs applied |
| clip | CLIP | CLIP with all enabled LoRAs applied |
| positive | CONDITIONING | Positive conditioning passthrough |
| negative | CONDITIONING | Negative conditioning passthrough |
| seed | INT | Seed passthrough |
| pipe | PIPE | `(model, clip, vae, positive, negative)` passthrough |

## LoRA Stack

Each entry in the stack contains:
- **name**: LoRA filename (relative path from `models/loras/`)
- **strength**: Applied to both model and CLIP weights (can be negative)
- **enabled**: When false, the LoRA is skipped without removing it from the stack

LoRAs are applied in stack order. The output model/CLIP reflects the cumulative effect of all enabled LoRAs.

## Base Model Validation

Set `base_model_definitions` in `config.json` to enable validation:

```json
{
  "base_model_definitions": [
    {"type": "sdxl", "keywords": ["sdxl", "xl"]},
    {"type": "sd15", "keywords": ["sd15", "sd1.5", "v1-5"]},
    {"type": "flux", "keywords": ["flux"]}
  ]
}
```

The UI compares the LoRA's `ss_base_model_version` or `modelspec.architecture` metadata field against the selected base model type and shows a compatibility indicator. This is UI-only and does not block execution.

## Civitai Integration

- **Preview images**: Fetched from the LoRA file's embedded metadata or a sidecar image file
- **Civitai lookup**: Triggered by the UI using the LoRA's SHA-256 hash via the `/modusflow/get_lora_civitai_info` API route
- **API key**: Add to `config.json` or wire the `civitai_api_key` input for access to NSFW models

```json
{
  "civitai_api_key": "your_api_key_here"
}
```

## Usage Patterns

### Basic LoRA Application
```
Model Loader → model, clip → LoRA Loader → model, clip → KSampler
```

### Via Pipe
```
Model Loader → pipe → LoRA Loader → pipe → KSampler
```

### Seed Passthrough
```
KSampler seed → LoRA Loader seed input → seed output → Save Image %seed%
```

## Tips

- **Multiple LoRAs**: Add all LoRAs to one node's stack — no need to chain multiple nodes
- **Disable without removing**: Toggle `enabled` on a stack entry to temporarily skip a LoRA
- **Strength 0**: Automatically skipped; same effect as disabling
- **Negative strength**: Inverts the LoRA effect
- **Trigger words**: Copy training keywords shown in the Civitai panel into your prompt

## Troubleshooting

- **LoRA not found**: Verify the file exists in `models/loras/`. Path matching is case-insensitive but the file must be present
- **No validation indicators**: Add `base_model_definitions` to `config.json` and select a base model type in the dropdown
- **Civitai errors**: Check internet connection and API key; some models require authentication
- **Empty positive/negative outputs**: If no conditioning is wired (and no pipe), outputs are empty lists — wire conditioning before this node or pass via pipe
