#!/usr/bin/env python3
"""transcribe.py — transcription in the common format of Nate Herk's kit. ElevenLabs Scribe by default, local WhisperX as fallback.

Usage: python3 scripts/transcribe.py <rush> [--out assets/derush/raw.json] [--engine scribe|whisperx] [--lang fr]
       [--segments segments.json]  # [{in,out}] in seconds: words are sorted by take. Scribe: a single call for the whole
                                   # rush. WhisperX: each take transcribed on its own (Whisper on the whole file swallows
                                   # retakes and can skip a take, measured 22/09 on a real talking-head rush).
       [--keep-number-words]       # keep « quarante mille » instead of « 40 000 »

Output: { text, audio_duration_secs, language, model, words: [{ text, start, end, type: "word", segment? }] }
This is the format Nate documents (docs/TOOLS-AND-API-KEYS.md) and that takes.py then stage.py read.

Scribe: `ELEVENLABS_API_KEY` in the environment (e.g. ~/.exports.sh), $0.22 per hour of audio. Measured 22/09: every retake
kept, word onsets within ±0.03 s. It writes numbers in words: converted to digits here (≥ 10, and « pour cent » → %).
WhisperX: env ~/.reel-kit/venv (scripts/setup-whisperx.sh), CPU, French wav2vec2 alignment.
"""
import argparse, json, os, subprocess, sys, tempfile, urllib.error, urllib.request, uuid, warnings
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("media")
ap.add_argument("--out")
ap.add_argument("--engine", choices=["scribe", "whisperx"])
ap.add_argument("--lang", default="fr")
ap.add_argument("--model", default=None, help="scribe_v2 (Scribe) or large-v3-turbo (WhisperX)")
ap.add_argument("--segments", help="JSON [{in,out}]: words sorted by take")
ap.add_argument("--keep-number-words", action="store_true")
ap.add_argument("--device", default="cpu")
ap.add_argument("--threads", type=int, default=8)
args = ap.parse_args()

VENV = Path.home() / ".reel-kit/venv/bin/python"
engine = args.engine or ("scribe" if os.environ.get("ELEVENLABS_API_KEY") else "whisperx")
if engine == "whisperx" and Path(sys.executable).resolve() != VENV.resolve():
    if not VENV.exists():
        sys.exit("neither an ELEVENLABS_API_KEY key (Scribe) nor ~/.reel-kit/venv (WhisperX, scripts/setup-whisperx.sh)")
    os.execv(str(VENV), [str(VENV), __file__, *sys.argv[1:], "--engine", "whisperx"])

src = Path(args.media)
out = Path(args.out) if args.out else src.with_suffix(".json")
slices = None
if args.segments:
    slices = [(float(s["in"]), float(s["out"]), k) for k, s in enumerate(json.load(open(args.segments)))]


def run_scribe(model):
    key = os.environ["ELEVENLABS_API_KEY"]
    tmp = Path(tempfile.mkdtemp(prefix="scribe-")) / "audio.m4a"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "aac", "-b:a", "64k", str(tmp)], check=True)
    b = uuid.uuid4().hex
    fields = {"model_id": model, "timestamps_granularity": "word", "diarize": "false", "tag_audio_events": "false", "language_code": args.lang}
    body = b"".join(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode() for k, v in fields.items())
    body += f'--{b}\r\nContent-Disposition: form-data; name="file"; filename="audio.m4a"\r\nContent-Type: audio/mp4\r\n\r\n'.encode() + tmp.read_bytes() + f"\r\n--{b}--\r\n".encode()
    req = urllib.request.Request("https://api.elevenlabs.io/v1/speech-to-text", data=body,
                                 headers={"xi-api-key": key, "Content-Type": f"multipart/form-data; boundary={b}"})
    try:
        with urllib.request.urlopen(req, timeout=900) as r:
            d = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Scribe HTTP {e.code}: {e.read().decode()[:400]}")
    words = [{"text": w["text"].strip(), "start": float(w["start"]), "end": float(w["end"])} for w in d["words"] if w.get("type") == "word" and w["text"].strip()]
    dur = float(d.get("audio_duration_secs") or (words[-1]["end"] if words else 0))
    if slices:
        kept = []
        for w in words:
            k = next((k for t0, t1, k in slices if t0 - 0.05 <= w["start"] < t1), None)
            if k is not None:
                kept.append({**w, "segment": k})
        words = kept
    print(f"Scribe {model}: {dur / 60:.1f} min of audio ≈ {dur / 3600 * 0.22 * 100:.1f} cent(s)")
    return words, dur, f"elevenlabs/{model}"


