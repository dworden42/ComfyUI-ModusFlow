"""
ModusFlow Save Audio Node

Enhanced audio save node with:
- Multiple output formats: flac, wav, mp3, ogg
- Filename variable substitution:
    %date%      -> YYYY-MM-DD
    %time%      -> HH-MM-SS
    %datetime%  -> YYYY-MM-DD_HH-MM-SS
    %year%, %month%, %day%, %hour%, %minute%, %second%  (native ComfyUI vars)
    %batch_num% -> batch index
    %seed%      -> seed value (requires seed input)
- Per-format quality options
"""

import os
import re
import json
import time
from io import BytesIO

import folder_paths

try:
    import av
    AV_AVAILABLE = True
except ImportError:
    AV_AVAILABLE = False


def _java_date_format(fmt_str: str, now) -> str:
    """Convert a Java/moment.js date format string to an actual date string."""
    fmt = fmt_str
    fmt = fmt.replace("yyyy", "%Y").replace("yy", "%y")
    fmt = fmt.replace("MM", "%m")
    fmt = fmt.replace("dd", "%d")
    fmt = fmt.replace("HH", "%H")
    fmt = fmt.replace("mm", "%M")
    fmt = fmt.replace("ss", "%S")
    return time.strftime(fmt, now)


def _expand_shorthand_vars(prefix: str, seed=None, title=None) -> str:
    """Expand all date/time/seed/title shorthands in a filename prefix."""
    now = time.localtime()
    year   = str(now.tm_year)
    month  = str(now.tm_mon).zfill(2)
    day    = str(now.tm_mday).zfill(2)
    hour   = str(now.tm_hour).zfill(2)
    minute = str(now.tm_min).zfill(2)
    second = str(now.tm_sec).zfill(2)

    # Expand %date:FORMAT% patterns (Java/moment.js format codes, e.g. %date:yyyy-MM-dd%)
    prefix = re.sub(r'%date:([^%]+)%', lambda m: _java_date_format(m.group(1), now), prefix)

    prefix = prefix.replace("%datetime%", f"{year}-{month}-{day}_{hour}-{minute}-{second}")
    prefix = prefix.replace("%date%", f"{year}-{month}-{day}")
    prefix = prefix.replace("%time%", f"{hour}-{minute}-{second}")
    prefix = prefix.replace("%year%", year)
    prefix = prefix.replace("%month%", month)
    prefix = prefix.replace("%day%", day)
    prefix = prefix.replace("%hour%", hour)
    prefix = prefix.replace("%minute%", minute)
    prefix = prefix.replace("%second%", second)

    if seed is not None:
        prefix = prefix.replace("%seed%", str(seed))
    else:
        prefix = prefix.replace("%seed%", "0")
    if title:
        safe_title = re.sub(r'[<>:"/\\|?*]', "_", title).strip()
        prefix = prefix.replace("%title%", safe_title)
    else:
        prefix = prefix.replace("%title%", "")
    return prefix


def _resolve_save_path(prefix: str, output_dir: str):
    """
    Resolve folder, base filename, and starting counter for a given prefix.
    Supports both relative paths (resolved under output_dir) and absolute paths.
    Returns (full_folder, base_filename, counter, subfolder_for_ui).
    """
    abs_prefix = os.path.abspath(prefix) if os.path.isabs(prefix) else None

    if abs_prefix is not None:
        # Absolute path: bypass get_save_image_path
        full_folder = os.path.dirname(abs_prefix)
        base_filename = os.path.basename(abs_prefix)
        os.makedirs(full_folder, exist_ok=True)
        # Find next counter
        counter = 1
        while True:
            candidate = os.path.join(full_folder, f"{base_filename}_{counter:05}_.flac")
            # Check any extension to find the next free slot
            import glob
            pattern = os.path.join(full_folder, f"{base_filename}_{counter:05}_.*")
            if not glob.glob(pattern):
                break
            counter += 1
        return full_folder, base_filename, counter, full_folder
    else:
        # Relative path: use ComfyUI's helper (handles counting, subfolder)
        full_folder, base_filename, counter, subfolder, _ = folder_paths.get_save_image_path(
            prefix, output_dir
        )
        return full_folder, base_filename, counter, subfolder


