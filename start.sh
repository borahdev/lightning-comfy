#!/bin/bash

cd /teamspace/studios/this_studio

# Load environment variables from .env if present (not tracked in git)
if [ -f .env ]; then
    set -a
    source .env
    set +a
fi

# Ensure ffmpeg is installed (cheap no-op if already present)
if ! command -v ffmpeg &> /dev/null; then
    echo "Installing ffmpeg..."
    sudo apt-get update && sudo apt-get install -y ffmpeg
fi

# Kill any stale process holding port 8001 (from a previous run)
if lsof -ti:8001 > /dev/null 2>&1; then
    echo "Port 8001 is in use, killing stale process..."
    lsof -ti:8001 | xargs -r kill -9
    sleep 1
fi

# Wait for ComfyUI to be ready
echo "Waiting for ComfyUI to be ready..."
until curl -s http://127.0.0.1:8000/system_stats > /dev/null 2>&1; do
    sleep 5
done
echo "ComfyUI is ready!"

# Start FastAPI in background
echo "Starting FastAPI..."
python main.py &

# Wait for FastAPI to start
sleep 3

# Kill any stale ngrok process (avoids "tunnel session already exists" issues)
if pgrep -x ngrok > /dev/null; then
    echo "Killing stale ngrok process..."
    pkill -x ngrok
    sleep 1
fi

# Start ngrok in background
echo "Starting ngrok tunnel..."
ngrok http 8001 > /tmp/ngrok.log 2>&1 &

# Wait for ngrok to start
sleep 8

# n8n webhook URL must be set via .env
if [ -z "$N8N_WEBHOOK_URL" ]; then
    echo "ERROR: N8N_WEBHOOK_URL is not set. Add it to .env"
    exit 1
fi

# Get URL from ngrok API and push to n8n webhook
curl -s http://127.0.0.1:4040/api/tunnels | N8N_WEBHOOK_URL="$N8N_WEBHOOK_URL" python3 -c "
import sys, json, os
import httpx

data = json.load(sys.stdin)
url = data['tunnels'][0]['public_url']

print('===============================')
print('PUBLIC URL:', url)
print('===============================')

# Push to n8n webhook
webhook_url = os.environ['N8N_WEBHOOK_URL']
r = httpx.post(
    webhook_url,
    json={'tunnel_url': url}
)
print('n8n response:', r.status_code, r.text)
print('URL pushed to n8n!')
"

wait