def run_whisperx(model):
    warnings.filterwarnings("ignore")
    import whisperx
    audio = whisperx.load_audio(str(src))
    dur = len(audio) / 16000
    asr = whisperx.load_model(model, args.device, compute_type="int8", language=args.lang, vad_method="silero", threads=args.threads)
    align_model, meta = whisperx.load_align_model(language_code=args.lang, device=args.device)
    words = []
    for t0, t1, k in (slices or [(0.0, dur, None)]):
        part = audio[int(t0 * 16000): int(t1 * 16000)]
        if len(part) < 1600:
            continue
        res = asr.transcribe(part, batch_size=8, language=args.lang)
        if not res["segments"]:
            continue
        aligned = whisperx.align(res["segments"], align_model, meta, part, args.device, return_char_alignments=False)
        seg_words = []
        for seg in aligned["segments"]:
            for w in seg.get("words", []):
                if w["word"].strip():
                    seg_words.append({"text": w["word"].strip(), "start": w.get("start"), "end": w.get("end"), "segment": k})
        # words without alignment (digits, symbols): time spread between the neighbours, within the take
        i = 0
        while i < len(seg_words):
            if seg_words[i]["start"] is None:
                j = i
                while j < len(seg_words) and seg_words[j]["start"] is None:
                    j += 1
                lo = seg_words[i - 1]["end"] if i > 0 else 0.0
                hi = seg_words[j]["start"] if j < len(seg_words) else min(t1 - t0, lo + 0.35 * (j - i))
                step = max(0.05, (hi - lo) / (j - i))
                for m in range(i, j):
                    seg_words[m]["start"], seg_words[m]["end"] = lo + step * (m - i), lo + step * (m - i + 1)
                i = j
            else:
                i += 1
        for w in seg_words:
            w["start"], w["end"] = t0 + float(w["start"]), t0 + float(w["end"])
            if k is None:
                w.pop("segment")
        words += seg_words
    return words, dur, f"whisperx/{model}"


# ----------------------------------------------------------------------------- number words → digits
UNITS = {"zéro": 0, "zero": 0, "un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9,
         "dix": 10, "onze": 11, "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16}
TENS = {"vingt": 20, "vingts": 20, "trente": 30, "quarante": 40, "cinquante": 50, "soixante": 60}
MULT = {"cent": 100, "cents": 100, "mille": 1000, "million": 10 ** 6, "millions": 10 ** 6, "milliard": 10 ** 9, "milliards": 10 ** 9}
PUNCT = ".,;:!?…«»\"'’"


def word_value(text):
    """« quatre-vingt-quatre » → ('n', 84) · « mille » → ('m', 1000) · otherwise None."""
    t = text.strip(PUNCT).lower().replace("’", "'")
    if t in MULT:
        return ("m", MULT[t])
    parts = [p for p in t.split("-") if p and p != "et"]
    if not parts or not all(p in UNITS or p in TENS or p == "quatre" for p in parts):
        return None
    v, i = 0, 0
    while i < len(parts):
        p = parts[i]
        if p == "quatre" and i + 1 < len(parts) and parts[i + 1] in ("vingt", "vingts"):
            v += 80; i += 2; continue
        v += UNITS.get(p, TENS.get(p, 0)); i += 1
    return ("n", v)


def numbers_to_digits(words):
    out, i = [], 0
    while i < len(words):
        j, group = i, []
        while j < len(words):
            wv = word_value(words[j]["text"])
            if wv is None:
                t = words[j]["text"].strip(PUNCT).lower()
                # « vingt et un », « soixante et onze » (French "et" inside a number)
                if t == "et" and group and group[-1][1][0] == "n" and group[-1][1][1] in TENS.values() and j + 1 < len(words) \
                        and (word_value(words[j + 1]["text"]) or (None,))[0] == "n":
                    group.append((words[j], ("et", 0))); j += 1; continue
                break
            group.append((words[j], wv)); j += 1
            if words[j - 1]["text"].rstrip()[-1:] in ".!?":  # end of sentence: the number stops
                break
        if not group:
            out.append(words[i]); i += 1; continue
        total, cur = 0, 0
        for _, (kind, v) in group:
            if kind == "n":
                cur += v
            elif kind == "m" and v == 100:
                cur = (cur or 1) * 100
            elif kind == "m":
                total += (cur or 1) * v; cur = 0
        value = total + cur
        if value < 10:
            out += [w for w, _ in group]; i = j; continue
        text = str(value) if 1900 <= value < 2100 else f"{value:,}".replace(",", " ")  # a year is written without a space
        last = group[-1][0]
        if j + 1 < len(words) and words[j]["text"].strip(PUNCT).lower() == "pour" and words[j + 1]["text"].strip(PUNCT).lower() == "cent":
            text += " %"; last = words[j + 1]; j += 2
        tail = last["text"][len(last["text"].rstrip(PUNCT)):]
        out.append({**group[0][0], "text": text + tail, "start": group[0][0]["start"], "end": last["end"]})
        i = j
    return out


if engine == "scribe":
    words, dur, model = run_scribe(args.model or "scribe_v2")
else:
    words, dur, model = run_whisperx(args.model or "large-v3-turbo")
if not args.keep_number_words:
    words = numbers_to_digits(words)
for w in words:
    w["start"], w["end"], w["type"] = round(float(w["start"]), 3), round(float(w["end"]), 3), "word"
for a, b in zip(words, words[1:]):  # never overlap
    if a["end"] > b["start"]:
        a["end"] = b["start"]

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps({"text": " ".join(w["text"] for w in words), "audio_duration_secs": round(dur, 3), "language": args.lang,
                           "model": model, "words": words}, ensure_ascii=False, indent=1))
print(f"{len(words)} words · {dur:.1f} s · {out}")
