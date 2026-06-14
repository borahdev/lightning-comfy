#!/bin/bash

cd /teamspace/studios/this_studio

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

# Start ngrok in background
echo "Starting ngrok tunnel..."
ngrok http 8001 > /tmp/ngrok.log 2>&1 &

# Wait for ngrok to start
sleep 8

# Get URL from ngrok API and push to n8n webhook
curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "
import sys, json
import httpx

data = json.load(sys.stdin)
url = data['tunnels'][0]['public_url']

print('===============================')
print('PUBLIC URL:', url)
print('===============================')

# Push to n8n webhook
r = httpx.post(
    'https://n8n-webhook-test.theautomation.pro/webhook/cab42216-8f44-4ba6-82b6-0f43f4ebd298',
    json={'tunnel_url': url}
)
print('n8n response:', r.status_code, r.text)
print('URL pushed to n8n!')
"

wait