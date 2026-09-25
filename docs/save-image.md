# ModusFlow Save Image

Save images to disk with variable filename support, format selection, and optional workflow metadata embedding.

## Inputs

| Input | Type | Description |
|-------|------|-------------|
| images | IMAGE | Batch of images to save |
| filename_prefix | STRING | Path/filename with optional variables (see below) |
| format | dropdown | `png`, `jpeg`, or `webp` |
| quality | INT 1–100 | JPEG/WebP quality (ignored for PNG) |
| embed_metadata | dropdown | `enabled` = embed workflow/prompt; `disabled` = strip all metadata |
| clean_vram | boolean | Clear CUDA VRAM cache after saving |
| seed | INT (optional) | Seed value for `%seed%` substitution |

## Output

Output node — no data outputs. Saved files appear in the ComfyUI output panel.

## Filename Variables

| Variable | Expands to |
|----------|-----------|
| `%date%` | `YYYY-MM-DD` |
| `%time%` | `HH-MM-SS` |
| `%datetime%` | `YYYY-MM-DD_HH-MM-SS` |
| `%year%` | 4-digit year |
| `%month%` | 2-digit month |
| `%day%` | 2-digit day |
| `%hour%` | 2-digit hour |
| `%minute%` | 2-digit minute |
| `%second%` | 2-digit second |
| `%seed%` | Seed value (requires seed input) |
| `%width%` | Image width in pixels |
| `%height%` | Image height in pixels |
| `%batch_num%` | Index within the current batch |
| `%date:FORMAT%` | Custom date using Java/moment.js format codes |

## Example Prefixes

```
images/%date%/ComfyUI_%seed%
renders/%datetime%_%width%x%height%
ComfyUI_%date%_%seed%
```

## Metadata Embedding

| Format | `enabled` | `disabled` |
|--------|-----------|------------|
| PNG | Workflow + prompt as text chunks (readable by ComfyUI drag-and-drop) | No metadata |
| JPEG | Workflow + prompt as EXIF ImageDescription | No EXIF |
| WebP | Workflow + prompt as XMP metadata | No XMP |

## Notes

- **PNG**: Lossless. `quality` is ignored.
- **JPEG**: `quality` controls compression (95 = near-lossless).
- **WebP**: `quality` controls compression.
- Only PNG metadata can be read back by ComfyUI's drag-and-drop workflow restore.
- Subdirectories are created automatically.
- Connect the seed output from your KSampler directly to the `seed` input.
