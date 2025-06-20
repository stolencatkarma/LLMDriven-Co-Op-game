import os
import json
import httpx
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "db" / "worldImages.json"

if DB_PATH.exists():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        world_images = json.load(f)
else:
    world_images = {}

async def ensure_world_image(location, description):
    images_dir = BASE_DIR / "db" / "worldImages"
    print(f"[DEBUG] ensure_world_image called for location: {location}")
    if location in world_images:
        file_path = images_dir / world_images[location]
        print(f"[DEBUG] Checking existing image at: {file_path}")
        if file_path.exists():
            try:
                from PIL import Image
                with Image.open(file_path) as img:
                    img.verify()
                print(f"[DEBUG] Existing image is valid: {file_path}")
                return str(file_path)
            except Exception as e:
                print(f"[DEBUG] Invalid or corrupted image found for {location}, regenerating... Exception: {e}")
                file_path.unlink(missing_ok=True)
    prompt = f"A beautiful, detailed illustration of: {description.replace('**', '')}"
    print(f"[DEBUG] Sending image generation request to SD WebUI for prompt: {prompt}")
    try:
        async with httpx.AsyncClient() as client:
            payload = {"prompt": prompt}
            endpoints = [
                "http://localhost:7860/sdapi/v1/txt2img",
                "http://127.0.0.1:7860/sdapi/v1/txt2img",
                "http://localhost:7860/sdapi/v1/txt2img/",
                "http://127.0.0.1:7860/sdapi/v1/txt2img/"
            ]
            for endpoint in endpoints:
                print(f"[DEBUG] Trying SD WebUI endpoint: {endpoint}")
                try:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        timeout=120
                    )
                except Exception as e:
                    print(f"[Bot] Exception connecting to {endpoint}: {e}")
                    continue
                print(f"[DEBUG] SD WebUI response status: {response.status_code}")
                print(f"[DEBUG] SD WebUI response text: {response.text[:500]!r}")
                if response.status_code == 200:
                    data = response.json()
                    images = data.get("images")
                    if not images or not images[0]:
                        print("[Bot] SD WebUI did not return an image.")
                        return None
                    import base64
                    filename = f"{location.replace(' ', '_').lower()}.png"
                    file_path = images_dir / filename
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, "wb") as f:
                        f.write(base64.b64decode(images[0]))
                    from PIL import Image
                    with Image.open(file_path) as img:
                        img.verify()
                    world_images[location] = filename
                    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                    with open(DB_PATH, "w", encoding="utf-8") as f:
                        json.dump(world_images, f, indent=2)
                    print(f"[DEBUG] Image saved and verified at: {file_path}")
                    return str(file_path)
                else:
                    print(f"[Bot] SD WebUI endpoint {endpoint} failed: {response.status_code} {response.text}")
            print("[Bot] All SD WebUI endpoints failed. Is the server running? Is the API enabled?")
            print("[Bot] TIP: If you see 404 errors, make sure the API is enabled in SD WebUI (check 'Settings > User interface > Show API' and restart).")
            return None
    except Exception as e:
        print("[Bot] SD WebUI image generation failed:", e)
    return None
