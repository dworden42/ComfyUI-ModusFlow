# Ollama Prompt Refiner

Full-pipeline AI prompt enhancement using local Ollama LLMs, with pipe support and conditioning output.

## Overview

The Ollama Prompt Refiner node enhances prompts using a locally running Ollama model. It encodes the refined text into conditioning and emits the full set of components (model, CLIP, VAE, conditioning, latent, seed, dimensions) via pipe and individual outputs — making it a self-contained prompt-to-conditioning node.

## Features

- **Two Modes**: `refine` (enhance an existing prompt) and `generate` (create a prompt from scratch)
- **Image Input**: Optionally supply an image for vision-guided generation
- **Image Usage Modes**: `vision_guidance` (image informs the prompt) or `pose_reference` (image drives a pose-specific system prompt)
- **Flux and Standard CLIP Support**: Automatically detects Flux CLIP type and applies guidance when enabled
- **Pipe Support**: Accepts and emits a full `(model, clip, vae, positive, negative)` pipe
- **Bypass Mode**: `refiner_status = "bypassed"` skips Ollama and encodes the original text unchanged
- **Graceful Degradation**: If Ollama is unavailable the node continues normally, encoding the original input text
- **Custom System Prompts**: Separate system prompt fields for refine, generate, and pose reference modes

## Inputs

### Required
- **refiner_status** (COMBO): `enabled` or `bypassed`
- **mode** (COMBO): `refine` or `generate`
- **text_input** (STRING): Prompt to refine or topic to generate from
- **negative_prompt** (STRING): Negative prompt text
- **prepend_positive** (STRING): Text prepended to the positive prompt before encoding
- **prepend_negative** (STRING): Text prepended to the negative prompt before encoding
- **positive_embeddings** (STRING): Embedding tokens appended to positive text
- **negative_embeddings** (STRING): Embedding tokens appended to negative text
- **ollama_model** (COMBO): Ollama model to use (auto-populated from running Ollama instance)
- **refine_mode_system_prompt** (STRING): System prompt used in `refine` mode
- **generate_mode_system_prompt** (STRING): System prompt used in `generate` mode
- **pose_reference_system_prompt** (STRING): System prompt used when `image_usage = pose_reference`
- **temperature** (FLOAT): LLM sampling temperature (0.0–2.0, default: 0.7)
- **max_tokens** (INT): Maximum tokens to generate (50–4096, default: 200)
- **seed** (INT): Seed for the LLM call
- **use_flux_guidance** (COMBO): `enabled` or `disabled` — adds guidance metadata to conditioning
- **flux_guidance** (FLOAT): Flux guidance scale (0.0–100.0, default: 3.5)

### Optional
- **pipe** (PIPE): Carries `(model, clip, vae, positive, negative)` — individual inputs override pipe
- **model** (MODEL): Diffusion model
- **clip** (CLIP): CLIP for text encoding
- **positive_conditioning** (CONDITIONING): If wired, bypasses text encoding for positive
- **negative_conditioning** (CONDITIONING): If wired, bypasses text encoding for negative
- **width** (INT): Output latent width (default: 1024)
- **height** (INT): Output latent height (default: 1024)
- **use_image_dimensions** (COMBO): `defined` (use width/height) or `original_image` (use supplied image dimensions)
- **image_usage** (COMBO): `vision_guidance` or `pose_reference` — controls which system prompt is used when an image is connected
- **seed_override** (INT): When ≥ 0 overrides the `seed` input for the LLM call
- **image** (IMAGE): Optional image for multimodal prompting
- **latent** (LATENT): If wired, used as the output latent (dimensions are read from it)

## Outputs

| Output | Type | Description |
|--------|------|-------------|
| model | MODEL | Model passthrough |
| positive | CONDITIONING | Encoded positive conditioning |
| negative | CONDITIONING | Encoded negative conditioning |
| refined_prompt | STRING | Final positive text after Ollama refinement |
| negative_prompt | STRING | Final negative text |
| clip | CLIP | CLIP passthrough |
| image | IMAGE | Image passthrough (or 1×1 blank if not connected) |
| seed | INT | Seed passthrough |
| latent | LATENT | Output latent (from input or newly created) |
| width | INT | Latent width in pixels |
| height | INT | Latent height in pixels |
| pipe | PIPE | `(model, clip, vae, positive, negative)` passthrough |

## How Mode Selection Works

| Condition | System Prompt Used |
|-----------|--------------------|
| `mode = refine` and no image, or image with `image_usage = vision_guidance` | `refine_mode_system_prompt` |
| `mode = generate` | `generate_mode_system_prompt` |
| Image connected and `image_usage = pose_reference` | `pose_reference_system_prompt` |

## Usage Patterns

### Text-Only Refinement
```
Text → text_input
Model Loader → pipe
Ollama Prompt Refiner → pipe → KSampler
```

### Vision-Guided Generation
```
Load Image → image (image_usage = vision_guidance, mode = generate)
Model Loader → pipe
Ollama Prompt Refiner → pipe, latent → KSampler
```

### Bypassed (No Ollama)
```
refiner_status = bypassed
Text is encoded directly without any Ollama call
```

## Configuration

Set the Ollama URL in `config.json`:
```json
{
  "ollama_url": "http://localhost:11434",
  "ollama_timeout": 120
}
```

## Tips

- **Ollama unavailable**: The node continues without error — original text is encoded unchanged
- **`ollama-not-running` in dropdown**: Normal when Ollama is stopped; node passes text through unchanged
- **Vision modes**: Require a multimodal model (e.g. `llava`, `llava-phi3`, `moondream`)
- **Prepend fields**: Use `prepend_positive` for style tags you always want (e.g. `masterpiece, best quality`)
- **Pre-encoded conditioning**: Wiring `positive_conditioning` or `negative_conditioning` skips text encoding entirely for that output — useful when chaining from another encoding node

## Troubleshooting

- **Empty conditioning**: Ensure CLIP is connected (via pipe or directly) and the text fields are not all empty
- **Multimodal errors**: Confirm the selected Ollama model supports vision
- **LLM output looks wrong**: Adjust the system prompt or lower `temperature`
