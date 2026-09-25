# ModusFlow Workflow & Node Usage Guide

This guide explains how to connect and use ModusFlow custom nodes in ComfyUI, from basic generation to advanced multi-pass detailing and upscaling.

---

## 1. Core Architecture: The ModusFlow Pipe

ModusFlow uses a unified **`PIPE`** bus that carries the complete generation state:
```
PIPE = (model, clip, vae, positive, negative)
```
Using the pipe significantly simplifies node graphs by eliminating bundles of wires running across the canvas. Individual inputs (e.g. hooking up a separate `positive` or `model`) always override what is inside the pipe.

```
[ Model Loader ] ── PIPE ──► [ LoRA Loader ] ── PIPE ──► [ KSampler ] ── PIPE ──► [ All-in-One Detailer ]
                                                              │
                                                            IMAGE
                                                              ▼
                                                   [ Upscaler / Restormer ]
```

---

## 2. Step-by-Step Workflows

### Workflow A: Clean Base Generation (Pipe-Driven)

1. **Add `ModusFlow Model Loader`**:
   - Select your checkpoint or UNet + CLIPs + VAE.
   - Outputs: `pipe`, `model`, `clip_merged`, `vae`.
2. **Add `ModusFlow LoRA Loader`** *(optional)*:
   - Connect `pipe` from the Model Loader to `pipe` on the LoRA Loader.
   - Add your desired LoRAs directly in the node UI. Adjust strengths and toggle them on/off as needed.
3. **Add Conditioning**:
   - Connect `clip` from the Model Loader (or LoRA Loader) to **`ModusFlow Text Editor`** or standard `CLIPTextEncode`.
   - Connect positive and negative conditionings into the LoRA Loader or KSampler inputs.
4. **Add `ModusFlow Latent Preset`**:
   - Choose a resolution preset (e.g. `1024x1024 (Square)`, `832x1216 (Portrait)`).
   - Connect `latent` into KSampler's `latent_image`.
5. **Add `ModusFlow KSampler`**:
   - Connect `pipe` into KSampler.
   - Set steps, CFG, sampler name, and scheduler.
   - Connect the output `image` to a preview or save node.

---

### Workflow B: AI Prompt Refinement with Ollama

Enhance simple ideas into detailed generation prompts using a local LLM before generation:

1. **Add `ModusFlow Ollama Prompt Refiner`**:
   - Enter your base prompt in `prompt` (e.g. `"cyberpunk street market at dusk"`).
   - Select an Ollama model (e.g. `llama3`, `mistral`, `llava`).
   - Choose an enhancement mode: `refine`, `generate`, `describe`, or `custom`.
2. **Wire to Conditioning**:
   - Connect `clip` from your Model Loader to the Prompt Refiner.
   - Connect the resulting `positive` output directly into KSampler.
3. **Inspect Output**:
   - Connect `refined_text` to **`ModusFlow ShowText`** to read the generated prompt text directly on the canvas.

---

### Workflow C: Multi-Pass Detailing (Faces, Hands, Eyes)

The **All-in-One Detailer** runs sequential YOLO detection and inpainting passes on detected regions:

1. **Configure Passes with `ModusFlow Detailer Slot`**:
   - Add a `Detailer Slot` for each feature you want to enhance (e.g. one for face, one for hands).
   - Select the YOLO detector model (e.g. `face_yolov8n.pt`, `hand_yolov8s.pt`).
   - Adjust `denoise` (typically `0.25` - `0.35` for subtle refinement, higher for reconstruction).
   - Configure `mask_blur`, `blend_feather`, and `steps`.
2. **Connect to `ModusFlow All-in-One Detailer`**:
   - Connect KSampler's output `image` to `image` on the detailer.
   - Connect KSampler's output `pipe` to `pipe` on the detailer.
   - Wire each configured `Detailer Slot` into `slot_1`, `slot_2`, etc.
3. **Execution**:
   - The detailer detects each region in sequence, crops with context padding, inpaints using your prompt and model, feathers the seams, and blends the result back into the main image.

---

### Workflow D: High-Resolution Tiled Upscaling & Restoration

1. **Add `ModusFlow Upscaler`**:
   - Connect the detailed image from the Detailer or KSampler.
   - Select an upscale model (e.g. UltraMix, NMKD, DAT) or choose bicubic/lanczos scaling.
   - If using tiled KSampler refinement, configure tile size, tile overlap, and seam blending.
2. **Add `ModusFlow Restormer`** *(optional finishing touch)*:
   - For removing blur or camera artifacts, route the upscaled image through Restormer.
   - Select task: `Motion_Deblurring`, `Single_Image_Defocus_Deblurring`, or `Gaussian_Color_Denoising`.
   - Set `tile_size` (e.g. 256 or 512) to restore high-resolution images within standard GPU VRAM.
3. **Save Output**:
   - Connect to **`ModusFlow Save Image`** for automatic metadata embedding and variable-based file naming (e.g. `{date}_{seed}_{model}`).

---

## 3. Recommended Node Pairings

| Task | Primary Node | Complementary Nodes |
|------|-------------|---------------------|
| Model & LoRA setup | `ModusFlow Model Loader` | `ModusFlow LoRA Loader`, `ModusFlow Latent Preset` |
| Prompting | `ModusFlow Text Editor` | `ModusFlow Ollama Prompt Refiner`, `ModusFlow ShowText` |
| Multi-encoder models (Flux/SD3) | `ModusFlow Multi-CLIP Text Encode` | `ModusFlow Model Loader` |
| Generation | `ModusFlow KSampler` | `ModusFlow Batch KSampler` |
| Inpainting & detailing | `ModusFlow All-in-One Detailer` | `ModusFlow Detailer Slot` |
| Upscaling & cleanup | `ModusFlow Upscaler` | `ModusFlow Restormer` |
| Export | `ModusFlow Save Image` | `ModusFlow Save Audio` |

---

## 4. Tips & Best Practices

- **Zero-Wire Reordering**: In the LoRA Loader, drag LoRAs in the stack to reorder execution or toggle their checkbox to disable without deleting.
- **Pipe Passthrough**: Nodes that accept a `pipe` also emit the updated `pipe`, allowing clean linear chains: `Model Loader -> LoRA Loader -> KSampler -> Detailer`.
- **YOLO Models**: Run `python utilities/download_models.py` to populate `models/ultralytics/` with face, hand, and person detector models.
