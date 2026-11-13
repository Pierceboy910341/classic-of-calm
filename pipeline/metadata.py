"""youtube.txt: title, description (with chapters + tracklist, Bestiary Card, AI disclosure), tags.

The plan.json ``youtube`` block written by the copywriter is the source of truth; this module
only fills in what must come from the finished audio (length label, chapter timestamps) and
adds the Bestiary Card / AI disclosure if the copy is missing them.
"""
from __future__ import annotations

import re
from pathlib import Path

from .common import fmt_ts, save_json, series_name

AI_DISCLOSURE = ("Music and artwork are generated with commercially licensed AI tools, then curated, "
                 "edited and mastered by a small human team. There are no invented \"artists\" here.")
DEFAULT_TAGS = {
    "study": ["study lofi", "lofi hip hop", "chinese lofi", "guzheng lofi", "study music", "focus music"],
    "sleep": ["sleep music", "lofi sleep", "chinese ambient", "guqin", "xiao flute", "relaxing music"],
    "work": ["work lofi", "chill beats", "chinese lofi", "pipa", "lofi cafe", "work music"],
}
COMMON_TAGS = ["Shan Hai Jing", "Classic of Mountains and Seas", "Classic of Calm", "AI music"]
USE_WORD = {"study": "Study", "sleep": "Sleep", "work": "Work"}


def length_label(seconds: float) -> str:
    m = seconds / 60
    if m < 50:
        return f"{max(1, int(round(m)))} min"
    if m < 80:
        return "1 hour"
    if m < 105:
        return "1.5 hours"
    return f"{int(round(m / 60))} hours"


def build_title(plan: dict, duration_s: float) -> str:
    yt = plan.get("youtube") or {}
    label = length_label(duration_s)
    title = yt.get("title")
    if title:
        if re.search(r"\[[^\]]*(hour|min)[^\]]*\]", title):
            return re.sub(r"\[[^\]]*(hour|min)[^\]]*\]", f"[{label}]", title)
        return title
    s = series_name(plan.get("series"))
    cre = plan.get("creature") or {}
    no = cre.get("no")
    tail = f" | Classic of Calm No.{int(no):02d}" if no is not None else " | Classic of Calm"
    inst = {"study": "guzheng & jazz beats", "sleep": "xiao & guqin ambient", "work": "pipa & acoustic beats"}[s]
    who = f" with {cre['en']}" if cre.get("en") else ""
    return f"{USE_WORD[s]} lofi{who} 🏔 {inst} [{label}]{tail}"


def chapter_lines(chapters: list[dict], with_notes: bool = True) -> list[str]:
    lines = []
    for i, c in enumerate(chapters):
        ts = "0:00" if i == 0 else fmt_ts(c["start_s"])
        t = c.get("title_en") or f"Track {i + 1}"
        if c.get("title_zh"):
            t += f" · {c['title_zh']}"
        if with_notes and c.get("lore_note"):
            t += f" — {c['lore_note']}"
        lines.append(f"{ts} {t}")
    return lines


def bestiary_card(cre: dict) -> str:
    if not cre:
        return ""
    head = f"📜 BESTIARY CARD · No.{int(cre['no']):02d}" if cre.get("no") is not None else "📜 BESTIARY CARD"
    lines = [f"{head} · {cre.get('zh', '')} {cre.get('en', '')}".rstrip()]
    if cre.get("source"):
        lines.append(f"Source: {cre['source']}")
    if cre.get("quote_zh"):
        lines.append(f"「{cre['quote_zh'].strip('「」')}」")
    if cre.get("quote_en"):
        lines.append(f"\"{cre['quote_en'].strip(chr(34))}\"")
    lines.append("(English rendering is our own; the original text is in the public domain.)")
    return "\n".join(lines)


