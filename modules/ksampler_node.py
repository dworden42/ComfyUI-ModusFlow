"""
ModusFlow KSampler Node

A KSampler that mimics the default ComfyUI KSampler but adds:
- PIPE input/output support
- Additional outputs for model, clip, positive, and negative conditioning
- CLIP input
- LATENT output
"""

import comfy.samplers
from nodes import KSampler


class ModusFlowKSampler:
    """
    Enhanced KSampler with pipe support and passthrough outputs.
    Compatible with standard ComfyUI workflows while adding convenience features.
    """
    
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 10000}),
                "cfg": ("FLOAT", {"default": 8.0, "min": 0.0, "max": 100.0, "step": 0.1, "round": 0.01}),
                "sampler_name": (comfy.samplers.KSampler.SAMPLERS, ),
                "scheduler": (comfy.samplers.KSampler.SCHEDULERS, ),
                "denoise": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1.0, "step": 0.01}),
                "use_cudnn": ("BOOLEAN", {"default": True}),
            },
            "optional": {
                # Pipe input (alternative to individual inputs)
                "pipe": ("PIPE",),

                # Individual inputs (override pipe if provided)
                "model": ("MODEL",),
                "clip": ("CLIP",),
                "vae": ("VAE",),
                "positive": ("CONDITIONING",),
                "negative": ("CONDITIONING",),
                "latent_image": ("LATENT",),
                "latent_operation": ("LATENT_OPERATION",),
            }
        }
    
    RETURN_TYPES = ("LATENT", "IMAGE", "AUDIO", "INT", "MODEL", "CLIP", "VAE", "CONDITIONING", "CONDITIONING", "PIPE")
    RETURN_NAMES = ("latent", "image", "audio", "seed", "model", "clip", "vae", "positive", "negative", "pipe")
    FUNCTION = "sample"
    CATEGORY = "ModusFlow/Sampling"
    OUTPUT_NODE = False

    def sample(self, seed, steps, cfg, sampler_name, scheduler, denoise, use_cudnn,
               pipe=None, model=None, clip=None, vae=None, positive=None, negative=None, latent_image=None, latent_operation=None):
        """
        Sample using KSampler with pipe support and passthrough outputs.
        """
        
        # Extract from pipe or use individual inputs
        if pipe is not None:
            # Pipe format: (model, clip, vae, positive, negative)
            
            # Individual inputs take priority over pipe
            model = model if model is not None else (pipe[0] if len(pipe) > 0 else None)
            clip = clip if clip is not None else (pipe[1] if len(pipe) > 1 else None)
            vae = vae if vae is not None else (pipe[2] if len(pipe) > 2 else None)
            positive = positive if positive is not None else (pipe[3] if len(pipe) > 3 else None)
            negative = negative if negative is not None else (pipe[4] if len(pipe) > 4 else None)
        
        # Validate required inputs
        if model is None:
            raise ValueError("MODEL is required (provide via pipe or individual input)")
        if positive is None:
            raise ValueError("POSITIVE conditioning is required (provide via pipe or individual input)")
        if negative is None:
            raise ValueError("NEGATIVE conditioning is required (provide via pipe or individual input)")
        if latent_image is None:
            raise ValueError("LATENT_IMAGE is required")
        if vae is None:
            raise ValueError("VAE is required (provide via pipe or individual input)")
        
        
        # Apply latent operation to model's CFG denoising loop if provided
        if latent_operation is not None:
            model = model.clone()
            def pre_cfg_function(args):
                conds_out = args["conds_out"]
                if len(conds_out) == 2:
                    conds_out[0] = latent_operation(latent=(conds_out[0] - conds_out[1])) + conds_out[1]
                else:
                    conds_out[0] = latent_operation(latent=conds_out[0])
                return conds_out
            model.set_model_sampler_pre_cfg_function(pre_cfg_function)

        # Set CUDNN state based on user preference BEFORE any VAE operations
        import torch.backends.cudnn as cudnn
        original_cudnn_enabled = cudnn.enabled
        original_cudnn_benchmark = cudnn.benchmark
        
        if not use_cudnn:
            cudnn.enabled = False
            cudnn.benchmark = False
        
        try:
            # Perform sampling using ComfyUI's KSampler node
            ksampler = KSampler()
            latent_samples = ksampler.sample(
                model=model,
                seed=seed,
                steps=steps,
                cfg=cfg,
                sampler_name=sampler_name,
                scheduler=scheduler,
                positive=positive,
                negative=negative,
                latent_image=latent_image,
                denoise=denoise
            )
            
            # Decode latent — branch on audio vs image
            latent_out = latent_samples[0]
            if latent_out.get("type") == "audio":
                raw = vae.decode(latent_out["samples"]).movedim(-1, 1)
                vae_sample_rate = getattr(vae, "audio_sample_rate", 44100)
                sample_rate = latent_out.get("sample_rate", vae_sample_rate)
                image = None
                audio_output = {"waveform": raw, "sample_rate": sample_rate}
            else:
                image = vae.decode(latent_out["samples"])
                audio_output = None
        finally:
            # Restore CUDNN settings
            if not use_cudnn:
                cudnn.enabled = original_cudnn_enabled
                cudnn.benchmark = original_cudnn_benchmark
        
        # Create output pipe
        output_pipe = (model, clip, vae, positive, negative)
        
        
        return (
            latent_samples[0],  # latent
            image,              # image (None for audio)
            audio_output,       # audio (None for image)
            seed,               # seed (passthrough)
            model,              # model (passthrough)
            clip,               # clip (passthrough)
            vae,                # vae (passthrough)
            positive,           # positive (passthrough)
            negative,           # negative (passthrough)
            output_pipe         # pipe (passthrough)
        )


# Node class mappings
NODE_CLASS_MAPPINGS = {
    "ModusFlowKSampler": ModusFlowKSampler
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModusFlowKSampler": "ModusFlow KSampler"
}
