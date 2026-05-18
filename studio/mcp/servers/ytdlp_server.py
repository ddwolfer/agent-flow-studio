import yt_dlp
from mcp.server.fastmcp import FastMCP

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
    opts = {"skip_download": True, "writesubtitles": True,
            "writeautomaticsub": True, "subtitleslangs": langs, "quiet": True}
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
    return None

mcp = FastMCP("yt-dlp")

@mcp.tool()
def ytdlp_search_videos(query: str, maxResults: int = 1, uploadDateFilter: str = "today"):
    """Search YouTube; returns [{video_id,title,upload_date,url}]."""
    spec = f"ytsearch{max(maxResults,1)*3}:{query}"
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True}) as ydl:
        info = ydl.extract_info(spec, download=False)
    return _map_search(info, maxResults)

@mcp.tool()
def ytdlp_download_transcript(video_url: str, language: str = "zh-Hant"):
    """Transcript text. Tries captions zh-TW/zh-Hant/zh/en. (gemma fallback: next task.)"""
    txt = _fetch_captions(video_url, [language, "zh-TW", "zh-Hant", "zh", "en"])
    if txt:
        return {"source": "captions", "text": txt}
    return {"source": "none", "text": "", "note": "no captions; fallback pending"}

if __name__ == "__main__":
    mcp.run()
