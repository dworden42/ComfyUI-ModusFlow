# ModusFlow Save Audio

An enhanced audio save node supporting multiple output formats, per-format quality control, and filename variable substitution.

---

## Overview

**ModusFlow Save Audio** replaces the default ComfyUI save-audio nodes with a single unified node. It writes audio to the output directory in your chosen format, with the filename pattern evaluated at save time.

---

## Inputs

| Input | Type | Description |
|-------|------|-------------|
| `audio` | AUDIO | Audio data to save |
| `filename_prefix` | STRING | Output path/filename pattern (supports variables) |
| `format` | Combo | Output format: `flac`, `wav`, `mp3`, `ogg` |
| `quality` | Combo | Quality level (see table below) |
| `seed` | INT *(optional)* | Seed value to embed in filename via `%seed%` |
| `title` | STRING *(optional)* | Song title to embed in filename via `%title%` (pipe from ACE Step Audio) |

---

## Filename Variables

Variables are replaced when the node runs:

| Variable | Expands to | Example |
|----------|-----------|---------|
| `%date%` | YYYY-MM-DD | `2025-03-03` |
| `%time%` | HH-MM-SS | `14-30-00` |
| `%datetime%` | YYYY-MM-DD_HH-MM-SS | `2025-03-03_14-30-00` |
| `%year%` | 4-digit year | `2025` |
| `%month%` | 2-digit month | `03` |
| `%day%` | 2-digit day | `03` |
| `%hour%` | 2-digit hour | `14` |
| `%minute%` | 2-digit minute | `30` |
| `%second%` | 2-digit second | `00` |
| `%batch_num%` | Batch index | `0`, `1`, `2`… |
| `%seed%` | Seed value (requires `seed` input) | `1234567890` |
| `%title%` | Song title (requires `title` input) | `Fly Away` |

Slashes in the prefix create subdirectories under ComfyUI's output folder.

**Examples:**
```
audio/%date%/ComfyUI          -> output/audio/2025-03-03/ComfyUI_00001_.flac
audio/%datetime%/song         -> output/audio/2025-03-03_14-30-00/song_00001_.mp3
music/%year%/%month%/track    -> output/music/2025/03/track_00001_.wav
audio/%date%/%title%          -> output/audio/2025-03-03/Fly Away_00001_.flac
```

---

## Quality Options

| Quality | FLAC | WAV | MP3 | OGG |
|---------|------|-----|-----|-----|
| `lossless` | ✓ lossless | ✓ lossless PCM | encoder default | encoder default |
| `V0` | — | — | Best VBR (~245 kbps) | ~500k VBR |
| `128k` | — | — | 128 kbps CBR | 128 kbps |
| `192k` | — | — | 192 kbps CBR | 192 kbps |
| `320k` | — | — | 320 kbps CBR | 320 kbps |

For `flac` and `wav`, the quality setting is ignored — both are always lossless.

---

## Usage Tips

- Use `%date%` in the prefix to automatically organise saved audio into date folders.
- Use `flac` for archival quality; use `mp3 V0` for small files with near-transparent quality.
- Batch workflows: include `%batch_num%` if you expect multiple audio outputs from a single run.
- The counter (`_00001_`) in the filename auto-increments to avoid overwriting existing files.

---

## Troubleshooting

**"PyAV (av) is required but not installed"**
Run `pip install av` in your ComfyUI Python environment.

**OGG files not playing in some apps**
OGG/Vorbis is widely supported but some older apps prefer MP3. Switch format to `mp3` if compatibility is needed.

**Files saved to unexpected location**
Paths are relative to ComfyUI's output directory. Avoid leading slashes in the prefix.
