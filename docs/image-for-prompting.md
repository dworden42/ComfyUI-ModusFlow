# Image For Prompting

Metadata extraction and AI-powered image descriptions for reference images.

## Overview

The Image For Prompting node extracts ComfyUI metadata from images and optionally generates AI descriptions using Ollama. Perfect for analyzing generated images or creating descriptions of reference images.

## Features

- **Metadata Extraction**: Automatically reads ComfyUI workflow metadata from PNG files
- **AI Descriptions**: Generate detailed image descriptions using Ollama
- **Smart File Selection**: Browse input directory with folder support
- **Multimodal AI**: Supports vision-capable models for accurate descriptions
- **Graceful Degradation**: Works even when Ollama is unavailable - uses metadata or returns empty description

## Inputs

### Required
- **image_file** (COMBO): Select image from ComfyUI input directory
- **describe_with_ollama** (BOOLEAN): Enable AI-powered description generation

### Optional (when describe_with_ollama is enabled)
- **model** (COMBO): Ollama model to use for descriptions

## Outputs

- **IMAGE**: Loaded image
- **STRING**: Extracted/generated description

## Usage

### Basic Metadata Extraction
1. Place images in ComfyUI's `input/` directory
2. Select image from dropdown
3. Metadata automatically extracted from PNG info

### AI Description Generation
1. Enable "describe_with_ollama"
2. Select a multimodal model (e.g., "llava")
3. Node generates detailed description of the image

## File Organization

- Supports nested folders in input directory
- Folders shown with `[FOLDER]` prefix
- Refresh button updates file list

## Tips

- **Reference Images**: Use for analyzing style/composition of reference images
- **Workflow Analysis**: Extract generation parameters from ComfyUI-generated images
- **Batch Processing**: Combine with Image Iterator for bulk description generation

## Troubleshooting

- **File not found**: Click refresh button to update file list
- **No metadata**: Only PNG files from ComfyUI contain metadata
- **Ollama unavailable**: Node continues without AI descriptions - workflow runs normally with metadata-only mode
