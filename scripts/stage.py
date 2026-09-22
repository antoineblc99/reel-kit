#!/usr/bin/env python3
"""stage.py — cuts the rush according to the validated takes and produces the assets in Nate Herk's schema.

Usage: python3 scripts/stage.py [--derush assets/derush] [--fps 30]

Reads : assets/derush/raw.mp4, raw.segments.json [{name,in,out}], raw.captions.json [{text,startMs,endMs}]  (output of takes.py)
Writes: assets/speaker.mp4      (trim+concat cut, H.264 yuv420p, one keyframe per second, no sound)
        assets/reel-audio.wav   (voice of the cut, loudnorm −16 LUFS, PCM 48 kHz)
        assets/transcript.json  {words:[{text,start,end,sourceStart,sourceEnd}], text, breaks}
        assets/edit-decisions.json {duration, fps, keeps:[{sourceStart,sourceEnd,start,end}], removals}
These two JSON files are the ones validate-plan.mjs and build-reel.py read.

The cut is a trim/atrim + concat (never a select mask: it would ignore the order of the takes). Boundaries are
frame-aligned so that video, sound and words stay in sync.
"""
import argparse, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sdr import sdr_vf, SDR_TAGS

ap = argparse.ArgumentParser()
ap.add_argument("--derush", default="assets/derush")
ap.add_argument("--fps", type=int, default=30)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parent.parent
D = (ROOT / args.derush) if not Path(args.derush).is_absolute() else Path(args.derush)
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)
FPS = args.fps
raw = D / "raw.mp4"
segs = json.loads((D / "raw.segments.json").read_text())
raw_words = json.loads((D / "raw.captions.json").read_text())

# 1. cut plan, frame-aligned
plan, frames = [], 0
for s in segs:
    fa, fb = round(s["in"] * FPS), round(s["out"] * FPS)
    plan.append({"name": s["name"], "fa": fa, "fb": fb, "offset": frames})
    frames += fb - fa
trims = ";".join(f"[0:v]trim=start_frame={p['fa']}:end_frame={p['fb']},setpts=PTS-STARTPTS[v{i}];"
                 f"[0:a]atrim=start={p['fa'] / FPS}:end={p['fb'] / FPS},asetpts=PTS-STARTPTS[a{i}]" for i, p in enumerate(plan))
concat = "".join(f"[v{i}][a{i}]" for i in range(len(plan))) + f"concat=n={len(plan)}:v=1:a=1[v0][a0];[v0]{sdr_vf(raw)}[v];[a0]loudnorm=I=-16:TP=-1.5:LRA=11[a]"
print(f"cut: {len(plan)} takes → {frames} frames ({frames / FPS:.2f} s) · order {' · '.join(p['name'] for p in plan)}")
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(raw), "-filter_complex", f"{trims};{concat}",
                "-map", "[v]", *SDR_TAGS, "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-r", str(FPS),
                "-g", str(FPS), "-keyint_min", str(FPS), "-movflags", "+faststart", "-an", str(ASSETS / "speaker.mp4"),
                "-map", "[a]", "-ac", "2", "-ar", "48000", "-c:a", "pcm_s16le", str(ASSETS / "reel-audio.wav")], check=True)
duration = round(float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                                str(ASSETS / "speaker.mp4")]).decode().strip()), 3)

# 2. edit decisions (Nate's schema)
keeps = [{"sourceStart": round(p["fa"] / FPS, 3), "sourceEnd": round(p["fb"] / FPS, 3),
          "start": round(p["offset"] / FPS, 3), "end": round((p["offset"] + p["fb"] - p["fa"]) / FPS, 3)} for p in plan]
removals, prev = [], 0.0
for k in keeps:
    if k["sourceStart"] - prev > 0.05:
        removals.append({"sourceStart": round(prev, 3), "sourceEnd": k["sourceStart"], "reason": "silence or retake (takes.py)"})
    prev = k["sourceEnd"]

# 3. words re-timed onto the cut
words = []
for k in keeps:
    shift = k["start"] - k["sourceStart"]
    for w in raw_words:
        ws = w["startMs"] / 1000
        if not (k["sourceStart"] - 0.02 <= ws < k["sourceEnd"]):
            continue
        start = round(max(k["start"], ws + shift), 3)
        end = round(min(k["end"], w["endMs"] / 1000 + shift), 3)
        if end <= start:
            continue
        words.append({"text": w["text"].strip(), "start": start, "end": end,
                      "sourceStart": round(start - shift, 3), "sourceEnd": round(end - shift, 3)})
for a, b in zip(words, words[1:]):  # never overlap (Nate's validator rejects it)
    if a["end"] > b["start"]:
        a["end"] = round(b["start"], 3)
        a["sourceEnd"] = round(a["sourceStart"] + (a["end"] - a["start"]), 3)

(ASSETS / "transcript.json").write_text(json.dumps({"words": words, "text": " ".join(w["text"] for w in words),
                                                    "breaks": [k["start"] for k in keeps[1:]]}, ensure_ascii=False, indent=1))
(ASSETS / "edit-decisions.json").write_text(json.dumps({"duration": duration, "fps": FPS, "keeps": keeps, "removals": removals}, indent=1))
print(f"speaker.mp4 {duration} s · reel-audio.wav · {len(keeps)} takes · {len(words)} words · transcript.json + edit-decisions.json → assets/")
