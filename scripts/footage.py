#!/usr/bin/env python3
"""footage.py — bring a B-roll clip into the project with its provenance (gate 4, beats + assets).

Usage: python3 scripts/footage.py <url-or-file> --slug <name> [--from 12.0] [--to 18.0]
                                  [--why "what this shot proves"] [--rights "own footage | licensed | our product's screen"]

Writes: assets/broll/<slug>.mp4  (H.264 yuv420p 30 fps, keyframe every second; audio kept, mute it in the storyboard)
        assets/broll/<slug>.jpg  (poster frame)
        a row in assets/broll/ledger.json (every clip brought in; build-reel.py writes assets/footage-ledger.json
        with only the clips a scene uses, in Nate's schema):
        { sourceSceneId, asset, sha256, sourceStart, sourceEnd, duration, provenance, why, rights, addedAt }
URLs are downloaded with yt-dlp (best MP4 up to 1080p, no playlist). Local files are used as they are.
The `scene` field of a row is filled by build-reel.py when the clip is used in a storyboard zone item
{"type": "video", "src": "assets/broll/<slug>.mp4", ...}; Nate's validate-footage.mjs then checks hash, interval and use.

You are responsible for the rights on what you bring in. Prefer your own footage, licensed stock, or screen
captures of things you own. A YouTube video is someone else's work: quote it briefly and credit it, or do not use it.
"""
import argparse, datetime, hashlib, json, re, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sdr import sdr_vf, SDR_TAGS

ap = argparse.ArgumentParser()
ap.add_argument("source", help="URL (yt-dlp) or local video file")
ap.add_argument("--slug", required=True, help="short id, e.g. cge-table, app-demo-1")
ap.add_argument("--from", dest="t_in", type=float, default=None, help="start in the source, seconds")
ap.add_argument("--to", dest="t_out", type=float, default=None, help="end in the source, seconds")
ap.add_argument("--why", default="", help="what this shot proves in the beat plan")
ap.add_argument("--rights", default="", help="own footage | licensed | screen capture of our product | quoted with credit")
ap.add_argument("--fps", type=int, default=30)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parent.parent
BROLL = ROOT / "assets" / "broll"
BROLL.mkdir(parents=True, exist_ok=True)
if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", args.slug):
    sys.exit("--slug: lowercase letters, digits and dashes only")

src = args.source
if re.match(r"https?://", src):
    print(f"downloading {src} with yt-dlp …")
    out_tpl = str(BROLL / f"{args.slug}-source.%(ext)s")
    r = subprocess.run(["yt-dlp", "--no-playlist", "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[ext=mp4]/b",
                        "--merge-output-format", "mp4", "-o", out_tpl, src], capture_output=True, text=True)
    if r.returncode:
        sys.exit("yt-dlp failed:\n" + r.stderr[-1500:])
    files = sorted(BROLL.glob(f"{args.slug}-source.*"), key=lambda p: p.stat().st_mtime)
    if not files:
        sys.exit("yt-dlp produced no file")
    source_file = files[-1]
else:
    source_file = Path(src).expanduser().resolve()
    if not source_file.exists():
        sys.exit(f"no such file: {source_file}")

probe = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(source_file)]).decode().strip()
src_dur = float(probe)
t_in = args.t_in if args.t_in is not None else 0.0
t_out = args.t_out if args.t_out is not None else src_dur
if not (0 <= t_in < t_out <= src_dur + 0.05):
    sys.exit(f"interval {t_in}–{t_out} is outside the source ({src_dur:.2f} s)")

clip = BROLL / f"{args.slug}.mp4"
poster = BROLL / f"{args.slug}.jpg"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t_in:.3f}", "-to", f"{t_out:.3f}", "-i", str(source_file),
                "-vf", sdr_vf(source_file), *SDR_TAGS, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-r", str(args.fps),
                "-g", str(args.fps), "-keyint_min", str(args.fps), "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(clip)], check=True)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-frames:v", "1", "-q:v", "3", str(poster)], check=True)
dur = round(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(clip)]).decode().strip()), 3)
sha = hashlib.sha256(clip.read_bytes()).hexdigest()

ledger_path = BROLL / "ledger.json"
rows = json.loads(ledger_path.read_text()) if ledger_path.exists() else []
rows = [r for r in rows if r.get("sourceSceneId") != args.slug]
rows.append({
    "sourceSceneId": args.slug,
    "asset": str(clip.relative_to(ROOT)),
    "sha256": sha,
    "sourceStart": 0.0,
    "sourceEnd": dur,
    "duration": dur,
    "provenance": {"source": src, "file": str(source_file.relative_to(ROOT)) if source_file.is_relative_to(ROOT) else str(source_file),
                   "in": t_in, "out": t_out},
    "why": args.why,
    "rights": args.rights,
    "addedAt": datetime.datetime.now().isoformat(timespec="seconds"),
})
ledger_path.write_text(json.dumps(rows, ensure_ascii=False, indent=1))
print(f"{clip.relative_to(ROOT)}  {dur} s  poster {poster.name}  sha256 {sha[:12]}…  → assets/broll/ledger.json ({len(rows)} clips)")
if not args.rights:
    print("note: no --rights given. Say where this footage comes from before it goes in a beat.")
