#!/usr/bin/env bash
# Python environment for transcription (WhisperX), shared by all reels: ~/.reel-kit/venv
# Requires uv (https://docs.astral.sh/uv/) and ffmpeg. Models are downloaded on first run (~2 GB, Hugging Face cache).
set -euo pipefail
mkdir -p ~/.reel-kit
[ -x ~/.reel-kit/venv/bin/python ] || uv venv --python 3.11 ~/.reel-kit/venv
VIRTUAL_ENV=$HOME/.reel-kit/venv uv pip install --quiet whisperx
~/.reel-kit/venv/bin/python -c "import whisperx; print('whisperx ok')"
