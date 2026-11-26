from google import genai
from google.genai import types
from PIL import Image
import io
import urllib.parse
import requests


def generate_ai_scene_image(
    prompt: str,
    style: str,
    gemini_api_key: str = "",
    pollinations_api_key: str = "",
    ref_image: Image.Image | None = None,
    aspect_ratio: str = "16:9",
) -> tuple[Image.Image | None, str]:
    """Generates rich AI character/story scenes via Gemini (Nano Banana) or Pollinations."""
    full_prompt = (
        f"{style} cinematic story illustration, expressive detailed character, "
        f"rich environment lighting, depth of field, no stick figures, {prompt}"
    ).strip()

    # 1. Primary: Gemini / Nano Banana native image generation
    if gemini_api_key.strip():
        try:
            client = genai.Client(api_key=gemini_api_key.strip())
            contents = [full_prompt]
            if ref_image is not None:
                buf = io.BytesIO()
                ref_image.convert("RGB").save(buf, format="PNG")
                contents.append(
                    types.Part.from_bytes(data=buf.getvalue(), mime_type="image/png")
                )
                contents.append(
                    "Keep the same main character appearance and visual style from the reference image while adapting to the new scene prompt."
                )

            for model_name in ("gemini-3.1-flash-image", "gemini-3.1-flash-lite-image"):
                try:
                    response = client.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
                        ),
                    )
                    candidates = getattr(response, "candidates", None) or []
                    for cand in candidates:
                        content = getattr(cand, "content", None)
                        for part in getattr(content, "parts", None) or []:
                            inline = getattr(part, "inline_data", None)
                            if inline and getattr(inline, "data", None):
                                img = Image.open(io.BytesIO(inline.data)).convert("RGB")
                                return img, f"Generated with {model_name}"
                except Exception:
                    continue
            return None, "Gemini image generation did not return image bytes. Check model access or billing/quota in Google AI Studio."
        except Exception as exc:
            return None, f"Gemini API error: {exc}"

    # 2. Secondary: Pollinations image API if key is provided
    if pollinations_api_key.strip():
        try:
            w, h = (768, 1280) if aspect_ratio == "9:16" else (1280, 720)
            encoded = urllib.parse.quote(full_prompt)
            url = (
                f"https://gen.pollinations.ai/image/{encoded}"
                f"?model=flux&width={w}&height={h}&key={urllib.parse.quote(pollinations_api_key.strip())}"
            )
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200 and resp.content:
                return Image.open(io.BytesIO(resp.content)).convert("RGB"), "Generated with Pollinations Flux"
            return None, f"Pollinations returned status {resp.status_code}."
        except Exception as exc:
            return None, f"Pollinations error: {exc}"

    return None, "Add a Gemini API Key (from Google AI Studio) in the sidebar or Streamlit Secrets to generate real AI characters and scenes."