def build_description(plan: dict, chapters: list[dict]) -> str:
    yt = plan.get("youtube") or {}
    cre = plan.get("creature") or {}
    base = (yt.get("description") or "").strip()
    for with_notes in (True, False):
        track_block = "⏱ Tracklist\n" + "\n".join(chapter_lines(chapters, with_notes))
        if base:
            paras = base.split("\n\n")
            idx = next((i for i, p in enumerate(paras) if "BESTIARY CARD" in p.upper()), min(2, len(paras)))
            desc = "\n\n".join(paras[:idx] + [track_block] + paras[idx:])
        else:
            s = series_name(plan.get("series"))
            intro = (f"{USE_WORD[s]} lofi from the Shan Hai Jing (Classic of Mountains and Seas)"
                     + (f" — Bestiary No.{int(cre['no']):02d}: {cre.get('en', '')}." if cre.get("no") is not None else "."))
            desc = intro + "\n\n" + track_block
        if cre.get("quote_zh") and cre["quote_zh"][:8] not in desc:
            desc += "\n\n" + bestiary_card(cre)
        if "AI" not in desc:
            desc += "\n\n🤖 " + AI_DISCLOSURE
        if len(desc) <= 5000:
            break
    return desc


def build_tags(plan: dict, limit: int = 500) -> list[str]:
    s = series_name(plan.get("series"))
    raw = list((plan.get("youtube") or {}).get("tags") or []) + DEFAULT_TAGS[s] + COMMON_TAGS
    out, seen, total = [], set(), 0
    for t in raw:
        t = str(t).strip()
        k = t.lower()
        if not t or k in seen:
            continue
        cost = len(t) + (2 if " " in t else 0) + (1 if out else 0)  # YouTube counts quotes + commas
        if total + cost > limit:
            continue
        out.append(t)
        seen.add(k)
        total += cost
    return out


def check(title: str, desc: str, tags: list[str], chapters: list[dict]) -> list[str]:
    notes = []
    if len(title) > 100:
        notes.append(f"❌ title is {len(title)} chars (max 100)")
    head = title[:60].lower()
    if not any(w in head for w in ("study", "sleep", "work")) or "lofi" not in head and "music" not in head:
        notes.append("⚠️ first 60 chars should contain Study/Sleep/Work + lofi")
    if len(desc) > 5000:
        notes.append(f"❌ description is {len(desc)} chars (max 5000)")
    if len(chapters) < 3:
        notes.append("⚠️ YouTube needs >= 3 chapters for chapter markers")
    gaps = [b["start_s"] - a["start_s"] for a, b in zip(chapters, chapters[1:])]
    if gaps and min(gaps) < 10:
        notes.append("⚠️ a chapter is shorter than 10 s (YouTube ignores chapter lists then)")
    if not notes:
        notes.append("✅ title / description / tags / chapters within YouTube limits")
    return notes


def write_youtube_txt(plan: dict, chapters: list[dict], duration_s: float, out_dir: str | Path) -> dict:
    out_dir = Path(out_dir)
    title = build_title(plan, duration_s)
    desc = build_description(plan, chapters)
    tags = build_tags(plan)
    notes = check(title, desc, tags, chapters)
    txt = "\n".join([
        "=== TITLE ===", title, "",
        "=== DESCRIPTION ===", desc, "",
        "=== TAGS ===", ", ".join(tags), "",
        "=== CHECKS ===", *notes, f"duration {fmt_ts(duration_s, True)} · {len(chapters)} chapters", "",
        "=== UPLOAD CHECKLIST ===",
        "1. Upload compilation.mp4, paste title / description / tags, set thumbnail.png",
        "2. Audience: No, it's not made for kids",
        "3. Altered or synthetic content: YES (every upload)",
        "4. Add to the Study / Sleep / Work playlist",
    ]) + "\n"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "youtube.txt").write_text(txt, encoding="utf-8")
    meta = {"title": title, "description": desc, "tags": tags, "checks": notes,
            "duration_s": round(duration_s, 2), "chapters": chapters}
    save_json(out_dir / "metadata.json", meta)
    return meta
