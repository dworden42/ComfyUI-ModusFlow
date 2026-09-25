"""
ModusFlow Model Loader Node

A comprehensive model loader that combines:
- Diffusion model (UNet) loading with weight dtype control
- Up to 4 CLIP loaders with individual controls and separate outputs
- CLIP skip support for layer control
- Checkpoint loader with optional CLIP extraction
- VAE loader
- T5 tokenizer settings (min_length, min_padding)

Outputs individual CLIPs (clip1-4) for separate text processing 
plus a merged CLIP for convenience.
"""

import folder_paths
from nodes import CheckpointLoaderSimple, CLIPLoader, DualCLIPLoader, VAELoader, UNETLoader


class ModusFlowModelLoader:
    """
    All-in-one model loader for flexible workflow configurations.
    Supports multiple CLIPs, checkpoint fallback, and advanced tokenizer settings.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        # Get available files from ComfyUI's folder_paths
        checkpoints = folder_paths.get_filename_list("checkpoints")
        unets = folder_paths.get_filename_list("unet")
        clips = folder_paths.get_filename_list("text_encoders")
        vaes = folder_paths.get_filename_list("vae")

        # Add "None" or "disabled" options
        checkpoint_list = ["None"] + checkpoints
        unet_list = ["None"] + unets
        clip_list = ["disabled"] + clips
        vae_list = ["None"] + vaes

        # Model types for CLIP configuration (must match comfy.sd.CLIPType enum names, lowercase)
        model_types = ["stable_diffusion", "sd3", "stable_audio", "mochi", "ltxv", "pixart",
                       "cosmos", "lumina2", "wan", "hidream", "chroma", "ace",
                       "omnigen2", "hunyuan_image", "flux2", "stable_cascade"]

        # Dual CLIP loader types (DualCLIPLoader accepts a different set)
        dual_model_types = ["sdxl", "sd3", "flux", "ace", "hunyuan_video", "hidream",
                            "hunyuan_image", "hunyuan_video_15", "kandinsky5",
                            "kandinsky5_image", "ltxv", "newbie"]

        # Device options
        device_options = ["auto", "cpu", "cuda", "cuda:0", "cuda:1"]

        # Weight dtypes for diffusion model
        weight_dtypes = ["default", "fp8_e4m3fn", "fp8_e5m2", "fp16", "fp32", "bf16"]

        return {
            "required": {
                # Diffusion Model (UNet) Settings
                "unet_name": (unet_list, {"default": "None"}),
                "weight_dtype": (weight_dtypes, {"default": "default"}),

                # Dual CLIP loader (for ACE Step 1.5, SDXL, Flux, etc.)
                # When enabled, clip1+clip2 are loaded together via DualCLIPLoader
                "use_dual_clip_loader": ("BOOLEAN", {"default": False}),
                "dual_clip_type": (dual_model_types, {"default": "sdxl"}),

                # CLIP Loaders (up to 4)
                "clip1_name": (clip_list, {"default": "disabled"}),
                "clip1_type": (model_types, {"default": "stable_diffusion"}),
                "clip1_device": (device_options, {"default": "auto"}),

                "clip2_name": (clip_list, {"default": "disabled"}),
                "clip2_type": (model_types, {"default": "stable_diffusion"}),
                "clip2_device": (device_options, {"default": "auto"}),

                "clip3_name": (clip_list, {"default": "disabled"}),
                "clip3_type": (model_types, {"default": "stable_diffusion"}),
                "clip3_device": (device_options, {"default": "auto"}),

                "clip4_name": (clip_list, {"default": "disabled"}),
                "clip4_type": (model_types, {"default": "stable_diffusion"}),
                "clip4_device": (device_options, {"default": "auto"}),
                
                # CLIP Skip (layer skipping for better compatibility)
                # 0 = disabled (use all layers), -1 to -24 = skip layers from the end
                "clip_skip": ("INT", {"default": 0, "min": -24, "max": 0, "step": 1}),
                
                # Checkpoint Loader (with optional CLIP)
                "checkpoint_name": (checkpoint_list, {"default": "None"}),
                "use_checkpoint_clip": ("BOOLEAN", {"default": False}),
                
                # VAE Loader
                "vae_name": (vae_list, {"default": "None"}),
                
                # T5 Tokenizer Settings
                "t5_min_length": ("INT", {"default": 256, "min": 0, "max": 8192, "step": 1}),
                "t5_min_padding": ("INT", {"default": 0, "min": 0, "max": 8192, "step": 1}),
            }
        }
    
    RETURN_TYPES = ("MODEL", "CLIP", "CLIP", "CLIP", "CLIP", "CLIP", "VAE", "PIPE")
    RETURN_NAMES = ("model", "clip_merged", "clip1", "clip2", "clip3", "clip4", "vae", "pipe")
    FUNCTION = "load_models"
    CATEGORY = "ModusFlow/Loaders"
    OUTPUT_NODE = False

    def load_models(self, unet_name, weight_dtype,
                   use_dual_clip_loader, dual_clip_type,
                   clip1_name, clip1_type, clip1_device,
                   clip2_name, clip2_type, clip2_device,
                   clip3_name, clip3_type, clip3_device,
                   clip4_name, clip4_type, clip4_device,
                   clip_skip,
                   checkpoint_name, use_checkpoint_clip,
                   vae_name, t5_min_length, t5_min_padding):
        model = None
        clip = None
        vae = None
        
        checkpoint_clip = None
        checkpoint_vae = None
        
        individual_clip1 = None
        individual_clip2 = None
        individual_clip3 = None
        individual_clip4 = None
        
        if checkpoint_name != "None":
            try:
                checkpoint_loader = CheckpointLoaderSimple()
                checkpoint_model, checkpoint_clip, checkpoint_vae = checkpoint_loader.load_checkpoint(checkpoint_name)
                
                model = checkpoint_model
                
                if use_checkpoint_clip:
                    if checkpoint_clip is not None:
                        clip = checkpoint_clip
                        individual_clip1 = checkpoint_clip
                    else:
                        pass
                else:
                    if checkpoint_clip is not None:
                        pass
                    else:
                        pass
                
                if vae_name == "None":
                    vae = checkpoint_vae
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
        
        if unet_name != "None" and model is None:
            try:
                unet_loader = UNETLoader()
                model_result = unet_loader.load_unet(unet_name, weight_dtype)
                model = model_result[0]
            except Exception as e:
                pass
        
        if clip is None and use_dual_clip_loader:
            if clip1_name != "disabled" and clip2_name != "disabled":
                try:
                    dual_loader = DualCLIPLoader()
                    clip_result = dual_loader.load_clip(clip1_name, clip2_name, dual_clip_type)
                    clip = clip_result[0]
                    individual_clip1 = clip
                    individual_clip2 = clip
                    print(f"[ModusFlow ModelLoader] Loaded dual CLIP ({clip1_name} + {clip2_name}, type={dual_clip_type})")
                except Exception as e:
                    import traceback
                    print(f"[ModusFlow ModelLoader] Error loading dual CLIP: {e}")
                    traceback.print_exc()
            elif clip1_name != "disabled":
                try:
                    dual_loader = DualCLIPLoader()
                    clip_result = dual_loader.load_clip(clip1_name, clip1_name, dual_clip_type)
                    clip = clip_result[0]
                    individual_clip1 = clip
                    print(f"[ModusFlow ModelLoader] Loaded dual CLIP single file ({clip1_name}, type={dual_clip_type})")
                except Exception as e:
                    import traceback
                    print(f"[ModusFlow ModelLoader] Error loading dual CLIP (single file): {e}")
                    traceback.print_exc()

        if clip is None:
            clip_loader = CLIPLoader()
            loaded_clips = []

            clip_configs = [
                (clip1_name, clip1_type, clip1_device, "CLIP 1", 0),
                (clip2_name, clip2_type, clip2_device, "CLIP 2", 1),
                (clip3_name, clip3_type, clip3_device, "CLIP 3", 2),
                (clip4_name, clip4_type, clip4_device, "CLIP 4", 3),
            ]
            
            for clip_name, clip_type, clip_device, label, index in clip_configs:
                if clip_name != "disabled":
                    try:
                        clip_result = clip_loader.load_clip(clip_name, type=clip_type)
                        loaded_clip = clip_result[0]
                        
                        if hasattr(loaded_clip, 'tokenizer') and hasattr(loaded_clip.tokenizer, 'set_parameters'):
                            try:
                                loaded_clip.tokenizer.set_parameters(
                                    min_length=t5_min_length,
                                    min_padding=t5_min_padding
                                )
                            except Exception as e:
                                pass
                        
                        if index == 0:
                            individual_clip1 = loaded_clip
                        elif index == 1:
                            individual_clip2 = loaded_clip
                        elif index == 2:
                            individual_clip3 = loaded_clip
                        elif index == 3:
                            individual_clip4 = loaded_clip
                        
                        loaded_clips.append(loaded_clip)
                    except Exception as e:
                        import traceback
                        print(f"[ModusFlow ModelLoader] Error loading {label} ({clip_name}, type={clip_type}): {e}")
                        traceback.print_exc()

            if len(loaded_clips) == 1:
                clip = loaded_clips[0]
            elif len(loaded_clips) > 1:
                clip = loaded_clips[0]
                for additional_clip in loaded_clips[1:]:
                    try:
                        if hasattr(clip, 'clone'):
                            clip = clip.clone()
                        if hasattr(clip, 'cond_stage_model') and hasattr(additional_clip, 'cond_stage_model'):
                            pass
                    except Exception as e:
                        pass
        
        if clip_skip != 0:
            if clip is not None:
                try:
                    if hasattr(clip, 'clip_layer'):
                        clip = clip.clone()
                        clip.clip_layer(clip_skip)
                    else:
                        pass
                except Exception as e:
                    pass
            
            for idx, individual_clip in enumerate([individual_clip1, individual_clip2, individual_clip3, individual_clip4], start=1):
                if individual_clip is not None:
                    try:
                        if hasattr(individual_clip, 'clip_layer'):
                            if idx == 1:
                                individual_clip1 = individual_clip.clone()
                                individual_clip1.clip_layer(clip_skip)
                            elif idx == 2:
                                individual_clip2 = individual_clip.clone()
                                individual_clip2.clip_layer(clip_skip)
                            elif idx == 3:
                                individual_clip3 = individual_clip.clone()
                                individual_clip3.clip_layer(clip_skip)
                            elif idx == 4:
                                individual_clip4 = individual_clip.clone()
                                individual_clip4.clip_layer(clip_skip)
                        else:
                            pass
                    except Exception as e:
                        pass
            
            pass
        
        if vae_name != "None" and vae is None:
            try:
                vae_loader = VAELoader()
                vae_result = vae_loader.load_vae(vae_name)
                vae = vae_result[0]
            except Exception as e:
                pass
        
        if model is None:
            raise ValueError("No model loaded! Please specify either a checkpoint or UNet.")
        
        if clip is None:
            raise ValueError("No CLIP loaded! Please specify checkpoint CLIP or at least one CLIP model.")
        
        if vae is None:
            pass
        
        output_pipe = (model, clip, vae, None, None)
        
        return (model, clip, individual_clip1, individual_clip2, individual_clip3, individual_clip4, vae, output_pipe)


NODE_CLASS_MAPPINGS = {
    "ModusFlowModelLoader": ModusFlowModelLoader
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModusFlowModelLoader": "ModusFlow Model Loader"
}