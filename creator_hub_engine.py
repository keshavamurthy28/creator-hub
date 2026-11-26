import asyncio
import hashlib
import os
import random
import re
import time
from typing import Dict, List, Optional, Tuple

import edge_tts
import numpy as np
from deep_translator import GoogleTranslator
from huggingface_hub import InferenceClient
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ---------------------------------------------------------------------------
# PRESET STORIES (Hanuman + Custom / Survival)
# ---------------------------------------------------------------------------
def get_preset_scenes(preset_name: str) -> List[Dict]:
    if preset_name == "Hanuman Story (5 Chapters)":
        return [
            {
                "chapter": "1. ಜನನ / Birth",
                "script": "Lord Hanuman was born to Anjana and Kesari with the blessings of Vayu, the wind god.",
                "prompt": "Divine newborn baby Hanuman glowing softly in sacred forest mountains at dawn, golden light rays, Indian mythological digital illustration, no text",
                "motion": "zoom_in",
                "duration": 4.5,
            },
            {
                "chapter": "2. ಬಾಲ್ಯದ ಸಾಧನೆಗಳು / Baby Achievements",
                "script": "As a child, Bal Hanuman leaped toward the radiant sun with fearless devotion and strength.",
                "prompt": "Young Bal Hanuman flying through golden clouds toward a glowing sun in the sky, radiant aura, epic Indian mythological art, no text",
                "motion": "pan_right",
                "duration": 4.5,
            },
            {
                "chapter": "3. ರಾಮಾಯಣ / Ramayana",
                "script": "In the Ramayana, Hanuman crossed the ocean, found Sita, and served Lord Rama with supreme courage.",
                "prompt": "Hanuman leaping across a vast ocean at sunrise toward distant mountains, golden aura, heroic Indian epic illustration, no text",
                "motion": "ken_burns_diag",
                "duration": 5.0,
            },
            {
                "chapter": "4. ಮಹಾಭಾರತ / Mahabharata",
                "script": "In the Mahabharata, Hanuman guided Bhima and protected Arjuna's chariot banner at Kurukshetra.",
                "prompt": "Majestic Hanuman standing strong in sacred mountain mist with a glowing golden mace, ancient Indian epic art, no text",
                "motion": "zoom_out",
                "duration": 4.5,
            },
            {
                "chapter": "5. ಇಂದಿನ ಸ್ಥಾನ / Where Is He Now?",
                "script": "As an eternal Chiranjeevi, Hanuman remains ever-present wherever Rama's name is remembered in devotion.",
                "prompt": "Serene Hanuman in peaceful meditation with glowing oil lamps in a sacred temple sanctuary, warm golden devotional art, no text",
                "motion": "pan_left",
                "duration": 5.0,
            },
        ]

    # Default: Forest Survival Story
    return [
        {
            "chapter": "1. ವಿಮಾನ ದುರಂತ / Flight Trouble",
            "script": "Flight landed in forest due to problem and few dies because of that.",
            "prompt": "Passenger airplane flying low over dense dark forest trees under stormy clouds, dramatic animation scene, no text",
            "motion": "zoom_in",
            "duration": 4.5,
        },
        {
            "chapter": "2. ಬದುಕುಳಿದವರು / Survivors",
            "script": "Few survives and overcome the hurdle finally and come back.",
            "prompt": "Small group of exhausted survivors standing together in a misty jungle clearing at dawn, hopeful light rays, animated story art, no text",
            "motion": "pan_right",
            "duration": 4.5,
        },
        {
            "chapter": "3. ಪ್ರಾಣಿಗಳ ಎದುರಿಸುವುದು / Fighting Animals",
            "script": "How they fight animals using torches and teamwork in the wild.",
            "prompt": "Survivors holding burning wooden torches around a campfire facing glowing animal eyes in a dark forest at night, dramatic animation, no text",
            "motion": "ken_burns_diag",
            "duration": 4.5,
        },
        {
            "chapter": "4. ಆಹಾರ ಹುಡುಕಾಟ / Finding Food",
            "script": "How they find food for survival near rivers and forest trees.",
            "prompt": "Survivors gathering wild fruits and catching fish by a clear forest stream in daylight, lush green jungle animation, no text",
            "motion": "zoom_out",
            "duration": 4.5,
        },
        {
            "chapter": "5. ಕೌಶಲ್ಯ ಕಲಿಕೆ / Learning Skills",
            "script": "How they learn skills like building shelters, starting fire, and navigating.",
            "prompt": "Survivors building a bamboo shelter and crafting tools in a forest camp, warm golden hour animation, no text",
            "motion": "pan_left",
            "duration": 4.5,
        },
    ]


