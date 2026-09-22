# reel-kit — the map (Claude Code and Codex)

One video = one folder cloned from this kit. `CLAUDE.md` is a symlink to this file, so both agents read the same map.
**The playbook is Nate Herk's `short-form-edit` skill, kept verbatim in `.claude/skills/`** (Codex mirror: `.agents/skills/`).
This file does not rewrite it. For each of Nate's steps it names the local tool that does the work and the gate where the
user says "ok". When in doubt, Nate's skill wins; this file only says how we run it here.

The user validates at every gate. Nothing is built before the "ok" on the current gate. That is the whole method.

## First run: setup

If `./setup.sh` has never been run on this machine, run it first and read its output. It names each missing tool with the
command to install it. If no transcription engine is set up, walk the user through it in plain words: option A, an
ElevenLabs key (they create it at https://elevenlabs.io/app/settings/api-keys and put it themselves in a `.env` file in
the project, `ELEVENLABS_API_KEY=…`, or in their shell profile; **never ask them to paste the key into the chat**, and if a
key appears in the chat, tell them to revoke it); option B, `./setup.sh --whisperx` for a free local engine. Then run
`./setup.sh` again. For gate 7, the user connects PlugKit's MCP server from their PlugKit dashboard (MCP page); confirm
it with a `whoami` call before any publication step.

## Read in this order

1. `RUN.md` of the project: state, gates ticked, decisions.
2. `.claude/skills/short-form-edit/SKILL.md` (the playbook) and its references: `quality-gates.md`, `plan-schema.md`,
   `curiosity-and-entertainment.md`, `reference-analysis.md`, `premium-motion-and-footage.md`.
