"""
ModusFlow All-in-One Detailer Nodes
DetailerSlot: config bundle for one detection + inpaint pass.
AllInOneDetailer: runs up to 6 slots sequentially on an image.
"""

import os
import re
import torch
import numpy as np
import folder_paths
import comfy.samplers
from PIL import Image, ImageFilter, ImageDraw
from nodes import KSampler, VAEEncode, VAEDecode

try:
    from ultralytics import YOLO
    ULTRALYTICS_AVAILABLE = True
except ImportError:
    ULTRALYTICS_AVAILABLE = False
    print("[AllInOneDetailer] WARNING: ultralytics not installed. Detection features will be disabled.")
    print("[AllInOneDetailer] Install with: pip install ultralytics")


# ---------------------------------------------------------------------------
# Model scanning
# ---------------------------------------------------------------------------

def _get_ultralytics_dirs() -> list:
    """Return all ultralytics folder paths in priority order.

    Tries ComfyUI-registered keys first (works with Impact-Pack or custom
    extra_model_paths.yaml), then falls back to the default
    models/ultralytics/{segm,bbox,} layout for vanilla installs.
    """
    dirs = []
    for key in ("ultralytics_segm", "ultralytics_bbox", "ultralytics"):
        try:
            dirs.extend(folder_paths.get_folder_paths(key))
        except Exception:
            pass

    # Fallback: default ComfyUI layout (models/ultralytics/segm, bbox, root)
    base = os.path.join(folder_paths.models_dir, "ultralytics")
    for sub in ("segm", "bbox", ""):
        dirs.append(os.path.join(base, sub) if sub else base)

    # Deduplicate while preserving order
    seen = set()
    return [d for d in dirs if not (d in seen or seen.add(d))]


def scan_detector_models() -> list:
    """Scan ComfyUI-registered ultralytics directories for .pt and .pth files."""
    seen = {}
    for d in _get_ultralytics_dirs():
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            if fname.lower().endswith((".pt", ".pth")) and fname not in seen:
                seen[fname] = os.path.join(d, fname)
    if not seen:
        return ["disabled", "(no models found)"]
    return ["disabled"] + sorted(seen.keys())


DETECTOR_MODELS = scan_detector_models()


def load_detector_model(model_name: str):
    """Search all ComfyUI-registered ultralytics directories and return a YOLO instance."""
    if not ULTRALYTICS_AVAILABLE:
        raise RuntimeError("ultralytics is not installed")
    for d in _get_ultralytics_dirs():
        candidate = os.path.join(d, model_name)
        if os.path.isfile(candidate):
            return YOLO(candidate)
    raise FileNotFoundError(
        f"[AllInOneDetailer] Detector model '{model_name}' not found in ultralytics directories."
    )


# ---------------------------------------------------------------------------
# Model type detection & mask extraction
# ---------------------------------------------------------------------------

def get_detection_masks(yolo_model, pil_image, confidence) -> list:
    """Run YOLO detection and return a list of binary PIL mask images."""
    results = yolo_model(pil_image, conf=confidence, verbose=False)
    masks = []
    orig_w, orig_h = pil_image.size

    if results[0].masks is not None:
        # Segmentation model
        for mask_tensor in results[0].masks.data:
            # mask_tensor: [H, W] float at model resolution
            mask_np = mask_tensor.cpu().numpy()
            mask_pil = Image.fromarray((mask_np * 255).astype(np.uint8))
            mask_pil = mask_pil.resize((orig_w, orig_h), Image.NEAREST)
            masks.append(mask_pil.convert("L"))
    else:
        # Bounding box model
        model_h, model_w = results[0].orig_shape
        scale_x = orig_w / model_w
        scale_y = orig_h / model_h
        for box in results[0].boxes.xyxy:
            x1 = int(box[0] * scale_x)
            y1 = int(box[1] * scale_y)
            x2 = int(box[2] * scale_x)
            y2 = int(box[3] * scale_y)
            mask_pil = Image.new("L", (orig_w, orig_h), 0)
            draw = ImageDraw.Draw(mask_pil)
            draw.rectangle([x1, y1, x2, y2], fill=255)
            masks.append(mask_pil)

    return masks


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def tensor_to_pil(tensor) -> Image.Image:
    """Convert a [1, H, W, C] or [H, W, C] float tensor to a PIL RGB image."""
    if tensor.ndim == 4:
        tensor = tensor[0]
    arr = (tensor.cpu().numpy() * 255).clip(0, 255).astype(np.uint8)
    return Image.fromarray(arr, "RGB")


