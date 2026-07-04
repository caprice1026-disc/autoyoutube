#!/usr/bin/env sh
set -eu

if [ "$#" -lt 1 ]; then
  echo "Usage: scripts/make-video.sh <project.youtube.json> [make-video args...]" >&2
  exit 40
fi

PROJECT_PATH="$1"
shift
AIVIS_BASE_URL="${AIVIS_SPEECH_BASE_URL:-http://127.0.0.1:10101}"

needs_aivis=1
for arg in "$@"; do
  if [ "$arg" = "--dry-run" ] || [ "$arg" = "--plan-only" ] || [ "$arg" = "--voice-mode" ]; then
    needs_aivis=0
  fi
done

if [ "$needs_aivis" -eq 1 ]; then
  if ! curl -fsS "$AIVIS_BASE_URL/version" >/dev/null 2>&1; then
    echo "[make-video.sh] AivisSpeech is not ready; starting Docker service."
    docker compose --profile aivis up -d aivis-engine
  fi

  i=0
  while [ "$i" -lt 60 ]; do
    if curl -fsS "$AIVIS_BASE_URL/version" >/dev/null 2>&1; then
      break
    fi
    i=$((i + 1))
    sleep 2
  done

  if [ "$i" -ge 60 ]; then
    echo "AivisSpeech did not become ready at $AIVIS_BASE_URL." >&2
    exit 40
  fi
fi

PYTHON_BIN="./.venv/Scripts/python.exe"
if [ ! -x "$PYTHON_BIN" ]; then
  PYTHON_BIN="./.venv/bin/python"
fi

PYTHONUTF8=1 PYTHONIOENCODING=utf-8 \
  "$PYTHON_BIN" -m src.main make-video "$PROJECT_PATH" "$@"
