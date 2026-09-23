# reel-kit

Edit a talking-head reel with an AI agent (Claude Code or Codex) and publish it from the same chat.
The agent does the work; you say "ok" at seven gates. Rendering is HyperFrames (HTML → video), the playbook is
Nate Herk's `short-form-edit` skill kept verbatim, publication goes through PlugKit.

```
rush.mov ──► 1 framing ──► 2 rough cut ──► 3 captions ──► 4 beats + assets ──► 5 opening ──► 6 animatic → final ──► 7 publish
```

## Start here

Five steps, about ten minutes the first time. You never write code.

**1. Get the kit.** Open a terminal and run:

```bash
git clone https://github.com/antoineblc99/reel-kit ~/reel-kit && cd ~/reel-kit && ./setup.sh
```

`setup.sh` checks Node 20+, ffmpeg, Python 3.10+ and numpy, and prints the install command for whatever is missing.
No terminal? Open Claude Code or Codex in any folder and paste this instead:

> Clone https://github.com/antoineblc99/reel-kit into ~/reel-kit, run ./setup.sh, and walk me through whatever is missing.

**2. Add a transcription key.** In the kit folder:

```bash
./setup.sh --key
```

It asks for your [ElevenLabs key](https://elevenlabs.io/app/settings/api-keys) and nothing shows on screen while you paste.
The key lands in a git-ignored `.env`. About 0.22 $ per hour of audio, so a cent per reel, and it keeps every retake.
No account? `./setup.sh --whisperx` installs a free local engine instead, slower, about 2 GB of models.

**3. Connect PlugKit,** so the agent can publish for you. In the PlugKit dashboard open the **MCP** page and copy the
command for Claude Code, or the JSON config for Codex, Cursor or VS Code. Paste it, restart your agent, done.
Skip this step if you only want the edit and will publish by hand.

**4. Start a video.** Copy the kit into a new folder, one folder per video, and open your agent there:

```bash
cp -R ~/reel-kit ~/videos/my-first-reel && cd ~/videos/my-first-reel
claude        # or: codex
```

**5. Hand it your rush** and paste a prompt like this one:

> Edit this rush into a 9:16 reel following AGENTS.md, gate by gate, and stop at each gate for my ok.
> Reference reel: <file or URL>. Brand: <site URL or logo>. CTA: comment "KEYWORD". Rush: <path to your file>

The agent reads `AGENTS.md`, cuts the rush and comes back with the list of takes it kept and dropped. That is gate 2,
and you answer in plain sentences, like you would to an editor. Six gates later the reel is rendered and published.

The same kit edits a 16:9 YouTube video (`"format": "youtube"` in `storyboard.json`, layout `Y`): the speaker moves to a
corner on a word, clips play in tilted phone frames, cards and numbers pop where the sentence says so.

Any language Scribe or WhisperX understands works, detected automatically. In French, spelled-out numbers become digits
on screen. `"locale"` in `storyboard.json` sets number formatting (`en-US` by default).

## What is inside

- `AGENTS.md` (= `CLAUDE.md`): the map, one line per gate: Nate's step, the local tool, what you validate.
- `DESIGN.md`: the default paper look. `MOTION.md`: motion rules and how the agent verifies its work.
- `scripts/`: `takes.py` (rough cut per take, retakes detected), `transcribe.py` (Scribe or WhisperX, numbers as digits),
  `stage.py` (cut → assets in Nate's schema), `footage.py` (B-roll with provenance), `build-reel.py`
  (storyboard.json → HyperFrames compositions, captions, plan.json), plus Nate's validators.
- `.claude/skills/`: HyperFrames 0.8.42 skills + Nate's `short-form-edit`, `video-storytelling`, `hyperframes-video-beats`.
  `.agents/skills/` is the same set for Codex.
- `assets/fonts/` (Archivo, Fraunces, Caveat, OFL), `references/` (Nate's motion philosophy and storytelling workbook).

Media never lives in git. See `THIRD_PARTY_NOTICES.md` for what comes from where.

## Credits

Built on Nate Herk's [HyperFrames Student Kit](https://github.com/nateherkai/hyperframes-student-kit) (MIT) and
[HyperFrames](https://github.com/heygen-com/hyperframes) (Apache-2.0). MIT license.