def pil_to_tensor(img: Image.Image) -> torch.Tensor:
    """Convert a PIL image to a [1, H, W, C] float32 tensor in [0, 1]."""
    arr = np.array(img.convert("RGB")).astype(np.float32) / 255.0
    return torch.from_numpy(arr).unsqueeze(0)


def expand_mask(mask_pil: Image.Image, padding: int) -> Image.Image:
    if padding > 0:
        return mask_pil.filter(ImageFilter.MaxFilter(size=padding * 2 + 1))
    return mask_pil


def apply_blur(mask_pil: Image.Image, blur: int) -> Image.Image:
    if blur > 0:
        return mask_pil.filter(ImageFilter.GaussianBlur(radius=blur))
    return mask_pil


def detail_region(image_tensor, mask_pil, model, clip, vae,
                  positive, negative, seed, steps, cfg, denoise,
                  sampler_name, scheduler, blend_feather=16, context_pad=32):
    """Crop a detected region, refine it with KSampler, and paste back.

    Uses VAEEncode (not VAEEncodeForInpaint) so the original pixel content
    is preserved in the latent — the model refines rather than replaces.

    context_pad expands the crop the diffusion model sees beyond the mask
    bounding box, giving it surrounding pixel context so its output naturally
    matches the neighborhood in color and texture.  Only the mask area is
    blended back into the final image.

    blend_feather applies an additional Gaussian blur to the compositing mask
    for a wider, softer transition zone (independent of mask_blur).

    A color correction step compares original vs. result in the seam zone and
    applies a per-channel mean shift to remove diffusion-induced tone drift.
    """
    mask_np = np.array(mask_pil)
    ys, xs = np.where(mask_np > 127)
    if len(ys) == 0:
        return image_tensor

    # Tight bounding box of the masked region
    y1, y2 = int(ys.min()), int(ys.max())
    x1, x2 = int(xs.min()), int(xs.max())

    full_pil = tensor_to_pil(image_tensor)
    full_w, full_h = full_pil.size

    # Expand the crop with context_pad so the diffusion model sees surrounding
    # pixels.  This is the primary fix for visible seams: the model's output
    # naturally aligns in color/texture with the neighborhood because it was
    # generated while "looking at" those pixels.
    cx1 = max(0, x1 - context_pad)
    cy1 = max(0, y1 - context_pad)
    cx2 = min(full_w - 1, x2 + context_pad)
    cy2 = min(full_h - 1, y2 + context_pad)

    crop_pil = full_pil.crop((cx1, cy1, cx2 + 1, cy2 + 1))
    crop_w, crop_h = crop_pil.size

    # Upscale the crop to at least 512px on the short side before encoding.
    # A tiny latent (e.g. 8×10) produces pure garbage from the diffusion model;
    # processing at a reasonable size then downscaling back is the correct approach.
    MIN_SIDE = 512
    short_side = min(crop_w, crop_h)
    if short_side < MIN_SIDE:
        scale = MIN_SIDE / short_side
        proc_w = int(crop_w * scale)
        proc_h = int(crop_h * scale)
    else:
        proc_w, proc_h = crop_w, crop_h
    # Round up to nearest 8-pixel multiple (VAE requirement)
    target_w = (proc_w + 7) // 8 * 8
    target_h = (proc_h + 7) // 8 * 8

    crop_pil_resized = crop_pil.resize((target_w, target_h), Image.LANCZOS)
    img_t = pil_to_tensor(crop_pil_resized)

    # Encode the crop directly — preserves original face content in the latent
    latent = VAEEncode().encode(vae, img_t)[0]

    # Refine: denoise < 1.0 keeps the face structure, only enhances detail
    sampled_latent = KSampler().sample(
        model, seed, steps, cfg, sampler_name, scheduler,
        positive, negative, latent, denoise=denoise
    )[0]

    # Decode and resize back to context crop dimensions
    decoded = VAEDecode().decode(vae, sampled_latent)[0]
    result_pil = tensor_to_pil(decoded)
    result_pil = result_pil.resize((crop_w, crop_h), Image.LANCZOS)

    # Build compositing mask at context crop coordinates.
    # Normalize so peak is 255, then apply blend_feather for wider soft transition.
    # Crop to the context area so the feathered edge blends context-aware result
    # pixels rather than a hard crop boundary.
    mask_arr = np.array(mask_pil).astype(np.float32)
    peak = mask_arr.max()
    if peak > 0:
        mask_arr = (mask_arr / peak * 255).clip(0, 255).astype(np.uint8)
    composite_mask = Image.fromarray(mask_arr)
    if blend_feather > 0:
        composite_mask = composite_mask.filter(ImageFilter.GaussianBlur(radius=blend_feather))
    mask_crop = composite_mask.crop((cx1, cy1, cx2 + 1, cy2 + 1))

    # Color correction: diffusion can still shift mean tone even with context.
    # Compare original vs. result in the seam transition zone and apply a
    # per-channel mean shift to the result to eliminate visible banding.
    mask_crop_np = np.array(mask_crop).astype(np.float32) / 255.0
    seam_zone = (mask_crop_np > 0.05) & (mask_crop_np < 0.5)
    if seam_zone.any():
        orig_crop_np = np.array(crop_pil).astype(np.float32)
        result_np = np.array(result_pil).astype(np.float32)
        orig_seam_mean = orig_crop_np[seam_zone].mean(axis=0)
        result_seam_mean = result_np[seam_zone].mean(axis=0)
        delta = orig_seam_mean - result_seam_mean
        result_pil = Image.fromarray(
            (result_np + delta).clip(0, 255).astype(np.uint8), "RGB"
        )

    # Paste at the context crop origin.  The mask is ~0 at the context border
    # and non-zero only in the detection area, so only the detected region is
    # replaced — but the result was generated with surrounding context.
    full_pil.paste(result_pil, (cx1, cy1), mask=mask_crop)

    return pil_to_tensor(full_pil)


