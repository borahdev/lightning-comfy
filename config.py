import os

# ComfyUI connection
COMFY_URL = os.environ.get("COMFY_URL", "http://127.0.0.1:8000")
COMFY_PUBLIC_URL = os.environ.get(
    "COMFY_PUBLIC_URL",
    "https://example.cloudspaces.litng.ai"
)  # set env, dont update directly
