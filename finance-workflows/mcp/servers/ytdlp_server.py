import yt_dlp
from mcp.server.fastmcp import FastMCP
import sys, pathlib as _pl, os, re, tempfile, shutil
sys.path.insert(0, str(_pl.Path(__file__).parents[1] / "lib"))
try:
    import gemma_transcribe as _gemma
except Exception:
    _gemma = None

# ── transcript size guard ──────────────────────────────────────────────────────
_MAX_CHARS = int(os.environ.get("STUDIO_TRANSCRIPT_MAX_CHARS", "48000"))
# head+tail split: keep 60 % head, 40 % tail (heuristic: Eason heavy picks toward end)
_HEAD_RATIO = 0.60

# video_url -> {"source": str, "text": str}  (full cleaned text, NOT truncated)
_TRANSCRIPT_CACHE: dict[str, dict] = {}


def _strip_vtt(raw: str) -> str:
    """Remove WEBVTT header, cue timestamps, <...> inline tags from a VTT/SRT blob."""
    lines = raw.splitlines()
    out = []
    for line in lines:
        # Skip WEBVTT header line
        if line.startswith("WEBVTT"):
            continue
        # Skip cue timing lines: "00:00:00.000 --> 00:00:03.000 ..." or "0:00 --> ..."
        if re.match(r"^[\d:]+\.\d+\s+-->\s+", line) or re.match(r"^[\d:]+\s+-->\s+", line):
            continue
        # Skip SRT sequence numbers (bare integer lines)
        if re.match(r"^\d+$", line.strip()):
            continue
        # Strip inline HTML/VTT tags like <00:00:03.400> <c> </c>
        cleaned = re.sub(r"<[^>]+>", "", line)
        # Strip optional VTT cue settings on pure timing lines already handled above
        out.append(cleaned)
    return "\n".join(out)


def _dedup_consecutive(text: str) -> str:
    """Remove consecutive duplicate non-empty lines (auto-captions repeat heavily)."""
    lines = text.splitlines()
    deduped = []
    prev = None
    for line in lines:
        stripped = line.strip()
        if stripped and stripped == prev:
            continue
        deduped.append(line)
        if stripped:
            prev = stripped
    return "\n".join(deduped)


def _collapse_blank_lines(text: str) -> str:
    """Collapse runs of 3+ blank lines into 1 blank line."""
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _clean_transcript(raw: str) -> str:
    """Full cleaning pipeline: strip VTT markup → dedup → collapse blanks."""
    text = _strip_vtt(raw)
    text = _dedup_consecutive(text)
    text = _collapse_blank_lines(text)
    return text


def _bound_transcript(text: str, max_chars: int = _MAX_CHARS) -> dict:
    """
    Return a dict with keys: text, full_chars, truncated.
    If len(text) <= max_chars → returned whole (truncated=False).
    Otherwise → head + elision marker + tail (truncated=True).
    """
    full_chars = len(text)
    if full_chars <= max_chars:
        return {"text": text, "full_chars": full_chars, "truncated": False}

    head_len = int(max_chars * _HEAD_RATIO)
    tail_len = max_chars - head_len
    elided = full_chars - head_len - tail_len
    head = text[:head_len]
    tail = text[full_chars - tail_len:]
    bounded = f"{head}\n\n[...middle elided {elided} chars...]\n\n{tail}"
    return {"text": bounded, "full_chars": full_chars, "truncated": True}


def _map_search(info: dict, max_results: int):
    out = []
    for e in (info.get("entries") or [])[:max_results]:
        d = e.get("upload_date") or ""
        iso = f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
        out.append({"video_id": e.get("id"), "title": e.get("title"),
                    "upload_date": iso,
                    "url": e.get("webpage_url") or f"https://youtu.be/{e.get('id')}"})
    return out


def _fetch_captions(video_url: str, langs: list[str]) -> str | None:
    """
    Fetch captions via yt_dlp, returning raw text WITHOUT writing any files to cwd.
    Uses a TemporaryDirectory as the working path so no .vtt/.srt files leak.
    """
    tmpdir = tempfile.mkdtemp(prefix="ytdlp_caps_")
    try:
        opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": langs,
            "quiet": True,
            # Redirect any file writes into the tmpdir (then we delete it)
            "paths": {"home": tmpdir},
            "outtmpl": {"default": "%(id)s.%(ext)s", "subtitle": "%(id)s.%(ext)s"},
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
        subs = {**(info.get("subtitles") or {}), **(info.get("automatic_captions") or {})}
        for lang in langs:
            if lang in subs and subs[lang]:
                import requests
                url = subs[lang][-1].get("url")
                if url:
                    t = requests.get(url, timeout=30).text
                    if t.strip():
                        return t
    finally:
        # Always clean up the temp directory, removing any written subtitle files
        shutil.rmtree(tmpdir, ignore_errors=True)
    return None


