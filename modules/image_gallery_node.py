import os
import folder_paths

class ModusFlowImageGallery:
    """
    A node that displays an image gallery from the output directory.
    Features breadcrumb navigation, lazy loading, and full-screen image preview.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {},
            "optional": {
                "refresh_trigger": ("INT", {"default": 0, "min": 0, "max": 999999}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "display_gallery"
    OUTPUT_NODE = True
    CATEGORY = "ModusFlow/Utilities"

    def display_gallery(self, refresh_trigger=0, unique_id=None):
        """
        Displays an image gallery interface.
        
        Args:
            refresh_trigger: Optional trigger to refresh the gallery
            unique_id: Hidden parameter for node identification
            
        Returns:
            Dictionary with UI display data
        """
        return {"ui": {"refresh_trigger": [refresh_trigger]}}
