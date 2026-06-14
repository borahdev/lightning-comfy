#!/bin/bash

# Push empty URL to n8n to signal studio is offline
python3 -c "
import httpx
r = httpx.post(
    'https://n8n-webhook-test.theautomation.pro/webhook/cab42216-8f44-4ba6-82b6-0f43f4ebd298',
    json={'tunnel_url': ''}
)
print('Cleared tunnel URL in n8n:', r.status_code)
"