"""Local/cloud audio→text for the caption-less YouTube fallback.

When a video has no fetchable captions, ytdlp downloads its audio and calls
`transcribe(video_url)`. Both engines run Whisper large-v3, so the source tag
stays "whisper" either way:

  1. Groq cloud (whisper-large-v3-turbo) — preferred when GROQ_API_KEY is set.
     ~200x realtime, large-v3 accuracy, ~$0.04/audio-hour. Long audio is split
     into <25MB chunks (Groq's upload limit).
  2. Local faster-whisper (CTranslate2, medium, int8 CPU) — offline fallback
     when there is no key or Groq errors out. ~1x realtime.

Why ASR and not an LLM (gemma/Gemini): we need verbatim transcription. A
generative model paraphrases/hallucinates digits and names — exactly the
finance data that must stay exact. Misheard DIGITS survive even on large-v3,
so the report layer (prompts/shared/faithfulness.md) cross-checks numbers.
"""
import os, subprocess, sys, tempfile, pathlib

DOWNLOAD_TIMEOUT_SEC = int(os.environ.get("STUDIO_YTDLP_DOWNLOAD_TIMEOUT", "600"))

# ── local faster-whisper (offline fallback) ────────────────────────────────────
MODEL_NAME = os.environ.get("STUDIO_WHISPER_MODEL", "medium")
COMPUTE = os.environ.get("STUDIO_WHISPER_COMPUTE", "int8")

# ── Groq cloud (preferred) ──────────────────────────────────────────────────────
GROQ_MODEL = os.environ.get("STUDIO_GROQ_MODEL", "whisper-large-v3-turbo")
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
# 16kHz mono s16 wav ≈ 32 KB/s, so 600s ≈ 19 MB — safely under Groq's 25 MB cap.
GROQ_CHUNK_SEC = int(os.environ.get("STUDIO_GROQ_CHUNK_SEC", "600"))

# Domain vocabulary biases decoding toward the right finance/crypto terms
# (反彈 not 彈期, 回踩 not 回彩, 阻力 not 主義, 以太幣 not 刻意太幣). Cannot fix
# misheard DIGITS — that risk is handled at the report layer.
INITIAL_PROMPT = os.environ.get(
    "STUDIO_WHISPER_PROMPT",
    "以下是加密貨幣與股市財經影片的逐字稿,請用繁體中文,常見詞彙:比特幣、以太幣、"
    "以太坊、BTC、ETH、合約、爆倉、多單、空單、反彈、回踩、回測、上攻、下殺、支撐、"
    "阻力、成本線、籌碼、巨鯨、減半、ETF、聯準會、升息、降息、那斯達克、台股、"
    "加權指數、台積電、輝達。",
)
# Same vocabulary bias for English-language channels. A Chinese prompt on
# English audio pushes Whisper toward translating, which breaks verbatim quotes.
INITIAL_PROMPT_EN = os.environ.get(
    "STUDIO_WHISPER_PROMPT_EN",
    "Crypto and macro market commentary. Terms: Bitcoin, BTC, Ethereum, ETH, "
    "altcoins, Solana, XRP, stablecoin, ETF, Fed, FOMC, CPI, PPI, yields, "
    "liquidation, funding rate, open interest, bull market, bear market.",
)


def _lang_and_prompt(language):
    """Whisper language code + matching vocabulary prompt.

    `language` is YouTube's reported spoken language ("en", "zh-TW", ...) or
    None. Unknown stays "zh" — the historical default, and the channels that
    reach the audio path are mostly Chinese (BTV, TiaBTC: no captions at all).
    """
    lang = (language or "zh").split("-")[0].lower()
    return lang, (INITIAL_PROMPT if lang == "zh" else INITIAL_PROMPT_EN)

_model = None


def _get_model():
    global _model
    if _model is None:
        from faster_whisper import WhisperModel
        _model = WhisperModel(MODEL_NAME, device="cpu", compute_type=COMPUTE)
    return _model


