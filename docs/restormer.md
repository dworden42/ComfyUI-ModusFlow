# ModusFlow Restormer

Image restoration node using the [Restormer](https://github.com/swz30/Restormer) architecture (Zamir et al., CVPR 2022). Runs entirely locally from pretrained `.pth` weights — no external repository required.

## Supported Tasks

| Task | Description | LayerNorm |
|------|-------------|-----------|
| `Motion_Deblurring` | Remove camera/subject motion blur | WithBias |
| `Single_Image_Defocus_Deblurring` | Correct lens defocus / shallow DoF blur | WithBias |
| `Real_Denoising` | Remove real-world sensor noise | BiasFree |
| `Gaussian_Color_Denoising` | Remove Gaussian noise from color images | BiasFree |

## Model Setup

1. Download pretrained weights from the [Restormer releases](https://github.com/swz30/Restormer/releases) or the official Google Drive links in the repository.
2. Place the `.pth` files in `ComfyUI/models/restormer/`.
3. The dropdown in the node will automatically list all `.pth` files found there.

Each task has its own pretrained model — make sure to select the matching `task` for the model you loaded.

## Inputs

| Input | Type | Default | Description |
|-------|------|---------|-------------|
| `image` | IMAGE | — | Input image tensor `[B, H, W, C]` in `[0, 1]` |
| `model_file` | dropdown | — | `.pth` file from `models/restormer/` |
| `task` | dropdown | `Motion_Deblurring` | Restoration task — must match the loaded model |
| `tile_size` | INT | 256 | Tile edge length in pixels. **0 = full image** (no tiling). Use tiling for large images that don't fit in VRAM. |
| `tile_overlap` | INT | 32 | Pixel overlap between adjacent tiles. Larger values reduce seam artifacts at the cost of extra computation. |

## Output

| Output | Type | Description |
|--------|------|-------------|
| `image` | IMAGE | Restored image, same shape as input |

## Tips

- **Tile size 0** processes the entire image in one pass — fastest but requires enough VRAM for the full resolution.
- **Tile size 256 with overlap 32** is a safe default for most GPUs at 1080p and below.
- For very large images (4K+), increase `tile_size` to 512 or 768 and keep `tile_overlap` at 32–64.
- The model is **lazy-loaded** on first use and **cached** as long as `model_file` and `task` stay the same. Switching either will trigger a reload.
- Input is expected to be float32 in `[0, 1]` — the standard ComfyUI IMAGE format. No additional normalization is applied.

## Troubleshooting

**"No .pth files found"** — Check that your weights are in `ComfyUI/models/restormer/` and have a `.pth` extension.

**Shape mismatch / unexpected keys on load** — Make sure the selected `task` matches the pretrained model. Mixing tasks and weights will cause a state-dict error.

**VRAM out of memory** — Enable tiling by setting `tile_size` to 256 or lower.

**`einops` not installed** — Run `pip install einops` in your ComfyUI Python environment.
