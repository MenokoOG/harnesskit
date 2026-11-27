#!/usr/bin/env bash
# Run the live eval against a local llama.cpp image and model. No internet, repo mounted read-only.
# Usage: MODEL_DIR=/path/to/models MODEL_FILE=model.gguf evals/run.sh [trials]
set -euo pipefail
: "${MODEL_DIR:?set MODEL_DIR}" "${MODEL_FILE:?set MODEL_FILE}"
IMAGE="${LLAMA_IMAGE:-linkfall-model:dev}"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
NET=harnesskit-eval
SERVER=harnesskit-eval-model

cleanup() { docker rm -f "$SERVER" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker network create --internal "$NET" >/dev/null
docker run -d --name "$SERVER" --network "$NET" --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --memory 6g -v "$MODEL_DIR:/models:ro" "$IMAGE" \
  --model "/models/$MODEL_FILE" --host 0.0.0.0 --port 8090 --threads 6 --ctx-size 8192 --parallel 1 --jinja >/dev/null

sandbox() {
  docker run --rm --network "$NET" --read-only --tmpfs /tmp --cap-drop ALL --security-opt no-new-privileges:true \
    --user 65534:65534 --memory 512m --pids-limit 128 -v "$REPO:/app:ro" -e PYTHONPATH=/app \
    -e PYTHONDONTWRITEBYTECODE=1 -e MODEL_URL="http://$SERVER:8090" -w /tmp python:3.13-slim "$@"
}

ready=no
for _ in $(seq 1 90); do
  if sandbox python -c 'import urllib.request as u; u.urlopen("http://harnesskit-eval-model:8090/health", timeout=3)' 2>/dev/null; then
    ready=yes; break
  fi
  sleep 5
done
[ "$ready" = yes ] || { echo "model server never became healthy" >&2; docker logs --tail 30 "$SERVER" >&2; exit 1; }

for trial in $(seq 1 "${1:-3}"); do
  sandbox python /app/evals/fix_bug.py "$trial"
done