# ---------------------------------------------------------------------------
# DetailerSlot node
# ---------------------------------------------------------------------------

class ModusFlowDetailerSlot:
    """Config bundle node for one detection + inpaint pass."""

    @classmethod
    def INPUT_TYPES(cls):
        samplers = comfy.samplers.KSampler.SAMPLERS
        schedulers = comfy.samplers.KSampler.SCHEDULERS
        default_sampler = "euler_ancestral" if "euler_ancestral" in samplers else samplers[0]
        default_scheduler = "karras" if "karras" in schedulers else schedulers[0]
        return {
            "required": {
                "model": (DETECTOR_MODELS,),
                "steps": ("INT", {"default": 20, "min": 1, "max": 150}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 1.0, "max": 30.0, "step": 0.5}),
                "denoise": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0, "step": 0.01}),
                "padding": ("INT", {"default": 32, "min": 0, "max": 256}),
                "mask_blur": ("INT", {"default": 4, "min": 0, "max": 64}),
                "blend_feather": ("INT", {"default": 16, "min": 0, "max": 128}),
                "context_pad": ("INT", {"default": 32, "min": 0, "max": 256}),
                "sampler": (samplers, {"default": default_sampler}),
                "scheduler": (schedulers, {"default": default_scheduler}),
                "enabled": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
            },
        }

    RETURN_TYPES = ("DETAILER_SLOT",)
    RETURN_NAMES = ("slot",)
    FUNCTION = "build"
    CATEGORY = "ModusFlow/Detailing"

    def build(self, model, steps, cfg, denoise, padding, mask_blur, blend_feather,
              context_pad, sampler, scheduler, enabled, positive=None, negative=None):
        slot = {
            "model": model,
            "steps": steps,
            "cfg": cfg,
            "denoise": denoise,
            "padding": padding,
            "mask_blur": mask_blur,
            "blend_feather": blend_feather,
            "context_pad": context_pad,
            "sampler": sampler,
            "scheduler": scheduler,
            "enabled": enabled,
            "positive": positive,
            "negative": negative,
        }
        return (slot,)


# ---------------------------------------------------------------------------
# AllInOneDetailer node
# ---------------------------------------------------------------------------

_SKIP_MODELS = {"disabled", "(no models found)"}


