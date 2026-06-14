import httpx
import asyncio
import json
import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from config import COMFY_URL, COMFY_PUBLIC_URL

app = FastAPI()

DEFAULT_G = "lofi anime illustration, painterly style, western animation art, gouache on textured canvas, warm amber and burnt orange color palette, deep teal and navy shadows, dramatic rim lighting, soft vignette edges, paper grain texture overlay, contemplative mood, emotional atmosphere, Studio Ghibli inspired, semi-realistic character design, brushstroke sky, golden hour lighting, melancholic aesthetic, portrait orientation, masterpiece, high quality, dramatic turbulent clouds, layered atmospheric depth, heavy vignette darkening edges, film grain overlay, slightly desaturated muted tones, detailed facial features, well defined face, symmetrical face, beautiful face, perfect anatomy, high detail portrait, sharp facial details"
DEFAULT_NEG = "photorealistic, 3D render, harsh lines, bright neon colors, flat colors, chibi, oversaturated, sharp edges, digital clean, ugly, blurry, low quality, text, watermark, extra limbs, bright even lighting, front lit face, clean smooth face, soft clouds, pastel colors, overexposed, monochromatic, single color palette, korean features, east asian features, anime eyes, monolid eyes, pale skin, asian facial structure, webtoon face, k-drama face, deformed face, disfigured, malformed face, asymmetrical face, bad anatomy, bad face, fused features, poorly drawn face, mutation, half face, cropped face, missing features, undefined face, smudged face, melting face"
DEFAULT_NEG_DISTANCE= "wide shot, full body, small figure, distant character"

class GenerateRequest(BaseModel):
    text_l: str
    text_g: str = DEFAULT_G
    negative: str = DEFAULT_NEG
    no_distance: bool = False
    seed: int | None = None

class TTSRequest(BaseModel):
    text: str
    reference_audio: str = "Ex3CgfbeKBFX7UpLNV3DF_xqBVxHxU.mp3"
    seed: int = 1880004348

def build_workflow(text_l: str, text_g: str, negative: str, no_distance: bool = False, seed: int | None = None):
    with open("sdxl-workflow.json", "r") as f:
        workflow = json.load(f)

    if no_distance:
        negative = f"{negative}, {DEFAULT_NEG_DISTANCE}"

    workflow["50"]["inputs"]["text_g"] = text_g
    workflow["50"]["inputs"]["text_l"] = text_l
    workflow["57"]["inputs"]["text_g"] = text_g
    workflow["57"]["inputs"]["text_l"] = text_l
    workflow["7"]["inputs"]["text"] = negative
    workflow["16"]["inputs"]["text"] = negative

    # Randomize base sampler seed so images vary per request
    if seed is None or seed == -1:
        seed = random.randint(0, 2**32 - 1)
    workflow["10"]["inputs"]["noise_seed"] = seed

    return workflow

@app.get("/health")
async def health():
    async with httpx.AsyncClient() as client:
        try:
            r = await client.get(f"{COMFY_URL}/system_stats", timeout=5)
            return {"status": "ok", "comfyui": r.status_code}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

