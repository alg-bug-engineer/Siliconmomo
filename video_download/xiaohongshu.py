#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Standalone XiaoHongShu (小红书) page extractor.

- No dependency on yt-dlp codebase
- Only external dependency: requests (pip install requests)

Usage:
  python xiaohongshu_extractor_standalone.py "https://www.xiaohongshu.com/explore/<id>"

Output:
  Prints a JSON dict similar to yt-dlp's info_dict:
  {
    "id": "...",
    "title": "...",
    "description": "...",
    "uploader_id": "...",
    "tags": [...],
    "formats": [...],
    "thumbnails": [...]
  }
"""

from __future__ import annotations

import ast
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import requests
except ImportError as e:
    raise SystemExit("Missing dependency: requests. Install with: pip install requests") from e


# ---------------------------
# Minimal "utils" equivalents
# ---------------------------

def int_or_none(v: Any) -> Optional[int]:
    try:
        if v is None:
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def float_or_none(v: Any, *, scale: float = 1.0) -> Optional[float]:
    try:
        if v is None:
            return None
        return float(v) / float(scale)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def url_or_none(u: Any) -> Optional[str]:
    if not isinstance(u, str):
        return None
    u = u.strip()
    if not u:
        return None
    if u.startswith("http://") or u.startswith("https://"):
        return u
    return None


def _html_unescape(s: str) -> str:
    # Minimal HTML entity decoding
    return (
        s.replace("&amp;", "&")
         .replace("&quot;", '"')
         .replace("&#39;", "'")
         .replace("&lt;", "<")
         .replace("&gt;", ">")
    )


def html_search_meta(names: List[str], html: str) -> Optional[str]:
    """
    Search <meta property="og:title" content="..."> or <meta name="...">
    """
    for name in names:
        # property=
        m = re.search(
            r'<meta[^>]+(?:property|name)\s*=\s*["\']%s["\'][^>]+content\s*=\s*["\']([^"\']+)["\']'
            % re.escape(name),
            html,
            flags=re.IGNORECASE,
        )
        if m:
            return _html_unescape(m.group(1)).strip()
    return None


# ---------------------------
# JS object -> JSON-ish parser
# ---------------------------

_RE_LINE_COMMENT = re.compile(r"//[^\n\r]*")
_RE_BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)

def js_to_json(js: str) -> str:
    """
    A practical (not perfect) JS-to-JSON converter sufficient for many embedded states.
    Strategy:
      - strip JS comments
      - replace undefined with null
      - quote unquoted keys in object literals
      - convert single-quoted strings to double-quoted strings where safe
      - remove trailing commas
    """
    s = js.strip()

    # Remove comments
    s = _RE_BLOCK_COMMENT.sub("", s)
    s = _RE_LINE_COMMENT.sub("", s)

    # Replace undefined -> null
    s = re.sub(r"\bundefined\b", "null", s)

    # Quote unquoted keys: {foo: 1} -> {"foo": 1}
    # Note: this is heuristic; works for typical JSON-like objects.
    s = re.sub(
        r'([{\[,]\s*)([A-Za-z_$][A-Za-z0-9_$]*)(\s*:)',
        r'\1"\2"\3',
        s
    )

    # Convert single-quoted strings to double-quoted strings (heuristic)
    # Handles escaped quotes inside.
    def _sq_to_dq(m: re.Match) -> str:
        inner = m.group(1)
        inner = inner.replace('\\', '\\\\').replace('"', '\\"')
        inner = inner.replace("\\'", "'")
        return '"' + inner + '"'

    s = re.sub(r"'((?:[^'\\]|\\.)*)'", _sq_to_dq, s)

    # Remove trailing commas: {"a":1,} or [1,2,]
    s = re.sub(r",\s*([}\]])", r"\1", s)

    return s


def extract_balanced_json(text: str, start_pos: int) -> Tuple[str, int]:
    """
    Given text and a start position where the next non-space char is '{' or '[',
    return the balanced JSON/JS object substring and end index (exclusive).
    """
    n = len(text)
    i = start_pos
    while i < n and text[i].isspace():
        i += 1
    if i >= n or text[i] not in "{[":
        raise ValueError("Expected '{' or '[' at start_pos")

    open_ch = text[i]
    close_ch = "}" if open_ch == "{" else "]"
    depth = 0
    in_str: Optional[str] = None  # "'" or '"'
    esc = False

    j = i
    while j < n:
        ch = text[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == in_str:
                in_str = None
        else:
            if ch in ("'", '"'):
                in_str = ch
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    return text[i : j + 1], j + 1
        j += 1

    raise ValueError("Unbalanced JSON/JS object")


def search_json(prefix_pattern: str, text: str) -> Dict[str, Any]:
    """
    Find JS assignment like:
      window.__INITIAL_STATE__ = {...}
    using a regex prefix, then parse the following object.
    """
    m = re.search(prefix_pattern, text)
    if not m:
        raise ValueError("Could not find JSON prefix pattern")

    # start scanning right after match
    start = m.end()
    # find first { or [
    m2 = re.search(r"[\{\[]", text[start:])
    if not m2:
        raise ValueError("Could not find JSON object start after prefix")
    obj_start = start + m2.start()

    raw_obj, _end = extract_balanced_json(text, obj_start)

    # First try strict JSON
    try:
        return json.loads(raw_obj)
    except Exception:
        pass

    # Try JS->JSON heuristic
    try:
        return json.loads(js_to_json(raw_obj))
    except Exception:
        pass

    # Last resort: python literal eval after mapping true/false/null
    # NOTE: still heuristic
    pyish = raw_obj
    pyish = re.sub(r"\btrue\b", "True", pyish)
    pyish = re.sub(r"\bfalse\b", "False", pyish)
    pyish = re.sub(r"\bnull\b", "None", pyish)
    pyish = re.sub(r"\bundefined\b", "None", pyish)
    try:
        return ast.literal_eval(pyish)
    except Exception as e:
        raise ValueError(f"Failed to parse embedded state as JSON/JS object: {e}") from e


# ---------------------------
# Extractor
# ---------------------------

@dataclass
class XiaoHongShuExtractor:
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
    timeout: int = 30

    _VALID_URL = re.compile(r"https?://www\.xiaohongshu\.com/explore/(?P<id>[\da-f]+)", re.IGNORECASE)

    def _download_webpage(self, url: str) -> str:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Connection": "close",
        }
        resp = requests.get(url, headers=headers, timeout=self.timeout)
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding or resp.encoding
        return resp.text

    def extract(self, url: str) -> Dict[str, Any]:
        m = self._VALID_URL.search(url)
        if not m:
            raise ValueError("Unsupported URL. Expected: https://www.xiaohongshu.com/explore/<hexid>")
        display_id = m.group("id")

        webpage = self._download_webpage(url)

        initial_state = search_json(r"window\.__INITIAL_STATE__\s*=\s*", webpage)

        # Equivalent to:
        # note_info = initial_state['note']['noteDetailMap'][display_id]['note']
        note_info = (
            initial_state.get("note", {})
                       .get("noteDetailMap", {})
                       .get(display_id, {})
                       .get("note")
        ) or {}

        # video_info = traverse_obj(note_info, ('video','media','stream', ('h264','av1','h265'), ...))
        streams = (
            note_info.get("video", {})
                     .get("media", {})
                     .get("stream", {})
        ) or {}

        video_info: List[Dict[str, Any]] = []
        for codec_key in ("h264", "av1", "h265"):
            v = streams.get(codec_key)
            if not v:
                continue
            if isinstance(v, list):
                video_info.extend([x for x in v if isinstance(x, dict)])
            elif isinstance(v, dict):
                # Sometimes stream[codec] can be a dict keyed by quality
                for vv in v.values():
                    if isinstance(vv, list):
                        video_info.extend([x for x in vv if isinstance(x, dict)])
                    elif isinstance(vv, dict):
                        video_info.append(vv)
            elif isinstance(v, (str, int, float)):
                # unexpected, ignore
                continue

        formats: List[Dict[str, Any]] = []
        for info in video_info:
            format_info = {
                "fps": int_or_none(info.get("fps")),
                "width": int_or_none(info.get("width")),
                "height": int_or_none(info.get("height")),
                "vcodec": str(info.get("videoCodec")) if info.get("videoCodec") is not None else None,
                "acodec": str(info.get("audioCodec")) if info.get("audioCodec") is not None else None,
                "abr": int_or_none(info.get("audioBitrate")),
                "vbr": int_or_none(info.get("videoBitrate")),
                "audio_channels": int_or_none(info.get("audioChannels")),
                "tbr": int_or_none(info.get("avgBitrate")),
                "format": str(info.get("qualityType")) if info.get("qualityType") is not None else None,
                "filesize": int_or_none(info.get("size")),
                "duration": float_or_none(info.get("duration"), scale=1000.0),
            }

            urls: List[str] = []
            u1 = url_or_none(info.get("mediaUrl"))
            if u1:
                urls.append(u1)

            backups = info.get("backupUrls")
            if isinstance(backups, list):
                for bu in backups:
                    buu = url_or_none(bu)
                    if buu:
                        urls.append(buu)

            for u in urls:
                formats.append({"url": u, **{k: v for k, v in format_info.items() if v is not None}})

        # thumbnails from imageList
        thumbnails: List[Dict[str, Any]] = []
        image_list = note_info.get("imageList")
        if isinstance(image_list, list):
            for image_info in image_list:
                if not isinstance(image_info, dict):
                    continue
                thumb_meta = {
                    "height": int_or_none(image_info.get("height")),
                    "width": int_or_none(image_info.get("width")),
                }
                for key in ("urlDefault", "urlPre"):
                    tu = url_or_none(image_info.get(key))
                    if tu:
                        thumbnails.append({"url": tu, **{k: v for k, v in thumb_meta.items() if v is not None}})

        # title: prefer note_info['title'], else og:title
        og_title = html_search_meta(["og:title"], webpage)
        title = note_info.get("title") if isinstance(note_info.get("title"), str) else None
        if not title:
            title = og_title

        description = note_info.get("desc") if isinstance(note_info.get("desc"), str) else None

        tags: List[str] = []
        tag_list = note_info.get("tagList")
        if isinstance(tag_list, list):
            for t in tag_list:
                if isinstance(t, dict) and isinstance(t.get("name"), str):
                    tags.append(t["name"])

        uploader_id = None
        user = note_info.get("user")
        if isinstance(user, dict) and isinstance(user.get("userId"), str):
            uploader_id = user["userId"]

        return {
            "id": display_id,
            "title": title,
            "description": description,
            "uploader_id": uploader_id,
            "tags": tags or None,
            "formats": formats,
            "thumbnails": thumbnails,
        }


# ---------------------------
# CLI
# ---------------------------

def main(argv: List[str]) -> int:
    if len(argv) < 2:
        print("Usage: python xiaohongshu_extractor_standalone.py <xiaohongshu_url>", file=sys.stderr)
        return 2

    url = argv[1].strip()
    ex = XiaoHongShuExtractor()
    info = ex.extract(url)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
