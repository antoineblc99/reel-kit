#!/usr/bin/env python3
"""build-reel.py — storyboard.json + transcript.json → compositions/*.html + index.html

Usage : python3 scripts/build-reel.py [storyboard.json]
Reads : storyboard.json (scenes, layouts, texts, captures), transcript.json (words start/end)
Writes: compositions/sNN-<layout>.html (one sub-composition per scene) and index.html (host:
        speaker video per scene, audio, scenes, captions).

Layouts: C = full-frame face on top + paper below · B = paper on top + face box below
         D = full-screen paper · F = full-frame video (face or screen shot) + tag / CTA card.
Blocks : headline, sub, note, card{rows|capture|logos}, mega, keyword, tag. See DESIGN.md.
"""
import hashlib
import html
import json
import pathlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SB = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "storyboard.json"
sb = json.loads(SB.read_text())
_tp = ROOT / "assets" / "transcript.json" if (ROOT / "assets" / "transcript.json").exists() else ROOT / "transcript.json"
transcript = json.loads(_tp.read_text()) if _tp.exists() else {"words": []}
FPS = int(sb.get("fps", 30))

W, H = (1920, 1080) if sb.get("format") == "youtube" else (1080, 1920)   # "youtube" = 16:9, layout Y
SPEAKER = sb.get("speaker", "assets/speaker.mp4")
AUDIO = sb.get("audio", "assets/reel-audio.wav")
DURATION = float(sb["duration"])
def kw_norm(t):
    """« d'Ingénieur, » → « ingénieur », « 40 825 » → « 40825 »: same form for keywords and transcript words."""
    t = re.sub(r"^(d|l|qu|n|s|j|c|m|t)['’]", "", t.lower())
    return re.sub(r"[^\w%]", "", t)


KEYWORDS = [kw_norm(k) for k in sb.get("keywords", [])]
LOCALE = sb.get("locale", "en-US")   # number formatting in count-ups: "40 825" in fr-FR, "40,825" in en-US
LANG = sb.get("lang", LOCALE.split("-")[0])
CAP_TOP = {"C": 850, "B": 940, "D": 1690, "F": 1500, "S": 780, "Y": 930}
CAP_MAX_WORDS = int(sb.get("caption_max_words", 4))
CAP_STYLE = sb.get("caption_style", "kit")          # "kit" = ink pill, uppercase · "pop" = Helvetica Neue Bold, keyword enlarged
CAP_FONT = sb.get("caption_font", '"Helvetica Neue", Helvetica, Arial, sans-serif')
CAP_ACCENT = sb.get("caption_accent", "var(--accent)")
CAP_SIZE = int(sb.get("caption_size", 64))

# ----------------------------------------------------------------------------- helpers

def snap(t):
    return round(round(float(t) * FPS) / FPS, 3)


def resolve_at(at, lo, hi):
    """`at` = seconds, or "w:word" = start of the first `word` spoken between lo and hi (word anchoring, Nate's rule)."""
    if isinstance(at, str) and at.startswith("w:"):
        target = re.sub(r"[^\w%']", "", at[2:].lower())
        for w in apply_lexicon(transcript.get("words", [])):
            if lo - 0.05 <= w["start"] <= hi and re.sub(r"[^\w%']", "", w["text"].lower()) == target:
                return round(w["start"], 3)
        raise SystemExit(f"anchor not found: {at} between {lo} and {hi}")
    return float(at)

def esc(s):
    return html.escape(s, quote=True)


def rich(s):
    """Text with <em> allowed, everything else escaped."""
    parts = re.split(r"(</?em>|<br\s*/?>)", s)
    return "".join(p if (p in ("<em>", "</em>") or p.startswith("<br")) else esc(p) for p in parts)


def r3(x):
    return f"{float(x):.3f}".rstrip("0").rstrip(".")


# ----------------------------------------------------------------------------- CSS shared by the scenes

