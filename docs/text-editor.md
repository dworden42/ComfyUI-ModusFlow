# Text Editor

Interactive text editor with positive/negative prompt management and save/load functionality.

## Overview

The Text Editor node provides a full-featured dual text editing interface (Positive and Negative prompts) with save/load capabilities, perfect for managing complex prompts in ComfyUI workflows. Prompts are stored as JSON files containing a category, positive text, and negative text.

## Features

- **Dual Editor**: Separate Positive and Negative text areas
- **Save/Load System**: Persistent storage as JSON files (`category`, `positive`, `negative`)
- **File Browser**: Browse and load saved prompts from a dropdown
- **Update in Place**: Overwrite an existing prompt with current text
- **Custom Directory**: Configure save location via `config.json`
- **Pass-through Outputs**: Both positive and negative text are available as outputs

## Inputs

### Required
- **positive** (STRING): Positive prompt text (large editor area)
- **negative** (STRING): Negative prompt text (smaller editor area, resizable)
- **saved_prompt** (dropdown): Select a previously saved `.json` prompt file

### Optional
- **positive_input** (STRING): Positive text from another node (overrides widget)
- **negative_input** (STRING): Negative text from another node (overrides widget)
- **embedding** (STRING): Embedding string to append to positive text (e.g., from LoRA Loader)

## Outputs

- **positive** (STRING): Current positive prompt text (with embedding appended if provided)
- **negative** (STRING): Current negative prompt text

> **Embedding Input**: When an embedding string is connected, it is automatically appended to the **positive** text with comma separation.

## UI Features

### Text Editors
- **Positive**: Large text area for comfortable editing
- **Negative**: Smaller default height but fully resizable
- Both support multi-line, word wrapping, undo/redo (Ctrl+Z / Ctrl+Y)

### Save Controls
- **💾 Save Prompt**: Prompts for a filename and optional category, then saves both texts as a `.json` file
- **✏️ Update Selected**: Overwrites the currently selected prompt with the current text (preserves existing category)
- **🔄 Refresh List**: Reloads the dropdown to show any newly added files

## Configuration

Set the save directory in `config.json`:

```json
{
  "prompts_save_directory": "C:/path/to/your/prompts"
}
```

**Default:** `ComfyUI-ModusFlow/saved_prompts/`

## JSON File Format

Each saved prompt is a `.json` file with the following structure:

```json
{
  "category": "Portraits",
  "positive": "beautiful woman, detailed face, soft lighting",
  "negative": "blurry, deformed, bad anatomy"
}
```

## File Management

### Saving Prompts
1. Edit text in the Positive and/or Negative editors
2. Click **💾 Save Prompt**
3. Enter a filename (without extension) and an optional category
4. File saved as `filename.json`

### Loading Prompts
1. Select a `.json` file from the dropdown
2. Both Positive and Negative fields are populated automatically

### Updating Prompts
1. Load a prompt from the dropdown
2. Edit the text
3. Click **✏️ Update Selected** to overwrite the file

### Organization
- All prompts saved as `.json` files
- Alphabetically sorted in the browser
- Click **🔄 Refresh List** to see newly saved files

## Usage Patterns

### Direct to Sampler
```
Model Loader → CLIP → Text Editor (edit prompt) → CLIP Text Encode → KSampler
```

### With Embeddings from LoRA
```
LoRA Loader → embedding_str → Text Editor (+ text)
                 ↓
             CLIP Text Encode → KSampler
```

### Prompt Library
```
Text Editor (empty) → Edit and save multiple prompts
                   → Load different prompts as needed
                   → Output conditioning to KSampler
```

### Prompt Refinement Workflow
```
Base Prompt → Ollama Refiner → Text Editor → CLIP Text Encode → Save refined version
                 ↓
               KSampler
```

### Text-Only Workflow
```
Text Editor → Text output → CLIP Text Encode → Conditioning
```

### Template System
```
Save prompt templates with placeholders
Load template → Edit specific parts → Generate with conditioning output
```

## Use Cases

### Style Prompts
- Save different art styles as templates
- Load and modify for each generation

### Negative Prompts
- Maintain library of negative prompts
- Load appropriate negatives per workflow

### Character Descriptions
- Store detailed character descriptions
- Mix and match traits from different prompts

### Scene Templates
- Save scene composition templates
- Reuse with variations

## Tips

- **Organization**: Use descriptive filenames (e.g., `portrait_style_realistic.txt`)
- **Backup**: Saved prompts directory can be backed up/synced
- **Version Control**: Save variants with version numbers
- **Snippets**: Save commonly used phrases/keywords as separate files

## Keyboard Shortcuts

- **Ctrl+A**: Select all text
- **Ctrl+C**: Copy
- **Ctrl+V**: Paste
- **Ctrl+Z**: Undo
- **Ctrl+Y**: Redo

## Troubleshooting

- **Can't save**: Check `prompts_save_directory` in config.json
- **File not found**: Ensure directory exists and has write permissions
- **Not loading**: Click refresh or check dropdown for file
- **Missing files**: Verify `.txt` files are in correct directory
