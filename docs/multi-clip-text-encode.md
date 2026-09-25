# Multi-CLIP Text Encode

Encodes separate prompts with up to 4 CLIP models and combines them into a single conditioning.

## Overview

The Multi-CLIP Text Encode node encodes text using multiple CLIP models simultaneously. Each CLIP has its own text input and enable toggle. The resulting conditionings are concatenated into a single `CONDITIONING` output. Optional Flux guidance can be applied to every entry.

## Features

- **Up to 4 CLIPs**: Individual text input per CLIP with per-CLIP enable/disable toggle
- **Single Conditioning Output**: Conditionings are concatenated (not averaged) for correct multi-CLIP behavior
- **Flux Guidance**: Optional guidance scalar applied to every conditioning entry
- **Merged CLIP Fallback**: If no individual CLIPs produce output, falls back to `clip_merged` with the first non-empty text
- **Graceful Handling**: Skips disabled CLIPs and CLIPs with empty text without error

## Inputs

### Required
- **text_clip1** (STRING): Prompt for CLIP 1
- **text_clip2** (STRING): Prompt for CLIP 2
- **text_clip3** (STRING): Prompt for CLIP 3
- **text_clip4** (STRING): Prompt for CLIP 4
- **enable_clip1** (BOOLEAN): Enable CLIP 1 (default: true)
- **enable_clip2** (BOOLEAN): Enable CLIP 2 (default: false)
- **enable_clip3** (BOOLEAN): Enable CLIP 3 (default: false)
- **enable_clip4** (BOOLEAN): Enable CLIP 4 (default: false)
- **use_flux_guidance** (BOOLEAN): Apply Flux guidance to conditioning (default: false)
- **flux_guidance** (FLOAT): Guidance scale value (default: 3.5, range: 0–100)

### Optional
- **clip1** (CLIP): First CLIP model
- **clip2** (CLIP): Second CLIP model
- **clip3** (CLIP): Third CLIP model
- **clip4** (CLIP): Fourth CLIP model
- **clip_merged** (CLIP): Fallback CLIP used if no individual CLIPs produce output

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| conditioning | CONDITIONING | Concatenated conditioning from all enabled CLIPs |

## Usage Patterns

### Single CLIP (Standard)
```
Enable only clip1, connect one CLIP model and text
```

### Flux Dual-CLIP (e.g. ACE Step 1.5)
```
Model Loader → clip1 + clip2
enable_clip1 = true, enable_clip2 = true
use_flux_guidance = true
```

### SDXL (clip_merged fallback)
```
Model Loader clip_merged → clip_merged input
Disable all individual CLIPs
The node encodes with the merged CLIP using text_clip1
```

### Per-CLIP Different Prompts
```
Different text in each text_clipN field for creative mixing
Each enabled CLIP encodes its own prompt independently
```

## Tips

- **Enable only what you need**: Disabled CLIPs and empty text fields are silently skipped
- **Flux models**: Enable `use_flux_guidance` and set `flux_guidance` to the desired strength (3.5 is a common default)
- **Concatenation vs averaging**: Conditioning entries are concatenated, preserving all CLIP metadata — this is the correct approach for multi-CLIP models
- **clip_merged fallback**: Useful when the model was loaded with DualCLIPLoader (Model Loader's `use_dual_clip_loader` path)

## Troubleshooting

- **"No conditioning generated"**: At least one CLIP must be enabled, connected, and have non-empty text
- **Unexpected output behavior**: Verify the correct CLIPs are enabled in the toggles
- **Flux guidance has no effect**: Ensure `use_flux_guidance` is set to true and the model is Flux-based
