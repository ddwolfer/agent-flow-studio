"""Local audio→text transcription via faster-whisper (CTranslate2 Whisper).

Used as the caption-less fallback for YouTube sources: when a video has no
fetchable captions, the ytdlp server downloads its audio and calls
`transcribe(video_url)` here. Whisper is a real ASR model (handles Mandarin +
English with auto language detection), unlike the previous ollama/gemma path
which silently ignored audio input on the OpenAI-compat endpoint.

Interface kept minimal: `transcribe(video_url) -> str`. The model is loaded
once per process and cached.
"""
import os, subprocess, tempfile, pathlib

MODEL_NAME = os.environ.get("STUDIO_WHISPER_MODEL", "medium")
# CTranslate2 has no Metal/MPS backend; int8 on Apple-Silicon CPU is the
# portable, fast default. Override with STUDIO_WHISPER_COMPUTE if needed.
COMPUTE = os.environ.get("STUDIO_WHISPER_COMPUTE", "int8")

# Domain vocabulary biases whisper's decoding toward the right finance/crypto
# terms (without it, small/medium hear 反彈→"彈期", 回踩→"回彩", 阻力→"主義",
# 以太幣→"刻意太幣", etc.). This cannot fix misheard DIGITS — that risk is
# handled at the report layer (whisper-sourced numbers are cross-checked).
INITIAL_PROMPT = os.environ.get(
    "STUDIO_WHISPER_PROMPT",
    "以下是加密貨幣與股市財經影片的逐字稿,常見詞彙:比特幣、以太幣、以太坊、"
    "BTC、ETH、合約、爆倉、多單、空單、反彈、回踩、回測、上攻、下殺、支撐、"
    "阻力、成本線、籌碼、巨鯨、減半、ETF、聯準會、升息、降息、那斯達克、台股、"
    "加權指數、台積電、輝達。",
)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE)
    return _model


def transcribe(video_url: str) -> str:
    """Download the video's audio and return its full transcript text.

    Auto-detects language (so Chinese and English channels both work).
    Raises on download failure; returns "" if the audio has no speech.
    """
    with tempfile.TemporaryDirectory() as d:
        dp = pathlib.Path(d)
        # Whisper (via PyAV) decodes/resamples internally, so we only need the
        # raw bestaudio file — no manual ffmpeg normalize/chunk step.
        subprocess.run([
            "yt-dlp", "-f", "bestaudio", "-x", "--audio-format", "wav",
            "-o", str(dp / "a.%(ext)s"), "--quiet", video_url,
        ], check=True)
        wavs = list(dp.glob("a.*"))
        if not wavs:
            raise RuntimeError("yt-dlp produced no audio file")
        segments, _info = _get_model().transcribe(
            str(wavs[0]), vad_filter=True, initial_prompt=INITIAL_PROMPT)
        return "\n".join(s.text.strip() for s in segments if s.text.strip())
