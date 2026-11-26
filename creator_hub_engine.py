import asyncio
import hashlib
import math
import os
import random
import re
import time
import urllib.parse
from typing import List, Optional, Tuple

import edge_tts
import numpy as np
import requests
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ---------------------------------------------------------------------------
# 1. FONT DISCOVERY (Fixes Kannada / Hindi / English glyph rendering)
# ---------------------------------------------------------------------------
def find_font(text: str, font_size: int = 40) -> ImageFont.FreeTypeFont:
    has_kannada = any("\u0c80" <= ch <= "\u0cff" for ch in text)
    has_devanagari = any("\u0900" <= ch <= "\u097f" for ch in text)

    kannada_fonts = [
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansKannada-Bold.otf",
        "/usr/share/fonts/truetype/lohit-kannada/Lohit-Kannada.ttf",
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/Tunga.ttf",
        "/System/Library/Fonts/Supplemental/Kannada MN.ttc",
    ]
    hindi_fonts = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/mangal.ttf",
    ]
    latin_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    if has_kannada:
        candidates = kannada_fonts + latin_fonts
    elif has_devanagari:
        candidates = hindi_fonts + latin_fonts
    else:
        candidates = latin_fonts + kannada_fonts

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except OSError:
                continue

    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# 2. FREE SCENE IMAGE GENERATION (Pollinations -> AI Horde -> Local Art Fallback)
# ---------------------------------------------------------------------------
def generate_procedural_art(prompt: str, width: int, height: int, out_path: str) -> str:
    """100% offline/local cinematic gradient + geometric light-bokeh art fallback."""
    seed = int(hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    palettes = [
        [(18, 24, 58), (88, 42, 130), (235, 110, 95)],
        [(12, 48, 56), (24, 115, 118), (240, 185, 85)],
        [(35, 18, 48), (140, 38, 82), (250, 155, 70)],
        [(15, 32, 65), (38, 92, 168), (110, 210, 235)],
    ]
    c1, c2, c3 = rng.choice(palettes)

    y_grid = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    x_grid = np.linspace(0, 1, width, dtype=np.float32)[None, :]
    blend = 0.65 * y_grid + 0.35 * x_grid

    img_arr = np.zeros((height, width, 3), dtype=np.float32)
    for ch in range(3):
        top_mid = c1[ch] * (1 - blend * 2) + c2[ch] * (blend * 2)
        mid_bot = c2[ch] * (1 - (blend - 0.5) * 2) + c3[ch] * ((blend - 0.5) * 2)
        img_arr[:, :, ch] = np.where(blend < 0.5, top_mid, mid_bot)

    base = Image.fromarray(np.clip(img_arr, 0, 255).astype(np.uint8)).convert("RGBA")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    for _ in range(18):
        rx = rng.randint(-50, width + 50)
        ry = rng.randint(-50, height + 50)
        rad = rng.randint(int(min(width, height) * 0.06), int(min(width, height) * 0.24))
        alpha = rng.randint(18, 55)
        draw.ellipse([rx - rad, ry - rad, rx + rad, ry + rad], fill=(255, 255, 255, alpha))

    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=18))
    combined = Image.alpha_composite(base, overlay).convert("RGB")
    combined.save(out_path, quality=92)
    return out_path


def try_pollinations(prompt: str, width: int, height: int, out_path: str, seed: int) -> bool:
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&nologo=true"
    try:
        resp = requests.get(url, timeout=25)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
            with open(out_path, "wb") as f:
                f.write(resp.content)
            return True
    except Exception:
        pass
    return False