class ModusFlowAllInOneDetailer:
    """Main detailer node — runs up to 6 DetailerSlot passes sequentially."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "confidence": ("FLOAT", {"default": 0.3, "min": 0.1, "max": 1.0, "step": 0.05}),
            },
            "optional": {
                "pipe": ("PIPE",),
                "image": ("IMAGE",),
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                # slot_1 is the seed socket; more are added dynamically by the JS frontend
                "slot_1": ("DETAILER_SLOT",),
            },
        }

    RETURN_TYPES = ("IMAGE", "PIPE")
    RETURN_NAMES = ("image", "pipe")
    FUNCTION = "detail"
    CATEGORY = "ModusFlow/Detailing"

    def detail(self, confidence,
               pipe=None, image=None, model=None, clip=None, vae=None,
               positive=None, negative=None, seed=0,
               **kwargs):

        # Resolve inputs: individual overrides take priority over pipe
        if pipe is not None:
            model    = model    if model    is not None else (pipe[0] if len(pipe) > 0 else None)
            clip     = clip     if clip     is not None else (pipe[1] if len(pipe) > 1 else None)
            vae      = vae      if vae      is not None else (pipe[2] if len(pipe) > 2 else None)
            positive = positive if positive is not None else (pipe[3] if len(pipe) > 3 else None)
            negative = negative if negative is not None else (pipe[4] if len(pipe) > 4 else None)

        # Validate required fields
        if image is None:
            raise ValueError("[AllInOneDetailer] IMAGE is required (wire an image input)")
        if model is None:
            raise ValueError("[AllInOneDetailer] MODEL is required (provide via pipe or direct input)")
        if vae is None:
            raise ValueError("[AllInOneDetailer] VAE is required (provide via pipe or direct input)")
        if positive is None:
            raise ValueError("[AllInOneDetailer] POSITIVE conditioning is required (provide via pipe or direct input)")
        if negative is None:
            raise ValueError("[AllInOneDetailer] NEGATIVE conditioning is required (provide via pipe or direct input)")

        # Collect all connected slot_N inputs in order (skip gaps so a
        # disconnected/disabled slot doesn't block later ones)
        slots = sorted(
            [(int(m.group(1)), v)
             for k, v in kwargs.items()
             if (m := re.fullmatch(r"slot_(\d+)", k))],
            key=lambda x: x[0],
        )

        print(f"[AllInOneDetailer] kwargs keys: {list(kwargs.keys())}")
        slot_summary = ", ".join(
            f"slot_{i}(enabled="
            f"{s.get('enabled') if isinstance(s, dict) else 'None'})"
            for i, s in slots
        )
        print(f"[AllInOneDetailer] collected {len(slots)} slot(s): {slot_summary}")

        current_tensor = image

        for i, slot in slots:
            if slot is None:
                print(f"[AllInOneDetailer] slot_{i}: skipping — value is None (node bypassed?)")
                continue
            if not slot.get("enabled", True):
                print(f"[AllInOneDetailer] slot_{i}: skipping — enabled=False")
                continue
            model_name = slot.get("model", "disabled")
            if model_name in _SKIP_MODELS:
                continue

            try:
                yolo_model = load_detector_model(model_name)
            except (FileNotFoundError, RuntimeError) as e:
                print(f"[AllInOneDetailer] Slot {i} ({model_name}): failed to load model — {e}")
                continue

            slot_positive = slot.get("positive") or positive
            slot_negative = slot.get("negative") or negative

            pil_image = tensor_to_pil(current_tensor)
            try:
                det_masks = get_detection_masks(yolo_model, pil_image, confidence)
            except Exception as e:
                print(f"[AllInOneDetailer] Slot {i} ({model_name}): detection failed — {e}")
                continue

            print(f"[AllInOneDetailer] Slot {i} ({model_name}): {len(det_masks)} detections")

            for mask in det_masks:
                try:
                    mask = expand_mask(mask, slot["padding"])
                    mask = apply_blur(mask, slot["mask_blur"])
                    current_tensor = detail_region(
                        current_tensor, mask,
                        model, clip, vae,
                        slot_positive, slot_negative,
                        seed,
                        slot["steps"], slot["cfg"], slot["denoise"],
                        slot["sampler"], slot["scheduler"],
                        blend_feather=slot.get("blend_feather", 16),
                        context_pad=slot.get("context_pad", 32),
                    )
                except Exception as e:
                    print(f"[AllInOneDetailer] Slot {i} ({model_name}): inpaint error — {e}")
                    continue

        output_pipe = (model, clip, vae, positive, negative)
        return (current_tensor, output_pipe)
