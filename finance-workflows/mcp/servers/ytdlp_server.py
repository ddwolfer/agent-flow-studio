import yt_dlp
from mcp.server.fastmcp import FastMCP
import sys, pathlib as _pl, os, re, tempfile, shutil, time, threading
sys.path.insert(0, str(_pl.Path(__file__).parents[1] / "lib"))
try:
    import whisper_transcribe as _asr
except Exception:
    _asr = None

# ── self-throttle ───────────────────────────────────────────────────────────────
# YouTube rate-limits bursts: a daily run hits 5+ channels' /videos + captions in
# quick succession and the later channels get blocked (anonymous rate ceiling).
# Diagnosis showed each request works fine in isolation — only the burst trips it.
# So we space every YouTube-hitting call by at least _MIN_GAP seconds, process-wide.
# (The MCP server is one long-lived process, so this state persists across tool calls.)
_MIN_GAP = float(os.environ.get("STUDIO_YTDLP_MIN_GAP", "4"))
_throttle_lock = threading.Lock()
_last_hit = [0.0]


def _throttle():
    with _throttle_lock:
        wait = _MIN_GAP - (time.monotonic() - _last_hit[0])
        if wait > 0:
            time.sleep(wait)
        _last_hit[0] = time.monotonic()


# ── cookies ──────────────────────────────────────────────────────────────────────
# A logged-in YouTube session (exported cookies.txt) raises the rate-limit ceiling
# so a daily multi-channel burst isn't blocked. We use a cookie FILE, not
# --cookies-from-browser, because the latter hangs headless on macOS (Keychain
# prompt) and would stall the launchd cron.
COOKIES_FILE = os.environ.get("STUDIO_YTDLP_COOKIES_FILE", "")

# EJS challenge solver (needs a JS runtime, e.g. `brew install deno`). Without it,
# YouTube's "n challenge" intermittently hides all real formats ("Only images are
# available") and bestaudio download fails. With it, formats reappear. Disable by
# setting STUDIO_YTDLP_EJS=0.
_EJS = ["ejs:github"] if os.environ.get("STUDIO_YTDLP_EJS", "1") != "0" else None


def _harden_opts(opts: dict) -> dict:
    """Add the YouTube-access hardening shared by every extract call: logged-in
    cookies (rate-limit ceiling) + EJS remote components (n-challenge solver)."""
    if COOKIES_FILE and os.path.exists(COOKIES_FILE):
        opts["cookiefile"] = COOKIES_FILE
    if _EJS:
        opts["remote_components"] = _EJS
    return opts

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


def _map_entries(info: dict) -> list[dict]:
    out = []
    for e in (info.get("entries") or []):
        d = e.get("upload_date") or ""
        iso = f"{d[0:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d
        out.append({"video_id": e.get("id"), "title": e.get("title"),
                    "upload_date": iso,
                    "url": e.get("webpage_url") or f"https://youtu.be/{e.get('id')}",
                    # None = public on the newer lockup listing path; never treat
                    # None as restricted.
                    "availability": e.get("availability"),
                    "live_status": e.get("live_status")})
    return out


def _map_search(info: dict, max_results: int):
    return _map_entries(info)[:max_results]


# Uploads no anonymous route can read: captions, audio and every third-party
# transcript service all fail on these, so trying them only burns YouTube
# requests. Coin Bureau publishes "Coin Bureau Club" members-only videos into
# the same /videos tab — on 2026-10-07, 4 of its newest 8 were subscriber_only.
_UNREADABLE_AVAILABILITY = frozenset({"subscriber_only", "premium_only",
                                      "needs_auth", "private"})
_UNREADABLE_LIVE = frozenset({"is_upcoming", "is_live"})


def _is_readable(entry: dict) -> bool:
    return (entry.get("availability") not in _UNREADABLE_AVAILABILITY
            and entry.get("live_status") not in _UNREADABLE_LIVE)


# video_url -> creator-written metadata (title/description/chapters) from the
# caption probe — the last-resort "description" source when no speech is
# obtainable. Costs no extra YouTube request.
_VIDEO_META: dict[str, dict] = {}

# video_url -> original spoken language reported by YouTube (e.g. "en", "zh-TW"),
# remembered from the caption probe so the whisper fallback can transcribe in
# the right language instead of assuming Chinese.
_VIDEO_LANG: dict[str, str] = {}


def _primary(lang: str | None) -> str:
    return (lang or "").split("-")[0].lower()


def _track_query(url: str) -> dict:
    from urllib.parse import parse_qs, urlparse
    return {k: v[0] for k, v in parse_qs(urlparse(url).query).items() if v}