def _get_full_transcript(video_url: str, language: str = "zh-Hant") -> dict:
    """Fetch + clean the FULL transcript once per video_url (cached). No truncation.

    Returns {"source": "captions"|"gemma4:e4b"|"none", "text": str}.
    """
    cached = _TRANSCRIPT_CACHE.get(video_url)
    if cached is not None:
        return cached
    result = {"source": "none", "text": ""}
    errors = []
    # 1) Try captions. A caption-fetch FAILURE (e.g. YouTube rate-limit / 503 raised
    #    inside extract_info) must NOT abort the gemma fallback — so it gets its own
    #    try block. (Bug fix: previously a captions exception jumped to the outer
    #    except and the gemma `elif` branch was never reached → @BTV_CN showed
    #    "transcription error" instead of falling back to audio transcription.)
    raw = None
    try:
        raw = _fetch_captions(video_url, [language, "zh-TW", "zh-Hant", "zh", "en"])
    except Exception as e:
        errors.append(f"captions: {e}")
    if raw:
        result = {"source": "captions", "text": _clean_transcript(raw)}
    elif _gemma is not None:
        # 2) Audio fallback: download audio + transcribe locally via gemma4:e4b.
        try:
            t = _gemma.transcribe(video_url)
            if t and t.strip():
                result = {"source": "gemma4:e4b", "text": _clean_transcript(t)}
            else:
                errors.append("gemma: empty transcript")
        except Exception as e:
            errors.append(f"gemma: {e}")
    if result["source"] == "none" and errors:
        result["error"] = "transcript failed: " + "; ".join(errors)
    # Cache key is video_url only; assumes a consistent language per URL within a session.
    _TRANSCRIPT_CACHE[video_url] = result
    return result


mcp = FastMCP("yt-dlp")

@mcp.tool()
def ytdlp_search_videos(query: str, maxResults: int = 1, uploadDateFilter: str = "today"):
    """Search YouTube; returns [{video_id,title,upload_date,url}]."""
    spec = f"ytsearch{max(maxResults,1)*3}:{query}"
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
        info = ydl.extract_info(spec, download=False)
    return _map_search(info, maxResults)

@mcp.tool()
def ytdlp_latest_from_channel(handle: str, max_results: int = 5):
    """Fetch the latest videos from a YouTube channel handle (e.g. '@crypto_punks').

    Hits the channel's /videos page directly via extract_flat — more reliable than
    `ytdlp_search_videos` for finding a specific channel's recent uploads (the keyword
    search can return unrelated channels when the handle name isn't unique).

    Returns [{video_id, title, upload_date, url}] in chronological order (newest first
    as returned by YouTube). Never raises — returns [] on any failure.
    """
    h = (handle or "").lstrip("@")
    if not h:
        return []
    url = f"https://www.youtube.com/@{h}/videos"
    try:
        opts = {"quiet": True, "extract_flat": True,
                "playlistend": max(int(max_results), 1)}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return []
    return _map_search(info, max_results)

@mcp.tool()
def ytdlp_download_transcript(video_url: str, language: str = "zh-Hant"):
    """
    Return the cleaned, bounded transcript text inline.

    Result shape: {source, text, full_chars, truncated}
    - source: "captions" | "gemma4:e4b" | "none"
    - text: cleaned plain text (VTT markup stripped, consecutive dups removed);
            if truncated=True, contains head + "[...middle elided N chars...]" + tail
    - full_chars: character count of the fully cleaned text (before any elision)
    - truncated: true if text was larger than STUDIO_TRANSCRIPT_MAX_CHARS and was elided

    NO subtitle files are written to disk. Always returns a structured dict (never raises).
    """
    try:
        raw = _fetch_captions(video_url, [language, "zh-TW", "zh-Hant", "zh", "en"])
        if raw:
            cleaned = _clean_transcript(raw)
            bounded = _bound_transcript(cleaned)
            return {"source": "captions", **bounded}
        if _gemma is not None:
            text = _gemma.transcribe(video_url)
            if text and text.strip():
                cleaned = _clean_transcript(text)
                bounded = _bound_transcript(cleaned)
                return {"source": "gemma4:e4b", **bounded}
    except Exception as e:
        return {"source": "none", "text": "", "full_chars": 0, "truncated": False,
                "error": f"transcript failed: {e}"}
    return {"source": "none", "text": "", "full_chars": 0, "truncated": False}

@mcp.tool()
def ytdlp_transcript_page(video_url: str, page: int = 0,
                          page_size: int = 12000, language: str = "zh-Hant"):
    """
    Return ONE page of the FULL cleaned transcript (no head/tail elision).

    The full transcript is fetched+cleaned once per video_url and cached, so
    paging through it is cheap. Each page is small enough for a single MCP
    tool result. Page through 0..total_pages-1 to read the entire transcript.

    Result: {source, page, total_pages, full_chars, text}
      - source: "captions" | "gemma4:e4b" | "none"
      - total_pages: number of pages of size page_size (0 if no transcript)
      - full_chars: length of the full cleaned transcript
      - text: the requested page slice ("" if page is out of range)
    Never raises; on failure returns source="none", text="", total_pages=0.
    """
    info = _get_full_transcript(video_url, language)
    text = info.get("text") or ""
    full = len(text)
    size = max(int(page_size), 1)
    total = (full + size - 1) // size if full else 0
    start = int(page) * size
    slice_ = text[start:start + size] if 0 <= start < full else ""
    out = {"source": info.get("source", "none"), "page": int(page),
           "total_pages": total, "full_chars": full, "text": slice_}
    if "error" in info:
        out["error"] = info["error"]
    return out


if __name__ == "__main__":
    mcp.run()