SCENE_CSS = """
#root { position: absolute; inset: 0; width: __W__px; height: __H__px; overflow: hidden; color: var(--ink); }
.paper { position: absolute; background: var(--paper); }
.paper::before { content: ""; position: absolute; inset: 0; background-image: var(--tex-grain); opacity: .28; mix-blend-mode: multiply; }
.paper::after { content: ""; position: absolute; inset: 0; background-image: linear-gradient(var(--grid-line) 1px, transparent 1px), linear-gradient(90deg, var(--grid-line) 1px, transparent 1px); background-size: var(--grid-size) var(--grid-size); }
.content { position: absolute; left: 70px; right: 70px; }
.kicker { display: flex; justify-content: space-between; font: 700 var(--size-label)/1 var(--font-display); letter-spacing: var(--track-wide); text-transform: uppercase; color: var(--muted); }
.headline { margin: 30px 0 0; font: 900 96px/.92 var(--font-display); letter-spacing: var(--track-tight); text-transform: uppercase; text-shadow: 0 2px 0 rgba(255,255,255,.6), 0 3px 0 rgba(23,19,14,.18); }
.headline em, .mega em, .keyword em { font-style: normal; color: var(--accent-ink); }
.sub { margin: 16px 0 0 4px; font: italic 900 54px/1.05 var(--font-serif); color: var(--accent-ink); }
.note { position: absolute; font: 700 var(--size-hand)/1 var(--font-hand); color: var(--alarm); transform: rotate(-6deg); z-index: 2; }
.card { position: relative; margin-top: 44px; width: 940px; background: #f7f2e7; border: 1px solid rgba(23,19,14,.18); border-radius: var(--radius-card); box-shadow: var(--shadow-card); transform: rotate(var(--tilt)); padding: 30px 38px; }
.card .t { font: 700 24px/1 var(--font-display); letter-spacing: .14em; text-transform: uppercase; color: var(--muted); margin: 0 0 22px; }
.row { display: flex; align-items: center; justify-content: space-between; border-top: 2px dashed var(--line); padding: 22px 0; font: 900 var(--size-row)/1 var(--font-display); text-transform: uppercase; }
.row:last-child { border-bottom: 2px dashed var(--line); }
.row .n { color: var(--accent-ink); margin-right: 18px; }
.row .meta { font: 700 34px/1 var(--font-display); color: var(--muted); text-transform: none; }
.row .ok { display: inline-block; width: 52px; height: 52px; border: 3px solid var(--ink); border-radius: 50%; background: var(--accent); color: #fff; text-align: center; line-height: 46px; font-size: 34px; margin-left: 16px; }
.row .todo { display: inline-block; width: 52px; height: 52px; border: 3px dashed var(--line); border-radius: 50%; margin-left: 16px; }
.capture { position: relative; margin-top: 44px; width: 940px; background: #fff; border: 1px solid rgba(23,19,14,.18); border-radius: 10px; box-shadow: var(--shadow-card); transform: rotate(var(--tilt)); overflow: hidden; }
.capture .bar { display: flex; align-items: center; gap: 8px; height: 46px; padding: 0 16px; background: #eae4d6; border-bottom: 1px solid rgba(23,19,14,.12); font: 700 18px/1 var(--font-display); color: var(--muted); }
.capture .bar i { width: 12px; height: 12px; border-radius: 50%; background: rgba(23,19,14,.25); display: inline-block; }
.capture .win { position: relative; overflow: hidden; }
.capture .win img { display: block; width: 100%; height: auto; }
.capture .hl { position: absolute; background: rgba(242,106,27,.35); border: 3px solid var(--accent); border-radius: 6px; }
.logos { margin-top: 44px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 26px; width: 940px; }
.logos .l { background: #f7f2e7; border: 1px solid rgba(23,19,14,.18); border-radius: 10px; box-shadow: var(--shadow-card); height: 230px; display: grid; place-items: center; }
.logos .l img { width: 120px; height: 120px; object-fit: contain; }
.mega { margin: 110px 0 0; font: 900 200px/.86 var(--font-display); letter-spacing: var(--track-tight); text-transform: uppercase; text-shadow: 0 2px 0 rgba(255,255,255,.6), 0 4px 0 rgba(23,19,14,.18); }
.mega .l { display: block; }
.circle { position: absolute; border: 6px solid var(--alarm); border-radius: 50%; transform: rotate(-4deg); }
.tag { position: absolute; background: var(--ink); color: var(--paper); font: 700 26px/1 var(--font-display); letter-spacing: .14em; text-transform: uppercase; padding: 16px 22px; transform: rotate(-2deg); z-index: 2; }
.ov { position: absolute; left: 0; right: 0; text-align: center; line-height: 1; font-family: var(--ov-font, "Helvetica Neue", Helvetica, Arial, sans-serif); font-weight: 800; color: #fff; letter-spacing: -.03em; text-shadow: 0 4px 10px rgba(0,0,0,.55), 0 10px 30px rgba(0,0,0,.4); }
.ov .it { display: block; line-height: 1.16; }
.ov .it.inline { display: inline-block; position: relative; }
.ov .lab { display: block; font-size: 34px; letter-spacing: .14em; font-weight: 700; margin-top: .22em; color: var(--ov-grey, #d9d5cf); }
.ov .strike { position: absolute; left: -20px; right: -20px; top: 50%; height: 12px; background: var(--ov-accent, #D40F30); transform: rotate(-6deg); transform-origin: 0 50%; }
.ov .ring { position: absolute; inset: -12px -34px; border: 8px solid var(--ov-accent, #D40F30); border-radius: 50%; transform: rotate(-4deg); }
.ov .ul { position: absolute; left: 0; right: 0; bottom: -6px; height: 10px; background: var(--ov-accent, #D40F30); transform-origin: 0 50%; }
.ov .check { color: var(--ov-accent, #D40F30); margin-right: 18px; }
.ov .chev { display: block; font-size: 120px; line-height: .9; color: var(--ov-accent, #D40F30); font-weight: 900; }
.ovimg { position: absolute; left: 0; width: 1080px; height: auto; box-shadow: 0 30px 80px rgba(0,0,0,.6); }
.ovbg { position: absolute; inset: 0; background: #0F0D0D; }
/* layout S : zone écran 0→980, marque via variables --z-* */
#zone { position: absolute; left: 0; top: 0; width: 1080px; height: 880px; overflow: hidden; background: var(--z-bg, #F3F1EE); font-family: var(--z-font, "Helvetica Neue", Helvetica, Arial, sans-serif); color: var(--z-ink, #0F0D0D); }
#zone::after { content: ""; position: absolute; inset: 0; background: radial-gradient(120% 80% at 50% 0%, rgba(255,255,255,.55), transparent 60%); pointer-events: none; }
.zc { position: absolute; background: #fff; border-radius: 26px; box-shadow: 0 2px 0 rgba(15,13,13,.06), 0 24px 60px rgba(15,13,13,.16); overflow: hidden; }
.zc .bar { height: 14px; background: var(--z-accent, #D40F30); }
.zc .ttl { padding: 26px 30px 0; font-weight: 800; font-size: 40px; letter-spacing: -.02em; line-height: 1.05; }
.zc .logos { display: grid; grid-template-columns: repeat(var(--cols, 3), minmax(0, 1fr)); gap: 18px 14px; padding: 22px 26px 30px; align-items: center; justify-items: center; width: 100%; box-sizing: border-box; }
.zc .logos img { height: var(--lh, 96px); width: 100%; max-width: 100%; object-fit: contain; }
.zc .num { padding: 18px 30px 0; font-weight: 800; font-size: 96px; letter-spacing: -.04em; line-height: 1; color: var(--z-accent, #D40F30); font-variant-numeric: tabular-nums; }
.zc .lab { padding: 10px 30px 30px; font-weight: 700; font-size: 26px; letter-spacing: .14em; color: #8F8B85; }
.zbadge { position: absolute; display: grid; place-items: center; width: 120px; height: 120px; border-radius: 50%; background: var(--z-accent, #D40F30); color: #fff; font-weight: 900; font-size: 44px; font-style: italic; box-shadow: 0 16px 40px rgba(212,15,48,.35); }
.zstamp { position: absolute; padding: 18px 34px; border: 8px solid var(--z-accent, #D40F30); color: var(--z-accent, #D40F30); font-weight: 900; font-size: 64px; letter-spacing: -.02em; border-radius: 18px; transform: rotate(-6deg); background: rgba(255,255,255,.7); }
.zline { position: absolute; font-weight: 700; font-size: 34px; letter-spacing: .04em; color: #7d7973; }
.zbig { position: absolute; left: 0; right: 0; text-align: center; font-weight: 800; letter-spacing: -.04em; line-height: 1; color: var(--z-accent, #D40F30); font-variant-numeric: tabular-nums; }
.zring { position: absolute; border: 10px solid var(--z-accent, #D40F30); border-radius: 50%; transform: rotate(-4deg); }
.zvideo { position: absolute; overflow: hidden; border-radius: 18px; box-shadow: 0 24px 60px rgba(15,13,13,.18); background: #000; }
.zimg { position: absolute; overflow: hidden; border-radius: 18px; box-shadow: 0 24px 60px rgba(15,13,13,.18); background: #fff; }
.zimg img { display: block; width: 100%; height: auto; }
.zimg .hl { position: absolute; border: 6px solid var(--z-accent, #D40F30); border-radius: 8px; background: rgba(212,15,48,.14); transform-origin: 0 50%; }
.zcheck { position: absolute; display: flex; align-items: center; gap: 22px; background: #fff; border-radius: 22px; padding: 22px 30px; box-shadow: 0 18px 44px rgba(15,13,13,.14); font-weight: 700; font-size: 44px; letter-spacing: -.01em; }
.zcheck .n { color: var(--z-accent, #D40F30); font-weight: 900; font-size: 34px; }
.zcheck .ck { margin-left: auto; width: 56px; height: 56px; border-radius: 50%; background: var(--z-accent, #D40F30); color: #fff; display: grid; place-items: center; font-size: 34px; font-weight: 900; }
.zcheck .ul { position: absolute; left: 30px; right: 30px; bottom: 14px; height: 8px; background: var(--z-accent, #D40F30); transform-origin: 0 50%; border-radius: 4px; }
.zstrike { position: absolute; height: 12px; background: var(--z-accent, #D40F30); transform-origin: 0 50%; border-radius: 6px; }
.zphoto { position: absolute; overflow: hidden; border-radius: 28px; box-shadow: 0 30px 80px rgba(15,13,13,.22), 0 2px 0 rgba(255,255,255,.6) inset; background: #fff; }
.zphoto img { display: block; width: 100%; height: 100%; object-fit: cover; }
.zchevs { position: absolute; left: 0; right: 0; text-align: center; line-height: .55; }
.zchev { display: block; font-size: 150px; font-weight: 900; color: var(--z-accent, #D40F30); }
/* layout Y (16:9): the speaker lives in the scene and moves; the zone is the whole frame, transparent */
/* layout Y: a full-frame world, the speaker is a card that moves inside it */
.ybg { position: absolute; inset: 0; overflow: hidden; background: var(--z-bg, #FBFAF8); }
.ybg .fill { position: absolute; inset: -5%; background-size: cover; background-position: center; transform-origin: 50% 50%; }
.ybg .mesh { background:
  radial-gradient(ellipse 78% 62% at 14% 18%, color-mix(in srgb, var(--z-accent) 30%, transparent), transparent 62%),
  radial-gradient(ellipse 66% 52% at 86% 12%, color-mix(in srgb, var(--z-accent) 16%, white), transparent 64%),
  radial-gradient(ellipse 92% 72% at 74% 88%, color-mix(in srgb, var(--z-accent) 20%, transparent), transparent 66%),
  radial-gradient(ellipse 60% 50% at 28% 92%, rgba(255,255,255,.75), transparent 62%),
  linear-gradient(158deg, #FFFCFA 0%, color-mix(in srgb, var(--z-accent) 7%, #FAF4F0) 55%, color-mix(in srgb, var(--z-accent) 14%, #F6EAE3) 100%); }
.yshadow { position: absolute; left: 0; top: 0; width: __W__px; height: __H__px; background: #100c0a; opacity: 0; box-shadow: 0 50px 120px rgba(23,19,14,.42); }
.yface { position: absolute; left: 0; top: 0; width: __W__px; height: __H__px; overflow: hidden; transform-origin: 0 0; background: #000; }
.yface video { width: 100%; height: 100%; object-fit: cover; }
/* glass cards, statements, pills, 3D cascades */
.zglass { position: absolute; border-radius: 30px; padding: 30px 34px 32px; background: rgba(255,255,255,.62); border: 1.5px solid rgba(255,255,255,.88); box-shadow: 0 30px 70px rgba(23,19,14,.16); backdrop-filter: blur(22px); -webkit-backdrop-filter: blur(22px); }
.zglass.dark { background: rgba(24,26,32,.74); border-color: rgba(255,255,255,.16); color: #fff; }
.zglass .ico { width: 82px; height: 82px; border-radius: 22px; display: grid; place-items: center; font-size: 40px; font-weight: 800; background: var(--z-accent, #E2604A); color: #fff; box-shadow: 0 14px 32px rgba(226,96,74,.38); }
.zglass .ttl { margin-top: 22px; font-family: inherit; font-style: normal; font-weight: 800; font-size: 52px; letter-spacing: -.025em; line-height: 1.02; }
.zglass .num2 { margin-top: 18px; font-weight: 800; font-size: 96px; letter-spacing: -.04em; line-height: 1; color: var(--z-accent, #E2604A); font-variant-numeric: tabular-nums; }
.zglass .sub { margin-top: 12px; font-family: inherit; font-style: normal; font-weight: 700; font-size: 20px; letter-spacing: .16em; text-transform: uppercase; color: #8a857f; }
.zglass.dark .sub { color: rgba(255,255,255,.62); }
.zglass .bars { margin-top: 24px; height: 150px; display: flex; align-items: flex-end; gap: 14px; }
.zglass .bars i { display: block; flex: 1; background: var(--z-accent, #E2604A); border-radius: 8px 8px 3px 3px; transform-origin: 50% 100%; }
.zglass .bars i:nth-child(odd) { opacity: .55; }
.zglass .shot { margin-top: 22px; border-radius: 16px; overflow: hidden; box-shadow: 0 14px 34px rgba(23,19,14,.18); background: #fff; }
.zglass .shot img { display: block; width: 100%; height: auto; }
.zst { position: absolute; }
.zst .kick { font-weight: 800; font-size: 26px; letter-spacing: .18em; text-transform: uppercase; color: #8a857f; }
.zst .big { margin-top: 20px; font-weight: 800; font-size: 104px; line-height: 1.02; letter-spacing: -.038em; color: var(--z-ink, #17130e); }
.zst .big em { font-style: normal; color: var(--z-accent-ink, #D3553F); }   /* the accent darkened: text on a light world must clear 3:1 */
.zst .sub2 { margin-top: 20px; font-weight: 500; font-size: 42px; line-height: 1.2; color: #55504a; }
.zpill { position: absolute; display: flex; align-items: center; gap: 20px; padding: 20px 24px 20px 34px; border-radius: 24px; background: rgba(255,255,255,.68); border: 1.5px solid rgba(255,255,255,.9); box-shadow: 0 24px 60px rgba(23,19,14,.16); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px); font-weight: 700; font-size: 36px; letter-spacing: -.01em; color: var(--z-ink, #17130e); }
.zpill .arw { width: 56px; height: 56px; border-radius: 17px; background: var(--z-accent, #E2604A); color: #fff; display: grid; place-items: center; font-size: 28px; font-weight: 800; }
.ztag { position: absolute; display: flex; align-items: center; gap: 12px; padding: 14px 26px; border-radius: 999px; background: rgba(255,255,255,.72); border: 1.5px solid rgba(255,255,255,.9); box-shadow: 0 16px 40px rgba(23,19,14,.14); backdrop-filter: blur(16px); -webkit-backdrop-filter: blur(16px); font-weight: 700; font-size: 30px; color: var(--z-ink, #17130e); }
.ztag .dot { width: 14px; height: 14px; border-radius: 50%; background: var(--z-accent, #E2604A); }
.ztag .lg { width: 40px; height: 40px; object-fit: contain; }
.ztag.chip { padding: 20px; border-radius: 50%; }
.ztag.chip .lg { width: 52px; height: 52px; }
.zlc { position: absolute; display: flex; align-items: center; gap: 26px; padding: 26px 36px 26px 26px; border-radius: 28px; background: rgba(255,255,255,.74); border: 1.5px solid rgba(255,255,255,.92); box-shadow: 0 26px 64px rgba(23,19,14,.18); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); }
.zlc .mk { width: 96px; height: 96px; border-radius: 26px; background: #fff; display: grid; place-items: center; box-shadow: 0 10px 24px rgba(23,19,14,.12); flex: none; }
.zlc .mk img { width: 64px; height: 64px; object-fit: contain; }
.zlc .tx { display: flex; flex-direction: column; gap: 12px; }
.zlc .nm { font-weight: 800; font-size: 46px; letter-spacing: -.025em; line-height: 1; color: var(--z-ink, #17130e); }
.zlc .rw { display: flex; align-items: center; gap: 10px; }
.zlc .ch { font-weight: 700; font-size: 27px; color: #55504a; background: rgba(23,19,14,.07); border-radius: 999px; padding: 8px 18px; white-space: nowrap; }
.zlc .bd { font-weight: 800; font-size: 19px; letter-spacing: .12em; color: #fff; background: var(--z-accent, #E2604A); border-radius: 999px; padding: 8px 14px; white-space: nowrap; }
.zcas { position: absolute; perspective: 2200px; }
.zcas .cd { position: absolute; top: 0; overflow: hidden; background: #000; border: 3px solid rgba(255,255,255,.55); box-shadow: 0 34px 90px rgba(23,19,14,.34); }
.zcas .cd video, .zcas .cd img { display: block; width: 100%; height: 100%; object-fit: cover; }
#zone.y { width: __W__px; height: __H__px; background: transparent; }
#zone.y::after { display: none; }
.zphone { position: absolute; overflow: hidden; border-radius: 44px; border: 10px solid #15120f; background: #000; box-shadow: 0 40px 90px rgba(0,0,0,.45); }
.zphone video { display: block; width: 100%; height: 100%; object-fit: cover; }
.zlogo { position: absolute; }
.zlogo img { width: 100%; height: auto; display: block; }
.cta { position: absolute; left: 70px; right: 70px; top: 1290px; background: #f7f2e7; border: 1px solid rgba(23,19,14,.18); border-radius: var(--radius-card); box-shadow: var(--shadow-card); transform: rotate(var(--tilt)); padding: 34px 40px 40px; }
.cta .kicker { justify-content: flex-start; }
.keyword { margin: 30px 0 0; font: 900 118px/1 var(--font-display); letter-spacing: var(--track-tight); text-transform: uppercase; }
.keyword em { display: inline-block; color: var(--accent); text-shadow: 0 3px 0 rgba(23,19,14,.25); }
"""