def _caption_candidates(info: dict, langs: list[str]) -> list[tuple[str, dict]]:
    """Ordered (label, track) list of caption tracks that are VERBATIM speech.

    1. Uploader-provided `subtitles` in `langs` order (human-made).
    2. Auto-generated ASR tracks in the video's ORIGINAL language only.

    YouTube's `automatic_captions` also lists machine TRANSLATIONS of the ASR
    into ~150 languages (timedtext URL carries `tlang=`). On auto-dubbed videos
    there are further ASR tracks of each dubbed audio track (`ar-orig`,
    `ja-orig`, ...). Regression 2026-10-07: for an English Altcoin Daily video
    the first "zh-Hant" track was Arabic-dub ASR machine-translated into
    Chinese — a translation of a translation, quoted in the report as if it
    were the speaker's words. faithfulness.md forbids exactly that, so
    translated tracks are never candidates; a wrong-language video falls
    through to whisper instead.
    """
    out = []
    for lang in langs:
        for t in (info.get("subtitles") or {}).get(lang) or []:
            out.append((f"subtitles:{lang}", t))

    orig = _primary(info.get("language"))
    auto = []
    for key, tracks in (info.get("automatic_captions") or {}).items():
        for t in tracks or []:
            q = _track_query(t.get("url") or "")
            if q.get("tlang"):
                continue                                   # machine translation
            spoken = _primary(q.get("lang") or key.removesuffix("-orig"))
            if orig and spoken != orig:
                continue                                   # dubbed-track ASR
            if not orig and key.removesuffix("-orig") not in langs:
                continue
            auto.append((f"auto:{key}", t))
    # Prefer keys the caller asked for, then the rest (stable within each).
    rank = {l: i for i, l in enumerate(langs)}
    auto.sort(key=lambda kt: rank.get(kt[0][5:].removesuffix("-orig"), len(langs)))
    return out + auto


def _open_caption(ydl, track: dict) -> str:
    """GET one caption track through the YoutubeDL session.

    yt-dlp marks every YouTube subtitle entry `impersonate: True`; its own
    subtitle downloader then sends a curl_cffi browser TLS fingerprint plus the
    entry's http_headers. Mirror that here so the request looks like the one
    yt-dlp itself would make. If no impersonation handler is installed
    (curl_cffi missing / out of yt-dlp's supported range) fall back to a plain
    session request instead of failing the track.
    """
    from yt_dlp.networking import Request
    from yt_dlp.networking.exceptions import NoSupportingHandlers
    headers = track.get("http_headers") or {}
    if track.get("impersonate"):
        from yt_dlp.networking.impersonate import ImpersonateTarget
        req = Request(track["url"], headers=headers,
                      extensions={"impersonate": ImpersonateTarget()})
        try:
            with ydl.urlopen(req) as resp:
                return resp.read().decode("utf-8", "replace")
        except NoSupportingHandlers:
            pass
    with ydl.urlopen(Request(track["url"], headers=headers)) as resp:
        return resp.read().decode("utf-8", "replace")


def _description_source(meta: dict) -> str:
    """Creator-written text for a video with no obtainable speech.

    Title + chapter list + description with URLs removed (descriptions are
    mostly affiliate/sponsor links). This is NOT what was said in the video —
    the "description" source label carries that to the report layer."""
    parts = [f"標題:{meta.get('title') or ''}"]
    chapters = meta.get("chapters") or []
    if chapters:
        parts.append("章節:")
        for c in chapters:
            sec = int(c.get("start_time") or 0)
            parts.append(f"  {sec // 60:02d}:{sec % 60:02d} {c.get('title') or ''}")
    desc_lines = []
    for line in (meta.get("description") or "").splitlines():
        line = re.sub(r"https?://\S+", "", line).strip()
        if line and not re.fullmatch(r"[\W_]+", line):
            desc_lines.append(line)
    if desc_lines:
        parts.append("說明欄:")
        parts.extend(desc_lines)
    return "\n".join(parts)[:6000]


def _looks_like_vtt(text: str) -> bool:
    """A real caption track starts with the WEBVTT header (optionally after a BOM).

    Anything else — notably Google's 429 "Sorry..." bot-check HTML page — must
    be rejected, not cleaned and passed off as a transcript."""
    return (text or "").lstrip("﻿ \t\r\n").startswith("WEBVTT")


