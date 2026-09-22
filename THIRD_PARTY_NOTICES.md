# Third-party notices

reel-kit is MIT-licensed (see `LICENSE`). It bundles or builds on the following:

- **Nate Herk's HyperFrames Student Kit** (https://github.com/nateherkai/hyperframes-student-kit, MIT). The skills
  `short-form-edit`, `video-storytelling` and `hyperframes-video-beats` in `.claude/skills/`, the scripts
  `scripts/validate-beat-sync.mjs` and `scripts/preflight.mjs`, and the references `references/nate-*.md` come from it,
  lightly adapted (headers point to this kit's tools). Licenses: `licenses/NATE-HERK-STUDENT-KIT-LICENSE` and
  `licenses/PIPELINE-USE-PERMISSION.txt`. Nothing here is endorsed by Nate Herk.
- **HyperFrames** (https://github.com/heygen-com/hyperframes, Apache-2.0): the renderer, installed on demand with
  `npx hyperframes@0.8.42`, and the `hyperframes*`, `media-use` and `motion-graphics` skills in `.claude/skills/`, bundled from
  the HyperFrames skill ecosystem. License: `licenses/HYPERFRAMES-LICENSE`.
- **GSAP** (`assets/gsap.min.js`), used under the GSAP Standard License (https://gsap.com/community/standard-license/).
- **Fonts**: Archivo, Fraunces and Caveat in `assets/fonts/`, SIL Open Font License 1.1 (`assets/fonts/OFL-*.txt`).
- **ElevenLabs Scribe** and **WhisperX** are called by `scripts/transcribe.py`; they are not bundled. Scribe needs your own
  ElevenLabs key and is billed to your account. WhisperX (BSD-2-Clause) installs into `~/.reel-kit/venv` only if you run
  `scripts/setup-whisperx.sh`.
- **yt-dlp** and **ffmpeg** are external tools used by `scripts/footage.py`, `takes.py` and `stage.py`; install them yourself.

Footage, logos, music and screenshots you bring into a project remain subject to their own rights. The kit records
provenance in `assets/footage-ledger.json` but cannot grant you rights to anything.
