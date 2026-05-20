import os, subprocess, tempfile, pathlib, base64, httpx

MODEL = os.environ.get("STUDIO_TRANSCRIBE_MODEL", "gemma4:e4b")
CHUNK = int(os.environ.get("STUDIO_TRANSCRIBE_CHUNK_SEC", "300"))
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
PROMPT = "Transcribe this Mandarin audio verbatim. Output plain text only, no commentary."

def _chunk_ranges(total_sec: int, chunk: int) -> list[tuple[int, int]]:
    """Return [(start, end), ...] second ranges covering total_sec in chunk-sized steps."""
    out, s = [], 0
    while s < total_sec:
        out.append((s, min(s + chunk, total_sec))); s += chunk
    return out or [(0, total_sec)]

def _audio_duration(path: str) -> int:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
        "format=duration", "-of", "default=nw=1:nk=1", path],
        capture_output=True, text=True, check=True)
    return int(float(r.stdout.strip() or "0"))

def _transcribe_chunk(wav_path: str) -> str:
    """Transcribe a single WAV chunk using gemma4:e4b via OpenAI-compatible API."""
    with open(wav_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "input_audio", "input_audio": {"data": b64, "format": "wav"}},
                ],
            }
        ],
        "stream": False,
    }
    resp = httpx.post(f"{OLLAMA_HOST}/v1/chat/completions", json=payload, timeout=600.0)
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()

def transcribe(video_url: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        dp = pathlib.Path(d)
        # Extract audio to wav directly via yt-dlp+ffmpeg; avoids container mismatch
        # when best-audio is webm/opus (which yt-dlp would name a.m4a but actually isn't).
        subprocess.run([
            "yt-dlp", "-f", "bestaudio", "-x",
            "--audio-format", "wav", "--audio-quality", "0",
            "-o", str(dp / "a.%(ext)s"), "--quiet", video_url,
        ], check=True)
        raw_wavs = list(dp.glob("a.*"))
        if len(raw_wavs) != 1 or raw_wavs[0].suffix.lower() != ".wav":
            raise RuntimeError(f"yt-dlp did not produce a.wav; found: {[f.name for f in raw_wavs]}")
        wav = str(dp / "norm.wav")
        subprocess.run(["ffmpeg", "-y", "-i", str(raw_wavs[0]), "-ac", "1", "-ar", "16000", wav],
                       capture_output=True, check=True)
        dur = _audio_duration(wav)
        parts = []
        for (s, e) in _chunk_ranges(dur, CHUNK):
            c = str(pathlib.Path(d) / f"c_{s}.wav")
            subprocess.run(["ffmpeg", "-y", "-i", wav, "-ss", str(s), "-to", str(e), c],
                           capture_output=True, check=True)
            parts.append(_transcribe_chunk(c))
        return "\n".join(p for p in parts if p)
