"""
ModusFlow Restormer Node
Image restoration node using the Restormer architecture.
Supports motion deblurring, defocus deblurring, real denoising, and Gaussian color denoising.

Place pretrained .pth files in ComfyUI/models/restormer/
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numbers
import os
import folder_paths
import comfy.model_management

# ──────────────────────────────────────────────────────────────────────────────
# Restormer Architecture (inference-only)
# Inlined from https://github.com/swz30/Restormer/blob/main/basicsr/models/archs/restormer_arch.py
# Zamir et al., "Restormer: Efficient Transformer for High-Resolution Image Restoration", CVPR 2022
# ──────────────────────────────────────────────────────────────────────────────

try:
    from einops import rearrange
except ImportError:
    raise ImportError(
        "[ModusFlow Restormer] The 'einops' package is required. "
        "Install it with: pip install einops"
    )


def _to_3d(x):
    return rearrange(x, 'b c h w -> b (h w) c')


def _to_4d(x, h, w):
    return rearrange(x, 'b (h w) c -> b c h w', h=h, w=w)


class _BiasFree_LayerNorm(nn.Module):
    def __init__(self, normalized_shape):
        super().__init__()
        if isinstance(normalized_shape, numbers.Integral):
            normalized_shape = (normalized_shape,)
        normalized_shape = torch.Size(normalized_shape)
        assert len(normalized_shape) == 1
        self.weight = nn.Parameter(torch.ones(normalized_shape))
        self.normalized_shape = normalized_shape

    def forward(self, x):
        sigma = x.var(-1, keepdim=True, unbiased=False)
        return x / torch.sqrt(sigma + 1e-5) * self.weight


class _WithBias_LayerNorm(nn.Module):
    def __init__(self, normalized_shape):
        super().__init__()
        if isinstance(normalized_shape, numbers.Integral):
            normalized_shape = (normalized_shape,)
        normalized_shape = torch.Size(normalized_shape)
        assert len(normalized_shape) == 1
        self.weight = nn.Parameter(torch.ones(normalized_shape))
        self.bias = nn.Parameter(torch.zeros(normalized_shape))
        self.normalized_shape = normalized_shape

    def forward(self, x):
        mu = x.mean(-1, keepdim=True)
        sigma = x.var(-1, keepdim=True, unbiased=False)
        return (x - mu) / torch.sqrt(sigma + 1e-5) * self.weight + self.bias


class _LayerNorm(nn.Module):
    def __init__(self, dim, LayerNorm_type):
        super().__init__()
        if LayerNorm_type == 'BiasFree':
            self.body = _BiasFree_LayerNorm(dim)
        else:
            self.body = _WithBias_LayerNorm(dim)

    def forward(self, x):
        h, w = x.shape[-2:]
        return _to_4d(self.body(_to_3d(x)), h, w)


class _FeedForward(nn.Module):
    def __init__(self, dim, ffn_expansion_factor, bias):
        super().__init__()
        hidden_features = int(dim * ffn_expansion_factor)
        self.project_in = nn.Conv2d(dim, hidden_features * 2, kernel_size=1, bias=bias)
        self.dwconv = nn.Conv2d(
            hidden_features * 2, hidden_features * 2,
            kernel_size=3, stride=1, padding=1, groups=hidden_features * 2, bias=bias
        )
        self.project_out = nn.Conv2d(hidden_features, dim, kernel_size=1, bias=bias)

    def forward(self, x):
        x = self.project_in(x)
        x1, x2 = self.dwconv(x).chunk(2, dim=1)
        x = F.gelu(x1) * x2
        x = self.project_out(x)
        return x


class _Attention(nn.Module):
    def __init__(self, dim, num_heads, bias):
        super().__init__()
        self.num_heads = num_heads
        self.temperature = nn.Parameter(torch.ones(num_heads, 1, 1))
        self.qkv = nn.Conv2d(dim, dim * 3, kernel_size=1, bias=bias)
        self.qkv_dwconv = nn.Conv2d(
            dim * 3, dim * 3, kernel_size=3, stride=1, padding=1, groups=dim * 3, bias=bias
        )
        self.project_out = nn.Conv2d(dim, dim, kernel_size=1, bias=bias)

    def forward(self, x):
        b, c, h, w = x.shape
        qkv = self.qkv_dwconv(self.qkv(x))
        q, k, v = qkv.chunk(3, dim=1)
        q = rearrange(q, 'b (head c) h w -> b head c (h w)', head=self.num_heads)
        k = rearrange(k, 'b (head c) h w -> b head c (h w)', head=self.num_heads)
        v = rearrange(v, 'b (head c) h w -> b head c (h w)', head=self.num_heads)
        q = F.normalize(q, dim=-1)
        k = F.normalize(k, dim=-1)
        attn = (q @ k.transpose(-2, -1)) * self.temperature
        attn = attn.softmax(dim=-1)
        out = attn @ v
        out = rearrange(out, 'b head c (h w) -> b (head c) h w', head=self.num_heads, h=h, w=w)
        out = self.project_out(out)
        return out


class _TransformerBlock(nn.Module):
    def __init__(self, dim, num_heads, ffn_expansion_factor, bias, LayerNorm_type):
        super().__init__()
        self.norm1 = _LayerNorm(dim, LayerNorm_type)
        self.attn = _Attention(dim, num_heads, bias)
        self.norm2 = _LayerNorm(dim, LayerNorm_type)
        self.ffn = _FeedForward(dim, ffn_expansion_factor, bias)

    def forward(self, x):
        x = x + self.attn(self.norm1(x))
        x = x + self.ffn(self.norm2(x))
        return x


class _OverlapPatchEmbed(nn.Module):
    def __init__(self, in_c=3, embed_dim=48, bias=False):
        super().__init__()
        self.proj = nn.Conv2d(in_c, embed_dim, kernel_size=3, stride=1, padding=1, bias=bias)

    def forward(self, x):
        return self.proj(x)


class _Downsample(nn.Module):
    def __init__(self, n_feat):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(n_feat, n_feat // 2, kernel_size=3, stride=1, padding=1, bias=False),
            nn.PixelUnshuffle(2),
        )

    def forward(self, x):
        return self.body(x)


class _Upsample(nn.Module):
    def __init__(self, n_feat):
        super().__init__()
        self.body = nn.Sequential(
            nn.Conv2d(n_feat, n_feat * 2, kernel_size=3, stride=1, padding=1, bias=False),
            nn.PixelShuffle(2),
        )

    def forward(self, x):
        return self.body(x)


class _Restormer(nn.Module):
    def __init__(
        self,
        inp_channels=3,
        out_channels=3,
        dim=48,
        num_blocks=(4, 6, 6, 8),
        num_refinement_blocks=4,
        heads=(1, 2, 4, 8),
        ffn_expansion_factor=2.66,
        bias=False,
        LayerNorm_type='WithBias',
        dual_pixel_task=False,
    ):
        super().__init__()

        self.patch_embed = _OverlapPatchEmbed(inp_channels, dim)

        self.encoder_level1 = nn.Sequential(*[
            _TransformerBlock(dim=dim, num_heads=heads[0],
                              ffn_expansion_factor=ffn_expansion_factor,
                              bias=bias, LayerNorm_type=LayerNorm_type)
            for _ in range(num_blocks[0])
        ])
        self.down1_2 = _Downsample(dim)
        self.encoder_level2 = nn.Sequential(*[
            _TransformerBlock(dim=int(dim * 2), num_heads=heads[1],
                              ffn_expansion_factor=ffn_expansion_factor,
                              bias=bias, LayerNorm_type=LayerNorm_type)
            for _ in range(num_blocks[1])
        ])
        self.down2_3 = _Downsample(int(dim * 2))
        self.encoder_level3 = nn.Sequential(*[
            _TransformerBlock(dim=int(dim * 4), num_heads=heads[2],
                              ffn_expansion_factor=ffn_expansion_factor,
                              bias=bias, LayerNorm_type=LayerNorm_type)
            for _ in range(num_blocks[2])
        ])
        self.down3_4 = _Downsample(int(dim * 4))
        self.latent = nn.Sequential(*[
            _TransformerBlock(dim=int(dim * 8), num_heads=heads[3],
                              ffn_expansion_factor=ffn_expansion_factor,
                              bias=bias, LayerNorm_type=LayerNorm_type)
            for _ in range(num_blocks[3])
        ])

        self.up4_3 = _Upsample(int(dim * 8))
        self.reduce_chan_level3 = nn.Conv2d(int(dim * 8), int(dim * 4), kernel_size=1, bias=bias)
        self.decoder_level3 = nn.Sequential(*[
            _TransformerBlock(dim=int(dim * 4), num_heads=heads[2],
                              ffn_expansion_factor=ffn_expansion_factor,
                              bias=bias, LayerNorm_type=LayerNorm_type)
            for _ in range(num_blocks[2])
        ])

        self.up3_2 = _Upsample(int(dim * 4))
        self.reduce_chan_level2 = nn.Conv2d(int(dim * 4), int(dim * 2), kernel_size=1, bias=bias)
        self.decoder_level2 = nn.Sequential(*[
            _TransformerBlock(dim=int(dim * 2), num_heads=heads[1],
                              ffn_expansion_factor=ffn_expansion_factor,
                              bias=bias, LayerNorm_type=LayerNorm_type)
            for _ in range(num_blocks[1])
        ])

        self.up2_1 = _Upsample(int(dim * 2))
        self.decoder_level1 = nn.Sequential(*[
            _TransformerBlock(dim=int(dim * 2), num_heads=heads[0],
                              ffn_expansion_factor=ffn_expansion_factor,
                              bias=bias, LayerNorm_type=LayerNorm_type)
            for _ in range(num_blocks[0])
        ])

        self.refinement = nn.Sequential(*[
            _TransformerBlock(dim=int(dim * 2), num_heads=heads[0],
                              ffn_expansion_factor=ffn_expansion_factor,
                              bias=bias, LayerNorm_type=LayerNorm_type)
            for _ in range(num_refinement_blocks)
        ])

        self.dual_pixel_task = dual_pixel_task
        if self.dual_pixel_task:
            self.skip_conv = nn.Conv2d(dim, int(dim * 2), kernel_size=1, bias=bias)

        self.output = nn.Conv2d(int(dim * 2), out_channels, kernel_size=3, stride=1, padding=1, bias=bias)

    def forward(self, inp_img):
        inp_enc_level1 = self.patch_embed(inp_img)
        out_enc_level1 = self.encoder_level1(inp_enc_level1)

        inp_enc_level2 = self.down1_2(out_enc_level1)
        out_enc_level2 = self.encoder_level2(inp_enc_level2)

        inp_enc_level3 = self.down2_3(out_enc_level2)
        out_enc_level3 = self.encoder_level3(inp_enc_level3)

        inp_enc_level4 = self.down3_4(out_enc_level3)
        latent = self.latent(inp_enc_level4)

        inp_dec_level3 = self.up4_3(latent)
        inp_dec_level3 = torch.cat([inp_dec_level3, out_enc_level3], 1)
        inp_dec_level3 = self.reduce_chan_level3(inp_dec_level3)
        out_dec_level3 = self.decoder_level3(inp_dec_level3)

        inp_dec_level2 = self.up3_2(out_dec_level3)
        inp_dec_level2 = torch.cat([inp_dec_level2, out_enc_level2], 1)
        inp_dec_level2 = self.reduce_chan_level2(inp_dec_level2)
        out_dec_level2 = self.decoder_level2(inp_dec_level2)

        inp_dec_level1 = self.up2_1(out_dec_level2)
        inp_dec_level1 = torch.cat([inp_dec_level1, out_enc_level1], 1)
        out_dec_level1 = self.decoder_level1(inp_dec_level1)

        out_dec_level1 = self.refinement(out_dec_level1)

        if self.dual_pixel_task:
            out_dec_level1 = out_dec_level1 + self.skip_conv(inp_enc_level1)
            out_dec_level1 = self.output(out_dec_level1)
        else:
            out_dec_level1 = self.output(out_dec_level1) + inp_img

        return out_dec_level1


# ──────────────────────────────────────────────────────────────────────────────
# Model folder registration
# ──────────────────────────────────────────────────────────────────────────────

_FOLDER_KEY = "restormer"
_restormer_models_dir = os.path.join(folder_paths.models_dir, _FOLDER_KEY)
os.makedirs(_restormer_models_dir, exist_ok=True)
folder_paths.add_model_folder_path(_FOLDER_KEY, _restormer_models_dir)


# Task → LayerNorm_type
_TASK_LAYERNORM = {
    "Motion_Deblurring": "WithBias",
    "Single_Image_Defocus_Deblurring": "WithBias",
    "Real_Denoising": "BiasFree",
    "Gaussian_Color_Denoising": "BiasFree",
}

_TASKS = list(_TASK_LAYERNORM.keys())


def _get_model_files():
    try:
        files = folder_paths.get_filename_list(_FOLDER_KEY)
        pth_files = sorted(f for f in files if f.lower().endswith('.pth'))
        return pth_files if pth_files else ["-- no .pth files found --"]
    except Exception:
        return ["-- no .pth files found --"]


# ──────────────────────────────────────────────────────────────────────────────
# Node
# ──────────────────────────────────────────────────────────────────────────────

class ModusFlowRestormer:
    """
    Restormer image restoration node.
    Supported tasks:
      - Motion_Deblurring
      - Single_Image_Defocus_Deblurring
      - Real_Denoising
      - Gaussian_Color_Denoising

    Place pretrained .pth files in ComfyUI/models/restormer/
    """

    def __init__(self):
        self._model = None
        self._model_key = None  # (model_file, task) — reload only when this changes

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "image": ("IMAGE",),
                "model_file": (_get_model_files(),),
                "task": (_TASKS,),
                "tile_size": ("INT", {"default": 256, "min": 0, "max": 2048, "step": 8,
                                      "tooltip": "Tile edge length in pixels. 0 = full image (no tiling)."}),
                "tile_overlap": ("INT", {"default": 32, "min": 0, "max": 256, "step": 8,
                                         "tooltip": "Overlap between adjacent tiles for seam blending."}),
            }
        }

    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("image",)
    FUNCTION = "restore"
    CATEGORY = "ModusFlow/Restoration"

    # ── Model loading ─────────────────────────────────────────────────────────

    def _load_model(self, model_file, task):
        key = (model_file, task)
        if self._model is not None and self._model_key == key:
            return self._model

        print(f"[ModusFlow Restormer] Loading '{model_file}' for task '{task}'")

        model_path = folder_paths.get_full_path(_FOLDER_KEY, model_file)
        if not model_path or not os.path.exists(model_path):
            raise FileNotFoundError(
                f"[ModusFlow Restormer] Model file not found: {model_file}\n"
                f"Place .pth files in: {_restormer_models_dir}"
            )

        layernorm_type = _TASK_LAYERNORM[task]

        checkpoint = torch.load(model_path, map_location='cpu', weights_only=False)
        if isinstance(checkpoint, dict):
            if 'params' in checkpoint:
                state_dict = checkpoint['params']
            elif 'state_dict' in checkpoint:
                state_dict = checkpoint['state_dict']
            else:
                state_dict = checkpoint
        else:
            state_dict = checkpoint

        # Auto-detect architecture from checkpoint weights to handle both
        # standard (inp_channels=3) and dual-pixel (inp_channels=6, dual_pixel_task=True) models.
        inp_channels = state_dict['patch_embed.proj.weight'].shape[1]
        dual_pixel_task = 'skip_conv.weight' in state_dict
        if dual_pixel_task:
            print(f"[ModusFlow Restormer] Detected dual-pixel model (inp_channels={inp_channels})")

        model = _Restormer(
            LayerNorm_type=layernorm_type,
            inp_channels=inp_channels,
            dual_pixel_task=dual_pixel_task,
        )
        model.load_state_dict(state_dict)
        model.eval()

        device = comfy.model_management.get_torch_device()
        model = model.to(device)

        self._model = model
        self._model_key = key
        print(f"[ModusFlow Restormer] Model ready on {device}")
        return model

    # ── Inference helpers ─────────────────────────────────────────────────────

    def _infer(self, model, img_bchw):
        """Run model on [B, C, H, W] float32, return clamped [B, C, H, W]."""
        with torch.no_grad():
            out = model(img_bchw)
        return torch.clamp(out, 0.0, 1.0)

    def _infer_tiled(self, model, img_bchw, tile_size, tile_overlap):
        """
        Tile the image, run the model on each tile, and blend with a Hann window.
        img_bchw: [B, C, H, W] float32 on the model device.
        Returns [B, C, H, W].
        """
        B, C, H, W = img_bchw.shape
        device = img_bchw.device
        stride = max(tile_size - tile_overlap, 1)

        # Reflect-pad so tiles cover the full image
        pad_h = (stride - (H - tile_overlap) % stride) % stride
        pad_w = (stride - (W - tile_overlap) % stride) % stride
        img_padded = F.pad(img_bchw, (0, pad_w, 0, pad_h), mode='reflect') if (pad_h or pad_w) else img_bchw
        _, _, pH, pW = img_padded.shape

        # Output channels may differ from input channels (e.g. dual-pixel models take 6 in, emit 3 out)
        out_C = model.output.weight.shape[0]
        output_sum = torch.zeros(B, out_C, pH, pW, device=device, dtype=img_bchw.dtype)
        weight_sum = torch.zeros(1, 1, pH, pW, device=device, dtype=img_bchw.dtype)

        # Hann window for smooth seam blending
        win_y = torch.hann_window(tile_size, periodic=False, device=device)
        win_x = torch.hann_window(tile_size, periodic=False, device=device)
        window = (win_y[:, None] * win_x[None, :]).unsqueeze(0).unsqueeze(0)  # [1, 1, T, T]

        def _tile_starts(length):
            starts = list(range(0, length - tile_size + 1, stride))
            if not starts or starts[-1] + tile_size < length:
                starts.append(max(length - tile_size, 0))
            return starts

        for y in _tile_starts(pH):
            for x in _tile_starts(pW):
                tile = img_padded[:, :, y:y + tile_size, x:x + tile_size]
                tile_out = self._infer(model, tile)
                output_sum[:, :, y:y + tile_size, x:x + tile_size] += tile_out * window
                weight_sum[:, :, y:y + tile_size, x:x + tile_size] += window

        output = output_sum / weight_sum.clamp(min=1e-6)
        return output[:, :, :H, :W]

    # ── Main entry point ──────────────────────────────────────────────────────

    def restore(self, image, model_file, task, tile_size, tile_overlap):
        """
        Restore the image.

        Args:
            image:        [B, H, W, C] float32 in [0, 1]
            model_file:   .pth filename from models/restormer/
            task:         restoration task name
            tile_size:    tile edge length (0 = full image)
            tile_overlap: overlap in pixels for tile blending

        Returns:
            ([B, H, W, C] float32,)
        """
        if model_file.startswith("--"):
            raise ValueError(
                "[ModusFlow Restormer] No model files available. "
                f"Place pretrained .pth files in: {_restormer_models_dir}"
            )

        device = comfy.model_management.get_torch_device()
        model = self._load_model(model_file, task)

        # [B, H, W, C] → [B, C, H, W]
        img = image.permute(0, 3, 1, 2).to(device)

        # Dual-pixel models expect 6 channels (left+right stacked).
        # When a standard 3-channel image is provided, duplicate it.
        expected_channels = model.patch_embed.proj.weight.shape[1]
        if expected_channels == 6 and img.shape[1] == 3:
            img = torch.cat([img, img], dim=1)

        if tile_size > 0:
            out = self._infer_tiled(model, img, tile_size, tile_overlap)
        else:
            out = self._infer(model, img)

        # [B, C, H, W] → [B, H, W, C], move back to CPU
        out = out.permute(0, 2, 3, 1).cpu()
        return (out,)


NODE_CLASS_MAPPINGS = {
    "ModusFlowRestormer": ModusFlowRestormer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModusFlowRestormer": "ModusFlow Restormer",
}