def _download_wav(video_url: str, dp: pathlib.Path) -> pathlib.Path:
    """Download bestaudio and normalize to 16kHz mono wav (small + ASR-ready).

    Runs yt-dlp as `<this python> -m yt_dlp`, NOT the bare `yt-dlp` on PATH.
    Regression 2026-10-07: PATH resolved to a separate Homebrew copy frozen at
    2026.03.17, which YouTube answered with HTTP 403 on every audio download,
    while the reports only said "exit status 1". One interpreter = one yt-dlp
    version to keep current (scripts/update_ytdlp.py), and stderr is surfaced.
    """
    cmd = [
        sys.executable, "-m", "yt_dlp",
        "-f", "bestaudio", "-x", "--audio-format", "wav",
        "--sleep-requests", "2",  # self-pace to avoid YouTube burst rate-limiting
        "-o", str(dp / "a.%(ext)s"), "--quiet",
    ]
    # EJS n-challenge solver (needs deno on PATH); without it bestaudio is
    # intermittently unavailable ("Only images are available").
    if os.environ.get("STUDIO_YTDLP_EJS", "1") != "0":
        cmd += ["--remote-components", "ejs:github"]
    cookies = os.environ.get("STUDIO_YTDLP_COOKIES_FILE", "")
    if cookies and os.path.exists(cookies):
        cmd += ["--cookies", cookies]
    cmd.append(video_url)
    try:
        # Bounded: an unbounded child process is the same class of hang as the
        # 2026-08-25 Chrome PDF stall that froze a launchd label for 32 hours.
        r = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=DOWNLOAD_TIMEOUT_SEC)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"yt-dlp audio download timed out after "
                           f"{DOWNLOAD_TIMEOUT_SEC}s")
    if r.returncode != 0:
        errs = [ln for ln in (r.stderr or "").splitlines() if "ERROR" in ln]
        tail = errs[-1] if errs else (r.stderr or "").strip()[-300:]
        raise RuntimeError(f"yt-dlp audio download failed "
                           f"(exit {r.returncode}): {tail}")
    raw = list(dp.glob("a.*"))
    if not raw:
        raise RuntimeError("yt-dlp produced no audio file")
    norm = dp / "norm.wav"
    subprocess.run(["ffmpeg", "-y", "-i", str(raw[0]), "-ac", "1", "-ar", "16000",
                    str(norm)], capture_output=True, check=True)
    return norm


def _audio_duration(path: pathlib.Path) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)],
                       capture_output=True, text=True, check=True)
    return int(float(r.stdout.strip() or "0"))


def _groq_transcribe(wav: pathlib.Path, dp: pathlib.Path, key: str,
                     language=None) -> str:
    """Transcribe via Groq, chunking long audio to stay under the 25MB limit."""
    import httpx
    lang, prompt = _lang_and_prompt(language)
    dur = _audio_duration(wav)
    starts = list(range(0, max(dur, 1), GROQ_CHUNK_SEC)) or [0]
    parts = []
    for i, s in enumerate(starts):
        chunk = wav if len(starts) == 1 else dp / f"g_{s}.wav"
        if len(starts) > 1:
            subprocess.run(["ffmpeg", "-y", "-i", str(wav), "-ss", str(s),
                            "-t", str(GROQ_CHUNK_SEC), str(chunk)],
                           capture_output=True, check=True)
        with open(chunk, "rb") as f:
            r = httpx.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"},
                           files={"file": (chunk.name, f, "audio/wav")},
                           data={"model": GROQ_MODEL, "language": lang,
                                 "prompt": prompt, "temperature": "0"},
                           timeout=180.0)
        r.raise_for_status()
        t = (r.json().get("text") or "").strip()
        if t:
            parts.append(t)
    return "\n".join(parts)


def _local_transcribe(wav: pathlib.Path, language=None) -> str:
    lang, prompt = _lang_and_prompt(language)
    segments, _info = _get_model().transcribe(
        str(wav), vad_filter=True, language=lang, initial_prompt=prompt)
    return "\n".join(s.text.strip() for s in segments if s.text.strip())


def transcribe(video_url: str, language=None) -> str:
    """Download the video's audio and return its full transcript text.

    Prefers Groq (fast, cloud); falls back to local faster-whisper if there is
    no GROQ_API_KEY or Groq fails. Raises only if BOTH paths fail.
    """
    with tempfile.TemporaryDirectory() as d:
        dp = pathlib.Path(d)
        wav = _download_wav(video_url, dp)
        key = os.environ.get("GROQ_API_KEY")
        if key:
            try:
                text = _groq_transcribe(wav, dp, key, language)
                if text.strip():
                    return text
            except Exception:
                pass  # fall through to local offline transcription
        return _local_transcribe(wav, language)
