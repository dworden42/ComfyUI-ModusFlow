"""
ModusFlow Upscaler Node
A comprehensive upscaler node similar to SD Ultimate Upscaler with CUDNN toggle.
Supports tiled upscaling with seam fixing for high-resolution outputs.
"""

import torch
import torch.nn.functional as F
import math
import comfy.utils
from nodes import KSampler
from comfy.utils import ProgressBar
import folder_paths


class ModusFlowUpscaler:
    """
    Advanced upscaler node with tiled processing and seam fixing.
    Similar to SD Ultimate Upscaler but with CUDNN control.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        # Get available upscaler models
        try:
            upscale_models = folder_paths.get_filename_list("upscale_models")
            upscale_models = ["None"] + sorted(upscale_models)
        except:
            upscale_models = ["None"]
        
        return {
            "required": {
                # Input
                "image": ("IMAGE",),
                
                # Upscale settings
                "upscale_by": ("FLOAT", {"default": 2.0, "min": 1.0, "max": 8.0, "step": 0.1}),
                "upscale_model_name": (upscale_models, {"default": "None"}),
                "fallback_method": (["Nearest", "Bilinear", "Bicubic", "Area", "Lanczos"], {"default": "Bicubic"}),
                
                # Pre-processing
                "pre_sharpen": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 2.0, "step": 0.1}),
                "pre_blur": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 10.0, "step": 0.1}),
                
                # Tile settings
                "tile_width": ("INT", {"default": 768, "min": 64, "max": 4096, "step": 8}),
                "tile_height": ("INT", {"default": 768, "min": 64, "max": 4096, "step": 8}),
                "tile_padding": ("INT", {"default": 64, "min": 0, "max": 256, "step": 8}),
                "tile_batch_size": ("INT", {"default": 1, "min": 1, "max": 16, "step": 1}),

                # Sampling settings
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 100.0, "step": 0.1}),
                "sampler_name": (["euler", "euler_ancestral", "heun", "heunpp2", "dpm_2", "dpm_2_ancestral",
                                "lms", "dpm_fast", "dpm_adaptive", "dpmpp_2s_ancestral", "dpmpp_sde",
                                "dpmpp_sde_gpu", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu",
                                "dpmpp_3m_sde", "dpmpp_3m_sde_gpu", "ddpm", "lcm", "ddim", "uni_pc",
                                "uni_pc_bh2"], {"default": "euler"}),
                "scheduler": (["normal", "karras", "exponential", "sgm_uniform", "simple", "ddim_uniform"],
                             {"default": "normal"}),
                "denoise": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01}),

                # Seam fix settings
                "seam_fix_mode": (["None", "Band Pass", "Half Tile", "Half Tile + Intersections"], {"default": "Half Tile"}),
                "seam_fix_denoise": ("FLOAT", {"default": 0.35, "min": 0.0, "max": 1.0, "step": 0.01}),
                "seam_fix_width": ("INT", {"default": 64, "min": 0, "max": 256, "step": 8}),
                "seam_fix_mask_blur": ("INT", {"default": 16, "min": 0, "max": 64, "step": 1}),
                
                # Post-processing
                "post_sharpen": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 2.0, "step": 0.1}),
                "contrast": ("FLOAT", {"default": 1.0, "min": 0.5, "max": 1.5, "step": 0.05}),
                "brightness": ("FLOAT", {"default": 0.0, "min": -0.5, "max": 0.5, "step": 0.05}),
                "saturation": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 2.0, "step": 0.05}),
                
                # Advanced settings
                "rescale_after_model": ("BOOLEAN", {"default": False}),
                "force_uniform_tiles": ("BOOLEAN", {"default": False}),

                # Batch processing
                "batch_mode": (["Parallel", "Sequential"], {"default": "Parallel"}),

                # VAE settings
                "use_cudnn": ("BOOLEAN", {"default": True}),
                "tile_vae": ("BOOLEAN", {"default": False}),
            },
            "optional": {
                # Pipe input (alternative to individual inputs)
                "pipe": ("PIPE",),
                # Model inputs (can come from pipe or individual connections)
                "model": ("MODEL",),
                "vae": ("VAE",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                # Optional mask for selective upscaling
                "mask": ("MASK",),
                # Optional upscaler model (for AI upscalers like ESRGAN, RealESRGAN, etc.)
                "upscaler": ("UPSCALE_MODEL",),
            }
        }
    
    RETURN_TYPES = ("IMAGE", "IMAGE", "PIPE")
    RETURN_NAMES = ("image", "original_image", "pipe")
    FUNCTION = "upscale_image"
    CATEGORY = "ModusFlow/Upscaling"
    
    def upscale_image(self, image, upscale_by, upscale_model_name,
                     fallback_method, pre_sharpen, pre_blur, tile_width, tile_height, tile_padding,
                     tile_batch_size, seed, steps, cfg, sampler_name, scheduler, denoise, seam_fix_mode,
                     seam_fix_denoise, seam_fix_width, seam_fix_mask_blur, post_sharpen,
                     contrast, brightness, saturation, rescale_after_model, force_uniform_tiles,
                     batch_mode, use_cudnn, tile_vae, pipe=None, model=None, vae=None, positive=None, negative=None,
                     mask=None, upscaler=None):
        """
        Upscale image using tiled processing with optional seam fixing.

        Batch Processing Modes:
        - Parallel: Process all images in batch simultaneously (faster, more VRAM)
        - Sequential: Process images one at a time (slower, less VRAM)
        """
        
        
        # Extract from pipe if provided (individual inputs override pipe)
        clip = None  # Initialize CLIP for passthrough
        if pipe is not None:
            # Pipe format: (model, clip, vae, positive, negative)
            
            model = model if model is not None else (pipe[0] if len(pipe) > 0 else None)
            clip = pipe[1] if len(pipe) > 1 else None  # Extract CLIP from pipe for passthrough
            vae = vae if vae is not None else (pipe[2] if len(pipe) > 2 else None)
            positive = positive if positive is not None else (pipe[3] if len(pipe) > 3 else None)
            negative = negative if negative is not None else (pipe[4] if len(pipe) > 4 else None)
            
        else:
            # Use individual inputs as provided
            pass
        
        # Validate required inputs
        if model is None or vae is None or positive is None or negative is None:
            raise ValueError("MODEL, VAE, POSITIVE, and NEGATIVE are required (provide via pipe or individual inputs)")
        
        # Set CUDNN state
        import torch.backends.cudnn as cudnn
        original_cudnn_enabled = cudnn.enabled
        original_cudnn_benchmark = cudnn.benchmark
        
        if not use_cudnn:
            cudnn.enabled = False
            cudnn.benchmark = False
        
        try:
            # Store original for passthrough
            original_image = image.clone()

            # Check batch size
            batch_size = image.shape[0]
            if batch_size > 1:

                # Sequential batch processing (lower VRAM usage)
                if batch_mode == "Sequential":
                    return self._upscale_sequential_batch(
                        image, upscale_by, upscale_model_name, fallback_method,
                        pre_sharpen, pre_blur, tile_width, tile_height, tile_padding,
                        seed, steps, cfg, sampler_name, scheduler, denoise,
                        seam_fix_mode, seam_fix_denoise, seam_fix_width, seam_fix_mask_blur,
                        post_sharpen, contrast, brightness, saturation,
                        rescale_after_model, tile_vae, model, clip, vae, positive, negative,
                        mask, upscaler
                    )

            # Parallel batch processing (or single image) - continues with current code
            # Step 0: Pre-processing
            if pre_sharpen > 0:
                image = self._apply_sharpen(image, pre_sharpen)
            if pre_blur > 0:
                image = self._apply_blur(image, pre_blur)
            
            # Step 1: Load and use upscaler model
            loaded_upscaler = None
            if upscale_model_name != "None":
                try:
                    loaded_upscaler = self._load_upscaler_model(upscale_model_name)
                except Exception as e:
                    print(f"[ModusFlow Upscaler] Failed to load upscaler model: {e}")
                    loaded_upscaler = None
            
            # Use upscaler parameter if provided (for pipe workflows)
            if upscaler is not None:
                loaded_upscaler = upscaler
            
            # Step 2: Initial upscale
            if loaded_upscaler is not None:
                # Use AI upscaler model
                upscaled = self._use_upscaler_model(image, loaded_upscaler, upscale_by)
            else:
                # Use simple interpolation
                upscaled = self._simple_upscale(image, upscale_by, fallback_method)
            
            B, H, W, C = upscaled.shape
            
            # If denoise is 0, skip tiled processing
            if denoise == 0:
                
                # Apply post-processing
                if post_sharpen > 0:
                    upscaled = self._apply_sharpen(upscaled, post_sharpen)
                if contrast != 1.0 or brightness != 0.0 or saturation != 1.0:
                    upscaled = self._apply_color_adjustments(upscaled, contrast, brightness, saturation)
                
                # Apply mask if provided
                if mask is not None:
                    upscaled_original = self._simple_upscale(original_image, upscale_by, fallback_method)
                    upscaled = self._apply_mask_selective(upscaled_original, upscaled, mask)
                
                output_pipe = (model, clip, vae, positive, negative)
                return (upscaled, original_image, output_pipe)
            
            # Step 2: Tiled processing
            processed = self._process_tiles(
                upscaled, model, vae, positive, negative,
                tile_width, tile_height, tile_padding,
                seed, steps, cfg, sampler_name, scheduler, denoise,
                tile_vae
            )
            
            # Step 3: Seam fixing (if enabled)
            if seam_fix_mode != "None" and seam_fix_denoise > 0:
                processed = self._fix_seams(
                    processed, model, vae, positive, negative,
                    tile_width, tile_height, tile_padding,
                    seed, steps, cfg, sampler_name, scheduler,
                    seam_fix_denoise, seam_fix_mode, seam_fix_width,
                    seam_fix_mask_blur, tile_vae
                )
            
            
            # Step 4: Post-processing
            if post_sharpen > 0:
                processed = self._apply_sharpen(processed, post_sharpen)
            
            if contrast != 1.0 or brightness != 0.0 or saturation != 1.0:
                processed = self._apply_color_adjustments(processed, contrast, brightness, saturation)
            
            # Step 5: Apply mask if provided (selective processing)
            if mask is not None:
                upscaled_original = self._simple_upscale(original_image, upscale_by, fallback_method)
                processed = self._apply_mask_selective(upscaled_original, processed, mask)
            
            # Step 6: Optional rescale after model processing
            if rescale_after_model and upscale_by != 1.0:
                processed = self._simple_upscale(processed, upscale_by, fallback_method)
            
            # Create output pipe
            output_pipe = (model, clip, vae, positive, negative)
            
            return (processed, original_image, output_pipe)
            
        finally:
            # Restore CUDNN settings
            if not use_cudnn:
                cudnn.enabled = original_cudnn_enabled
                cudnn.benchmark = original_cudnn_benchmark

    def _upscale_sequential_batch(self, image, upscale_by, upscale_model_name, fallback_method,
                                  pre_sharpen, pre_blur, tile_width, tile_height, tile_padding,
                                  seed, steps, cfg, sampler_name, scheduler, denoise,
                                  seam_fix_mode, seam_fix_denoise, seam_fix_width, seam_fix_mask_blur,
                                  post_sharpen, contrast, brightness, saturation,
                                  rescale_after_model, tile_vae, model, clip, vae, positive, negative,
                                  mask, upscaler):
        """
        Process batch sequentially (one image at a time) to reduce VRAM usage.
        """
        batch_size = image.shape[0]
        processed_images = []
        original_images = []


        # Initialize progress bar
        pbar = ProgressBar(batch_size)

        for batch_idx in range(batch_size):
            pbar.update_absolute(batch_idx + 1, batch_size)

            # Extract single image from batch
            single_image = image[batch_idx:batch_idx+1]
            single_mask = mask[batch_idx:batch_idx+1] if mask is not None else None

            # Process single image using main upscale logic
            result = self.upscale_image(
                single_image, upscale_by, upscale_model_name, fallback_method,
                pre_sharpen, pre_blur, tile_width, tile_height, tile_padding,
                1,  # tile_batch_size
                seed + batch_idx,  # Vary seed per image
                steps, cfg, sampler_name, scheduler, denoise,
                seam_fix_mode, seam_fix_denoise, seam_fix_width, seam_fix_mask_blur,
                post_sharpen, contrast, brightness, saturation,
                rescale_after_model, False,  # force_uniform_tiles
                "Parallel",  # batch_mode (prevent recursive sequential calls)
                True,  # use_cudnn
                tile_vae,
                pipe=None, model=model, vae=vae, positive=positive, negative=negative,
                mask=single_mask, upscaler=upscaler
            )

            # Extract processed and original images from result
            processed_img, original_img, _ = result
            processed_images.append(processed_img)
            original_images.append(original_img)

        # Concatenate all processed images back into a batch
        processed_batch = torch.cat(processed_images, dim=0)
        original_batch = torch.cat(original_images, dim=0)

        # Create output pipe
        output_pipe = (model, clip, vae, positive, negative)


        return (processed_batch, original_batch, output_pipe)

    def _simple_upscale(self, image, scale, mode):
        """Simple upscaling using various interpolation methods."""
        B, H, W, C = image.shape
        
        new_h = int(H * scale)
        new_w = int(W * scale)
        
        if mode == "None" or scale == 1.0:
            return image
        
        # Permute to (B, C, H, W) for interpolate
        image_permuted = image.permute(0, 3, 1, 2)
        
        # Map mode names to torch modes
        mode_map = {
            "Nearest": "nearest",
            "Bilinear": "bilinear",
            "Bicubic": "bicubic",
            "Area": "area",
            "Lanczos": "bicubic",  # Lanczos approximated with bicubic
        }
        
        torch_mode = mode_map.get(mode, "bilinear")
        align_corners = torch_mode in ["bilinear", "bicubic"]
        
        # Upscale
        upscaled = F.interpolate(
            image_permuted,
            size=(new_h, new_w),
            mode=torch_mode,
            align_corners=align_corners if align_corners else None
        )
        
        # Permute back to (B, H, W, C)
        return upscaled.permute(0, 2, 3, 1)
    
    def _process_tiles(self, image, model, vae, positive, negative,
                      tile_w, tile_h, padding, seed, steps, cfg,
                      sampler_name, scheduler, denoise, tile_vae):
        """Process image in tiles with overlap."""
        
        B, H, W, C = image.shape
        
        # Calculate tile positions
        tiles = self._calculate_tiles(W, H, tile_w, tile_h, padding)
        
        
        # Initialize progress bar
        pbar = ProgressBar(len(tiles))
        
        # Process each tile
        result = image.clone()
        
        for idx, (x, y, tile_width, tile_height) in enumerate(tiles):
            pbar.update_absolute(idx + 1, len(tiles))
            
            # Extract tile
            tile_img = image[:, y:y+tile_height, x:x+tile_width, :]
            
            # Process tile
            processed_tile = self._process_single_tile(
                tile_img, model, vae, positive, negative,
                seed + idx, steps, cfg, sampler_name, scheduler,
                denoise, tile_vae
            )
            
            # Blend tile back with feathering
            result = self._blend_tile(
                result, processed_tile, x, y, tile_width, tile_height, padding
            )
        
        return result
    
    def _calculate_tiles(self, width, height, tile_w, tile_h, padding):
        """Calculate tile positions with overlap."""
        tiles = []
        
        # Calculate number of tiles needed
        cols = math.ceil((width - padding) / (tile_w - padding))
        rows = math.ceil((height - padding) / (tile_h - padding))
        
        for row in range(rows):
            for col in range(cols):
                # Calculate tile position
                x = col * (tile_w - padding)
                y = row * (tile_h - padding)
                
                # Adjust last tiles to fit within image
                if x + tile_w > width:
                    x = width - tile_w
                if y + tile_h > height:
                    y = height - tile_h
                
                # Ensure non-negative
                x = max(0, x)
                y = max(0, y)
                
                # Calculate actual tile size
                actual_w = min(tile_w, width - x)
                actual_h = min(tile_h, height - y)
                
                tiles.append((x, y, actual_w, actual_h))
        
        # Remove duplicates
        tiles = list(dict.fromkeys(tiles))
        
        return tiles
    
    def _process_single_tile(self, tile, model, vae, positive, negative,
                            seed, steps, cfg, sampler_name, scheduler,
                            denoise, tile_vae):
        """Process a single tile through VAE encode -> sample -> decode."""
        
        try:
            # Encode tile to latent
            latent = vae.encode(tile[:, :, :, :3])
            latent_samples = {"samples": latent}
            
            # Sample
            if denoise > 0:
                ksampler = KSampler()
                sampled_latent = ksampler.sample(
                    model=model,
                    seed=seed,
                    steps=steps,
                    cfg=cfg,
                    sampler_name=sampler_name,
                    scheduler=scheduler,
                    positive=positive,
                    negative=negative,
                    latent_image=latent_samples,
                    denoise=denoise
                )
                latent_samples = sampled_latent[0]
            
            # Decode
            decoded = vae.decode(latent_samples["samples"])
            
            return decoded
            
        except Exception as e:
            return tile
    
    def _blend_tile(self, base, tile, x, y, tile_w, tile_h, padding):
        """Blend tile back into base image with feathering."""
        
        B, H, W, C = base.shape
        
        # Create feather mask
        mask = self._create_feather_mask(tile_h, tile_w, padding)
        mask = mask.to(base.device)
        
        # Ensure mask matches tile dimensions
        if mask.shape[0] != tile_h or mask.shape[1] != tile_w:
            mask = F.interpolate(
                mask.unsqueeze(0).unsqueeze(0),
                size=(tile_h, tile_w),
                mode='bilinear',
                align_corners=False
            ).squeeze(0).squeeze(0)
        
        # Expand mask for channels
        mask = mask.unsqueeze(0).unsqueeze(-1)  # (1, H, W, 1)
        
        # Resize tile if needed to match target region
        target_h = min(tile_h, H - y)
        target_w = min(tile_w, W - x)
        
        if tile.shape[1] != target_h or tile.shape[2] != target_w:
            tile_permuted = tile.permute(0, 3, 1, 2)
            tile_resized = F.interpolate(
                tile_permuted,
                size=(target_h, target_w),
                mode='bilinear',
                align_corners=False
            )
            tile = tile_resized.permute(0, 2, 3, 1)
        
        # Resize mask to match
        if mask.shape[1] != target_h or mask.shape[2] != target_w:
            mask = F.interpolate(
                mask.permute(0, 3, 1, 2),
                size=(target_h, target_w),
                mode='bilinear',
                align_corners=False
            ).permute(0, 2, 3, 1)
        
        # Blend
        base_region = base[:, y:y+target_h, x:x+target_w, :]
        blended = base_region * (1 - mask) + tile * mask
        
        # Copy back
        result = base.clone()
        result[:, y:y+target_h, x:x+target_w, :] = blended
        
        return result
    
    def _create_feather_mask(self, height, width, padding):
        """Create a feather mask for blending tiles."""
        
        mask = torch.ones((height, width))
        
        if padding <= 0:
            return mask
        
        # Create gradient for feathering
        for i in range(padding):
            fade = i / padding
            
            # Top
            if i < height:
                mask[i, :] *= fade
            
            # Bottom
            if height - i - 1 >= 0:
                mask[height - i - 1, :] *= fade
            
            # Left
            if i < width:
                mask[:, i] *= fade
            
            # Right
            if width - i - 1 >= 0:
                mask[:, width - i - 1] *= fade
        
        return mask
    
    def _fix_seams(self, image, model, vae, positive, negative,
                   tile_w, tile_h, padding, seed, steps, cfg,
                   sampler_name, scheduler, denoise, mode,
                   seam_width, mask_blur, tile_vae):
        """Fix seams between tiles using various methods."""
        
        if mode == "None":
            return image
        
        
        B, H, W, C = image.shape
        
        if mode == "Band Pass":
            # Process vertical and horizontal seams
            seams = self._find_seams(W, H, tile_w, tile_h, padding, seam_width)
            
            for idx, (seam_x, seam_y, seam_w, seam_h) in enumerate(seams):
                # Extract seam region
                seam_img = image[:, seam_y:seam_y+seam_h, seam_x:seam_x+seam_w, :]
                
                # Process seam
                processed_seam = self._process_single_tile(
                    seam_img, model, vae, positive, negative,
                    seed + 9999, steps, cfg, sampler_name, scheduler,
                    denoise, tile_vae
                )
                
                # Blend back with mask blur
                mask = self._create_seam_mask(seam_h, seam_w, mask_blur)
                mask = mask.to(image.device).unsqueeze(0).unsqueeze(-1)
                
                if mask.shape[1] != seam_h or mask.shape[2] != seam_w:
                    mask = F.interpolate(
                        mask.permute(0, 3, 1, 2),
                        size=(seam_h, seam_w),
                        mode='bilinear',
                        align_corners=False
                    ).permute(0, 2, 3, 1)
                
                base_region = image[:, seam_y:seam_y+seam_h, seam_x:seam_x+seam_w, :]
                blended = base_region * (1 - mask) + processed_seam * mask
                image[:, seam_y:seam_y+seam_h, seam_x:seam_x+seam_w, :] = blended
        
        elif mode in ["Half Tile", "Half Tile + Intersections"]:
            # Process with half-tile offsets
            offset_x = tile_w // 2
            offset_y = tile_h // 2
            
            tiles = self._calculate_tiles(W, H, tile_w, tile_h, padding)
            offset_tiles = []
            
            for x, y, tw, th in tiles:
                new_x = x + offset_x
                new_y = y + offset_y
                
                if new_x + tw <= W and new_y + th <= H:
                    offset_tiles.append((new_x, new_y, tw, th))
            
            
            pbar = ProgressBar(len(offset_tiles))
            
            for idx, (x, y, tw, th) in enumerate(offset_tiles):
                pbar.update_absolute(idx + 1, len(offset_tiles))
                
                tile_img = image[:, y:y+th, x:x+tw, :]
                
                processed_tile = self._process_single_tile(
                    tile_img, model, vae, positive, negative,
                    seed + 10000 + idx, steps, cfg, sampler_name,
                    scheduler, denoise, tile_vae
                )
                
                image = self._blend_tile(image, processed_tile, x, y, tw, th, padding)
        
        return image
    
    def _find_seams(self, width, height, tile_w, tile_h, padding, seam_width):
        """Find seam positions between tiles."""
        seams = []
        
        # Calculate tile grid
        cols = math.ceil((width - padding) / (tile_w - padding))
        rows = math.ceil((height - padding) / (tile_h - padding))
        
        # Vertical seams
        for col in range(1, cols):
            x = col * (tile_w - padding) - seam_width // 2
            if x >= 0 and x + seam_width <= width:
                seams.append((x, 0, seam_width, height))
        
        # Horizontal seams
        for row in range(1, rows):
            y = row * (tile_h - padding) - seam_width // 2
            if y >= 0 and y + seam_width <= height:
                seams.append((0, y, width, seam_width))
        
        return seams
    
    def _create_seam_mask(self, height, width, blur):
        """Create a mask for seam blending."""
        mask = torch.ones((height, width))
        
        if blur > 0:
            # Simple feathering on edges
            for i in range(min(blur, height // 2, width // 2)):
                fade = i / blur
                mask[i, :] *= fade
                mask[height - i - 1, :] *= fade
                mask[:, i] *= fade
                mask[:, width - i - 1] *= fade
        
        return mask
    
    def _apply_sharpen(self, image, amount):
        """Apply unsharp mask sharpening."""
        if amount <= 0:
            return image
        
        
        # Convert to (B, C, H, W)
        img_permuted = image.permute(0, 3, 1, 2)
        
        # Create Gaussian blur kernel
        kernel_size = 5
        sigma = 1.0
        
        # Simple box blur approximation for speed
        kernel = torch.ones(1, 1, kernel_size, kernel_size, device=image.device) / (kernel_size * kernel_size)
        
        # Apply blur to each channel
        blurred_channels = []
        for c in range(img_permuted.shape[1]):
            channel = img_permuted[:, c:c+1, :, :]
            blurred = F.conv2d(channel, kernel, padding=kernel_size//2)
            blurred_channels.append(blurred)
        
        blurred = torch.cat(blurred_channels, dim=1)
        
        # Unsharp mask: original + amount * (original - blurred)
        sharpened = img_permuted + amount * (img_permuted - blurred)
        sharpened = torch.clamp(sharpened, 0, 1)
        
        return sharpened.permute(0, 2, 3, 1)
    
    def _apply_blur(self, image, amount):
        """Apply Gaussian blur."""
        if amount <= 0:
            return image
        
        
        # Convert to (B, C, H, W)
        img_permuted = image.permute(0, 3, 1, 2)
        
        # Calculate kernel size from amount
        kernel_size = int(amount * 2) * 2 + 1  # Ensure odd number
        kernel_size = max(3, min(kernel_size, 31))  # Clamp to reasonable range
        
        # Simple box blur
        kernel = torch.ones(1, 1, kernel_size, kernel_size, device=image.device) / (kernel_size * kernel_size)
        
        # Apply blur to each channel
        blurred_channels = []
        for c in range(img_permuted.shape[1]):
            channel = img_permuted[:, c:c+1, :, :]
            blurred = F.conv2d(channel, kernel, padding=kernel_size//2)
            blurred_channels.append(blurred)
        
        blurred = torch.cat(blurred_channels, dim=1)
        
        return blurred.permute(0, 2, 3, 1)
    
    def _apply_color_adjustments(self, image, contrast, brightness, saturation):
        """Apply contrast, brightness, and saturation adjustments."""
        if contrast == 1.0 and brightness == 0.0 and saturation == 1.0:
            return image
        
        
        result = image.clone()
        
        # Brightness
        if brightness != 0.0:
            result = result + brightness
        
        # Contrast
        if contrast != 1.0:
            mean = result.mean()
            result = (result - mean) * contrast + mean
        
        # Saturation
        if saturation != 1.0:
            # Convert to grayscale
            grayscale = 0.299 * result[:, :, :, 0:1] + 0.587 * result[:, :, :, 1:2] + 0.114 * result[:, :, :, 2:3]
            grayscale = grayscale.repeat(1, 1, 1, 3)
            
            # Blend between grayscale and original
            result = grayscale * (1 - saturation) + result * saturation
        
        # Clamp to valid range
        result = torch.clamp(result, 0, 1)
        
        return result
    
    def _load_upscaler_model(self, model_name):
        """Load an upscaler model from ComfyUI's upscale_models folder."""
        from comfy_extras.nodes_upscale_model import UpscaleModelLoader
        
        loader = UpscaleModelLoader()
        result = loader.load_model(model_name)
        
        # Result is a tuple (upscale_model,)
        return result[0]
    
    def _use_upscaler_model(self, image, upscaler, scale):
        """Use an AI upscaler model (ESRGAN, RealESRGAN, etc.)."""
        if upscaler is None:
            return image
        
        
        try:
            from comfy_extras.nodes_upscale_model import ImageUpscaleWithModel
            
            upscale_node = ImageUpscaleWithModel()
            result = upscale_node.upscale(upscaler, image)
            
            # Result is a tuple (upscaled_image,)
            upscaled = result[0]
            
            # Get the actual scale from the model
            actual_scale = upscaled.shape[1] / image.shape[1]  # height ratio
            
            # If we need a different scale, resize accordingly
            if abs(actual_scale - scale) > 0.01:
                # Calculate additional scaling needed
                additional_scale = scale / actual_scale
                upscaled = self._simple_upscale(upscaled, additional_scale, "Bicubic")
            
            return upscaled
            
        except Exception as e:
            return self._simple_upscale(image, scale, "Bicubic")
    
    def _apply_mask_selective(self, original, processed, mask):
        """Apply processing selectively using a mask."""
        if mask is None:
            return processed
        
        
        # Ensure mask dimensions match
        B, H, W, C = processed.shape
        
        if mask.ndim == 2:
            mask = mask.unsqueeze(0).unsqueeze(-1)
        elif mask.ndim == 3:
            mask = mask.unsqueeze(-1)
        
        # Resize mask if needed
        if mask.shape[1] != H or mask.shape[2] != W:
            mask_permuted = mask.permute(0, 3, 1, 2)
            mask_resized = F.interpolate(
                mask_permuted,
                size=(H, W),
                mode='bilinear',
                align_corners=False
            )
            mask = mask_resized.permute(0, 2, 3, 1)
        
        # Blend
        result = original * (1 - mask) + processed * mask
        
        return result


NODE_CLASS_MAPPINGS = {
    "ModusFlowUpscaler": ModusFlowUpscaler
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModusFlowUpscaler": "ModusFlow Upscaler"
}