# ----------------------------------------------------------------------------- content blocks

def block_card(sid, card):
    if "capture" in card:
        hl = card.get("highlight")
        hl_html = f'<div class="hl" id="{sid}-hl" style="left:{hl[0]}px;top:{hl[1]}px;width:{hl[2]}px;height:{hl[3]}px"></div>' if hl else ""
        h = card.get("height", 560)
        try:
            from PIL import Image
            with Image.open(ROOT / card["capture"]) as im:
                scaled = int(940 * im.height / im.width)
            h = min(h, scaled)
            card["_pan"] = max(0, min(int(card.get("pan", 0)), scaled - h))
        except Exception:
            card["_pan"] = int(card.get("pan", 0))
        return (f'<div class="capture" id="{sid}-card" data-layout-allow-overflow><div class="bar"><i></i><i></i><i></i> {esc(card.get("url", ""))}</div>'
                f'<div class="win" style="height:{h}px"><img id="{sid}-shot" src="{esc(card["capture"])}" alt="">{hl_html}</div></div>')
    rows = []
    for i, row in enumerate(card.get("rows", []), 1):
        num, label = row[0], row[1]
        meta = row[2] if len(row) > 2 and row[2] else ""
        state = row[3] if len(row) > 3 else None
        right = (f'<span class="meta">{esc(meta)}</span>' if meta else "")
        if state is True:
            right += '<span class="ok">✓</span>'
        elif state is False:
            right += '<span class="todo"></span>'
        rows.append(f'<div class="row" id="{sid}-row-{i}"><span><span class="n">{esc(num)}</span><span data-slot="row-{i}">{rich(label)}</span></span><span>{right}</span></div>')
    title = f'<p class="t" data-slot="card-title">{esc(card["title"])}</p>' if card.get("title") else ""
    return f'<div class="card" id="{sid}-card">{title}{"".join(rows)}</div>'


def block_logos(sid, logos):
    cells = "".join(f'<div class="l" id="{sid}-logo-{i}"><img src="{esc(p)}" alt=""></div>' for i, p in enumerate(logos, 1))
    return f'<div class="logos" id="{sid}-logos">{cells}</div>'


def paper_content(sid, sc, top, bottom=None):
    """Kicker + headline + sub + note + card/logos, inside a .content area."""
    parts = [f'<div class="kicker"><span data-slot="kicker">{esc(sc.get("kicker", ""))}</span><span data-slot="index">{esc(sc.get("index", ""))}</span></div>']
    if sc.get("headline"):
        parts.append(f'<h2 class="headline" id="{sid}-headline" data-slot="headline" style="font-size:{sc.get("headline_size", 96)}px">{rich(sc["headline"])}</h2>')
    if sc.get("sub"):
        parts.append(f'<p class="sub" id="{sid}-sub" data-slot="sub">{rich(sc["sub"])}</p>')
    if sc.get("card"):
        parts.append(block_card(sid, sc["card"]))
    if sc.get("logos"):
        parts.append(block_logos(sid, sc["logos"]))
    note = ""
    if sc.get("note"):
        pos = sc.get("note_pos", [640, 300])
        note = f'<div class="note" id="{sid}-note" data-slot="note" style="left:{pos[0]}px;top:{pos[1]}px">{esc(sc["note"])}</div>'
    style = f"top:{top}px;" + (f"bottom:{bottom}px;" if bottom is not None else "")
    return f'<div class="content" id="{sid}-content" style="{style}">{"".join(parts)}{note}</div>'


# ----------------------------------------------------------------------------- timelines

def tl_common(sid, sc, slot):
    t = []
    t.append(f'tl.from("#{sid}-content .kicker", {{ opacity: 0, y: 20, duration: 0.3, ease: "steps(6)" }}, 0.1);')
    t.append(f'if (document.querySelector("#{sid}-headline")) tl.from("#{sid}-headline", {{ opacity: 0, y: 40, scale: 0.94, duration: 0.42, ease: "back.out(2.2)" }}, 0.18);')
    t.append(f'if (document.querySelector("#{sid}-sub")) tl.from("#{sid}-sub", {{ opacity: 0, x: -30, duration: 0.3, ease: "steps(6)" }}, 0.5);')
    t.append(f'if (document.querySelector("#{sid}-card")) {{ tl.from("#{sid}-card", {{ opacity: 0, y: 90, rotation: 3, duration: 0.42, ease: "back.out(2.2)" }}, 0.6); tl.to("#{sid}-card", {{ scale: 1.02, duration: {r3(max(slot - 0.6, 0.5))}, ease: "none" }}, 0.6); }}')
    t.append(f'if (document.querySelector("#{sid}-card .row")) {{ tl.from("#{sid}-card .row", {{ opacity: 0, x: -30, duration: 0.3, ease: "steps(6)", stagger: 0.12 }}, 0.9); tl.from("#{sid}-card .row .ok", {{ scale: 0, duration: 0.32, ease: "back.out(2.6)", stagger: 0.12 }}, 1.15); }}')
    t.append(f'if (document.querySelector("#{sid}-logos")) {{ tl.from("#{sid}-logos .l", {{ opacity: 0, scale: 0.4, rotation: -8, duration: 0.36, ease: "back.out(2.4)", stagger: 0.1 }}, 0.7); }}')
    if sc.get("card", {}).get("capture"):
        pan = sc["card"].get("_pan", sc["card"].get("pan", 0))
        t.append(f'tl.fromTo("#{sid}-shot", {{ y: 0 }}, {{ y: {-int(pan)}, duration: {r3(max(slot - 1.0, 1))}, ease: "power1.inOut" }}, 1.0);')
        if sc["card"].get("highlight"):
            t.append(f'tl.from("#{sid}-hl", {{ scaleX: 0, transformOrigin: "0 50%", duration: 0.5, ease: "power2.out" }}, 1.6);')
    t.append(f'if (document.querySelector("#{sid}-note")) tl.from("#{sid}-note", {{ opacity: 0, scale: 0.4, rotation: 8, duration: 0.36, ease: "back.out(2.2)" }}, {r3(sc.get("note_at", 1.7))});')
    return t


