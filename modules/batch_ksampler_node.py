import torch
from nodes import KSampler

class ModusFlowBatchKSampler:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "model": ("MODEL",),
                "latent_image": ("LATENT",),
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "steps": ("INT", {"default": 20, "min": 1, "max": 100}),
                "cfg": ("FLOAT", {"default": 7.0, "min": 0.0, "max": 20.0}),
                "sampler_name": (["euler", "euler_a", "dpm_2", "dpm_2_a", "dpm_fast", "dpm_adaptive", "dpmpp_2s_a", "dpmpp_2m", "dpmpp_sde", "dpmpp_2m_sde", "dpmpp_2m_sde_gpu", "dpmpp_2m_sde_karras"], {"default": "euler"}),
                "scheduler": (["normal", "karras", "exponential", "polyexponential"], {"default": "normal"}),
                "positive_conditioning": ("CONDITIONING",),
                "negative_conditioning": ("CONDITIONING",),
            }
        }

    RETURN_TYPES = ("LATENT",)
    RETURN_NAMES = ("latent",)
    FUNCTION = "sample"
    CATEGORY = "ModusFlow/Batching"

    def sample(self, model, latent_image, seed, steps, cfg, sampler_name, scheduler, positive_conditioning, negative_conditioning):
        ksampler = KSampler()
        # The latent_image is a dictionary from the iterator, which is what KSampler expects.
        result = ksampler.sample(model, seed, steps, cfg, sampler_name, scheduler, positive_conditioning, negative_conditioning, latent_image)
        return (result[0],)

NODE_CLASS_MAPPINGS = {
    "ModusFlowBatchKSampler": ModusFlowBatchKSampler
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "ModusFlowBatchKSampler": "ModusFlow Batch KSampler"
}
