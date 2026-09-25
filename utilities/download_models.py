import argparse
import os
import sys
import urllib.request

# Models to download (Source: Bingsu/adetailer on Hugging Face)
# Format: (Filename, Category)
MODELS = [
    # Face (BBox)
    ("face_yolov8n.pt", "bbox"),
    ("face_yolov8n_v2.pt", "bbox"),
    ("face_yolov8s.pt", "bbox"),
    ("face_yolov8m.pt", "bbox"),
    ("face_yolov9c.pt", "bbox"),

    # Hand (BBox)
    ("hand_yolov8n.pt", "bbox"),
    ("hand_yolov8s.pt", "bbox"),
    ("hand_yolov9c.pt", "bbox"),

    # Person (Segmentation)
    ("person_yolov8n-seg.pt", "segm"),
    ("person_yolov8s-seg.pt", "segm"),
    ("person_yolov8m-seg.pt", "segm"),

    # Clothing (Segmentation)
    ("deepfashion2_yolov8s-seg.pt", "segm"),
]

BASE_URL = "https://huggingface.co/Bingsu/adetailer/resolve/main/"


def get_default_ultralytics_dir() -> str:
    """Resolve default ultralytics directory to native ComfyUI models path."""
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # Check environment variable override
    if "COMFYUI_MODELS_DIR" in os.environ:
        return os.path.join(os.environ["COMFYUI_MODELS_DIR"], "ultralytics")

    # Locate ComfyUI root and import folder_paths if possible
    for candidate in [
        os.path.abspath(os.path.join(script_dir, "..", "..", "..")),
        os.path.abspath(os.path.join(script_dir, "..", "..")),
        os.getcwd(),
        os.path.abspath(os.path.join(os.getcwd(), "..")),
    ]:
        if os.path.isfile(os.path.join(candidate, "folder_paths.py")) or os.path.isdir(os.path.join(candidate, "comfy")):
            if candidate not in sys.path:
                sys.path.insert(0, candidate)
            break

    try:
        import folder_paths
        bbox_paths = folder_paths.get_folder_paths("ultralytics_bbox")
        if bbox_paths:
            return os.path.dirname(bbox_paths[0])
        return os.path.join(folder_paths.models_dir, "ultralytics")
    except Exception:
        pass

    # Fallback to standard relative ComfyUI structure: ComfyUI/models/ultralytics
    for rel_root in [
        os.path.abspath(os.path.join(script_dir, "..", "..", "..")),
        os.path.abspath(os.path.join(script_dir, "..", "..")),
    ]:
        comfy_models = os.path.join(rel_root, "models", "ultralytics")
        if os.path.exists(os.path.join(rel_root, "models")):
            return comfy_models

    return os.path.join(script_dir, "models", "ultralytics")


def download_file(filename: str, category_dir: str):
    url = BASE_URL + filename
    target_path = os.path.join(category_dir, filename)

    if os.path.exists(target_path):
        print(f"Skipping {filename} (Already exists)")
        return

    print(f"Downloading {filename}...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req) as response, open(target_path, "wb") as f:
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                f.write(chunk)
        print(f"Successfully downloaded {filename}")
    except Exception as e:
        print(f"Failed to download {filename}: {str(e)}")


def main():
    parser = argparse.ArgumentParser(description="Download YOLO detection models for ModusFlow / ADetailer")
    parser.add_argument(
        "--dir", "-d",
        type=str,
        default=None,
        help="Target base directory for ultralytics models (defaults to ComfyUI models/ultralytics)",
    )
    args = parser.parse_args()

    base_dir = os.path.abspath(args.dir) if args.dir else get_default_ultralytics_dir()
    bbox_dir = os.path.join(base_dir, "bbox")
    segm_dir = os.path.join(base_dir, "segm")

    # Ensure directories exist
    os.makedirs(bbox_dir, exist_ok=True)
    os.makedirs(segm_dir, exist_ok=True)

    print("Starting model download for ModusFlow Detailer...")
    print(f"Target Directory: {base_dir}")

    for model_name, category in MODELS:
        target_dir = bbox_dir if category == "bbox" else segm_dir
        download_file(model_name, target_dir)

    print("\nDownload complete!")
    print("If your models folder is outside standard ComfyUI paths, ensure extra_model_paths.yaml points 'ultralytics' to it.")


if __name__ == "__main__":
    main()
