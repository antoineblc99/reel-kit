# reel-kit

Edit a talking-head reel with an AI agent (Claude Code or Codex) and publish it from the same chat.
The agent does the work; you say "ok" at seven gates. Rendering is HyperFrames (HTML → video), the playbook is
Nate Herk's `short-form-edit` skill kept verbatim, publication goes through PlugKit.

```
rush.mov ──► 1 framing ──► 2 rough cut ──► 3 captions ──► 4 beats + assets ──► 5 opening ──► 6 animatic → final ──► 7 publish
```

## Setup, once per machine

```bash
git clone https://github.com/antoineblc99/reel-kit && cd reel-kit && ./setup.sh
```

You need Node 20+, ffmpeg, Python 3.10+ (with numpy) and a transcription engine:

- **ElevenLabs Scribe** (recommended): `export ELEVENLABS_API_KEY=...` in your shell profile. About 0.22 $ per hour of audio,
  so a cent per reel. Keeps every retake, word timing within 30 ms.
- or **WhisperX**, local and free: `./setup.sh --whisperx` (about 2 GB of models, CPU).

For gate 7, connect PlugKit's MCP server to your agent: in the PlugKit dashboard, open **MCP** and copy the command for
Claude Code (`claude mcp add --transport http … plugkit <url>`), or the JSON config for Codex (`~/.codex/config.toml`),
Cursor or VS Code. ChatGPT users run the kit through Codex, the same MCP config applies.

Any language Scribe or WhisperX understands works; the language is detected automatically (`--lang fr` to force it).
In French, spelled-out numbers become digits on screen ("quarante mille" → 40 000). Set `"locale"` in `storyboard.json`
for number formatting in count-ups (`en-US` by default, `fr-FR` for a French reel).

## A video

```bash
cp -R ~/reel-kit ~/videos/2026-09-22-my-reel && cd ~/videos/2026-09-22-my-reel
claude        # or: codex
```

Then paste a prompt like:

> Edit this rush into a 9:16 reel following AGENTS.md, gate by gate, and stop at each gate for my ok.
> Reference reel: <file or URL>. Brand: <site URL or logo>. CTA: comment "KEYWORD". Rush: <path>

The agent reads `AGENTS.md`, runs `scripts/takes.py` on the rush, and comes back with the take list. That is gate 2.

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
