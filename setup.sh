#!/usr/bin/env bash
# reel-kit setup: checks the tools the kit needs, warms up HyperFrames, and tells you what is missing.
# Run once per machine, from the kit folder:  ./setup.sh
# Optional: ./setup.sh --whisperx   (local transcription fallback, ~2 GB of models)
set -uo pipefail
cd "$(dirname "$0")"
ok=1
say() { printf '  %s\n' "$*"; }
need() { # need <cmd> <hint>
  if command -v "$1" >/dev/null 2>&1; then say "ok   $1 ($(command -v "$1"))"; else say "MISSING $1  →  $2"; ok=0; fi
}

echo "reel-kit setup"
need node   "install Node 20+ from https://nodejs.org"
need npx    "comes with Node"
need ffmpeg "macOS: brew install ffmpeg · Linux: apt install ffmpeg"
need ffprobe "comes with ffmpeg"
need python3 "install Python 3.10+"
if command -v yt-dlp >/dev/null 2>&1; then say "ok   yt-dlp"; else say "note yt-dlp not found: only needed for scripts/footage.py with URLs (brew install yt-dlp / pipx install yt-dlp)"; fi

if node -e 'process.exit(parseInt(process.versions.node) >= 20 ? 0 : 1)' 2>/dev/null; then say "ok   node $(node -v)"; else say "MISSING node >= 20 (found $(node -v 2>/dev/null || echo none))"; ok=0; fi
if python3 -c 'import numpy' 2>/dev/null; then say "ok   python numpy"; else say "MISSING python module numpy  →  python3 -m pip install numpy"; ok=0; fi

if [ -z "${ELEVENLABS_API_KEY:-}" ] && [ -f .env ]; then
  ELEVENLABS_API_KEY=$(grep -E '^ELEVENLABS_API_KEY=' .env | head -1 | cut -d= -f2- | tr -d "\"' ")
fi
if [ -n "${ELEVENLABS_API_KEY:-}" ]; then
  say "ok   ELEVENLABS_API_KEY is set (${#ELEVENLABS_API_KEY} chars) → transcription = ElevenLabs Scribe (~0.22 $/h of audio)"
elif [ -x "$HOME/.reel-kit/venv/bin/python" ]; then
  say "ok   WhisperX found in ~/.reel-kit/venv → transcription = local WhisperX"
else
  say "MISSING transcription engine. Two options:"
  say "     A) ElevenLabs Scribe (recommended, ~1 cent per reel): create a key at https://elevenlabs.io/app/settings/api-keys"
  say "        (any plan, the key needs the speech_to_text permission), then put it in a file named .env in this folder:"
  say "            ELEVENLABS_API_KEY=your_key"
  say "        the safe way, nothing shows on screen:   ./setup.sh --key"
  say "        or in your shell profile: export ELEVENLABS_API_KEY=your_key   (then restart your agent)"
  say "        Do it yourself: never paste the key into a chat with an agent."
  say "     B) WhisperX, local and free, no account: ./setup.sh --whisperx   (about 2 GB of models, slower, CPU)"
  ok=0
fi

if [ "${1:-}" = "--key" ]; then
  # the key is typed blind and lands in .env, never in the terminal, the history or a screen recording
  printf '  paste your ElevenLabs key (nothing will show): '
  stty -echo 2>/dev/null; IFS= read -r _K; stty echo 2>/dev/null; printf '\n'
  if [ -z "$_K" ]; then say "nothing pasted, .env untouched"; exit 1; fi
  _N=${#_K}
  touch .env
  grep -v '^ELEVENLABS_API_KEY=' .env 2>/dev/null > .env.tmp || true
  printf 'ELEVENLABS_API_KEY=%s\n' "$_K" >> .env.tmp && mv .env.tmp .env && chmod 600 .env
  _K=""
  say "ok   key written to .env ($_N characters, never shown), readable by you only"
  say "     .env is in .gitignore: it never leaves this machine"
  exec "$0"
fi

if [ "${1:-}" = "--whisperx" ]; then
  echo "installing WhisperX into ~/.reel-kit/venv"
  need uv "https://docs.astral.sh/uv/ (curl -LsSf https://astral.sh/uv/install.sh | sh)"
  bash scripts/setup-whisperx.sh
fi

echo "warming up HyperFrames (pinned 0.8.42, downloaded once by npx)"
if npx --yes hyperframes@0.8.42 --version >/dev/null 2>&1; then say "ok   hyperframes $(npx --yes hyperframes@0.8.42 --version 2>/dev/null | head -1)"; else say "MISSING hyperframes could not run through npx (check your network / Node install)"; ok=0; fi

echo "PlugKit (gate 7): connect its MCP server to your agent from the PlugKit dashboard → MCP page (copy the command for Claude Code or the config for Codex)."
if [ "$ok" = 1 ]; then
  echo "all good. Start a project: cp -R . ~/videos/<slug> && cd ~/videos/<slug> && claude   (or codex)"
else
  echo "fix the MISSING lines above, then run ./setup.sh again"; exit 1
fi