# ---------------------------------------------------------------------------
# TRANSLATION
# ---------------------------------------------------------------------------
def translate_to_kannada(text: str) -> str:
    clean = text.strip()
    if not clean:
        return ""
    if any("\u0c80" <= ch <= "\u0cff" for ch in clean):
        return clean
    try:
        return GoogleTranslator(source="auto", target="kn").translate(clean) or clean
    except Exception:
        return clean


def translate_to_english(text: str) -> str:
    clean = text.strip()
    if not clean:
        return ""
    try:
        return GoogleTranslator(source="auto", target="en").translate(clean) or clean
    except Exception:
        return clean


# ---------------------------------------------------------------------------
# DUAL-SCRIPT FONT RENDERING (Kannada + English together)
# ---------------------------------------------------------------------------
def _load_font(paths: List[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def get_fonts(size: int) -> Tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    latin = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    kannada = [
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansKannada-Bold.otf",
        "/usr/share/fonts/truetype/lohit-kannada/Lohit-Kannada.ttf",
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/Tunga.ttf",
        "/System/Library/Fonts/Supplemental/Kannada MN.ttc",
    ]
    return _load_font(latin, size), _load_font(kannada, size)


def _runs(text: str) -> List[Tuple[str, bool]]:
    if not text:
        return []
    out: List[Tuple[str, bool]] = []
    buf = [text[0]]
    prev_kn = "\u0c80" <= text[0] <= "\u0cff"
    for ch in text[1:]:
        is_kn = "\u0c80" <= ch <= "\u0cff"
        if is_kn == prev_kn:
            buf.append(ch)
        else:
            out.append(("".join(buf), prev_kn))
            buf = [ch]
            prev_kn = is_kn
    out.append(("".join(buf), prev_kn))
    return out


def _measure(draw: ImageDraw.ImageDraw, text: str, lat_f, kn_f) -> Tuple[int, int]:
    w, h = 0, 0
    for seg, is_kn in _runs(text):
        f = kn_f if is_kn else lat_f
        b = draw.textbbox((0, 0), seg, font=f)
        w += b[2] - b[0]
        h = max(h, b[3] - b[1])
    return w, h


def _draw_text(draw: ImageDraw.ImageDraw, xy: Tuple[int, int], text: str, lat_f, kn_f, fill) -> None:
    x, y = xy
    for seg, is_kn in _runs(text):
        f = kn_f if is_kn else lat_f
        draw.text((x, y), seg, font=f, fill=fill)
        b = draw.textbbox((0, 0), seg, font=f)
        x += b[2] - b[0]


def _wrap(draw: ImageDraw.ImageDraw, text: str, lat_f, kn_f, max_w: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    lines = []
    cur = words[0]
    for w in words[1:]:
        cand = f"{cur} {w}"
        if _measure(draw, cand, lat_f, kn_f)[0] <= max_w:
            cur = cand
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# SINGLE API: HUGGING FACE INFERENCE CLIENT (+ LOCAL FALLBACK)
# ---------------------------------------------------------------------------
def _fallback_scene_image(prompt: str, width: int, height: int, out_path: str) -> str:
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)
    top_c = rng.choice([(20, 26, 56), (34, 20, 52), (16, 42, 54)])
    bot_c = rng.choice([(225, 132, 56), (95, 155, 135), (235, 168, 76)])

    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    arr = np.zeros((height, width, 3), dtype=np.float32)
    for c in range(3):
        arr[:, :, c] = top_c[c] * (1 - y) + bot_c[c] * y

    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    glow = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gx, gy = width // 2, int(height * 0.38)
    gr = int(min(width, height) * 0.14)
    gdraw.ellipse([gx - gr, gy - gr, gx + gr, gy + gr], fill=(255, 222, 130, 140))
    for _ in range(12):
        rx = rng.randint(0, width)
        ry = rng.randint(0, int(height * 0.75))
        rr = rng.randint(20, 85)
        gdraw.ellipse([rx - rr, ry - rr, rx + rr, ry + rr], fill=(255, 210, 120, 45))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=18))
    img = Image.alpha_composite(img, glow)

    fg = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fg)
    base_y = int(height * 0.70)
    fdraw.polygon([(0, height), (0, base_y), (width // 2, base_y - int(height * 0.10)), (width, base_y), (width, height)], fill=(15, 22, 20, 225))
    Image.alpha_composite(img, fg).convert("RGB").save(out_path, quality=92)
    return out_path


def generate_hf_scene_image(
    prompt: str,
    hf_token: str,
    model_id: str,
    width: int,
    height: int,
    out_path: str,
) -> Tuple[str, Optional[str]]:
    """Generates an image via Hugging Face InferenceClient; returns (path, error_or_none)."""
    eng_prompt = translate_to_english(prompt)
    token = hf_token.strip()
    if not token:
        return _fallback_scene_image(eng_prompt, width, height, out_path), "No HF_TOKEN provided; used local fallback art."

    try:
        client = InferenceClient(token=token)
        pil_img = client.text_to_image(prompt=eng_prompt, model=model_id)
        pil_img = pil_img.convert("RGB").resize((width, height), Image.Resampling.LANCZOS)
        pil_img.save(out_path, quality=92)
        return out_path, None
    except Exception as e:
        fallback_p = _fallback_scene_image(eng_prompt, width, height, out_path)
        return fallback_p, f"HF image fallback used ({model_id}): {e}"


# ---------------------------------------------------------------------------
# VOICEOVER (edge-tts) & VIDEO RENDERER
# ---------------------------------------------------------------------------
async def _synth_tts(text: str, voice: str, out_mp3: str) -> None:
    await edge_tts.Communicate(text=text, voice=voice).save(out_mp3)


def make_voiceover(text: str, voice: str, out_mp3: str) -> Tuple[Optional[str], float]:
    clean = text.strip()
    if not clean:
        return None, 0.0
    spoken = translate_to_kannada(clean) if voice.startswith("kn-IN") else clean
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_synth_tts(spoken, voice, out_mp3))
    except Exception:
        return None, 0.0
    finally:
        loop.close()

    if os.path.exists(out_mp3) and os.path.getsize(out_mp3) > 0:
        clip = AudioFileClip(out_mp3)
        dur = float(clip.duration)
        clip.close()
        return out_mp3, dur
    return None, 0.0


def _build_overlay(width: int, height: int, chapter: str, subtitle: str) -> np.ndarray:
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if chapter.strip():
        c_lat, c_kn = get_fonts(max(20, int(height * 0.032)))
        lw, lh = _measure(draw, chapter.strip(), c_lat, c_kn)
        draw.rounded_rectangle([24, 24, 24 + lw + 32, 24 + lh + 16], radius=10, fill=(16, 18, 30, 210), outline=(255, 195, 65, 190), width=2)
        _draw_text(draw, (40, 31), chapter.strip(), c_lat, c_kn, (255, 210, 80, 255))

    if subtitle.strip():
        s_lat, s_kn = get_fonts(max(28, int(height * 0.045)))
        lines = _wrap(draw, subtitle.strip(), s_lat, s_kn, int(width * 0.85))
        ws, hs = [], []
        for ln in lines:
            lw, lh = _measure(draw, ln, s_lat, s_kn)
            ws.append(lw)
            hs.append(lh + 12)
        bw = min(width - 36, max(ws) + 48)
        bh = sum(hs) + 26
        bx = (width - bw) // 2
        by = height - bh - 30
        draw.rounded_rectangle([bx, by, bx + bw, by + bh], radius=16, fill=(10, 12, 20, 228), outline=(255, 200, 70, 150), width=2)
        cy = by + 13
        for ln, lw, lh in zip(lines, ws, hs):
            tx = bx + (bw - lw) // 2
            _draw_text(draw, (tx + 2, cy + 2), ln, s_lat, s_kn, (0, 0, 0, 235))
            _draw_text(draw, (tx, cy), ln, s_lat, s_kn, (255, 255, 255, 255))
            cy += lh

    return np.array(layer)


def render_video_from_scenes(
    scenes: List[Dict],
    workdir: str,
    out_mp4: str,
    width: int = 1280,
    height: int = 720,
    enable_audio: bool = True,
    voice: str = "kn-IN-SapnaNeural",
    progress_cb=None,
) -> Tuple[str, List[str]]:
    warnings: List[str] = []
    clips: List[CompositeVideoClip] = []
    total = len(scenes)

    for i, sc in enumerate(scenes):
        if progress_cb:
            progress_cb(i / max(total, 1), f"Rendering scene {i + 1}/{total}...")

        audio_path = None
        audio_dur = 0.0
        narration = sc.get("subtitle_kn") or sc.get("script", "")
        if enable_audio and narration.strip():
            mp3_p = os.path.join(workdir, f"vo_{i}_{int(time.time()*1000)}.mp3")
            audio_path, audio_dur = make_voiceover(narration, voice=voice, out_mp3=mp3_p)
            if not audio_path:
                warnings.append(f"Scene {i + 1}: Voiceover unavailable; used scene duration.")

        dur = max(float(sc.get("duration", 4.5)), audio_dur + 0.5) if audio_dur > 0 else float(sc.get("duration", 4.5))
        motion = sc.get("motion", "zoom_in")

        base = np.array(Image.open(sc["image_path"]).convert("RGB").resize((width, height), Image.Resampling.LANCZOS))

        def frame_fn(t: float, arr=base, d=dur, m=motion) -> np.ndarray:
            p = np.clip(t / max(d, 0.01), 0.0, 1.0)
            ease = p * p * (3.0 - 2.0 * p)
            if m == "zoom_in":
                scale, cx, cy = 1.0 + 0.15 * ease, 0.5, 0.5
            elif m == "zoom_out":
                scale, cx, cy = 1.15 - 0.15 * ease, 0.5, 0.5
            elif m == "pan_right":
                scale, cx, cy = 1.14, 0.43 + 0.14 * ease, 0.5
            elif m == "pan_left":
                scale, cx, cy = 1.14, 0.57 - 0.14 * ease, 0.5
            else:
                scale, cx, cy = 1.04 + 0.11 * ease, 0.46 + 0.08 * ease, 0.46 + 0.08 * ease

            cw = int(round(width / scale))
            ch = int(round(height / scale))
            x1 = max(0, min(width - cw, int(round(cx * width - cw / 2))))
            y1 = max(0, min(height - ch, int(round(cy * height - ch / 2))))
            crop = arr[y1 : y1 + ch, x1 : x1 + cw]
            return np.array(Image.fromarray(crop).resize((width, height), Image.Resampling.BILINEAR))

        bg_clip = ImageClip(base).set_duration(dur).fl(lambda gf, t, fn=frame_fn: fn(t), apply_to=[]).set_fps(24)
        ov_arr = _build_overlay(width, height, sc.get("chapter", ""), sc.get("subtitle_kn", ""))
        ov_clip = ImageClip(ov_arr, ismask=False).set_duration(dur).crossfadein(min(0.3, dur * 0.2))

        comp = CompositeVideoClip([bg_clip, ov_clip], size=(width, height)).set_duration(dur)
        if audio_path and os.path.exists(audio_path):
            comp = comp.set_audio(AudioFileClip(audio_path))
        if i > 0:
            comp = comp.crossfadein(0.45)
        clips.append(comp)

    if progress_cb:
        progress_cb(0.92, "Encoding final MP4...")

    final = concatenate_videoclips(clips, method="compose", padding=-0.45 if len(clips) > 1 else 0)
    final.write_videofile(
        out_mp4,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        audio=enable_audio,
        preset="medium",
        threads=4,
        logger=None,
    )
    if progress_cb:
        progress_cb(1.0, "Done!")
    return out_mp4, warnings


def split_custom_lines(text: str) -> List[str]:
    return [line.strip() for line in re.split(r"(?<=[.!?।])\s+|\n+", text.strip()) if line.strip()]