def try_ai_horde(prompt: str, out_path: str) -> bool:
    """Free community Stable Diffusion cluster using public anonymous key."""
    headers = {"apikey": "0000000000", "Content-Type": "application/json"}
    payload = {
        "prompt": prompt,
        "params": {"width": 512, "height": 512, "steps": 18, "n": 1},
        "nsfw": False,
        "censor_nsfw": True,
    }
    try:
        res = requests.post("https://stablehorde.net/api/v2/generate/async", json=payload, headers=headers, timeout=15)
        if res.status_code != 202:
            return False
        job_id = res.json().get("id")
        if not job_id:
            return False

        for _ in range(25):
            time.sleep(2.5)
            chk = requests.get(f"https://stablehorde.net/api/v2/generate/status/{job_id}", timeout=10).json()
            if chk.get("done") and chk.get("generations"):
                img_url = chk["generations"][0].get("img")
                if img_url:
                    img_data = requests.get(img_url, timeout=15).content
                    with open(out_path, "wb") as f:
                        f.write(img_data)
                    return True
    except Exception:
        pass
    return False


def get_free_ai_scene_image(
    scene_prompt: str,
    style_desc: str,
    width: int,
    height: int,
    out_path: str,
    seed: int,
) -> str:
    full_prompt = f"{scene_prompt}, {style_desc}, cinematic lighting, high detail, digital illustration, no text"
    if try_pollinations(full_prompt, width, height, out_path, seed):
        return out_path
    if try_ai_horde(full_prompt, out_path):
        return out_path
    return generate_procedural_art(full_prompt, width, height, out_path)


# ---------------------------------------------------------------------------
# 3. FREE NEURAL VOICEOVER (edge-tts)
# ---------------------------------------------------------------------------
async def _synth_edge_tts(text: str, voice: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(out_path)


def synthesize_line_audio(text: str, voice: str, out_path: str) -> Optional[float]:
    """Generates MP3 audio for a single scene and returns its exact duration in seconds."""
    clean = text.strip()
    if not clean:
        return None
    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_synth_edge_tts(clean, voice, out_path))
    finally:
        loop.close()

    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        clip = AudioFileClip(out_path)
        dur = clip.duration
        clip.close()
        return dur
    return None


# ---------------------------------------------------------------------------
# 4. TYPOGRAPHY & ANIMATED OVERLAYS (Top Title + Bottom Styled Subtitles)
# ---------------------------------------------------------------------------
def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    curr = words[0]
    for w in words[1:]:
        test = f"{curr} {w}"
        bbox = draw.textbbox((0, 0), test, font=font)
        if (bbox[2] - bbox[0]) <= max_width:
            curr = test
        else:
            lines.append(curr)
            curr = w
    lines.append(curr)
    return lines


def render_banner_overlay(
    width: int,
    height: int,
    top_title: str = "",
    bottom_caption: str = "",
    accent_color: Tuple[int, int, int] = (255, 196, 54),
) -> np.ndarray:
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Top Title Pill (optional)
    if top_title.strip():
        t_font = find_font(top_title, font_size=max(26, int(height * 0.042)))
        t_lines = wrap_text(draw, top_title.strip(), t_font, int(width * 0.84))
        t_heights, t_widths = [], []
        for line in t_lines:
            bb = draw.textbbox((0, 0), line, font=t_font)
            t_widths.append(bb[2] - bb[0])
            t_heights.append((bb[3] - bb[1]) + 8)
        box_w = min(width - 48, max(t_widths) + 44)
        box_h = sum(t_heights) + 24
        bx = (width - box_w) // 2
        by = 26
        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=14,
            fill=(15, 20, 35, 210),
            outline=(*accent_color, 180),
            width=2,
        )
        cy = by + 12
        for line, lw, lh in zip(t_lines, t_widths, t_heights):
            tx = bx + (box_w - lw) // 2
            draw.text((tx, cy), line, font=t_font, fill=(*accent_color, 255))
            cy += lh

    # Bottom Subtitle Card
    if bottom_caption.strip():
        c_font = find_font(bottom_caption, font_size=max(30, int(height * 0.048)))
        c_lines = wrap_text(draw, bottom_caption.strip(), c_font, int(width * 0.86))
        c_heights, c_widths = [], []
        for line in c_lines:
            bb = draw.textbbox((0, 0), line, font=c_font)
            c_widths.append(bb[2] - bb[0])
            c_heights.append((bb[3] - bb[1]) + 10)
        box_w = min(width - 40, max(c_widths) + 52)
        box_h = sum(c_heights) + 32
        bx = (width - box_w) // 2
        by = height - box_h - 34

        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=18,
            fill=(10, 12, 20, 222),
            outline=(255, 255, 255, 55),
            width=2,
        )
        # Left accent bar
        draw.rounded_rectangle(
            [bx + 10, by + 12, bx + 17, by + box_h - 12],
            radius=4,
            fill=(*accent_color, 255),
        )
        cy = by + 16
        for line, lw, lh in zip(c_lines, c_widths, c_heights):
            tx = bx + (box_w - lw) // 2 + 4
            draw.text((tx + 2, cy + 2), line, font=c_font, fill=(0, 0, 0, 230))
            draw.text((tx, cy), line, font=c_font, fill=(255, 255, 255, 255))
            cy += lh

    return np.array(overlay)