def zone_items(sid, z, t0, t1, tl):
    """Screen-zone items (layouts S and Y): returns the HTML, appends the GSAP calls to tl."""
    items_html = []
    def rel(t):
        return r3(max(0, resolve_at(t, t0, t1) - t0))
    for j, it in enumerate(z.get("items", [])):
        iid = f"{sid}-z{j}"
        typ = it.get("type", "line")
        at = rel(it.get("at", t0))
        x, y = it.get("x", 60), it.get("y", 120)
        if typ == "card":
            logos = "".join(f'<img src="{esc(l)}" alt="">' for l in it.get("logos", []))
            num = f'<div class="num" id="{iid}-num" data-value="{it["value"]}" data-suffix="{esc(it.get("suffix", " €"))}">{"0" + esc(it.get("suffix", " €")) if it.get("count") else esc(it.get("number", ""))}</div>' if (it.get("value") is not None or it.get("number")) else ""
            items_html.append(f'<div class="zc" id="{iid}" style="left:{x}px;top:{y}px;width:{it.get("w", 460)}px;{"height:" + str(it["h"]) + "px;" if it.get("h") else ""}"><div class="bar"></div>{("<div class=\"ttl\">" + rich(it["title"]) + "</div>") if it.get("title") else ""}{num}{("<div class=\"lab\">" + esc(it["label"]) + "</div>") if it.get("label") else ""}{("<div class=\"logos\" style=\"--cols:" + str(it.get("cols", 3)) + ";--lh:" + str(it.get("logo_h", 96)) + "px\">" + logos + "</div>") if logos else ""}</div>')
            frm = it.get("from", "up")
            if frm != "none":
                start_pos = {"left": "x: -520, rotation: -4", "right": "x: 520, rotation: 4", "up": "y: 90", "down": "y: -90"}[frm]
                tl.append(f'tl.from("#{iid}", {{ {start_pos}, opacity: 0, duration: 0.55, ease: "back.out(1.5)" }}, {at});')
            if it.get("value") is not None and it.get("count"):
                tl.append(f'(function(){{ const el = document.getElementById("{iid}-num"); const o = {{ v: 0 }}; tl.to(o, {{ v: {it["value"]}, duration: {r3(it.get("count", 0.9))}, ease: "power2.out", onUpdate: () => {{ el.textContent = Math.round(o.v).toLocaleString("{LOCALE}").replace(/\u202f|\u00a0/g, " ") + el.dataset.suffix; }} }}, {rel(it.get("count_at", it.get("at", t0)))}); }})();')
            if it.get("shrink_at") is not None:
                tl.append(f'tl.to("#{iid}", {{ scale: {it.get("shrink_scale", 0.62)}, x: {it.get("shrink_x", 0)}, y: {it.get("shrink_y", 0)}, duration: 0.5, ease: "power3.inOut", transformOrigin: "50% 0%" }}, {rel(it["shrink_at"])});')
            if it.get("strike_at") is not None:
                items_html.append(f'<div class="zstrike" id="{iid}-strike" style="left:{x + 24}px;top:{y + it.get("strike_y", 120)}px;width:{it.get("w", 460) - 48}px;transform:rotate(-6deg)"></div>')
                tl.append(f'tl.from("#{iid}-strike", {{ scaleX: 0, duration: 0.3, ease: "power3.out" }}, {rel(it["strike_at"])});')
        elif typ == "badge":
            items_html.append(f'<div class="zbadge" id="{iid}" style="left:{x}px;top:{y}px">{esc(it["text"])}</div>')
            tl.append(f'tl.from("#{iid}", {{ scale: 0, rotation: -30, duration: 0.45, ease: "back.out(2.4)" }}, {at});')
        elif typ == "stamp":
            items_html.append(f'<div class="zstamp" id="{iid}" style="left:{x}px;top:{y}px">{esc(it["text"])}</div>')
            tl.append(f'tl.from("#{iid}", {{ scale: 1.8, opacity: 0, rotation: -14, duration: 0.32, ease: "power4.out" }}, {at});')
        elif typ == "image":
            hls = "".join(f'<div class="hl" id="{iid}-hl{k}" style="left:{h[0]}px;top:{h[1]}px;width:{h[2]}px;height:{h[3]}px"></div>' for k, h in enumerate(it.get("highlights", [])))
            items_html.append(f'<div class="zimg" id="{iid}" style="left:{x}px;top:{y}px;width:{it.get("w", 960)}px;{"height:" + str(it["h"]) + "px;" if it.get("h") else ""}"><div id="{iid}-in" style="position:relative;transform-origin:{it.get("origin", "50% 50%")}"><img src="{esc(it["src"])}" alt="">{hls}</div></div>')
            tl.append(f'tl.from("#{iid}", {{ y: 80, opacity: 0, duration: 0.45, ease: "power3.out" }}, {at});')
            if it.get("zoom_at") is not None:
                tl.append(f'tl.to("#{iid}-in", {{ scale: {it.get("zoom", 1.8)}, x: {it.get("zoom_x", 0)}, y: {it.get("zoom_y", 0)}, duration: 0.7, ease: "power3.inOut" }}, {rel(it["zoom_at"])});')
            for k, h in enumerate(it.get("highlights", [])):
                tl.append(f'tl.from("#{iid}-hl{k}", {{ scaleX: 0, duration: 0.35, ease: "power3.out" }}, {rel(it.get("highlight_at", it.get("at", t0)))});')
        elif typ == "video":
            v_end = rel(it["out_at"]) if it.get("out_at") is not None else r3(t1 - t0)
            klass = "zphone" if it.get("phone") else "zvideo"
            tilt = f'transform:perspective(1800px) rotateY({it.get("tilt", 0)}deg) rotateX({it.get("tilt_x", 0)}deg);' if it.get("tilt") or it.get("tilt_x") else ""
            items_html.append(f'<div class="{klass}" id="{iid}" style="left:{x}px;top:{y}px;width:{it.get("w", 960)}px;height:{it.get("h", 540)}px;{tilt}"><video id="{iid}-v" class="clip" src="{esc(it["src"])}" data-start="{at}" data-duration="{r3(float(v_end) - float(at))}" data-media-start="{r3(it.get("media_start", 0))}" data-track-index="{40 + j}" muted playsinline style="width:100%;height:100%;object-fit:cover;object-position:{it.get("pos", "50% 50%")}"></video></div>')
            frm = it.get("from", "up")
            start_pos = {"left": "x: -400", "right": "x: 400", "up": "y: 120", "down": "y: -120", "far": "z: -900"}.get(frm, "y: 120")
            tl.append(f'tl.from("#{iid}", {{ {start_pos}, opacity: 0, duration: 0.55, ease: "back.out(1.4)" }}, {at});')
        elif typ == "glass":
            ico = f'<div class="ico">{esc(it["icon"])}</div>' if it.get("icon") else ""
            ttl = f'<div class="ttl">{rich(it["title"])}</div>' if it.get("title") else ""
            num = (f'<div class="num2" id="{iid}-n" data-suffix="{esc(it.get("suffix", ""))}">0{esc(it.get("suffix", ""))}</div>' if it.get("count")
                   else f'<div class="num2">{esc(it["number"])}</div>' if it.get("number") else "")
            sub = f'<div class="sub">{esc(it["sub"])}</div>' if it.get("sub") else ""
            bars = ('<div class="bars">' + "".join(f'<i id="{iid}-b{k}" style="height:{v}%"></i>' for k, v in enumerate(it["bars"])) + "</div>") if it.get("bars") else ""
            shot = f'<div class="shot"><img src="{esc(it["shot"])}" alt=""></div>' if it.get("shot") else ""
            items_html.append(f'<div class="zglass{" dark" if it.get("dark") else ""}" id="{iid}" style="left:{x}px;top:{y}px;width:{it.get("w", 520)}px;{"height:" + str(it["h"]) + "px;" if it.get("h") else ""}">{ico}{ttl}{num}{sub}{bars}{shot}</div>')
            frm = it.get("from", "up")
            start_pos = {"left": "x: -260", "right": "x: 260", "up": "y: 90", "down": "y: -90", "none": "y: 0"}.get(frm, "y: 90")
            tl.append(f'tl.from("#{iid}", {{ {start_pos}, opacity: 0, scale: 0.94, duration: 0.55, ease: "back.out(1.5)" }}, {at});')
            if it.get("count"):
                tl.append(f'(function(){{ const el = document.getElementById("{iid}-n"); const o = {{ v: 0 }}; tl.to(o, {{ v: {it["count"]}, duration: {r3(it.get("count_dur", 0.9))}, ease: "power2.out", onUpdate: () => {{ el.textContent = Math.round(o.v).toLocaleString("{LOCALE}").replace(/\u202f|\u00a0/g, " ") + el.dataset.suffix; }} }}, {r3(float(at) + 0.2)}); }})();')
            for k in range(len(it.get("bars", []))):
                tl.append(f'tl.from("#{iid}-b{k}", {{ scaleY: 0, duration: 0.45, ease: "back.out(1.6)" }}, {r3(float(at) + 0.25 + 0.08 * k)});')
        elif typ == "statement":
            kick = f'<div class="kick" id="{iid}-k">{esc(it["kicker"])}</div>' if it.get("kicker") else ""
            big = f'<div class="big" id="{iid}-t">{rich(it["text"])}</div>' if it.get("text") else ""
            sub2 = f'<div class="sub2" id="{iid}-s">{rich(it["sub"])}</div>' if it.get("sub") else ""
            items_html.append(f'<div class="zst" id="{iid}" style="left:{x}px;top:{y}px;width:{it.get("w", 860)}px;{"text-align:" + it["align"] + ";" if it.get("align") else ""}">{kick}{big}{sub2}</div>')
            for k, part in enumerate([nm for nm, ok in (("k", it.get("kicker")), ("t", it.get("text")), ("s", it.get("sub"))) if ok]):
                tl.append(f'tl.from("#{iid}-{part}", {{ y: 42, opacity: 0, duration: 0.5, ease: "power3.out" }}, {r3(float(at) + 0.12 * k)});')
        elif typ == "pill":
            arw = f'<span class="arw">{esc(it.get("arrow", "\u2197"))}</span>' if it.get("arrow", True) else ""
            items_html.append(f'<div class="zpill" id="{iid}" style="left:{x}px;top:{y}px">{rich(it["text"])}{arw}</div>')
            tl.append(f'tl.from("#{iid}", {{ y: 30, opacity: 0, scale: 0.92, duration: 0.45, ease: "back.out(1.8)" }}, {at});')
        elif typ == "tag":
            mark = f'<img class="lg" src="{esc(it["logo"])}" alt="">' if it.get("logo") else '<span class="dot"></span>'
            round_only = it.get("logo") and not it.get("text")
            items_html.append(f'<div class="ztag{" chip" if round_only else ""}" id="{iid}" style="left:{x}px;top:{y}px">{mark}{esc(it.get("text", ""))}</div>')
            tl.append(f'tl.from("#{iid}", {{ y: 26, opacity: 0, scale: 0.9, duration: 0.4, ease: "back.out(2)" }}, {at});')
        elif typ == "logocard":
            badge = f'<span class="bd" id="{iid}-bd">{esc(it["badge"])}</span>' if it.get("badge") else ""
            chip = f'<span class="ch" id="{iid}-ch">{esc(it["chip"])}</span>' if it.get("chip") else ""
            items_html.append(f'<div class="zlc" id="{iid}" style="left:{x}px;top:{y}px;{"width:" + str(it["w"]) + "px;" if it.get("w") else ""}">'
                              f'<span class="mk" id="{iid}-mk"><img src="{esc(it["logo"])}" alt=""></span>'
                              f'<span class="tx"><span class="nm">{esc(it["title"])}</span><span class="rw">{chip}{badge}</span></span></div>')
            a = float(at)
            tl.append(f'tl.from("#{iid}", {{ y: 54, opacity: 0, scale: 0.93, duration: 0.5, ease: "back.out(1.6)" }}, {at});')
            tl.append(f'tl.from("#{iid}-mk", {{ scale: 0.45, rotation: -14, opacity: 0, duration: 0.45, ease: "back.out(2.6)" }}, {r3(a + 0.12)});')
            if chip:
                tl.append(f'tl.from("#{iid}-ch", {{ x: -26, opacity: 0, duration: 0.35, ease: "power3.out" }}, {r3(a + 0.26)});')
            if badge:
                tl.append(f'tl.from("#{iid}-bd", {{ scale: 0, opacity: 0, duration: 0.4, ease: "back.out(3)" }}, {r3(a + 0.42)});')
                tl.append(f'tl.to("#{iid}-bd", {{ scale: 1.1, duration: 0.18, ease: "sine.inOut", repeat: 1, yoyo: true }}, {r3(a + 0.9)});')
        elif typ == "cascade":
            cw, ch = it.get("cw", 330), it.get("ch", 586)
            step, tilt, rise = it.get("step", 250), it.get("tilt", 24), it.get("rise", 26)
            out_rel = rel(it["out_at"]) if it.get("out_at") is not None else r3(t1 - t0)
            cards = []
            for k, src in enumerate(it["src"]):
                inner = (f'<video id="{iid}-c{k}-v" class="clip" src="{esc(src)}" data-start="{at}" data-duration="{r3(float(out_rel) - float(at))}" data-media-start="{r3(it.get("media_start", 0))}" data-track-index="{44 + j * 4 + k}" muted playsinline></video>'
                         if src.lower().endswith((".mp4", ".mov", ".webm")) else f'<img src="{esc(src)}" alt="">')
                cards.append(f'<div class="cd" id="{iid}-c{k}" style="left:{k * step}px;top:{k * rise}px;width:{cw}px;height:{ch}px;border-radius:{it.get("radius", 24)}px;transform:rotateY({tilt}deg);z-index:{len(it["src"]) - k}">{inner}</div>')
            items_html.append(f'<div class="zcas" id="{iid}" style="left:{x}px;top:{y}px;width:{(len(it["src"]) - 1) * step + cw}px;height:{ch + (len(it["src"]) - 1) * rise}px">{"".join(cards)}</div>')
            for k in range(len(it["src"])):
                tl.append(f'tl.from("#{iid}-c{k}", {{ x: 170, opacity: 0, duration: 0.6, ease: "power3.out" }}, {r3(float(at) + 0.1 * k)});')
        elif typ == "big":
            items_html.append(f'<div class="zbig" id="{iid}" style="top:{y}px;{"left:" + str(it["x"]) + "px;right:auto;width:" + str(it.get("w", 800)) + "px;" if it.get("x") is not None and it.get("x") != "center" else ""}font-size:{it.get("size", 200)}px;{"color:" + it["color"] + ";" if it.get("color") else ""}"><span id="{iid}-t" style="display:inline-block;position:relative;padding:0 30px">{esc(it.get("text", "")) if not it.get("value") else "0" + esc(it.get("suffix", " €"))}{"<span class=\"zring\" id=\"" + iid + "-ring\" style=\"inset:-16px -30px\"></span>" if it.get("circle_at") is not None else ""}</span>{("<div style=\"font-size:30px;letter-spacing:.14em;color:#8F8B85;margin-top:18px;font-weight:700\">" + esc(it["label"]) + "</div>") if it.get("label") else ""}</div>')
            tl.append(f'tl.from("#{iid}", {{ scale: 0.6, opacity: 0, duration: 0.4, ease: "back.out(2)" }}, {at});')
            if it.get("value"):
                tl.append(f'(function(){{ const el = document.getElementById("{iid}-t").childNodes[0]; const o = {{ v: 0 }}; tl.to(o, {{ v: {it["value"]}, duration: {r3(it.get("count", 0.8))}, ease: "power2.out", onUpdate: () => {{ el.textContent = Math.round(o.v).toLocaleString("{LOCALE}").replace(/\u202f|\u00a0/g, " ") + "{esc(it.get("suffix", " €"))}"; }} }}, {at}); }})();')
            if it.get("circle_at") is not None:
                tl.append(f'tl.from("#{iid}-ring", {{ scale: 0.3, opacity: 0, duration: 0.4, ease: "back.out(2)" }}, {rel(it["circle_at"])});')
        elif typ == "check":
            items_html.append(f'<div class="zcheck" id="{iid}" style="left:{x}px;top:{y}px;width:{it.get("w", 960)}px"><span class="n">{esc(it.get("n", ""))}</span><span>{rich(it["text"])}</span><span class="ck" id="{iid}-ck">✓</span>{"<span class=\"ul\" id=\"" + iid + "-ul\"></span>" if it.get("underline_at") is not None else ""}</div>')
            tl.append(f'tl.from("#{iid}", {{ x: -300, opacity: 0, duration: 0.45, ease: "back.out(1.4)" }}, {at});')
            tl.append(f'tl.from("#{iid}-ck", {{ scale: 0, duration: 0.35, ease: "back.out(2.6)" }}, {rel(it.get("check_at", it.get("at", t0)))});')
            if it.get("underline_at") is not None:
                tl.append(f'tl.from("#{iid}-ul", {{ scaleX: 0, duration: 0.3, ease: "power3.out" }}, {rel(it["underline_at"])});')
        elif typ == "logo":
            items_html.append(f'<div class="zlogo" id="{iid}" style="left:{x}px;top:{y}px;width:{it.get("w", 600)}px"><img src="{esc(it["src"])}" alt=""></div>')
            tl.append(f'tl.from("#{iid}", {{ scale: 0.7, opacity: 0, duration: 0.45, ease: "back.out(1.8)" }}, {at});')
        elif typ == "photo":
            items_html.append(f'<div class="zphoto" id="{iid}" style="left:{x}px;top:{y}px;width:{it.get("w", 700)}px;height:{it.get("h", 900)}px;transform:rotate({it.get("rotate", 0)}deg)"><img src="{esc(it["src"])}" alt="" style="object-position:{it.get("pos", "50% 50%")}"></div>')
            tl.append(f'tl.from("#{iid}", {{ y: 120, opacity: 0, rotation: {it.get("rotate", 0) - 6}, duration: 0.6, ease: "back.out(1.4)" }}, {at});')
            if it.get("drift"):
                tl.append(f'tl.to("#{iid} img", {{ scale: 1.08, duration: {r3(t1 - t0)}, ease: "none" }}, 0);')
        elif typ == "chevrons":
            chs = "".join(f'<span class="zchev" id="{iid}-c{k}" data-layout-allow-overlap>⌄</span>' for k in range(it.get("n", 3)))
            items_html.append(f'<div class="zchevs" id="{iid}" style="top:{y}px">{chs}</div>')
            atf = float(at)
            for k in range(it.get("n", 3)):
                tl.append(f'tl.from("#{iid}-c{k}", {{ opacity: 0, y: -30, duration: 0.28, ease: "power2.out" }}, {r3(atf + 0.14 * k)});')
            tl.append(f'tl.to("#{iid}", {{ y: 22, duration: 0.5, ease: "sine.inOut", repeat: {max(1, int((t1 - t0 - atf) / 1.0) * 2 - 1)}, yoyo: true }}, {r3(atf + 0.5)});')
        else:  # line
            pos = 'left:0;right:0;text-align:center;' if x == "center" else f'left:{x}px;'
            items_html.append(f'<div class="zline" id="{iid}" style="{pos}top:{y}px;{"font-size:" + str(it["size"]) + "px;" if it.get("size") else ""}{"color:" + it["color"] + ";" if it.get("color") else ""}{"font-weight:" + str(it["weight"]) + ";" if it.get("weight") else ""}{"letter-spacing:" + it["tracking"] + ";" if it.get("tracking") else ""}">{rich(it["text"])}</div>')
            tl.append(f'tl.from("#{iid}", {{ opacity: 0, y: 16, duration: 0.3, ease: "power2.out" }}, {at});')
        if it.get("out_at") is not None:
            tl.append(f'tl.to("#{iid}", {{ opacity: 0, duration: 0.25 }}, {rel(it["out_at"])});')
    return items_html


