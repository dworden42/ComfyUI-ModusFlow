"""
ModusFlow ACE Step Audio Node

Enhanced TextEncodeAceStepAudio1.5 node with save/load functionality for:
  - Title, tags and lyrics saved together as a song (.json in saved_songs/)
  - Tags saved individually             (.txt in saved_songs/tags/)
  - Lyrics saved individually           (.txt in saved_songs/lyrics/)

The title is used as the save filename and is passed through as a STRING
output so it can be used in the Save Audio node via the %title% variable.
"""

import os


def _get_songs_dir():
    """Return the root songs directory (does NOT create subdirs)."""
    try:
        from ..config import settings, BASE_DIR
        songs_dir = settings.get("songs_save_directory", "").strip()
        if not songs_dir:
            songs_dir = os.path.join(BASE_DIR, "saved_songs")
    except Exception:
        songs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "saved_songs")
    return songs_dir


def _tags_dir():
    return os.path.join(_get_songs_dir(), "tags")


def _lyrics_dir():
    return os.path.join(_get_songs_dir(), "lyrics")


# Key/scale options matching the original node
_KEYSCALE_OPTIONS = [
    f"{root} {quality}"
    for quality in ["major", "minor"]
    for root in ["C", "C#", "Db", "D", "D#", "Eb", "E", "F", "F#", "Gb", "G", "G#", "Ab", "A", "A#", "Bb", "B"]
]

_LANGUAGE_OPTIONS = [
    "en", "ja", "zh", "es", "de", "fr", "pt", "ru", "it", "nl",
    "pl", "tr", "vi", "cs", "fa", "id", "ko", "uk", "hu", "ar", "sv", "ro", "el",
]


class ModusFlowAceStepAudio:
    """
    Enhanced TextEncodeAceStepAudio1.5 node with song save/load functionality.

    Three save/load scopes:
      saved_tags   — load/save only the Tags field   (saved_songs/tags/*.txt)
      saved_lyrics — load/save only the Lyrics field (saved_songs/lyrics/*.txt)
      saved_song   — load/save Tags + Lyrics together (saved_songs/*.json)
    """

    @classmethod
    def INPUT_TYPES(cls):
        saved_songs  = cls._list_songs()
        saved_tags   = cls._list_tags()
        saved_lyrics = cls._list_lyrics()
        return {
            "required": {
                "clip": ("CLIP",),
                # Song title — used as save filename and passed through as output
                "title": ("STRING", {"default": "", "multiline": False}),
                # Tags field + its own save/load dropdown
                "tags": ("STRING", {"default": "", "multiline": True}),
                "saved_tags": (saved_tags, {"default": saved_tags[0]}),
                # Lyrics field + its own save/load dropdown
                "lyrics": ("STRING", {"default": "", "multiline": True}),
                "saved_lyrics": (saved_lyrics, {"default": saved_lyrics[0]}),
                # Combined save/load dropdown
                "saved_song": (saved_songs, {"default": saved_songs[0]}),
                # Generation parameters
                "seed": ("INT", {"default": 0, "min": 0, "max": 0xffffffffffffffff}),
                "bpm": ("INT", {"default": 120, "min": 10, "max": 300}),
                "duration": ("FLOAT", {"default": 120.0, "min": 0.0, "max": 2000.0, "step": 0.1}),
                "timesignature": (["2", "3", "4", "6"], {"default": "4"}),
                "language": (_LANGUAGE_OPTIONS, {"default": "en"}),
                "keyscale": (_KEYSCALE_OPTIONS, {"default": "C major"}),
                # Advanced parameters
                "generate_audio_codes": ("BOOLEAN", {"default": True}),
                "cfg_scale": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 100.0, "step": 0.05}),
                "temperature": ("FLOAT", {"default": 0.85, "min": 0.0, "max": 2.0, "step": 0.01}),
                "top_p": ("FLOAT", {"default": 0.9, "min": 0.0, "max": 2000.0, "step": 0.01}),
                "top_k": ("INT", {"default": 0, "min": 0, "max": 100}),
                "min_p": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 1.0, "step": 0.001}),
            },
            "hidden": {
                "unique_id": "UNIQUE_ID",
                "extra_pnginfo": "EXTRA_PNGINFO",
            },
        }

    # ── list helpers ──────────────────────────────────────────────────────────

    @classmethod
    def _list_songs(cls):
        try:
            d = _get_songs_dir()
            if os.path.isdir(d):
                files = sorted(f for f in os.listdir(d) if f.endswith(".json"))
                if files:
                    return ["--select song--"] + files
        except Exception as e:
            print(f"[ModusFlow AceStepAudio] Error listing songs: {e}")
        return ["--no songs found--"]

    @classmethod
    def _list_tags(cls):
        try:
            d = _tags_dir()
            if os.path.isdir(d):
                files = sorted(f for f in os.listdir(d) if f.endswith(".txt"))
                if files:
                    return ["--select tags--"] + files
        except Exception as e:
            print(f"[ModusFlow AceStepAudio] Error listing tags: {e}")
        return ["--no tags found--"]

    @classmethod
    def _list_lyrics(cls):
        try:
            d = _lyrics_dir()
            if os.path.isdir(d):
                files = sorted(f for f in os.listdir(d) if f.endswith(".txt"))
                if files:
                    return ["--select lyrics--"] + files
        except Exception as e:
            print(f"[ModusFlow AceStepAudio] Error listing lyrics: {e}")
        return ["--no lyrics found--"]

    # ── node metadata ─────────────────────────────────────────────────────────

    RETURN_TYPES = ("CONDITIONING", "STRING")
    RETURN_NAMES = ("conditioning", "title")
    FUNCTION = "encode"
    OUTPUT_NODE = False
    CATEGORY = "ModusFlow/Audio"

    # ── execute ───────────────────────────────────────────────────────────────

    def encode(
        self,
        clip,
        title,
        tags,
        saved_tags,
        lyrics,
        saved_lyrics,
        saved_song,
        seed,
        bpm,
        duration,
        timesignature,
        language,
        keyscale,
        generate_audio_codes,
        cfg_scale,
        temperature,
        top_p,
        top_k,
        min_p,
        unique_id=None,
        extra_pnginfo=None,
    ):
        tokens = clip.tokenize(
            tags,
            lyrics=lyrics,
            bpm=bpm,
            duration=duration,
            timesignature=int(timesignature),
            language=language,
            keyscale=keyscale,
            seed=seed,
            generate_audio_codes=generate_audio_codes,
            cfg_scale=cfg_scale,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            min_p=min_p,
        )
        conditioning = clip.encode_from_tokens_scheduled(tokens)

        if unique_id is not None and extra_pnginfo is not None:
            if isinstance(extra_pnginfo, dict) and "workflow" in extra_pnginfo:
                workflow = extra_pnginfo["workflow"]
                node = next(
                    (x for x in workflow["nodes"] if str(x["id"]) == str(unique_id)),
                    None,
                )
                if node:
                    node["widgets_values"] = [
                        title, tags, saved_tags, lyrics, saved_lyrics, saved_song,
                        seed, bpm, duration, timesignature, language, keyscale,
                        generate_audio_codes, cfg_scale, temperature, top_p, top_k, min_p,
                    ]

        return (conditioning, title)