@app.post("/generate")
async def generate(req: GenerateRequest):
    workflow = build_workflow(req.text_l, req.text_g, req.negative, req.no_distance, req.seed)

    async with httpx.AsyncClient(timeout=300) as client:
        # Submit to ComfyUI
        try:
            r = await client.post(
                f"{COMFY_URL}/prompt",
                json={"prompt": workflow}
            )
            print("Submit response:", r.status_code, r.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reach ComfyUI: {str(e)}")

        if r.status_code != 200:
            raise HTTPException(status_code=500, detail=f"ComfyUI error: {r.text}")

        response_data = r.json()
        print("Submit response data:", response_data)

        if "prompt_id" not in response_data:
            raise HTTPException(status_code=500, detail=f"No prompt_id returned: {response_data}")

        prompt_id = response_data["prompt_id"]
        print(f"Prompt ID: {prompt_id}")

        # Poll until done
        for i in range(120):
            await asyncio.sleep(3)
            try:
                history = await client.get(f"{COMFY_URL}/history/{prompt_id}")
                data = history.json()
                print(f"Poll {i} - history keys: {list(data.keys())}")
            except Exception as e:
                print(f"Poll error: {e}")
                continue

            if prompt_id in data:
                outputs = data[prompt_id].get("outputs", {})

                # Find node with images
                for node_id, node_output in outputs.items():
                    if "images" in node_output and len(node_output["images"]) > 0:
                        image_info = node_output["images"][0]
                        filename = image_info["filename"]
                        subfolder = image_info.get("subfolder", "")
                        type_ = image_info.get("type", "output")
                        url = f"{COMFY_PUBLIC_URL}/view?filename={filename}&subfolder={subfolder}&type={type_}"
                        print(f"Image URL: {url}")
                        return {
                            "status": "done",
                            "image_url": url
                        }

                raise HTTPException(
                    status_code=500,
                    detail=f"No images in output. Raw output: {outputs}"
                )

    raise HTTPException(status_code=504, detail="Generation timed out")

def build_tts_workflow(text: str, reference_audio: str, seed: int):
    with open("tts-workflow.json", "r") as f:
        workflow = json.load(f)

    # Set the narration text
    workflow["3"]["inputs"]["text"] = text
    workflow["3"]["inputs"]["seed"] = seed

    # Set reference audio filename
    workflow["5"]["inputs"]["audio"] = reference_audio
    workflow["5"]["inputs"]["audioUI"] = f"/api/view?filename={reference_audio}&type=input&subfolder=&rand=0.5"

    return workflow


@app.post("/generate-tts")
async def generate_tts(req: TTSRequest):
    workflow = build_tts_workflow(req.text, req.reference_audio, req.seed)

    async with httpx.AsyncClient(timeout=300) as client:
        try:
            r = await client.post(f"{COMFY_URL}/prompt", json={"prompt": workflow})
            print("TTS submit response:", r.status_code, r.text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to reach ComfyUI: {str(e)}")

        if r.status_code != 200:
            raise HTTPException(status_code=500, detail=f"ComfyUI error: {r.text}")

        response_data = r.json()
        if "prompt_id" not in response_data:
            raise HTTPException(status_code=500, detail=f"No prompt_id returned: {response_data}")

        prompt_id = response_data["prompt_id"]
        print(f"TTS Prompt ID: {prompt_id}")

        for i in range(120):
            await asyncio.sleep(3)
            try:
                history = await client.get(f"{COMFY_URL}/history/{prompt_id}")
                data = history.json()
                print(f"TTS Poll {i} - history keys: {list(data.keys())}")
            except Exception as e:
                print(f"TTS Poll error: {e}")
                continue

            if prompt_id not in data:
                continue

            outputs = data[prompt_id].get("outputs", {})

            # Find audio output (node 3 or 4)
            audio_url = None
            for node_id in ["4", "3"]:
                node_out = outputs.get(node_id, {})
                audio_list = node_out.get("audio", [])
                if audio_list:
                    a = audio_list[0]
                    filename = a["filename"]
                    subfolder = a.get("subfolder", "")
                    type_ = a.get("type", "output")
                    audio_url = f"{COMFY_PUBLIC_URL}/view?filename={filename}&subfolder={subfolder}&type={type_}"
                    break

            # Transcript from node 7 (PreviewAny wrapping Whisper index 2)
            transcript = None
            node7_out = outputs.get("7", {})
            for key in node7_out:
                transcript = node7_out[key]
                break

            # Duration from node 9 (PreviewAny wrapping Audio Duration index 1)
            duration = None
            node9_out = outputs.get("9", {})
            for key in node9_out:
                duration = node9_out[key]
                break

            if audio_url:
                print(f"TTS Audio URL: {audio_url}")
                # Unwrap transcript: ComfyUI returns a list containing a JSON string
                parsed_transcript = None
                if isinstance(transcript, list) and transcript:
                    try:
                        parsed_transcript = json.loads(transcript[0])
                    except (json.JSONDecodeError, TypeError):
                        parsed_transcript = transcript[0]
                elif transcript is not None:
                    parsed_transcript = transcript
                # Unwrap duration: may come as a list or scalar
                parsed_duration = None
                if isinstance(duration, list) and duration:
                    try:
                        parsed_duration = float(duration[0])
                    except (ValueError, TypeError):
                        parsed_duration = duration[0]
                elif duration is not None:
                    try:
                        parsed_duration = float(duration)
                    except (ValueError, TypeError):
                        parsed_duration = duration
                return {
                    "status": "done",
                    "audio_url": audio_url,
                    "duration_seconds": parsed_duration,
                    "transcript": parsed_transcript,
                }

            if outputs:
                raise HTTPException(
                    status_code=500,
                    detail=f"No audio in output. Raw output: {outputs}"
                )

    raise HTTPException(status_code=504, detail="TTS generation timed out")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)