# ---------------------------------------------------------------------------
# 5. MOTION & SCENE COMPOSITING
# ---------------------------------------------------------------------------
def prepare_canvas(img_path: str, width: int, height: int) -> np.ndarray:
    src = Image.open(img_path).convert("RGB")
    bg = src.resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=14))
    bg_arr = (np.asarray(bg, dtype=np.float32) * 0.45).astype(np.uint8)

    src_ratio = src.width / src.height
    dst_ratio = width / height
    if src_ratio > dst_ratio:
        new_w = width
        new_h = int(width / src_ratio)
    else:
        new_h = height
        new_w = int(height * src_ratio)

    fg = src.resize((new_w, new_h), Image.Resampling.LANCZOS)
    canvas = Image.fromarray(bg_arr)
    canvas.paste(fg, ((width - new_w) // 2, (height - new_h) // 2))
    return np.array(canvas)


def build_animated_scene(
    img_path: str,
    duration: float,
    top_title: str,
    caption: str,
    width: int,
    height: int,
    motion: str,
    audio_path: Optional[str] = None,
) -> CompositeVideoClip:
    base_frame = prepare_canvas(img_path, width, height)

    def make_frame(t: float) -> np.ndarray:
        p = np.clip(t / max(duration, 0.01), 0.0, 1.0)
        ease = p * p * (3.0 - 2.0 * p)

        if motion == "zoom_in":
            scale, cx, cy = 1.0 + 0.14 * ease, 0.5, 0.5
        elif motion == "zoom_out":
            scale, cx, cy = 1.14 - 0.14 * ease, 0.5, 0.5
        elif motion == "pan_right":
            scale, cx, cy = 1.12, 0.43 + 0.14 * ease, 0.5
        elif motion == "pan_left":
            scale, cx, cy = 1.12, 0.57 - 0.14 * ease, 0.5
        else:  # ken_burns_diag
            scale, cx, cy = 1.03 + 0.11 * ease, 0.46 + 0.08 * ease, 0.47 + 0.06 * ease

        crop_w = int(round(width / scale))
        crop_h = int(round(height / scale))
        x1 = max(0, min(width - crop_w, int(round(cx * width - crop_w / 2))))
        y1 = max(0, min(height - crop_h, int(round(cy * height - crop_h / 2))))

        cropped = base_frame[y1 : y1 + crop_h, x1 : x1 + crop_w]
        resized = Image.fromarray(cropped).resize((width, height), Image.Resampling.BILINEAR)
        return np.array(resized)

    bg_clip = ImageClip(base_frame).set_duration(duration).fl(lambda gf, t: make_frame(t), apply_to=[]).set_fps(24)

    layers = [bg_clip]
    if top_title.strip() or caption.strip():
        overlay_arr = render_banner_overlay(width, height, top_title=top_title, bottom_caption=caption)
        txt_clip = ImageClip(overlay_arr, ismask=False).set_duration(duration).crossfadein(min(0.35, duration * 0.25))
        layers.append(txt_clip)

    comp = CompositeVideoClip(layers, size=(width, height)).set_duration(duration)
    if audio_path and os.path.exists(audio_path):
        comp = comp.set_audio(AudioFileClip(audio_path))
    return comp


# ---------------------------------------------------------------------------
# 6. MAIN SCRIPT-TO-VIDEO PIPELINE
# ---------------------------------------------------------------------------
def split_script_scenes(script: str, max_scenes: int = 8) -> List[str]:
    lines = [s.strip() for s in re.split(r"(?<=[.!?।])\s+|\n+", script.strip()) if s.strip()]
    if not lines:
        return []
    if len(lines) <= max_scenes:
        return lines

    buckets: List[List[str]] = [[] for _ in range(max_scenes)]
    for i, line in enumerate(lines):
        idx = min(i * max_scenes // len(lines), max_scenes - 1)
        buckets[idx].append(line)
    return [" ".join(b) for b in buckets]


def create_creator_hub_video(
    script: str,
    description: str,
    video_title: str,
    workdir: str,
    output_path: str,
    uploaded_images: Optional[List[str]] = None,
    visual_mode: str = "ai_auto",  # "ai_auto", "uploaded_only", "hybrid"
    resolution: Tuple[int, int] = (1280, 720),
    default_scene_sec: float = 4.0,
    enable_voiceover: bool = True,
    voice_name: str = "kn-IN-SapnaNeural",
    progress_callback=None,
) -> str:
    width, height = resolution
    uploaded_images = uploaded_images or []

    beats = split_script_scenes(script if script.strip() else description)
    if not beats:
        raise ValueError("Please enter a script or description to build your video.")

    if visual_mode == "uploaded_only" and uploaded_images:
        # Align beats to number of uploaded images
        if len(beats) != len(uploaded_images):
            beats = split_script_scenes("\n".join(beats), max_scenes=len(uploaded_images))

    motions = ["zoom_in", "pan_right", "ken_burns_diag", "zoom_out", "pan_left"]
    clips: List[CompositeVideoClip] = []
    total = len(beats)

    for idx, beat in enumerate(beats):
        if progress_callback:
            progress_callback(idx / total, f"Building scene {idx + 1}/{total}...")

        # 1. Resolve visual for this scene
        scene_img = os.path.join(workdir, f"scene_vis_{idx}.jpg")
        if visual_mode == "uploaded_only" and uploaded_images:
            scene_img = uploaded_images[idx % len(uploaded_images)]
        elif visual_mode == "hybrid" and idx < len(uploaded_images):
            scene_img = uploaded_images[idx]
        else:
            scene_prompt = f"{beat}. Context: {description}"
            get_free_ai_scene_image(
                scene_prompt=scene_prompt,
                style_desc=description or "cinematic digital art",
                width=width,
                height=height,
                out_path=scene_img,
                seed=1000 + idx * 37,
            )

        # 2. Generate per-scene voiceover so timing matches narration naturally
        audio_file = None
        scene_dur = default_scene_sec
        if enable_voiceover:
            candidate_mp3 = os.path.join(workdir, f"voice_{idx}.mp3")
            spoken_dur = synthesize_line_audio(beat, voice=voice_name, out_path=candidate_mp3)
            if spoken_dur:
                audio_file = candidate_mp3
                scene_dur = max(2.8, spoken_dur + 0.55)

        # 3. Animate scene
        clip = build_animated_scene(
            img_path=scene_img,
            duration=scene_dur,
            top_title=video_title if idx == 0 else "",
            caption=beat,
            width=width,
            height=height,
            motion=motions[idx % len(motions)],
            audio_path=audio_file,
        )
        if idx > 0:
            clip = clip.crossfadein(0.5)
        clips.append(clip)

    if progress_callback:
        progress_callback(0.92, "Encoding final MP4 video...")

    final_video = concatenate_videoclips(clips, method="compose", padding=-0.5 if len(clips) > 1 else 0)
    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
    )
    if progress_callback:
        progress_callback(1.0, "Done!")
    return output_path