def _fetch_captions(video_url: str, langs: list[str]) -> str | None:
    """
    Fetch captions via yt_dlp, returning raw text WITHOUT writing any files to cwd.
    Uses a TemporaryDirectory as the working path so no .vtt/.srt files leak.

    The caption URL is fetched through the SAME YoutubeDL session
    (`ydl.urlopen`) that extracted it, so it carries the session's cookies,
    User-Agent and client headers. Regression 2026-10-07: a bare
    `requests.get` on the timedtext URL got HTTP 429 + Google's "Sorry..."
    bot-check page, while `ydl.urlopen` on the very same URL returned real
    WEBVTT. Worse, that HTML was accepted as "captions", so the whisper
    fallback never ran and the report said 「字幕抓取回傳 Google 反機器人頁面」.

    Returns None when there is no usable text track (caller falls back to ASR).
    Raises RuntimeError when tracks existed but every fetch was rejected, so
    the reason survives into the transcript `error` field if ASR also fails.
    """
    _throttle()
    tmpdir = tempfile.mkdtemp(prefix="ytdlp_caps_")
    rejected = []
    try:
        opts = {
            "skip_download": True,
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": langs,
            "quiet": True,
            # Unplayable videos (premieres, format-less) still yield metadata.
            "ignore_no_formats_error": True,
            # Redirect any file writes into the tmpdir (then we delete it)
            "paths": {"home": tmpdir},
            "outtmpl": {"default": "%(id)s.%(ext)s", "subtitle": "%(id)s.%(ext)s"},
        }
        with yt_dlp.YoutubeDL(_harden_opts(opts)) as ydl:
            info = ydl.extract_info(video_url, download=False)
            if info.get("language"):
                _VIDEO_LANG[video_url] = info["language"]
            _VIDEO_META[video_url] = {k: info.get(k) for k in
                                      ("title", "description", "chapters")}
            for label, s in _caption_candidates(info, langs):
                # Only directly-downloadable VTT. Skip HLS/m3u8 subtitle variants:
                # their "url" is an .m3u8 manifest, and a plain GET returns the
                # manifest text, not captions (this silently corrupted a source).
                proto = s.get("protocol") or ""
                url = s.get("url") or ""
                if (s.get("ext") != "vtt" or proto.startswith("m3u8")
                        or "manifest" in url or not url):
                    continue
                try:
                    t = _open_caption(ydl, s)
                except Exception as e:
                    rejected.append(f"{label}: {type(e).__name__}: {e}")
                    continue
                if _looks_like_vtt(t):
                    return t
                rejected.append(f"{label}: non-VTT response "
                                f"({t.strip()[:60]!r} — bot-check page?)")
    finally:
        # Always clean up the temp directory, removing any written subtitle files
        shutil.rmtree(tmpdir, ignore_errors=True)
    if rejected:
        raise RuntimeError("caption tracks found but none usable: "
                           + "; ".join(rejected[:3]))
    return None


def _get_full_transcript(video_url: str, language: str = "zh-Hant") -> dict:
    """Fetch + clean the FULL transcript once per video_url (cached). No truncation.

    Returns {"source": "captions"|"whisper"|"description"|"none", "text": str}.
    "description" = no speech obtainable; text is the creator's title/chapters/
    description (NOT a transcript) and `error` still says why speech failed.
    """
    cached = _TRANSCRIPT_CACHE.get(video_url)
    if cached is not None:
        return cached
    result = {"source": "none", "text": ""}
    errors = []
    # 1) Try captions. A caption-fetch FAILURE (e.g. YouTube rate-limit / 503 raised
    #    inside extract_info) must NOT abort the whisper fallback — so it gets its
    #    own try block. (Previously a captions exception jumped to the outer except
    #    and the fallback branch was never reached.)
    raw = None
    try:
        raw = _fetch_captions(video_url, [language, "zh-TW", "zh-Hant", "zh", "en"])
    except Exception as e:
        errors.append(f"captions: {e}")
    if raw:
        result = {"source": "captions", "text": _clean_transcript(raw)}
    elif _asr is not None:
        # 2) Audio fallback: download audio + transcribe locally via faster-whisper.
        try:
            t = _asr.transcribe(video_url, language=_VIDEO_LANG.get(video_url))
            if t and t.strip():
                result = {"source": "whisper", "text": _clean_transcript(t)}
            else:
                errors.append("whisper: empty transcript")
        except Exception as e:
            errors.append(f"whisper: {e}")
    if result["source"] == "none":
        meta = _VIDEO_META.get(video_url) or {}
        if (meta.get("description") or "").strip() or meta.get("chapters"):
            result = {"source": "description", "text": _description_source(meta)}
    if result["source"] in ("none", "description") and errors:
        result["error"] = "transcript failed: " + "; ".join(errors)
    # Cache key is video_url only; assumes a consistent language per URL within a session.
    _TRANSCRIPT_CACHE[video_url] = result
    return result


