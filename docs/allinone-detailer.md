# ModusFlow All-in-One Detailer

Two nodes for modular, slot-based image detailing using YOLO detection and VAE inpainting.

---

## Nodes

### ModusFlow Detailer Slot

A config bundle node. One per subject to detail (face, hands, body, etc.). Outputs a `DETAILER_SLOT` dict containing all settings for one detection + inpaint pass.

**Inputs**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| model | dropdown | disabled | YOLO detector model (.pt / .pth) from `models/ultralytics/` |
| steps | INT | 20 | Inpainting sampler steps |
| cfg | FLOAT | 7.0 | CFG scale |
| denoise | FLOAT | 0.5 | Denoising strength |
| padding | INT | 32 | Mask expansion in pixels |
| mask_blur | INT | 4 | Gaussian blur radius on the detection mask (affects inpaint boundary) |
| blend_feather | INT | 16 | Additional blur on the compositing mask for a wider, softer transition |
| context_pad | INT | 32 | Extra pixels of surrounding image the model sees during diffusion (not pasted back) |
| sampler | dropdown | euler_ancestral | Sampler name |
| scheduler | dropdown | karras | Noise scheduler |
| enabled | BOOLEAN | True | Skip this slot when False |
| positive | CONDITIONING (optional) | — | Per-slot positive prompt override |
| negative | CONDITIONING (optional) | — | Per-slot negative prompt override |

**Output:** `DETAILER_SLOT`

---

### ModusFlow All-in-One Detailer

The main processing node. Accepts a pipe carrying model/clip/vae/conditioning plus any number of `DETAILER_SLOT` inputs added dynamically by the frontend. Runs each enabled slot sequentially, feeding the output of slot N as input to slot N+1.

**Inputs**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| confidence | FLOAT | 0.3 | YOLO detection confidence threshold |
| pipe | PIPE (optional) | — | Carries model, clip, vae, positive, negative |
| image | IMAGE (optional) | — | Source image to detail |
| model | MODEL (optional) | — | Overrides pipe model |
| clip | CLIP (optional) | — | Overrides pipe clip |
| vae | VAE (optional) | — | Overrides pipe vae |
| positive | CONDITIONING (optional) | — | Overrides pipe positive |
| negative | CONDITIONING (optional) | — | Overrides pipe negative |
| seed | INT (optional) | 0 | Sampling seed |
| slot_1 … slot_N | DETAILER_SLOT (optional) | — | Any number of detailing passes (slots added dynamically via the node UI) |

**Outputs**

| Name | Type | Description |
|------|------|-------------|
| image | IMAGE | Fully detailed image after all slots |
| pipe | PIPE | Input pipe passed through unchanged |

---

## Usage

### Typical workflow

```
Model Loader → pipe ──────────────────────────────┐
KSampler → image ─────────────────────────────────┤
                                                   ▼
Detailer Slot (face model) → slot_1    All-in-One Detailer → image → Save Image
Detailer Slot (hand model) → slot_2           │
                                               └── pipe → (next node)
```

### Pipe-based chaining

Wire a `PIPE` from any ModusFlow node (Model Loader, KSampler, etc.) into the `pipe` input. The node resolves model/clip/vae/conditioning from the pipe automatically. Individual inputs override the pipe when both are connected.

### Per-slot conditioning

Connect a different positive/negative to a `DetailerSlot` to use a subject-specific prompt for that pass (e.g. "detailed face, skin texture" for the face slot). Slots without conditioning wired will fall back to the global conditioning.

---

## Model Setup

Place Ultralytics YOLO models (`.pt` or `.pth`) in any of:
- `ComfyUI/models/ultralytics/segm/` — segmentation models (preferred for masks)
- `ComfyUI/models/ultralytics/bbox/` — bounding box models
- `ComfyUI/models/ultralytics/` — root

The dropdown is populated at startup. Restart ComfyUI after adding new models.

---

## Tips

- Start with `denoise` around 0.4–0.6 for subtle refinement; higher values change anatomy.
- Increase `padding` for faces (32–64) to give the inpainter room to blend edges.
- `mask_blur` softens the inpaint boundary; `blend_feather` controls the compositing transition width; `context_pad` expands how much surrounding image the model sees. They are all independent — use all three to tune blending.
- `context_pad` is the most effective fix for visible seams: by giving the diffusion model surrounding pixels to look at, its output naturally matches the neighborhood in color and texture. The context border is never pasted back.
- If the pasted region is still visible as a box, raise `context_pad` (try 64–96) and `blend_feather` (try 24–48). A color correction step also automatically corrects for diffusion-induced tone drift at the seam.
- Set `enabled = False` on slots you want to temporarily skip without rewiring.
- Slots are processed in ascending order; later slots see the output of earlier ones.
- The `image` output is always available directly — no pipe unpacking needed.

---

## Troubleshooting

**No detections / slot skipped**
- Check the confidence threshold (lower it for harder-to-detect subjects).
- Confirm the model file exists in one of the ultralytics directories.
- Check the ComfyUI console for `[AllInOneDetailer]` log lines.

**ultralytics not installed**
```bash
pip install ultralytics
```

**Inpaint looks wrong / artifacts**
- Reduce `denoise` to preserve more of the original.
- Increase `mask_blur` to soften the inpaint boundary.
- Try a different sampler/scheduler (dpmpp_2m / karras works well).

**Visible box / seam around the detailed region**
- Raise `context_pad` (default 32 — try 64–96). This is the primary fix: the model generates output that matches the surrounding pixels because it can see them.
- Raise `blend_feather` (default 16 — try 24–48) for a wider compositing fade.
- Increase `padding` so the mask boundary has room to feather into neutral background.
- A built-in color correction step handles residual tone drift automatically.
