# ModusFlow Ollama Text Refiner

A lightweight node that sends a text string to a local Ollama model and returns the refined result. Useful for quickly improving prompts inline without the full Ollama Prompt Refiner's pipeline.

## Inputs

| Input | Type | Description |
|-------|------|-------------|
| text | STRING | The text to refine |
| ollama_model | dropdown | Ollama model to use |
| system_prompt | STRING | Instruction given to the model |
| temperature | FLOAT (0–2) | Sampling temperature |
| max_tokens | INT (50–4096) | Maximum tokens to generate |
| seed | INT | Seed for reproducibility |

## Output

| Output | Type | Description |
|--------|------|-------------|
| refined_text | STRING | The model's refined output |

## Notes

- If Ollama is unavailable or returns an error the original `text` is passed through unchanged.
- The default system prompt is tuned for image-generation prompt refinement; edit it freely for other use cases.
