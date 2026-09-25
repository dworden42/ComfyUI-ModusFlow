# ModusFlow ACE Step Audio 1.5

An enhanced `TextEncodeAceStepAudio1.5` node with song save/load functionality, modelled after the ModusFlow Text Editor. Write your tags and lyrics once, save them by name, and recall them instantly in future sessions.

---

## Overview

This node is a drop-in replacement for ComfyUI's built-in `TextEncodeAceStepAudio1.5`. It adds a **Title** field and save/load controls:

| Button | Action |
|--------|--------|
| **💾 Save Song** | Saves current title + tags + lyrics to `saved_songs/<title>.json` (uses title as filename; prompts if title is empty) |
| **✏️ Update Song** | Overwrites the file currently shown in the dropdown with the current content |
| **🔄 Refresh All** | Re-reads the saved_songs folder and repopulates all dropdowns |

Selecting a file from the **Saved Song** dropdown automatically loads the title, tags, and lyrics into the node.

The **title** is also passed through as a STRING output so it can be used as `%title%` in the ModusFlow Save Audio filename prefix.

---

## Inputs

### Required

| Input | Type | Description |
|-------|------|-------------|
| `clip` | CLIP | ACE Step CLIP model |
| `title` | STRING | Song title — used as the save filename and passed through as output |
| `tags` | STRING | Style/genre tags (e.g. `pop, upbeat, electric guitar`) |
| `lyrics` | STRING | Song lyrics, optionally with `[verse]`, `[chorus]` markers |
| `saved_song` | Combo | Dropdown of saved `.json` song files |
| `seed` | INT | Generation seed |
| `bpm` | INT | Beats per minute (10–300, default 120) |
| `duration` | FLOAT | Target duration in seconds (default 120) |
| `timesignature` | Combo | Time signature: `2`, `3`, `4`, `6` |
| `language` | Combo | Language code for lyrics (e.g. `en`, `ja`, `zh`…) |
| `keyscale` | Combo | Musical key and scale (e.g. `C major`, `A minor`) |

### Advanced

| Input | Type | Description |
|-------|------|-------------|
| `generate_audio_codes` | BOOLEAN | Enable the LLM audio code generator (default `true`) |
| `cfg_scale` | FLOAT | CFG guidance scale (default 2.0) |
| `temperature` | FLOAT | Sampling temperature (default 0.85) |
| `top_p` | FLOAT | Top-p nucleus sampling (default 0.9) |
| `top_k` | INT | Top-k sampling (default 0 = disabled) |
| `min_p` | FLOAT | Min-p sampling threshold (default 0.0) |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `conditioning` | CONDITIONING | Encoded conditioning ready for the ACE Step sampler |
| `title` | STRING | Song title passthrough — connect to Save Audio's `title` input to use `%title%` in the filename |

---

## Song File Format

Songs are saved as JSON files in `ComfyUI-ModusFlow/saved_songs/` (configurable via `songs_save_directory` in `config.json`):

```json
{
  "title": "Fly Away",
  "tags": "pop, upbeat, electric guitar, female vocals",
  "lyrics": "[verse1]\nWaking up to a brand new day\n\n[chorus]\nFly away, fly away..."
}
```

---

## Usage Tips

- Use `[verse]`, `[chorus]`, `[bridge]`, `[outro]` markers in lyrics for structure.
- Tags drive the overall genre and instrumentation — keep them concise and comma-separated.
- Disable `generate_audio_codes` if you are providing a reference audio (faster generation).
- Save each song variant with a descriptive name so you can A/B different lyrics or styles.

---

## Troubleshooting

**Dropdown shows "--no songs found--"**
No `.json` files exist yet in the `saved_songs` folder. Click **💾 Save Song** to create your first one.

**Saved song not appearing after saving**
Click **🔄 Refresh List** to reload the dropdown from disk.

**Node outputs wrong conditioning**
Make sure the connected CLIP model is an ACE Step 1.5 CLIP — using a regular CLIP will error.
