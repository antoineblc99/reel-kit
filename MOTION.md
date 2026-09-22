# reel-kit — Editing rules for the agent

> Read before planning a reel's scenes. DESIGN.md says what it looks like; this file says how it moves
> and how we verify. The technical rules come from Nate Herk's kit (MOTION_PHILOSOPHY.md, MIT).

## The DNA of the render

1. **It moves all the time.** Never more than 2 to 4 s without a visual change. A static element = a dead frame.
2. **You name it, you show it.** Every tool, product, number or proof spoken aloud gets its real visual: a capture of the real site,
   the real README, the real UI. First what already exists (`assets/captures/`, the user's own asset bank), then a real capture (`npx hyperframes capture <URL>`), generation last and only with the user's ok.
3. **One idea per scene.** If a scene says two things, split it in two.
4. **Alternate layouts**: C → B → F → D, never the same one twice in a row. The face comes back at least every 8 s.
5. **Captions on every frame**, keyword in orange, synced word for word to the transcript.
6. **Full-screen hook from frame 1.** Zero dead time at the open.
7. **Anchor to the word, not the sentence.** A graphic that lands a beat after the word is worth less than nothing.
8. **Show the thing, don't label it.** A rectangle with a sentence inside is the failure mode of lazy editing.
9. **Readable with the sound off.** A viewer scrolling on mute must understand.
10. **Restraint is planned.** A beat left bare is decided and justified in the table, it is not forgotten.
11. **The CTA is the moment that pays.** Exact keyword, big, in the accent color, spelling checked against the user's brief.

## HyperFrames rules learned the hard way

- **Timeline padding.** Every sub-composition ends with `tl.to({}, { duration: SLOT }, 0)` with `SLOT` ≥ its
  `data-duration` in the host. Otherwise HyperFrames hides it before the end of the slot: black flash at the end of the scene.
- **Poster and last frame** around every inserted `<video>`: an image before (the clip flickers on start), an image
  after (black when the source ends). `ffmpeg -ss 0 -frames:v 1 poster.jpg` and `ffmpeg -sseof -0.04 -frames:v 1 last.jpg`.
- **Captions outside sub-compositions**: direct children of the root in `index.html`, tracks ≥ 20.
- **The `<video>` is the clip**: `class="clip"` + `data-start` + `data-duration` + `data-track-index` on the tag.
  Animate its untimed wrapper, never the tag.
- **Separate audio**: `<audio>` WAV PCM 48 kHz, never the MP4's own track. Check the full duration on the master.
- **Even heights** everywhere, x264 refuses anything else.
- **Unique ids** on the assembled page: prefix with the composition id inside sub-compositions.
- **Full-screen background on a child** `position:absolute; inset:0`, never on the root (the render may output it black).
- **Determinism**: no `Date.now()`, no unseeded `Math.random()`, no network, no `repeat: -1`.

## Three rules borrowed from a pro editor's pipeline

- **RUN.md per reel**: the job state (done / remaining / decisions), read first by every new session, Claude or Codex.
- **Measured voice, never "by ear"**: `loudnorm=I=-16:TP=-1.5:LRA=11` on the voice track before editing.
- **Three correction rounds maximum** after the check, then show the user. Beyond that, it's polish.

## Verification before saying "done"

1. `npm run check` at 0 findings.
2. `npm run preflight` (root structure, clips, nested videos).
3. `npm run beats` if scenes carry a `data-anchor`: entrance between 1.8 s before and 0.2 s after the word.
4. Duration diagnostic in the Studio console: any timeline shorter than its `data-duration` is a black flash.
   ```js
   const p = document.querySelector('hyperframes-player');
   const iw = p.shadowRoot.querySelector('iframe').contentWindow;
   Object.fromEntries(Object.entries(iw.__timelines).map(([k, v]) => [k, +v.duration().toFixed(3)]));
   ```
5. `npm run frames`: one image on each side of every cut (±0.1 s). Look for: cropped face, overflowing text,
   black frame, double title, caption over the mouth.
6. Look at every hero frame at phone size (375 px wide). Unreadable = redo.
7. Listen to the audio junctions.
8. Write what was verified in the project's `VERIFY.md`. A passing lint does not prove visual quality.

## Validation gate

The user scrubs in the Studio (`npm run dev`) before any render. `npm run render` only after their ok.
