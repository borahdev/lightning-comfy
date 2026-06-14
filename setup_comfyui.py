#!/usr/bin/env python3
"""
Setup script for ComfyUI custom nodes and models.

Reads:
  - custom_nodes.txt  : one git repo URL per line (lines starting with # are ignored)
  - models.txt        : one entry per line, format: <destination_path>|<url>

Usage:
  python setup_comfyui.py                  # installs both nodes and models
  python setup_comfyui.py --nodes-only     # only custom nodes
  python setup_comfyui.py --models-only    # only models
  python setup_comfyui.py --nodes-file custom_nodes.txt --models-file models.txt
"""

import argparse
import os
import subprocess
import sys
import urllib.request

COMFY_DIR = "ComfyUI"
CUSTOM_NODES_DIR = os.path.join(COMFY_DIR, "custom_nodes")


def run(cmd, cwd=None):
    print(f"  $ {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"  WARNING: command failed with exit code {result.returncode}")
    return result.returncode == 0


def read_lines(path):
    if not os.path.exists(path):
        print(f"File not found: {path} (skipping)")
        return []
    lines = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            lines.append(line)
    return lines


def install_custom_nodes(nodes_file):
    print("\n=== Installing custom nodes ===")
    repos = read_lines(nodes_file)
    if not repos:
        print("No custom nodes to install.")
        return

    os.makedirs(CUSTOM_NODES_DIR, exist_ok=True)

    for repo in repos:
        name = os.path.basename(repo).removesuffix(".git")
        dest = os.path.join(CUSTOM_NODES_DIR, name)

        print(f"\n-- {name} --")
        if os.path.isdir(dest):
            print(f"Already exists, pulling latest...")
            run(["git", "pull"], cwd=dest)
        else:
            print(f"Cloning {repo} ...")
            run(["git", "clone", repo], cwd=CUSTOM_NODES_DIR)

        req_file = os.path.join(dest, "requirements.txt")
        if os.path.isfile(req_file):
            print(f"Installing requirements for {name} ...")
            run([sys.executable, "-m", "pip", "install", "--break-system-packages",
                 "-r", req_file])
        else:
            print("No requirements.txt found, skipping pip install.")


def download_with_progress(url, dest, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req) as response:
        total = int(response.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1024 * 1024  # 1MB

        tmp_dest = dest + ".part"
        with open(tmp_dest, "wb") as out_file:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                out_file.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded / total * 100
                    mb_done = downloaded / (1024 * 1024)
                    mb_total = total / (1024 * 1024)
                    print(f"\r  {mb_done:8.1f} MB / {mb_total:8.1f} MB ({pct:5.1f}%)",
                          end="", flush=True)
                else:
                    mb_done = downloaded / (1024 * 1024)
                    print(f"\r  {mb_done:8.1f} MB downloaded", end="", flush=True)

        print()  # newline after progress bar
        os.rename(tmp_dest, dest)


def download_models(models_file):
    print("\n=== Downloading models ===")
    entries = read_lines(models_file)
    if not entries:
        print("No models to download.")
        return

    hf_token = os.environ.get("HF_TOKEN")
    civitai_token = os.environ.get("CIVITAI_TOKEN")

    for entry in entries:
        if "|" not in entry:
            print(f"Skipping malformed line: {entry}")
            continue

        dest, url = entry.split("|", 1)
        dest = dest.strip()
        url = url.strip()

        print(f"\n-- {dest} --")

        if os.path.isfile(dest):
            size_mb = os.path.getsize(dest) / (1024 * 1024)
            print(f"Already exists ({size_mb:.1f} MB), skipping.")
            continue

        os.makedirs(os.path.dirname(dest), exist_ok=True)

        headers = {}
        if "huggingface.co" in url and hf_token:
            headers["Authorization"] = f"Bearer {hf_token}"
        elif "civitai.com" in url and civitai_token:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}token={civitai_token}"

        try:
            print(f"Downloading from {url} ...")
            download_with_progress(url, dest, headers=headers)
        except Exception as e:
            print(f"  ERROR downloading {dest}: {e}")
            # Clean up partial file if it exists
            tmp_dest = dest + ".part"
            if os.path.exists(tmp_dest):
                os.remove(tmp_dest)
            continue

        size_mb = os.path.getsize(dest) / (1024 * 1024)
        if size_mb < 0.5:
            print(f"  WARNING: downloaded file is suspiciously small ({size_mb:.2f} MB).")
            print(f"  It may be an error page rather than the actual model.")
        else:
            print(f"  Done ({size_mb:.1f} MB)")


def main():
    parser = argparse.ArgumentParser(description="Set up ComfyUI custom nodes and models.")
    parser.add_argument("--nodes-file", default="custom_nodes.txt",
                         help="Path to custom nodes list (default: custom_nodes.txt)")
    parser.add_argument("--models-file", default="models.txt",
                         help="Path to models list (default: models.txt)")
    parser.add_argument("--nodes-only", action="store_true",
                         help="Only install custom nodes")
    parser.add_argument("--models-only", action="store_true",
                         help="Only download models")
    args = parser.parse_args()

    if args.models_only:
        download_models(args.models_file)
    elif args.nodes_only:
        install_custom_nodes(args.nodes_file)
    else:
        install_custom_nodes(args.nodes_file)
        download_models(args.models_file)

    print("\nAll done.")


if __name__ == "__main__":
    main()