def scene_html(sid, sc):
    layout = sc["layout"]
    slot = float(sc["end"]) - float(sc["start"])
    body, tl = [], []
    if layout == "C":
        body.append('<div class="paper" id="%s-paper" data-layout-allow-overflow style="left:-60px;right:-60px;top:940px;bottom:-80px;transform:rotate(-1.2deg);transform-origin:50%% 0"></div>' % sid)
        body.append(paper_content(sid, sc, top=1080, bottom=60))
        tl.append(f'tl.from("#{sid}-paper", {{ y: 140, duration: 0.42, ease: "back.out(2.2)" }}, 0.06);')
        tl += tl_common(sid, sc, slot)
    elif layout == "B":
        body.append(f'<div class="paper" id="{sid}-paper" style="inset:0"></div>')
        body.append(paper_content(sid, sc, top=70))
        tl += tl_common(sid, sc, slot)
    elif layout == "D":
        body.append(f'<div class="paper" id="{sid}-paper" style="inset:0"></div>')
        if sc.get("mega"):
            plain = [re.sub(r"</?em>", "", l) for l in sc["mega"]]
            longest = max(len(l) for l in plain)
            size = min(int(sc.get("mega_size", 200)), int(920 / (0.8 * longest)))
            lines = "".join(f'<span class="l" data-layout-allow-overlap>{rich(l)}</span>' for l in sc["mega"])
            circle = ""
            c = sc.get("circle")
            if c == "auto" or c is True:
                n = len(plain); last = plain[-1]
                top = 70 + 26 + 110 + int(0.86 * size * (n - 1)) - 24
                c = [-30, top, min(1000, int(0.8 * size * len(last)) + 90), int(0.86 * size) + 56]
            if c:
                circle = f'<div class="circle" id="{sid}-circle" style="left:{c[0]}px;top:{c[1]}px;width:{c[2]}px;height:{c[3]}px"></div>'
            sc = dict(sc)
            sc["_mega_html"] = f'<h2 class="mega" id="{sid}-mega" data-slot="mega" style="font-size:{size}px">{lines}</h2>{circle}'
        content = paper_content(sid, sc, top=70, bottom=70)
        if sc.get("_mega_html"):
            # insert the mega right after the kicker (never inside it: the kicker's flex would crush everything)
            content = re.sub(r'(<div class="kicker">.*?</div>)', lambda m: m.group(1) + sc["_mega_html"], content, count=1, flags=re.S)
        body.append(content)
        tl += tl_common(sid, sc, slot)
        if sc.get("mega"):
            tl.append(f'tl.from("#{sid}-mega", {{ opacity: 0, scale: 0.7, y: 60, duration: 0.42, ease: "back.out(2.2)" }}, 0.16);')
            if sc.get("circle"):
                tl.append(f'tl.from("#{sid}-circle", {{ scale: 0.2, opacity: 0, rotation: -30, duration: 0.36, ease: "back.out(2.2)" }}, 0.8);')
        tl.append(f'tl.to("#{sid}-content", {{ scale: 1.03, duration: {r3(slot)}, ease: "none", transformOrigin: "50% 40%" }}, 0);')
    elif layout == "S":
        z = sc.get("zone", {})
        brand = sb.get("brand", {})
        t0, t1 = float(sc["start"]), float(sc["end"])
        body.append(f'<style>#root {{ --z-bg: {brand.get("bg", "#F3F1EE")}; --z-ink: {brand.get("ink", "#0F0D0D")}; --z-accent: {brand.get("accent", "#D40F30")}; --z-font: {brand.get("font", "\"Helvetica Neue\", Helvetica, Arial, sans-serif")}; }}</style>')
        def rel(t):
            return r3(max(0, resolve_at(t, t0, t1) - t0))
        items_html = zone_items(sid, z, t0, t1, tl)
        zh = 1920 if z.get("full") else int(z.get("height", 880))
        zbg = f'background: linear-gradient(135deg, {brand.get("bg", "#F3F1EE")} 0%, {brand.get("bg", "#F3F1EE")} 55%, {brand.get("soft", "#FDEAE6")} 78%, {brand.get("soft2", "#F5C2C9")} 100%);' if z.get("gradient") else ""
        body.append(f'<div id="zone" style="height:{zh}px;{zbg}">{"".join(items_html)}</div>')
        if z.get("in") is not None:
            tl.append(f'tl.fromTo("#zone", {{ clipPath: "inset(0px 0px 1040px 0px)" }}, {{ clipPath: "inset(0px 0px 0px 0px)", duration: 0.55, ease: "power4.inOut" }}, {rel(z["in"])});')
        else:
            tl.append(f'tl.from("#zone", {{ y: -40, opacity: 0, duration: 0.35, ease: "power3.out" }}, 0);')
        if z.get("out") is not None:
            tl.append(f'tl.to("#zone", {{ opacity: 0, duration: 0.3, ease: "power2.in" }}, {rel(z["out"])});')
    elif layout == "Y":
        z = sc.get("zone", {})
        brand = sb.get("brand", {})
        t0, t1 = float(sc["start"]), float(sc["end"])
        body.append(f'<style>#root {{ --z-bg: {brand.get("bg", "#FBFAF8")}; --z-ink: {brand.get("ink", "#17130e")}; --z-accent: {brand.get("accent", "#E2604A")}; --z-accent-ink: {brand.get("accent_ink", brand.get("accent", "#E2604A"))}; --z-font: {brand.get("font", "\"Helvetica Neue\", Helvetica, Arial, sans-serif")}; }}</style>')
        def rel(t):
            return r3(max(0, resolve_at(t, t0, t1) - t0))
        # the world: a mesh gradient or an image, drifting slowly so the frame is never frozen
        bg = sc.get("bg", sb.get("bg", "mesh"))
        fill = (f'<div class="fill mesh" id="{sid}-fill" data-layout-allow-overflow></div>' if bg == "mesh"
                else f'<div class="fill" id="{sid}-fill" data-layout-allow-overflow style="background-image:url({esc(bg)})"></div>')
        body.append(f'<div class="ybg" id="{sid}-bg">{fill}</div>')
        tl.append(f'tl.fromTo("#{sid}-fill", {{ scale: 1 }}, {{ scale: 1.05, duration: {r3(slot)}, ease: "none" }}, 0);')
        body.append(f'<div class="yshadow" id="{sid}-shadow"></div>')
        pos = sc.get("face_pos", sb.get("face_pos_y", "50% 50%"))
        body.append(f'<div class="yface" id="{sid}-face"><video id="{sid}-face-v" class="clip" src="{esc(SPEAKER)}" data-start="0" data-duration="{r3(min(slot, DURATION - float(sb.get("freeze_tail", 0)) - t0))}" data-media-start="{r3(t0)}" data-track-index="0" muted playsinline style="object-position:{pos}"></video></div>')
        # the speaker card: crop (clip-path) + transform, so a 16:9 source becomes a portrait card without distortion
        m = int(sc.get("face_margin", 70))
        SPOTS = {"full": (0, 0, W, H, 0), "wide": (m + 90, m + 50, W - 2 * (m + 90), H - 2 * (m + 50), 34),
                 "left": (m, 90, 620, 900, 34), "right": (W - 620 - m, 90, 620, 900, 34),
                 "tl": (m, m, 430, 600, 30), "tr": (W - 430 - m, m, 430, 600, 30),
                 "bl": (m, H - 600 - m, 430, 600, 30), "br": (W - 430 - m, H - 600 - m, 430, 600, 30),
                 "center": ((W - 680) / 2, 100, 680, 880, 34)}
        fx, fy = sc.get("face_crop", sb.get("face_crop_y", [0.5, 0.42]))
        zoom = float(sc.get("face_zoom", sb.get("face_zoom_y", 1.22)))

        def card(spot):
            x, y, w, h, rad = SPOTS[spot]
            if spot in sc.get("face_size", {}):
                w, h = sc["face_size"][spot]
            k = max(w / W, h / H) * (1.0 if spot == "full" else zoom)
            vw, vh = w / k, h / k
            left, top = (W - vw) * fx, (H - vh) * fy
            clip = f"inset({r3(top)}px {r3(W - left - vw)}px {r3(H - top - vh)}px {r3(left)}px round {r3(rad / k)}px)"
            return (x, y, w, h, rad, f'x: {r3(x - left * k)}, y: {r3(y - top * k)}, scale: {r3(k)}, clipPath: "{clip}", transformOrigin: "0 0"')

        start_spot = sc.get("face_start", "full")
        if start_spot != "full":
            x, y, w, h, rad, tw = card(start_spot)
            tl.append(f'tl.set("#{sid}-face", {{ {tw} }}, 0);')
            tl.append(f'tl.set("#{sid}-shadow", {{ x: {r3(x)}, y: {r3(y)}, width: {r3(w)}, height: {r3(h)}, borderRadius: "{rad}px", opacity: 0.22 }}, 0);')
        for mv in sc.get("face", []):
            spot = mv.get("pos", "full")
            d = mv.get("duration", 0.65)
            when = rel(mv.get("at", t0))
            if spot == "hidden":
                tl.append(f'tl.to("#{sid}-face", {{ opacity: 0, duration: 0.3 }}, {when});')
                tl.append(f'tl.to("#{sid}-shadow", {{ opacity: 0, duration: 0.3 }}, {when});')
                continue
            x, y, w, h, rad, tw = card(spot)
            tl.append(f'tl.to("#{sid}-face", {{ {tw}, opacity: 1, duration: {d}, ease: "power3.inOut" }}, {when});')
            tl.append(f'tl.to("#{sid}-shadow", {{ x: {r3(x)}, y: {r3(y)}, width: {r3(w)}, height: {r3(h)}, borderRadius: "{rad}px", opacity: {0 if spot == "full" else 0.22}, duration: {d}, ease: "power3.inOut" }}, {when});')
        items_html = zone_items(sid, z, t0, t1, tl)
        body.append(f'<div id="zone" class="y">{"".join(items_html)}</div>')
    elif layout == "F":
        ov = sc.get("overlay")
        if ov:
            t0 = float(sc["start"])
            accent = sb.get("caption_accent", "#D40F30")
            body.append(f'<style>#root {{ --ov-accent: {accent}; --ov-font: {sb.get("caption_font", "Helvetica Neue")}; }}</style>')
            if ov.get("bg"):
                body.append(f'<div class="ovbg" id="{sid}-ovbg"></div>')
                tl.append(f'tl.from("#{sid}-ovbg", {{ opacity: 0, duration: 0.2 }}, 0);')
            html = []
            for j, it in enumerate(ov.get("items", [])):
                iid = f"{sid}-ov{j}"
                at = resolve_at(it.get("at", t0), t0, float(sc["end"])) - t0
                if "image" in it:
                    html.append(f'<img class="ovimg" id="{iid}" src="{esc(it["image"])}" style="top:{it.get("top", 380)}px;{"left:" + str(it["left"]) + "px;width:" + str(it["w"]) + "px;box-shadow:none;" if it.get("w") else ""}">')
                    tl.append(f'tl.from("#{iid}", {{ opacity: 0, y: 60, duration: 0.4, ease: "power3.out" }}, {r3(max(0, at))});')
                    continue
                if it.get("chevrons"):
                    html.append(f'<div class="ov" id="{iid}" style="top:{it.get("top", 1700)}px"><span class="chev" data-layout-allow-overlap>⌄</span><span class="chev" data-layout-allow-overlap>⌄</span><span class="chev" data-layout-allow-overlap>⌄</span></div>')
                    tl.append(f'tl.from("#{iid} .chev", {{ opacity: 0, y: -20, duration: 0.3, ease: "power2.out", stagger: 0.12 }}, {r3(max(0, at))});')
                    tl.append(f'tl.to("#{iid}", {{ y: 14, duration: 0.5, yoyo: true, repeat: 3, ease: "sine.inOut" }}, {r3(at + 0.6)});')
                    continue
                color = {"red": accent, "grey": "#d9d5cf", "white": "#fff"}.get(it.get("color", "white"), it.get("color", "#fff"))
                style = f'font-size:{it.get("size", 120)}px;color:{color};' + ("font-style:italic;" if it.get("italic") else "") + (f'font-weight:{it["weight"]};' if it.get("weight") else "") + (f'letter-spacing:{it["tracking"]};' if it.get("tracking") else "")
                inner = ("<span class=\"check\">✓</span>" if it.get("check") else "") + rich(it["text"])
                deco = ""
                if it.get("strike_at") is not None:
                    deco += f'<span class="strike" id="{iid}-strike"></span>'
                if it.get("circle_at") is not None:
                    deco += f'<span class="ring" id="{iid}-ring"></span>'
                if it.get("underline_at") is not None:
                    deco += f'<span class="ul" id="{iid}-ul"></span>'
                label = f'<span class="lab">{esc(it["label"])}</span>' if it.get("label") else ""
                pad = f'padding-left:{it["left"]}px;' if it.get("left") else ""
                html.append(f'<div class="ov" id="{iid}" style="top:{it.get("top", 300)}px;text-align:{it.get("align", "center")};{style}{pad}"><span class="it inline">{inner}{deco}</span>{label}</div>')
                pop = it.get("pop", "scale")
                if pop == "scale":
                    tl.append(f'tl.from("#{iid}", {{ opacity: 0, scale: 0.6, duration: 0.32, ease: "back.out(2.2)", transformOrigin: "50% 50%" }}, {r3(max(0, at))});')
                else:
                    tl.append(f'tl.from("#{iid}", {{ opacity: 0, y: 24, duration: 0.28, ease: "power3.out" }}, {r3(max(0, at))});')
                for key, sel, anim in (("strike_at", "-strike", '{ scaleX: 0, duration: 0.28, ease: "power3.out" }'), ("circle_at", "-ring", '{ scale: 0.3, opacity: 0, duration: 0.36, ease: "back.out(2)" }'), ("underline_at", "-ul", '{ scaleX: 0, duration: 0.3, ease: "power3.out" }')):
                    if it.get(key) is not None:
                        tl.append(f'tl.from("#{iid}{sel}", {anim}, {r3(max(0, resolve_at(it[key], t0, float(sc["end"])) - t0))});')
                if it.get("dim_at") is not None:
                    tl.append(f'tl.to("#{iid}", {{ opacity: {it.get("dim_to", 0.55)}, scale: {it.get("dim_scale", 0.72)}, y: {it.get("dim_y", 0)}, duration: 0.4, ease: "power2.inOut", transformOrigin: "50% 50%" }}, {r3(max(0, resolve_at(it["dim_at"], t0, float(sc["end"])) - t0))});')
                if it.get("out_at") is not None:
                    tl.append(f'tl.to("#{iid}", {{ opacity: 0, duration: 0.25 }}, {r3(max(0, resolve_at(it["out_at"], t0, float(sc["end"])) - t0))});')
            body += html
            if ov.get("out") is not None:
                tl.append(f'tl.to("#root .ov, #root .ovimg, #root .ovbg", {{ opacity: 0, duration: 0.3, ease: "power2.in" }}, {r3(max(0, float(ov["out"]) - t0))});')
        if sc.get("tag"):
            pos = sc.get("tag_pos", [70, 120])
            body.append(f'<div class="tag" id="{sid}-tag" data-slot="tag" style="left:{pos[0]}px;top:{pos[1]}px">{esc(sc["tag"])}</div>')
            tl.append(f'tl.from("#{sid}-tag", {{ opacity: 0, scale: 0.3, rotation: 12, duration: 0.3, ease: "back.out(2.6)" }}, 0.2);')
        if sc.get("keyword"):
            body.append(f'<div class="cta" id="{sid}-cta"><div class="kicker"><span data-slot="kicker">{esc(sc.get("kicker", ""))}</span></div>'
                        f'<p class="keyword" id="{sid}-keyword" data-slot="keyword">{rich(sc["keyword"])}</p></div>')
            if sc.get("note"):
                pos = sc.get("note_pos", [640, 1230])
                body.append(f'<div class="note" id="{sid}-note" data-slot="note" style="left:{pos[0]}px;top:{pos[1]}px">{esc(sc["note"])}</div>')
                tl.append(f'tl.from("#{sid}-note", {{ opacity: 0, scale: 0.4, rotation: 8, duration: 0.36, ease: "back.out(2.2)" }}, 1.4);')
            tl.append(f'tl.from("#{sid}-cta", {{ opacity: 0, y: 120, rotation: 3, duration: 0.42, ease: "back.out(2.2)" }}, 0.3);')
            tl.append(f'tl.from("#{sid}-keyword em", {{ scale: 0.3, duration: 0.4, ease: "back.out(2.6)" }}, 0.8);')
            tl.append(f'tl.to("#{sid}-keyword em", {{ scale: 1.04, transformOrigin: "50% 60%", duration: 0.5, yoyo: true, repeat: 3, ease: "sine.inOut" }}, 1.4);')
    else:
        raise SystemExit(f"unknown layout: {layout}")
    tl.append(f"tl.to({{}}, {{ duration: {r3(slot)} }}, 0);")
    return f"""<!doctype html>
<html lang="{LANG}"><head><meta charset="UTF-8" /><!-- generated by scripts/build-reel.py: edit storyboard.json, not this file --></head>
<body><template>
<style>{SCENE_CSS.replace('__W__', str(W)).replace('__H__', str(H))}</style>
<div id="root" data-composition-id="{sid}" data-width="{W}" data-height="{H}">
{chr(10).join(body)}
</div>
<script>
window.__timelines = window.__timelines || {{}};
(function () {{
  const tl = gsap.timeline({{ paused: true }});
  {chr(10).join("  " + x for x in tl)}
  window.__timelines["{sid}"] = tl;
}})();
</script>
</template></body></html>
"""


