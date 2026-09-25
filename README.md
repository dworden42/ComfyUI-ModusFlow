# ModusFlow

> [!NOTE]
> **AI-Assisted Development**: These custom nodes, UI extensions, scripts, and documentation were created with AI assistance. In the spirit of complete transparency: if you prefer not to use AI-assisted code, please feel free to pass on this custom node suite.
>
> This project is AI Assisted, by AI for AI

A comprehensive collection of professional-grade custom nodes for ComfyUI, featuring AI-powered prompt refinement, advanced model loading, multi-section detailing, tiled upscaling, and sophisticated batch processing workflows.

---

## 🌟 Overview

ComfyUI-ModusFlow provides 20 custom nodes organized into six categories:

**🤖 AI & Prompt Enhancement**
- Ollama Prompt Refiner - Full-pipeline prompt enhancement with Ollama LLMs, conditioning output, and pipe support
- Ollama Text Refiner - Lightweight text refinement via Ollama
- Image For Prompting - Metadata extraction and AI-powered image descriptions

**📦 Model & Resource Loading**
- Model Loader - UNet/checkpoint, multi-CLIP (DualCLIP + up to 4 individual), and VAE loader
- LoRA Loader - Stack-based LoRA management with validation and Civitai integration
- Multi-CLIP Text Encode - Per-CLIP text inputs with Flux guidance and single conditioning output

**🎨 Sampling & Generation**
- KSampler - Enhanced sampler with pipe support, audio latent handling, and CUDNN control
- Batch KSampler - Simplified KSampler for batch workflows
- Latent Preset - Blank latent generator with common resolution presets

**🖼️ Image Enhancement**
- Detailer Slot - Config bundle for one YOLO detection + inpaint pass
- All-in-One Detailer - Runs any number of Detailer Slots sequentially with pipe support
- Upscaler - Tiled upscaling with seam fixing and post-processing
- Restormer - Deep learning image restoration (motion deblur, defocus, denoising)

**🔊 Audio**
- Save Audio - Multi-format audio export (flac, wav, mp3, ogg) with filename variables
- ACE Step Audio 1.5 - TextEncodeAceStepAudio1.5 with song save/load for tags and lyrics

**⚙️ Conditioning**
- Conditioning Concat - Encode text and concatenate onto existing conditioning

**️ Utilities**
- Show Text - Simple text display for prompts and debugging
- Text Editor - Interactive text editor with save/load functionality
- Image Gallery - Browse output directory with metadata viewing
- Save Image - Save images in PNG/JPEG/WebP with filename variables and metadata embedding

---

## 💾 Installation

1. Navigate to ComfyUI custom_nodes directory:
   ```bash
   cd ComfyUI/custom_nodes/
   ```

2. Clone this repository:
   ```bash
   git clone https://github.com/ModusFlow/ComfyUI-ModusFlow.git
   ```

3. Install dependencies:
   ```bash
   cd ComfyUI-ModusFlow
   pip install -r requirements.txt
   ```
   *Installs core dependencies including `ultralytics` (for YOLO detection in All-in-One Detailer) and `av` (for multi-format audio encoding in Save Audio).*

4. Restart ComfyUI

---

## ⚙️ Configuration

### Option A: ComfyUI Settings UI (Recommended)
You can configure ModusFlow directly within ComfyUI without editing any files:
1. Click the **⚙️ Settings** icon in ComfyUI (top bar or sidebar).
2. Locate the **ModusFlow** category.
3. Configure your **Ollama URL**, **Ollama Timeout**, **Civitai API Key**, and **Prompts Directory Override**. Changes apply immediately in real time.

### Option B: `config.json` File
Alternatively, create a `config.json` file in the node directory:

```bash
cp config.json.example config.json
```

Edit `config.json` to configure:
- `ollama_url` - Ollama API endpoint (default: `http://127.0.0.1:11434`)
- `ollama_timeout` - Timeout in seconds for LLM requests (default: `120`)
- `civitai_api_key` - For LoRA preview images and metadata
- `prompts_save_directory` - Custom path for saved prompts (optional)
- `base_model_definitions` - Custom model architecture definitions (Flux, SDXL, Pony, etc.)

---

## 📖 Documentation

- 🧭 **[Workflow & Node Usage Guide](docs/workflow-guide.md)** — Step-by-step guide to connecting nodes, pipe-driven workflows, detailing passes, and upscaling.

### Node Documentation

**AI & Prompt Enhancement**
- [Ollama Prompt Refiner](docs/ollama-prompt-refiner.md)
- [Ollama Text Refiner](docs/ollama-text-refiner.md)
- [Image For Prompting](docs/image-for-prompting.md)

**Model & Resource Loading**
- [Model Loader](docs/model-loader.md)
- [LoRA Loader](docs/lora-loader.md)
- [Multi-CLIP Text Encode](docs/multi-clip-text-encode.md)

**Sampling & Generation**
- [KSampler](docs/ksampler.md)
- [Batch KSampler](docs/batch-ksampler.md)
- [Latent Preset](docs/latent-preset.md)

**Image Enhancement**
- [All-in-One Detailer](docs/allinone-detailer.md)
- [Upscaler](docs/upscaler.md)
- [Restormer](docs/restormer.md)

**Audio**
- [Save Audio](docs/save-audio.md)
- [ACE Step Audio 1.5](docs/ace-step-audio.md)

**Conditioning**
- [Conditioning Concat](docs/conditioning-concat.md)

**Utilities**
- [Show Text](docs/show-text.md)
- [Text Editor](docs/text-editor.md)
- [Image Gallery](docs/image-gallery.md)
- [Save Image](docs/save-image.md)

---

## 🎯 Quick Start

### Basic Generation Workflow
```
Model Loader → Multi-CLIP Text Encode → KSampler → VAE Decode
```

### AI Prompt Enhancement
```
Text → Ollama Prompt Refiner → CLIP Text Encode → Generation
```

### Detail Enhancement
```
KSampler → image → All-in-One Detailer → Upscaler → Save Image
```

---

## 🔧 Requirements

- ComfyUI (latest version recommended)
- Python 3.8 or higher
- For Ollama nodes: Ollama installed with at least one model (`ollama pull llava`)
- For All-in-One Detailer: `pip install ultralytics` (YOLO detection models)
- For Restormer: `pip install einops`
- For Upscaler: Upscale models in `ComfyUI/models/upscale_models/`

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🙏 Credits

- ComfyUI team for the excellent framework
- Ollama for local LLM capabilities
- Ultralytics for YOLO models
- Segment Anything team for SAM
- Community for feedback and testing

---

## 📞 Support

- **Issues**: [Report bugs or request features](https://github.com/ModusFlow/ComfyUI-ModusFlow/issues)
- **Discussions**: [Ask questions and share workflows](https://github.com/ModusFlow/ComfyUI-ModusFlow/discussions)

---

**Maintainer:** [@dworden42](https://github.com/dworden42)