3. `DESIGN.md` (the kit's default paper look) and `MOTION.md` (motion rules and verification). A brand brief supplied by the
   user (tokens from a site capture, a logo, fonts) replaces the kit's look for that project.
4. `hyperframes-core` before writing any composition; `hyperframes-video-beats` and `video-storytelling` to plan beats.

## The seven gates

| # | Gate | Nate's step (short-form-edit) | Tool here | The user validates |
|---|---|---|---|---|
| 1 | **Framing** | Probe source and reference | Rush copied, never moved. `ffprobe` (format, rotation, pix_fmt). 16:9 rush → three vertical crops proposed on three moments. `takes.py` converts HEVC / 10-bit to H.264 `yuv420p` itself. | the crop |
| 2 | **Rough cut** | Silence + mistake tools, manual transcript review, render the clean cut once | `python3 scripts/takes.py <rush>` → `assets/derush/`: measured silence threshold, cut points on the waveform, transcription (ElevenLabs Scribe, words grouped per take, numbers as digits; WhisperX locally if no key), retakes and false starts detected, decision list printed; on a quiet or noisy track that yields one long take it splits on the word gaps of a whole-file Scribe transcript instead. Every clip is tone-mapped to SDR bt709 on the way in (`scripts/sdr.py`): an HDR source would switch HyperFrames to its HDR pipeline, which ghosts hidden layers. Then `python3 scripts/stage.py`: trim + concat → `assets/speaker.mp4`, `assets/reel-audio.wav`, `assets/transcript.json`, `assets/edit-decisions.json`. | the take list, then the cut-only video |
| 3 | **Captions** | Captions | One-scene `storyboard.json` (layout `F`, `caption_style` `pop` or `kit`) → `build-reel.py` → draft render. | caption style, spelling of names (`lexicon`) |
| 4 | **Beats and assets** | Reference analysis, asset shortlist, DESIGN.md, beat plan, OPEN-LOOPS | `REFERENCE-ANALYSIS.md` (timecode / idea / visual / sound / question / payoff), `DESIGN.md` of the project (audience, direction, shortlist, three opening concepts, sequences), `OPEN-LOOPS.json`, the beats table in chat, one line per beat, bare moments included. **Footage**: real screenshots first (`npx hyperframes capture <URL>` → `assets/captures/<slug>/`, brand tokens in `extracted/`), the user's own asset bank, then clips the user points to or the agent finds: `python3 scripts/footage.py <url-or-file> --slug x --from 12 --to 18 --why "…" --rights "…"` → `assets/broll/x.mp4` + `assets/broll/ledger.json` (build-reel.py then writes `assets/footage-ledger.json` for the clips actually used). Every asset has a provenance and a usable interval. No invented mockup when the real thing exists, no generated footage unless the user asks. | the beats table line by line, each B-roll with its reason and its rights |
| 5 | **Opening** | Three rough openings, compare the first 3 s | Three first frames (HTML + headless Chrome, or three storyboards) side by side. Choice and reason written in `DESIGN.md`. | A / B / C |
| 6 | **Animatic → final** | Animatic before polish, build the visual world, layers and actions, music, lint / preview / draft / final | Full `storyboard.json` → `python3 scripts/build-reel.py` → `compositions/`, `index.html`, captions, `assets/plan.json`. `npm run check` at 0, `node .claude/skills/short-form-edit/scripts/validate-plan.mjs .`, `validate-footage.mjs .` when B-roll is used, draft render → the user's feedback in sentences → v2, v3. Then Studio (`npm run dev`, give the exact URL printed) and `npm run render`. Three correction rounds max. Music and SFX (`media-use`, `hyperframes-audio`, 14–20 dB under the voice, −16 LUFS) only if the user wants them. | each animatic, the Studio pass, the final render |
| 7 | **Publish** | Delivery, VERIFY | `VERIFY.md` (hash, what was actually checked), `ENTERTAINMENT-REVIEW.md`. Publication through PlugKit's MCP server, see below. | caption, keyword, date |

### Gate 7 with PlugKit

PlugKit is connected to the agent as an MCP server (Claude Code or Codex). The calls, in order:

1. `whoami` → the profile and the connected accounts (Instagram, Facebook Page, TikTok, YouTube, X, LinkedIn).
2. `create_media_upload` with the file name → `uploadUrl`, `mediaUrl`, `singlePutMaxBytes`. The agent holds the file, so it
   sends it itself: `curl -T renders/<slug>.mp4 "<uploadUrl>"`. Above `singlePutMaxBytes`, hand the user `uploadPageUrl` instead.
3. `check_media_upload` with the `mediaUrl` until the file is there.
4. `create_post` with `profileId`, `accountIds`, `content` (the caption the user approved), `mediaUrls: [mediaUrl]`, and either
   `scheduledFor` + `timezone`, `publishNow: true`, or nothing (draft). Reels on Instagram: `shareToFeed` defaults to true.
   TikTok: read `get_publish_options` first and let the user choose the visibility.
5. If the caption has a keyword call to action ("comment KEYWORD"): `create_comment_automation` on the Instagram or Facebook
   account with `keywords`, `dmText`, `dmButtonLabel` + `dmButtonUrl`, **before** the post goes live. A comment posted before
   the automation exists never gets its DM.

Nothing is uploaded or published without the user's explicit "ok" on the caption, the keyword and the date.

## Files of a project

```
<project>/
├── RUN.md · DESIGN.md · REFERENCE-ANALYSIS.md · OPEN-LOOPS.json · ENTERTAINMENT-REVIEW.md · VERIFY.md
├── storyboard.json            scenes, the source of the build (format below)
├── assets/                    speaker.mp4, reel-audio.wav (ignored by git) · transcript.json · edit-decisions.json · plan.json (generated)
│                              derush/ (raw.mp4 ignored, raw.segments.json, raw.captions.json, takes.json)
│                              broll/ (clips ignored, ledger.json) · footage-ledger.json (generated) · captures/ · brand/ · fonts/
├── index.html · compositions/ generated by build-reel.py, never edited by hand
├── scripts/                   takes.py · transcribe.py · stage.py · footage.py · build-reel.py · preflight · beat-sync · frames · sync-codex-skills
└── .claude/skills/ (canon) · .agents/skills/ (Codex mirror) · .codex/config.toml
```

## storyboard.json

```json
{ "id": "slug", "title": "…", "duration": 35.8, "fps": 30, "speaker": "assets/speaker.mp4", "audio": "assets/reel-audio.wav",
  "caption_style": "pop", "caption_font": "\"Helvetica Neue\", Helvetica, Arial, sans-serif", "caption_accent": "#D40F30", "caption_size": 62,
  "caption_max_words": 3, "keywords": ["salaries", "managers", "40 825"], "lexicon": {"cloud": "Claude"},
  "brand": {"bg": "#F3F1EE", "ink": "#0F0D0D", "accent": "#D40F30", "font": "\"Helvetica Neue\", Helvetica, Arial, sans-serif"},
  "locale": "fr-FR", "freeze_tail": 3.0, "face_pos_s": "50% 72%",
  "scenes": [
    { "layout": "S", "start": 0, "end": 4.5, "holdReason": "the duel stays on screen until the source", "zone": { "out": 4.35, "items": [
        { "type": "card", "title": "Engineering<br>school", "logos": ["assets/brand/a.png", "assets/brand/b.png"], "cols": 2, "x": 40, "y": 80, "w": 480, "h": 440, "from": "left", "at": 0.15 },
        { "type": "badge", "text": "VS", "x": 480, "y": 150, "at": 2.3 },
        { "type": "stamp", "text": "WHO EARNS MORE?", "x": 130, "y": 590, "at": "w:more" } ] } },
    { "layout": "F", "start": 4.5, "end": 6.5, "cap_top": 1580, "holdReason": "transition, the source is coming" },
    { "layout": "S", "start": 6.5, "end": 8.5, "zone": { "items": [
        { "type": "image", "src": "assets/captures/report/table.png", "x": 40, "y": 120, "w": 1000, "at": 6.55, "highlights": [[419, 395, 81, 31]], "highlight_at": 7.0, "zoom_at": 7.25, "zoom": 1.9, "origin": "48% 76%" } ] } },
    { "layout": "S", "start": 8.5, "end": 14, "zone": { "items": [
        { "type": "card", "title": "Managers", "label": "BUSINESS SCHOOL · 2026 AVERAGE", "value": 40825, "suffix": " €", "count": 0.9, "x": 40, "y": 110, "w": 480, "h": 400, "at": "w:40 825" },
        { "type": "video", "src": "assets/broll/campus.mp4", "x": 560, "y": 110, "w": 480, "h": 400, "at": 10, "media_start": 2, "out_at": 13.5 } ] } },
    { "layout": "S", "start": 14, "end": 21, "zone": { "items": [ { "type": "big", "value": 1540, "suffix": " €", "label": "GAP PER YEAR", "y": 470, "size": 200, "at": "w:1 540", "count": 0.7, "circle_at": 20.6 } ] } },
    { "layout": "S", "start": 31, "end": 35.7, "zone": { "items": [ { "type": "check", "n": "#1", "text": "the jobs you aim for", "x": 60, "y": 120, "w": 960, "at": "w:jobs", "check_at": "w:aim" } ] } },
    { "layout": "S", "start": 35.7, "end": 38.8, "kind": "cta", "holdReason": "end screen", "zone": { "full": true, "gradient": true, "in": 35.8, "items": [
        { "type": "logo", "src": "assets/brand/icon.png", "x": 410, "y": 120, "w": 260, "at": 35.95 },
        { "type": "photo", "src": "assets/brand/team.jpg", "x": 180, "y": 430, "w": 720, "h": 740, "rotate": -3, "drift": true, "at": 36.15 },
        { "type": "line", "text": "Tap the button", "x": "center", "y": 1290, "size": 84, "weight": 800, "color": "#0F0D0D", "at": 36.6 },
        { "type": "chevrons", "y": 1520, "at": 37.05 } ] } }
  ] }
```

Layouts: **F** full-frame face, optional `overlay` (text, image, chevrons) or CTA card `keyword` · **S** Nate's split: a screen
zone on top (0→880 px, brand colors) and the face below; `zone.items` of type `card`, `badge`, `stamp`, `image`, `video`,
`big`, `check`, `logo`, `photo`, `chevrons`, `line`; `zone.full` + `in` = a full-frame end screen that curtains down over the
face · **C / B / D**: the paper look of `DESIGN.md` (face top + paper bottom, paper top + face box, full paper) ·
**Y** (16:9, needs `"format": "youtube"` at the top of the storyboard, 1920×1080): the speaker fills the frame and **moves**
on word anchors, `"face": [{"pos": "br", "at": "w:right"}, {"pos": "tl", "at": "w:left"}, {"pos": "full", "at": 12}]` with
`full`, `tl`, `tr`, `bl`, `br`, `left`, `right`, `center`, `hidden`; the same `zone.items` as S, positioned in 1920×1080, plus
`"phone": true` on a `video` item (9:16 clip in a phone frame), `"tilt": 18` (3D angle) and `"from": "far"` (flies in from the
back), `"x"`/`"w"` on `big` to put it on one side; captions sit on a dark pill at the bottom. Made for a YouTube intro where
each sentence triggers what it describes, edited by the kit itself.
Every timed value accepts a word anchor: `"at": "w:word"` = the start of that word in the transcript. Scenes must start on a
word (Nate's validator wants an anchor within −0.15 / +0.2 s); a scene with no visual event for more than 2.2 s carries a
`holdReason`. `caption_style`: `kit` (pill, uppercase) or `pop` (Helvetica Neue Bold, keyword ×1.55 in the accent color,
word-by-word reveal). `lexicon` fixes one word → one word (proper nouns). `keywords` are matched ignoring case, punctuation
and elisions ("d'ingénieur" matches "ingénieur", "40 825" matches "40 825"). `locale` (default `en-US`) formats the numbers in
count-ups and sets the HTML `lang`; `lang` overrides the latter. Transcription detects the language on its own
(`transcribe.py --lang xx` forces it); only French spelled-out numbers are converted to digits.

## Commands

```bash
./setup.sh                               # once per machine: checks node, ffmpeg, python, the transcription key, warms up HyperFrames
python3 scripts/takes.py <rush>          # gate 2: take list to validate (writes assets/derush/)
python3 scripts/stage.py                 # gate 2: cut → assets/speaker.mp4, reel-audio.wav, transcript.json, edit-decisions.json
python3 scripts/footage.py <url|file> --slug x --from 12 --to 18 --why "…" --rights "…"   # gate 4: B-roll with provenance
python3 scripts/build-reel.py            # storyboard.json → compositions + index.html + captions + assets/plan.json
npm run check · npm run preflight · npm run snapshot -- --at 1.5,6 --no-end
node .claude/skills/short-form-edit/scripts/validate-plan.mjs .      # Nate's plan gate
node .claude/skills/short-form-edit/scripts/validate-footage.mjs .   # when B-roll is used
npm run dev                              # Studio, in the background; give the user the exact URL printed
npm run render (always --sdr: an HDR source would switch HyperFrames to its HDR pipeline, which ghosts hidden layers) · npm run frames
node scripts/sync-codex-skills.mjs       # after any change in .claude/skills/
```

## Hard rules

Nothing is built before the user's "ok" on the current gate. Real screenshots over invented mockups. Nothing on the face, no
cutout, no matting. Media never in git. Exact spelling of proper nouns through `lexicon`. Never edit a generated file. Footage
has a provenance and rights before it enters a beat. No secret on screen: API keys live in the environment, never in a
file, a command line or a message. Nothing is uploaded or published without the user's explicit ok.

## HyperFrames contract, reminder

Root `div` with `id`, `data-composition-id`, `data-start="0"`, `data-duration`, `data-width`, `data-height`. Every timed element:
`data-start`, `data-duration`, `data-track-index`, `class="clip"`; the track is only time, the visual order is z-index. One paused
GSAP timeline per composition on `window.__timelines["<id>"]`. Sub-composition: everything inside `<template>`, root `#root`,
host id = inner id. Strict determinism. See `MOTION.md`.
