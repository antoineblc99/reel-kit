#!/usr/bin/env python3
"""takes.py — derush by takes: measured silences, boundaries on the waveform, transcription PER TAKE, retakes detected.

Usage: python3 scripts/takes.py <rush.mov> [--out raw.segments.json] [--captions raw.captions.json]
       [--transcribe "python3 scripts/transcribe.py"] [--keep-json takes.json]   # Scribe by default, WhisperX without a key

Why per take: whisper run on the whole file swallows repetitions (false start followed by the same sentence,
sentence said again): the retake vanishes from the transcript and we keep it twice in the edit. Each take transcribed
on its own cannot be merged with the next one. Then neighbouring takes are compared:
  - next take contains the previous one → drop the previous one;
  - same shared 3-gram and similar lengths → retake, drop the previous one;
  - short take (≤ 3 words) whose words are all in the next one → false start, dropped;
  - the next one starts with the end of the previous one → trim the end of the previous one.
Output: raw.segments.json [{name,in,out}] + raw.captions.json [{text,startMs,endMs}] verbatim, ready for cut.mjs.
Every decision is printed: this is the list the user validates (derush gate).
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, unicodedata
from pathlib import Path

import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("rush")
ap.add_argument("--derush", default="assets/derush", help="output folder inside the reel: raw.mp4, raw.segments.json, raw.captions.json, takes.json")
ap.add_argument("--out", default=None)
ap.add_argument("--captions", default=None)
ap.add_argument("--transcribe", default=os.environ.get("TRANSCRIBE", f"python3 {Path(__file__).resolve().parent}/transcribe.py"), help="Scribe if ELEVENLABS_API_KEY is set, otherwise WhisperX")
ap.add_argument("--keep-json", default=None)
ap.add_argument("--fps", type=int, default=30)
ap.add_argument("--min-silence", type=float, default=0.35)
ap.add_argument("--head", type=float, default=0.05)
ap.add_argument("--tail", type=float, default=0.10)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parent.parent
D = (ROOT / args.derush) if not Path(args.derush).is_absolute() else Path(args.derush)
D.mkdir(parents=True, exist_ok=True)
args.out = args.out or str(D / "raw.segments.json")
args.captions = args.captions or str(D / "raw.captions.json")
args.keep_json = args.keep_json or str(D / "takes.json")
rush = Path(args.rush).expanduser().resolve()
raw = D / "raw.mp4"
if raw.resolve() != rush:
    probe = subprocess.check_output(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name,pix_fmt,r_frame_rate",
                                     "-of", "csv=p=0", str(rush)]).decode().strip().split(",")
    if probe[:2] == ["h264", "yuv420p"] and probe[2] in (f"{args.fps}/1", f"{args.fps * 1000}/1001"):
        shutil.copy(rush, raw)
    else:
        print(f"rush {probe[0]} {probe[1]} {probe[2]} → H.264 yuv420p {args.fps} fps: {raw.relative_to(ROOT)}")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(rush), "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p",
                        "-r", str(args.fps), "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(raw)], check=True)
rush = raw
tmp = Path(tempfile.mkdtemp(prefix="takes-"))
dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(rush)]).decode().strip())

# 1. 10 ms envelope, 120 Hz high-pass
pcm = tmp / "raw16.pcm"
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(rush), "-vn", "-ac", "1", "-ar", "16000", "-af", "highpass=f=120", "-f", "s16le", "-c:a", "pcm_s16le", str(pcm)], check=True)
x = np.frombuffer(pcm.read_bytes(), dtype=np.int16).astype(np.float32) / 32768
win = 160
n = len(x) // win
db = 20 * np.log10(np.sqrt((x[: n * win].reshape(n, win) ** 2).mean(1) + 1e-12) + 1e-9)
floor = float(np.percentile(db, 5))
speech = float(np.percentile(db, 80))
voice_thr = floor + 18
# silencedetect threshold: halfway down the dip between floor and speech, never a fixed number
sd_thr = round((floor + speech) / 2)
print(f"duration {dur:.1f} s · floor {floor:.1f} dB · speech {speech:.1f} dB · silence threshold {sd_thr} dB · voice threshold {voice_thr:.1f} dB")

# 2. silences
out = subprocess.run(["ffmpeg", "-v", "info", "-i", str(rush), "-vn", "-af", f"highpass=f=120,silencedetect=noise={sd_thr}dB:d=0.30", "-f", "null", "-"], capture_output=True, text=True).stderr
starts = [float(v) for v in re.findall(r"silence_start: ([0-9.]+)", out)]
ends = [float(v) for v in re.findall(r"silence_end: ([0-9.]+)", out)]
sil = [(a, b) for a, b in zip(starts, ends) if b - a > args.min_silence]
runs, cur = [], 0.0
for a, b in sil:
    if a > cur + 0.25:
        runs.append((cur, a))
    cur = b
if dur - cur > 0.4:
    runs.append((cur, dur))


def onset(a, b):
    i = int(a * 100)
    while i < int(b * 100) - 3:
        if db[i] > voice_thr and db[i + 1] > voice_thr and db[i + 2] > voice_thr:
            return i / 100
        i += 1


def offset(a, b):
    i = min(int(b * 100), len(db)) - 1
    while i > int(a * 100) + 3:
        if db[i] > voice_thr and db[i - 1] > voice_thr and db[i - 2] > voice_thr:
            return (i + 1) / 100
        i -= 1


takes = []
for a, b in runs:
    on, off = onset(max(0, a - 0.3), b), offset(a, min(dur, b + 0.6))
    if on is None or off is None or off - on < 0.35:
        continue
    takes.append({"in": round(max(0, on - args.head), 2), "out": round(min(dur, off + args.tail), 2)})
print(f"{len(takes)} speech takes")

# 3. transcription: Scribe (one call, words sorted by take) or WhisperX (each take transcribed on its own)
(tmp / "takes-in.json").write_text(json.dumps([{"in": t["in"], "out": t["out"]} for t in takes]))
r = subprocess.run(args.transcribe.split() + [str(rush), "--segments", str(tmp / "takes-in.json"), "--out", str(tmp / "takes-words.json")],
                   capture_output=True, text=True)
if r.returncode:
    sys.exit("transcription failed:\n" + r.stderr[-2000:])
for t in takes:
    t["words"] = []
for v in json.loads((tmp / "takes-words.json").read_text())["words"]:
    takes[v["segment"]]["words"].append({"text": v["text"].strip(".,;:!?…«»\""), "start": v["start"], "end": v["end"]})
for t in takes:
    t["words"] = [w for w in t["words"] if w["text"]]
    t["text"] = " ".join(v["text"] for v in t["words"])


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    s = re.sub(r"[̀-ͯ]", "", s)
    s = re.sub(r"[^a-z0-9' ]", " ", s)
    return [v.rstrip("s") if len(v) > 3 else v for v in s.split()]


def ngrams(ws, k=3):
    return {tuple(ws[i: i + k]) for i in range(len(ws) - k + 1)}


# 4. retakes between neighbouring takes
for t in takes:
    t["norm"], t["keep"], t["why"] = norm(t["text"]), True, ""
for i in range(len(takes) - 1):
    A, B = takes[i], takes[i + 1]
    a, b = A["norm"], B["norm"]
    if not a:
        A["keep"], A["why"] = False, "empty"
        continue
    if len(a) <= 3 and all(v in b for v in a):
        A["keep"], A["why"] = False, "false start"
        continue
    if " ".join(a) in " ".join(b):
        A["keep"], A["why"] = False, "contained in the next one"
        continue
    shared = ngrams(a) & ngrams(b)
    if shared and abs(len(a) - len(b)) <= 4 and len(shared) >= max(1, len(ngrams(a)) // 3):
        A["keep"], A["why"] = False, "retake, keeping the next one"
        continue
    for k in (3, 2):
        if len(a) > k and a[-k:] == b[:k]:
            A["trim_out"] = round(A["words"][len(A["words"]) - k]["start"] - 0.05, 2)
            A["why"] = f"end trimmed: « {' '.join(A['text'].split()[-k:])} » repeated at the start of the next one"
            break

print("\ntake   in→out            decision")
segs, words = [], []
for i, t in enumerate(takes, 1):
    d = ("kept" if t["keep"] else "DROPPED") + (f" until {t['trim_out']}" if t.get("trim_out") else "")
    print(f"{i:02d}  {t['in']:7.2f}→{t['out']:7.2f}  {d:22} {t['why']:45} {t['text'][:60]}")
    if not t["keep"]:
        continue
    end = t.get("trim_out", t["out"])
    segs.append({"name": f"t{i:02d}", "in": t["in"], "out": end})
    words += [v for v in t["words"] if v["start"] < end - 0.02]

Path(args.out).write_text(json.dumps(segs, indent=1))
Path(args.captions).write_text(json.dumps([{"text": " " + v["text"], "startMs": int(v["start"] * 1000), "endMs": int(v["end"] * 1000)} for v in words], ensure_ascii=False, indent=1))
if args.keep_json:
    Path(args.keep_json).write_text(json.dumps(takes, ensure_ascii=False, indent=1))
print(f"\n{len(segs)} takes kept · {len(words)} words · duration ≈ {sum(s['out'] - s['in'] for s in segs):.1f} s → {args.out}, {args.captions}")