mcp = FastMCP("yt-dlp")

@mcp.tool()
def ytdlp_search_videos(query: str, maxResults: int = 1, uploadDateFilter: str = "today"):
    """Search YouTube; returns [{video_id,title,upload_date,url}]."""
    spec = f"ytsearch{max(maxResults,1)*3}:{query}"
    _throttle()
    with yt_dlp.YoutubeDL(_harden_opts({"quiet": True, "extract_flat": True})) as ydl:
        info = ydl.extract_info(spec, download=False)
    return _map_search(info, maxResults)

@mcp.tool()
def ytdlp_latest_from_channel(handle: str, max_results: int = 5):
    """Fetch the latest videos from a YouTube channel by handle OR channel-ID.

    `handle` accepts either:
      - a handle like '@crypto_punks' (or 'crypto_punks'), → /@handle/videos
      - a permanent channel ID like 'UCRvqjQPSeaWn-uEx-w0XOIg', → /channel/<id>/videos
        (use the channel ID when a handle 404s or changes — IDs are permanent).

    Hits the channel's /videos page directly via extract_flat — more reliable than
    `ytdlp_search_videos` for a specific channel's recent uploads (keyword search can
    return unrelated channels when the handle name isn't unique).

    Returns [{video_id, title, upload_date, url, availability, live_status}]
    newest-first. Members-only / upcoming / live entries are skipped so the
    caller gets the newest video that can actually be transcribed; if EVERY
    recent entry is unreadable they are returned as-is (availability tells the
    caller why) rather than an empty list that would read as "no uploads".
    Never raises → [] on failure.
    """
    h = (handle or "").strip().lstrip("@")
    if not h:
        return []
    if re.fullmatch(r"UC[0-9A-Za-z_-]{20,}", h):
        url = f"https://www.youtube.com/channel/{h}/videos"
    else:
        url = f"https://www.youtube.com/@{h}/videos"
    try:
        _throttle()
        n = max(int(max_results), 1)
        # Over-fetch so skipping members-only uploads still leaves n entries;
        # still one listing request.
        opts = {"quiet": True, "extract_flat": True, "playlistend": n + 8}
        with yt_dlp.YoutubeDL(_harden_opts(opts)) as ydl:
            info = ydl.extract_info(url, download=False)
    except Exception:
        return []
    entries = _map_entries(info)
    readable = [e for e in entries if _is_readable(e)]
    return (readable or entries)[:n]

@mcp.tool()
def ytdlp_download_transcript(video_url: str, language: str = "zh-Hant"):
    """
    Return the cleaned, bounded transcript text inline.

    Result shape: {source, text, full_chars, truncated}
    - source: "captions" | "whisper" | "description" | "none"
      ("description" = creator's title/chapters/description, NOT speech)
    - text: cleaned plain text (VTT markup stripped, consecutive dups removed);
            if truncated=True, contains head + "[...middle elided N chars...]" + tail
    - full_chars: character count of the fully cleaned text (before any elision)
    - truncated: true if text was larger than STUDIO_TRANSCRIPT_MAX_CHARS and was elided

    NO subtitle files are written to disk. Always returns a structured dict (never raises).

    Shares _get_full_transcript's cascade (and cache) with ytdlp_transcript_page,
    so a caption failure falls through to whisper here too — this tool used to
    carry its own copy of the cascade where a caption exception skipped ASR.
    """
    try:
        info = _get_full_transcript(video_url, language)
    except Exception as e:
        return {"source": "none", "text": "", "full_chars": 0, "truncated": False,
                "error": f"transcript failed: {e}"}
    if info.get("source", "none") == "none":
        out = {"source": "none", "text": "", "full_chars": 0, "truncated": False}
        if "error" in info:
            out["error"] = info["error"]
        return out
    out = {"source": info["source"], **_bound_transcript(info["text"])}
    if "error" in info:
        out["error"] = info["error"]          # "description": why speech failed
    return out

@mcp.tool()
def ytdlp_transcript_page(video_url: str, page: int = 0,
                          page_size: int = 12000, language: str = "zh-Hant"):
    """
    Return ONE page of the FULL cleaned transcript (no head/tail elision).

    The full transcript is fetched+cleaned once per video_url and cached, so
    paging through it is cheap. Each page is small enough for a single MCP
    tool result. Page through 0..total_pages-1 to read the entire transcript.

    Result: {source, page, total_pages, full_chars, text}
      - source: "captions" | "whisper" | "description" | "none"
        ("description" = no speech obtainable; text is the creator's title/
        chapters/description — NOT a transcript, never quote it as speech)
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
