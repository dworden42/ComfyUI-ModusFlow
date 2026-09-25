# Show Text

Simple text display node for viewing prompt outputs and debugging.

## Overview

The Show Text node provides a clean interface for displaying text strings in the ComfyUI UI, useful for viewing AI-generated prompts, debugging workflow values, and inspecting text outputs.

## Features

- **Clean Display**: Formatted text display in the UI
- **Copyable**: Easy selection and copying of displayed text
- **Pass-through**: Outputs the same text for chaining
- **Debugging**: View intermediate text values in workflows

## Inputs

### Required
- **text** (STRING): Text to display

## Outputs

- **STRING**: Pass-through of input text (for chaining)

## Usage

### View AI Prompts
```
Ollama Prompt Refiner → Show Text → CLIP Text Encode
```
See the refined prompt before encoding.

### Debug Text Processing
```
Text Node → Show Text
```
Inspect text values during workflow development.

### Chain Multiple Displays
```
Text Source → Show Text → Processing → Show Text
```
View text before and after processing.

## UI Appearance

The node displays text in a formatted text area with:
- Word wrapping for long text
- Scrollable for very long text
- Monospace font for code/structured text
- Dark theme matching ComfyUI

## Tips

- **Prompt Refinement**: Use to verify AI prompt refinements before generation
- **Metadata Display**: View extracted image metadata
- **Workflow Documentation**: Display workflow notes or instructions
- **Value Inspection**: Debug string formatting or text manipulation nodes

## Example Workflows

### Prompt Pipeline Visualization
```
Base Prompt → Ollama Refiner → Show Text (view refined)
                                    ↓
                              CLIP Text Encode
```

### Metadata Extraction
```
Image For Prompting → Show Text → String Processing
```