class ModusFlowSaveAudio:
    """
    Save audio to disk with format and quality control.

    Supported filename variables:
      %date%      -> YYYY-MM-DD
      %time%      -> HH-MM-SS
      %datetime%  -> YYYY-MM-DD_HH-MM-SS
      %year%      -> 4-digit year
      %month%     -> 2-digit month
      %day%       -> 2-digit day
      %hour%      -> 2-digit hour
      %minute%    -> 2-digit minute
      %second%    -> 2-digit second
      %batch_num% -> batch index
      %seed%      -> seed value (pipe from KSampler seed output)
      %title%     -> song title (pipe from ACE Step Audio title output)

    Quality by format:
      flac  -> lossless (quality ignored)
      wav   -> lossless PCM 16-bit (quality ignored)
      mp3   -> V0 (best VBR), 128k, 192k, 320k
      ogg   -> V0 (~500k VBR), 128k, 192k, 320k
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "audio": ("AUDIO",),
                "filename_prefix": ("STRING", {"default": "audio/%date%/ComfyUI"}),
                "format": (["flac", "wav", "mp3", "ogg"], {"default": "flac"}),
                "quality": (["lossless", "V0", "128k", "192k", "320k"], {"default": "lossless"}),
            },
            "optional": {
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "title": ("STRING", {"forceInput": True}),
            },
            "hidden": {
                "prompt": "PROMPT",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    RETURN_TYPES = ()
    FUNCTION = "save_audio"
    OUTPUT_NODE = True
    CATEGORY = "ModusFlow/Audio"

    def save_audio(self, audio, filename_prefix, format, quality, seed=None, title=None, prompt=None, extra_pnginfo=None):
        if not AV_AVAILABLE:
            raise ImportError(
                "[ModusFlow SaveAudio] PyAV (av) is required but not installed. "
                "Install it with: pip install av"
            )

        prefix = _expand_shorthand_vars(filename_prefix, seed=seed, title=title)
        output_dir = folder_paths.get_output_directory()

        full_output_folder, filename, counter, subfolder = _resolve_save_path(prefix, output_dir)

        metadata = {}
        if prompt is not None:
            metadata["prompt"] = json.dumps(prompt)
        if extra_pnginfo is not None:
            for key, value in extra_pnginfo.items():
                metadata[key] = json.dumps(value)

        results = []

        for batch_number, waveform in enumerate(audio["waveform"].cpu()):
            sample_rate = audio["sample_rate"]
            layout = "mono" if waveform.shape[0] == 1 else "stereo"

            filename_with_batch = filename.replace("%batch_num%", str(batch_number))
            file = f"{filename_with_batch}_{counter:05}_.{format}"
            output_path = os.path.join(full_output_folder, file)

            output_buffer = BytesIO()

            if format == "wav":
                out_container = av.open(output_buffer, mode="w", format="wav")
                out_stream = out_container.add_stream("pcm_s16le", rate=sample_rate, layout=layout)

            elif format == "flac":
                out_container = av.open(output_buffer, mode="w", format="flac")
                out_stream = out_container.add_stream("flac", rate=sample_rate, layout=layout)

            elif format == "mp3":
                out_container = av.open(output_buffer, mode="w", format="mp3")
                out_stream = out_container.add_stream("libmp3lame", rate=sample_rate, layout=layout)
                if quality == "V0":
                    out_stream.codec_context.qscale = 1
                elif quality == "128k":
                    out_stream.bit_rate = 128000
                elif quality == "192k":
                    out_stream.bit_rate = 192000
                elif quality == "320k":
                    out_stream.bit_rate = 320000
                # "lossless" -> use encoder default

            elif format == "ogg":
                out_container = av.open(output_buffer, mode="w", format="ogg")
                out_stream = out_container.add_stream("libvorbis", rate=sample_rate, layout=layout)
                if quality == "V0":
                    out_stream.bit_rate = 500000
                elif quality == "128k":
                    out_stream.bit_rate = 128000
                elif quality == "192k":
                    out_stream.bit_rate = 192000
                elif quality == "320k":
                    out_stream.bit_rate = 320000
                # "lossless" -> use encoder default

            else:
                raise ValueError(f"[ModusFlow SaveAudio] Unsupported format: {format}")

            for key, value in metadata.items():
                out_container.metadata[key] = value

            frame = av.AudioFrame.from_ndarray(
                waveform.movedim(0, 1).reshape(1, -1).float().numpy(),
                format="flt",
                layout=layout,
            )
            frame.sample_rate = sample_rate
            frame.pts = 0

            out_container.mux(out_stream.encode(frame))
            out_container.mux(out_stream.encode(None))
            out_container.close()

            output_buffer.seek(0)
            with open(output_path, "wb") as f:
                f.write(output_buffer.getbuffer())

            print(f"[ModusFlow SaveAudio] Saved: {output_path}")

            results.append({
                "filename": file,
                "subfolder": subfolder,
                "type": "output",
            })
            counter += 1

        return {"ui": {"audio": results}}
