#!/bin/bash

# This script runs every time your Studio starts, from your home directory.

# Logs from previous runs can be found in ~/.lightning_studio/logs/

# List files under fast_load that need to load quickly on start (e.g. model checkpoints).
#
# ! fast_load
# <your file here>

# Add your startup commands below.
#
# Example: streamlit run my_app.py
# Example: gradio my_app.py
python - <<'EOF'
import json
import os

file_path = os.path.expanduser("~/ComfyUI/user/default/comfy.settings.json")
theme = os.environ.get("LIGHTNING_THEME", None)

if theme not in ["light", "dark"]:
    print("No valid LIGHTNING_THEME set. Exiting.")
    exit(0)

# Read existing content or create empty object
try:
    with open(file_path, "r") as f:
        content = f.read().strip()
        data = json.loads(content) if content else {}
except (json.JSONDecodeError, FileNotFoundError):
    data = {}

# Get current value
current_value = data.get("Comfy.ColorPalette", None)

# Only update if the current value is 'light', 'dark', or doesn't exist
if current_value in ["light", "dark", None]:
    data["Comfy.ColorPalette"] = theme
    print(f"Updated ComfyUI theme to {theme}")
else:
    print(f"Skipping update - current value '{current_value}' is not 'light' or 'dark'")

data["Comfy.Templates.SelectedRunsOn"] = ["ComfyUI"]

with open(file_path, "w") as f:
    json.dump(data, f, indent=2)

EOF
bash /teamspace/studios/this_studio/start.sh &

python ComfyUI/main.py --enable-manager-legacy-ui --port=8000 --enable-cors-header="*"