# ----------------------------------------------------------------------------- captions

def apply_lexicon(words):
    lex = {k.lower(): v for k, v in sb.get("lexicon", {}).items()}
    for k in lex:
        if len(k.split()) > 1:
            raise SystemExit(f"lexicon: « {k} » spans several words; the validator requires 1 word → 1 word. Fix assets/transcript.json by hand.")
    out, i = [], 0
    while i < len(words):
        hit = None
        for k, v in lex.items():
            n = len(k.split())
            if " ".join(re.sub(r"[^\w%']", "", w["text"].lower()) for w in words[i:i + n]) == k:
                hit = (n, v); break
        if hit:
            n, v = hit
            out.append({"text": v, "start": words[i]["start"], "end": words[i + n - 1]["end"]}); i += n
        else:
            out.append(words[i]); i += 1
    return out


kw_tl = []   # (id, start) of the keywords, animated by the host timeline


def captions(scenes):
    words = apply_lexicon(transcript.get("words", []))
    breaks = sorted(float(b) for b in transcript.get("breaks", []))
    chunks, cur = [], []
    def flush():
        if cur:
            chunks.append(list(cur)); cur.clear()
    def crosses_break(prev_end, start):
        return any(prev_end - 0.05 <= b <= start + 0.05 for b in breaks)
    # 1) sentences: split at sentence-initial capitals, take boundaries, gaps and punctuation
    sentences = []
    for w in words:
        starts_sentence = bool(cur) and w["text"][:1].isupper() and not re.match(r"^[A-Z0-9]{2,}$", w["text"])
        if cur and (w["start"] - cur[-1]["end"] > 0.5 or starts_sentence or crosses_break(cur[-1]["end"], w["start"])):
            sentences.append(list(cur)); cur.clear()
        cur.append(w)
        if re.search(r"[.!?]$", w["text"]):
            sentences.append(list(cur)); cur.clear()
    if cur:
        sentences.append(list(cur))
    # 2) balanced groups of at most 4 words inside each sentence (10 words → 4+3+3, never 4+4+2)
    for sen in sentences:
        n = len(sen); k = max(1, -(-n // CAP_MAX_WORDS)); size = -(-n // k)
        for a in range(0, n, size):
            chunks.append(sen[a:a + size])
    out = []
    for i, ch in enumerate(chunks, 1):
        start, end = ch[0]["start"], max(ch[-1]["end"], ch[0]["start"] + 0.5)
        if i < len(chunks):
            end = min(end + 0.25, chunks[i][0]["start"])
        scene = next((s for s in scenes if float(s["start"]) <= start < float(s["end"])), {"layout": "F"})
        layout = scene["layout"]
        top = scene.get("cap_top", 1140 if (layout == "F" and scene.get("keyword")) else CAP_TOP[layout])
        zz = scene.get("zone") or {}
        on_zone = " on-zone" if (layout == "S" and (not zz.get("full") or zz.get("in") is not None) and scene.get("cap_on_zone", True)) else (" on-y" if layout == "Y" else "")
        parts, kws = [], []
        for j, w in enumerate(ch):
            is_kw = kw_norm(w["text"]) in KEYWORDS
            wid = f"cap-{i}-w{j}"
            if is_kw:
                parts.append(f'<em id="{wid}">{esc(w["text"])}</em>')
                kws.append((wid, w["start"], True))
            else:
                parts.append(f'<b id="{wid}">{esc(w["text"])}</b>')
                kws.append((wid, w["start"], False))
        txt = " ".join(parts)
        kw_tl.extend(kws)
        out.append(f'<div id="cap-{i}" class="cap clip{on_zone}" data-start="{r3(start)}" data-duration="{r3(end - start)}" data-track-index="{20 + (i % 4)}" style="top:{top}px"><span>{txt}</span></div>')
    return out


# ----------------------------------------------------------------------------- host

CAP_CSS_KIT = """.cap { position: absolute; left: 60px; right: 60px; z-index: 5; text-align: center; font: 900 var(--size-cap)/1.05 var(--font-display); text-transform: uppercase; color: #fff; letter-spacing: -.01em; -webkit-text-stroke: 1.5px #000; text-shadow: 0 0 2px #000, 0 4px 0 #000, 3px 0 0 #000, -3px 0 0 #000, 0 -3px 0 #000; }
      .cap span { display: inline-block; background: rgba(23, 19, 14, .8); padding: 12px 28px; border-radius: 14px; }
      .cap em { font-style: normal; color: var(--accent); }"""
CAP_CSS_POP = f""".cap {{ position: absolute; left: {80 if W < H else 260}px; right: {80 if W < H else 260}px; z-index: 5; text-align: center; font: 700 {CAP_SIZE}px/1.08 {CAP_FONT}; color: #fff; letter-spacing: -.01em; text-shadow: 0 3px 6px rgba(0,0,0,.55), 0 8px 24px rgba(0,0,0,.45); }}
      .cap span {{ display: inline-block; max-width: {920 if W < H else 1400}px; }}
      .cap b {{ font-weight: inherit; display: inline-block; }}
      .cap em {{ display: inline-block; font-style: normal; font-size: 1.55em; line-height: 1; color: {CAP_ACCENT}; text-shadow: 0 3px 6px rgba(0,0,0,.5), 0 10px 26px rgba(0,0,0,.45); vertical-align: -0.08em; }}"""
CAP_CSS_POP += f"""
      .cap.on-zone {{ color: {sb.get("brand", {}).get("ink", "#0F0D0D")}; text-shadow: none; }}
      .cap.on-zone em {{ text-shadow: none; }}
      .cap.on-y span {{ background: rgba(10,10,10,.62); padding: 10px 26px 12px; border-radius: 16px; text-shadow: none; }}"""
CAP_CSS_NATE = f""".cap {{ position: absolute; left: {80 if W < H else 200}px; right: {80 if W < H else 200}px; z-index: 5; text-align: center; font: 700 {CAP_SIZE}px/1.15 {CAP_FONT}; color: #fff; letter-spacing: -.015em; }}
      .cap span {{ display: inline-block; max-width: {880 if W < H else 1380}px; background: rgba(20,20,24,.86); padding: 14px 30px 16px; border-radius: 20px; box-shadow: 0 18px 44px rgba(0,0,0,.28); }}
      .cap b {{ font-weight: inherit; display: inline-block; }}
      .cap em {{ font-style: normal; display: inline-block; background: {CAP_ACCENT}; color: #fff; border-radius: 12px; padding: 2px 14px 4px; margin: 0 2px; }}"""
CAP_CSS = {"pop": CAP_CSS_POP, "nate": CAP_CSS_NATE}.get(CAP_STYLE, CAP_CSS_KIT)


def build():
    comp_dir = ROOT / "compositions"
    comp_dir.mkdir(exist_ok=True)
    for old in comp_dir.glob("s[0-9][0-9]-*.html"):
        old.unlink()
    scene_clips, face_clips, face_css = [], [], []
    last_wrap, last_pos = "face-f", "50% 50%"
    for n, sc in enumerate(sb["scenes"], 1):
        sc["start"], sc["end"] = snap(sc["start"]), snap(sc["end"])
        sid = f"s{n:02d}-{sc['layout'].lower()}"
        sc["id"] = sid
        (comp_dir / f"{sid}.html").write_text(scene_html(sid, sc))
        start, dur = float(sc["start"]), float(sc["end"]) - float(sc["start"])
        scene_clips.append(f'<div id="{sid}-slot" class="clip scene" data-composition-id="{sid}" data-composition-src="compositions/{sid}.html" data-start="{r3(start)}" data-duration="{r3(dur)}" data-track-index="1" data-width="{W}" data-height="{H}"></div>')
        lay = sc["layout"]
        if lay in ("C", "B", "F", "S"):
            wrap = {"C": "face-c", "B": "face-b", "F": "face-f", "S": "face-s"}[lay]
            sp_end = DURATION - float(sb.get("freeze_tail", 0))
            zf = (sc.get("zone") or {}) if lay == "S" else {}
            if start >= sp_end or (zf.get("full") and zf.get("in") is None):
                continue
            dur = min(dur, sp_end - start - 1 / FPS)  # never the last frame of the media: extraction misses it
            if dur <= 0:
                continue
            default_pos = {"C": sb.get("face_pos_c", "50% 62%"), "B": sb.get("face_pos_b", "50% 45%"), "F": sb.get("face_pos_f", "50% 50%"), "S": sb.get("face_pos_s", "50% 50%")}[lay]
            pos = sc.get("face_pos", default_pos)
            face_clips.append(f'<div class="{wrap}" id="{sid}-face-wrap"><video id="{sid}-face" class="clip" src="{esc(SPEAKER)}" data-start="{r3(start)}" data-duration="{r3(dur)}" data-media-start="{r3(start)}" data-track-index="0" muted playsinline style="object-position:{pos}"></video></div>')
            last_wrap, last_pos = wrap, pos
    tail = float(sb.get("freeze_tail", 0))
    if tail > 0:
        speaker_end = DURATION - tail - 1 / FPS
        tail += 1 / FPS
        import subprocess as _sp
        _sp.run(["ffmpeg", "-v", "error", "-y", "-sseof", "-0.08", "-i", str(ROOT / SPEAKER), "-frames:v", "1", "-q:v", "2", str(ROOT / "assets" / "last-frame.jpg")], check=True)
        # same framing as the last spoken scene: no jump when the video stops
        face_clips.append(f'<div class="{last_wrap} clip" id="freeze-tail" data-start="{r3(speaker_end)}" data-duration="{r3(tail)}" data-track-index="0"><img src="assets/last-frame.jpg" style="width:100%;height:100%;object-fit:cover;object-position:{last_pos}"></div>')
    caps = captions(sb["scenes"])
    cap_tl = ""
    if CAP_STYLE == "pop":
        cap_tl = "\n      ".join(
            [f'tl.from("#cap-{i} span", {{ scale: 0.92, opacity: 0, duration: 0.18, ease: "power3.out", transformOrigin: "50% 100%" }}, {r3(float(re.search(r"data-start=\"([0-9.]+)\"", c).group(1)))});' for i, c in enumerate(caps, 1)]
            + [(f'tl.from("#{kid}", {{ scale: 0.55, opacity: 0, duration: 0.28, ease: "back.out(2.4)" }}, {r3(max(0, kstart - 0.03))});' if is_kw
                else f'tl.from("#{kid}", {{ opacity: 0, y: 8, duration: 0.12, ease: "power2.out" }}, {r3(max(0, kstart - 0.03))});') for kid, kstart, is_kw in kw_tl])
    CAP_TL = cap_tl
    index = f"""<!doctype html>
<html lang="{LANG}">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <title>{esc(sb.get("title", "reel"))}</title>
    <script src="assets/gsap.min.js"></script>
    <link rel="stylesheet" href="tokens.css" />
    <style>
      /* generated by scripts/build-reel.py: edit storyboard.json, not this file */
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      html, body {{ width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; }}
      #root-bg {{ position: absolute; inset: 0; background: var(--paper); }}
      .face-c {{ position: absolute; left: 0; top: 0; width: 1080px; height: 1000px; overflow: hidden; z-index: 0; }}
      .face-f {{ position: absolute; inset: 0; overflow: hidden; z-index: 0; }}
      .face-s {{ position: absolute; left: 0; top: 880px; width: 1080px; height: 1040px; overflow: hidden; z-index: 0; }}
      .face-s video {{ width: 100%; height: 100%; object-fit: cover; }}
      .face-b {{ position: absolute; left: 90px; top: 1030px; width: 900px; height: 780px; z-index: 3; }}
      .face-c video, .face-f video, .face-b video {{ width: 100%; height: 100%; object-fit: cover; }}
      /* rayon et ombre sur la vidéo (un clip, donc cachée hors de sa fenêtre), jamais sur le wrapper non timé */
      .face-b video {{ border-radius: var(--radius-face); box-shadow: var(--shadow-face); }}
      .scene {{ position: absolute; inset: 0; z-index: 1; }}
      {CAP_CSS}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="{esc(sb.get("id", "reel"))}" data-start="0" data-duration="{r3(DURATION)}" data-width="{W}" data-height="{H}">
      <div id="root-bg"></div>
      <!-- speaker: one clip per scene, same source, data-media-start = scene time -->
      {chr(10).join("      " + x for x in face_clips)}
      <audio id="voice" class="clip" src="{esc(AUDIO)}" data-start="0" data-duration="{r3(DURATION)}" data-track-index="10" data-volume="1"></audio>
      <!-- scenes -->
      {chr(10).join("      " + x for x in scene_clips)}
      <!-- captions -->
      {chr(10).join("      " + x for x in caps)}
    </div>
    <script>
      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});
      document.querySelectorAll(".face-c").forEach((el) => tl.fromTo(el, {{ scale: 1.0 }}, {{ scale: 1.04, duration: 4, ease: "none", transformOrigin: "50% 40%" }}, 0));
      {CAP_TL}
      tl.to({{}}, {{ duration: {r3(DURATION)} }}, 0);
      window.__timelines["{esc(sb.get("id", "reel"))}"] = tl;
    </script>
  </body>
</html>
"""
    (ROOT / "index.html").write_text(index)
    write_plan(sb["scenes"], caps)
    print(f"{len(sb['scenes'])} scenes, {len(caps)} captions, {len(face_clips)} speaker clips → index.html + assets/plan.json")


LAYOUT_NATE = {"C": "split", "B": "split", "D": "paper", "F": "face", "S": "split", "Y": "face"}


def write_plan(scenes, caps):
    """assets/plan.json in the validate-plan.mjs schema: scenes anchored to a word, real events, caption groups."""
    words = apply_lexicon(transcript.get("words", []))
    plan_scenes, events, ledger = [], [], []
    staging_path = ROOT / "assets" / "broll" / "ledger.json"   # written by footage.py: every clip brought in
    staging = json.loads(staging_path.read_text()) if staging_path.exists() else []
    for sc in scenes:
        start, end = float(sc["start"]), float(sc["end"])
        anchor = next((w for w in words if start - 0.15 <= w["start"] <= start + 0.2), None)
        if anchor is None:
            anchor = min(words, key=lambda w: abs(w["start"] - start)) if words else None
        entry = {"id": sc["id"], "start": round(start, 3), "end": round(end, 3), "layout": LAYOUT_NATE.get(sc["layout"], "face"),
                 "kind": sc.get("kind", "hook" if start == 0 else ("cta" if sc.get("keyword") else "beat")),
                 "anchor": anchor["text"] if anchor else "", "anchorTime": anchor["start"] if anchor else start}
        vids = [it for it in (sc.get("zone") or {}).get("items", []) if it.get("type") == "video"]
        if vids:
            v = vids[0]
            slug = pathlib.Path(v["src"]).stem
            entry["layout"], entry["kind"] = "broll-split", f"broll/{slug}"
            staged = next((r for r in staging if r.get("sourceSceneId") == slug or r.get("asset") == v["src"]), None)
            v_at = resolve_at(v.get("at", start), start, end)
            v_end = resolve_at(v["out_at"], start, end) if v.get("out_at") is not None else end
            ms = float(v.get("media_start", 0))
            ledger.append({"scene": sc["id"], "sourceSceneId": slug, "asset": v["src"],
                           "sha256": staged["sha256"] if staged else hashlib.sha256((ROOT / v["src"]).read_bytes()).hexdigest(),
                           "sourceStart": round(ms, 3), "sourceEnd": round(ms + (v_end - v_at), 3),
                           "provenance": staged.get("provenance") if staged else None, "why": staged.get("why", "") if staged else "",
                           "rights": staged.get("rights", "") if staged else ""})
        if sc.get("holdReason"):
            entry["holdReason"] = sc["holdReason"]
        elif sc["layout"] == "F" and not sc.get("keyword") and not sc.get("tag"):
            entry["holdReason"] = "face only, the viewer follows the speech"
        plan_scenes.append(entry)
        if sc["layout"] not in ("F", "S") or sc.get("tag") or sc.get("keyword"):
            events.append({"time": round(start + 0.1, 3), "type": "scene-enter", "visual": sc["id"], "anchor": entry["anchor"]})
        for mv in sc.get("face", []):
            events.append({"time": round(min(resolve_at(mv.get("at", start), start, end), end - 0.01), 3), "type": "face-move", "visual": sc["id"], "anchor": str(mv.get("at", ""))})
        for it in ((sc.get("overlay") or {}).get("items", []) + (sc.get("zone") or {}).get("items", [])):
            t = resolve_at(it.get("at", start), start, end)
            events.append({"time": round(min(t, end - 0.01), 3), "type": "overlay-pop", "visual": sc["id"], "anchor": str(it.get("at", ""))})
            for key in ("strike_at", "circle_at", "underline_at", "dim_at"):
                if it.get(key) is not None:
                    events.append({"time": round(resolve_at(it[key], start, end), 3), "type": key.replace("_at", ""), "visual": sc["id"], "anchor": str(it[key])})
    for kid, kstart, is_kw in kw_tl:
        if is_kw:
            sc = next((s for s in plan_scenes if s["start"] <= kstart < s["end"]), plan_scenes[-1])
            w = next((w for w in words if abs(w["start"] - kstart) < 0.01), None)
            events.append({"time": round(kstart, 3), "type": "caption-emphasis", "visual": sc["id"], "anchor": w["text"] if w else ""})
    events.sort(key=lambda e: e["time"])
    # caption groups: same words as the transcript (the validator compares word by word)
    groups, i = [], 0
    for c in caps:
        m = re.findall(r'id="cap-\d+-w\d+">([^<]*)<', c)
        n = len(m)
        grp = words[i:i + n]; i += n
        if grp:
            groups.append({"start": grp[0]["start"], "end": grp[-1]["end"], "words": [{k: w.get(k) for k in ("text", "start", "end", "sourceStart", "sourceEnd")} for w in grp]})
    plan = {"duration": round(DURATION, 3), "fps": FPS, "scenes": plan_scenes, "events": events, "captions": groups}
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "assets" / "footage-ledger.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=1))
    (ROOT / "assets" / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    build()
