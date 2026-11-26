import asyncio
import hashlib
import os
import random
import re
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple

import edge_tts
import numpy as np
import requests
from deep_translator import GoogleTranslator
from moviepy.editor import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ---------------------------------------------------------------------------
# 1. FREE TRANSLATION (English / Hindi -> Kannada or English)
# ---------------------------------------------------------------------------
def translate_text(text: str, target_lang: str = "kn") -> str:
    """Free translation via deep-translator (no API key required)."""
    clean = text.strip()
    if not clean:
        return ""
    try:
        return GoogleTranslator(source="auto", target=target_lang).translate(clean)
    except Exception:
        return clean


# ---------------------------------------------------------------------------
# 2. DUAL-SCRIPT FONT ENGINE (Fixes Kannada + English mixed text!)
# ---------------------------------------------------------------------------
def _load_font_from_list(paths: List[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def get_script_fonts(font_size: int) -> Tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
    """Returns (latin_font, kannada_font) so mixed text renders both cleanly."""
    latin_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    kannada_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansKannada-Bold.otf",
        "/usr/share/fonts/truetype/lohit-kannada/Lohit-Kannada.ttf",
        "C:/Windows/Fonts/NirmalaB.ttf",
        "C:/Windows/Fonts/Tunga.ttf",
        "/System/Library/Fonts/Supplemental/Kannada MN.ttc",
    ]
    return _load_font_from_list(latin_paths, font_size), _load_font_from_list(kannada_paths, font_size)


def split_script_runs(text: str) -> List[Tuple[str, bool]]:
    """Splits text into [(substring, is_kannada), ...]."""
    runs: List[Tuple[str, bool]] = []
    if not text:
        return runs
    curr_chars = []
    curr_is_kn = "\u0c80" <= text[0] <= "\u0cff"
    for ch in text:
        is_kn = "\u0c80" <= ch <= "\u0cff"
        if is_kn == curr_is_kn:
            curr_chars.append(ch)
        else:
            runs.append(("".join(curr_chars), curr_is_kn))
            curr_chars = [ch]
            curr_is_kn = is_kn
    if curr_chars:
        runs.append(("".join(curr_chars), curr_is_kn))
    return runs


def measure_mixed_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    latin_font: ImageFont.FreeTypeFont,
    kn_font: ImageFont.FreeTypeFont,
) -> Tuple[int, int]:
    total_w = 0
    max_h = 0
    for segment, is_kn in split_script_runs(text):
        fnt = kn_font if is_kn else latin_font
        bb = draw.textbbox((0, 0), segment, font=fnt)
        total_w += bb[2] - bb[0]
        max_h = max(max_h, bb[3] - bb[1])
    return total_w, max_h


def draw_mixed_text(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    latin_font: ImageFont.FreeTypeFont,
    kn_font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
) -> None:
    x, y = xy
    for segment, is_kn in split_script_runs(text):
        fnt = kn_font if is_kn else latin_font
        draw.text((x, y), segment, font=fnt, fill=fill)
        bb = draw.textbbox((0, 0), segment, font=fnt)
        x += bb[2] - bb[0]


def wrap_mixed_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    latin_font: ImageFont.FreeTypeFont,
    kn_font: ImageFont.FreeTypeFont,
    max_width: int,
) -> List[str]:
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    curr = words[0]
    for w in words[1:]:
        test = f"{curr} {w}"
        tw, _ = measure_mixed_text(draw, test, latin_font, kn_font)
        if tw <= max_width:
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

    # Top Title Pill
    if top_title.strip():
        lat_f, kn_f = get_script_fonts(max(24, int(height * 0.038)))
        t_lines = wrap_mixed_text(draw, top_title.strip(), lat_f, kn_f, int(width * 0.84))
        t_heights, t_widths = [], []
        for line in t_lines:
            lw, lh = measure_mixed_text(draw, line, lat_f, kn_f)
            t_widths.append(lw)
            t_heights.append(lh + 10)
        box_w = min(width - 48, max(t_widths) + 44)
        box_h = sum(t_heights) + 22
        bx = (width - box_w) // 2
        by = 24
        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=14,
            fill=(15, 20, 35, 215),
            outline=(*accent_color, 190),
            width=2,
        )
        cy = by + 11
        for line, lw, lh in zip(t_lines, t_widths, t_heights):
            tx = bx + (box_w - lw) // 2
            draw_mixed_text(draw, (tx, cy), line, lat_f, kn_f, (*accent_color, 255))
            cy += lh

    # Bottom Subtitle Card
    if bottom_caption.strip():
        lat_f, kn_f = get_script_fonts(max(28, int(height * 0.044)))
        c_lines = wrap_mixed_text(draw, bottom_caption.strip(), lat_f, kn_f, int(width * 0.86))
        c_heights, c_widths = [], []
        for line in c_lines:
            lw, lh = measure_mixed_text(draw, line, lat_f, kn_f)
            c_widths.append(lw)
            c_heights.append(lh + 12)
        box_w = min(width - 40, max(c_widths) + 52)
        box_h = sum(c_heights) + 30
        bx = (width - box_w) // 2
        by = height - box_h - 32

        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=18,
            fill=(10, 12, 20, 225),
            outline=(255, 255, 255, 60),
            width=2,
        )
        draw.rounded_rectangle(
            [bx + 10, by + 12, bx + 17, by + box_h - 12],
            radius=4,
            fill=(*accent_color, 255),
        )
        cy = by + 15
        for line, lw, lh in zip(c_lines, c_widths, c_heights):
            tx = bx + (box_w - lw) // 2 + 4
            draw_mixed_text(draw, (tx + 2, cy + 2), line, lat_f, kn_f, (0, 0, 0, 230))
            draw_mixed_text(draw, (tx, cy), line, lat_f, kn_f, (255, 255, 255, 255))
            cy += lh

    return np.array(overlay)


# ---------------------------------------------------------------------------
# 3. FREE SCENE IMAGE GENERATION
# ---------------------------------------------------------------------------
def generate_procedural_art(prompt: str, width: int, height: int, out_path: str) -> str:
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
        draw.ellipse([rx - rad, ry - rad, rx + rad, ry + rad], fill=(255, 255, 255, rng.randint(18, 55)))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=18))
    Image.alpha_composite(base, overlay).convert("RGB").save(out_path, quality=92)
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


def get_free_ai_scene_image(scene_prompt: str, style_desc: str, width: int, height: int, out_path: str, seed: int) -> str:
    # Always translate image prompt to English so image models understand Kannada scripts too
    eng_prompt = translate_text(scene_prompt, target_lang="en")
    eng_style = translate_text(style_desc, target_lang="en")
    full_prompt = f"{eng_prompt}, {eng_style}, cinematic lighting, high detail, digital illustration, no text"
    if try_pollinations(full_prompt, width, height, out_path, seed):
        return out_path
    return generate_procedural_art(full_prompt, width, height, out_path)


# ---------------------------------------------------------------------------
# 4. FREE NEURAL VOICEOVER (Auto-aligns language with voice!)
# ---------------------------------------------------------------------------
async def _synth_edge_tts(text: str, voice: str, out_path: str) -> None:
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(out_path)


def synthesize_line_audio(text: str, voice: str, out_path: str) -> Optional[float]:
    clean = text.strip()
    if not clean:
        return None

    # If user picked a Kannada voice (kn-IN-*) but text is in English, translate to Kannada so voiceover works properly
    spoken_text = clean
    if voice.startswith("kn-IN") and not any("\u0c80" <= ch <= "\u0cff" for ch in clean):
        spoken_text = translate_text(clean, target_lang="kn")
    elif voice.startswith("hi-IN") and not any("\u0900" <= ch <= "\u097f" for ch in clean):
        spoken_text = translate_text(clean, target_lang="hi")

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_synth_edge_tts(spoken_text, voice, out_path))
    except Exception:
        return None
    finally:
        loop.close()

    if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
        clip = AudioFileClip(out_path)
        dur = clip.duration
        clip.close()
        return dur
    return None


# ---------------------------------------------------------------------------
# 5. MOTION & RENDER FROM EDITABLE SCENE LIST
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
        else:
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


def split_script_scenes(script: str, max_scenes: int = 10) -> List[str]:
    lines = [s.strip() for s in re.split(r"(?<=[.!?।])\s+|\n+", script.strip()) if s.strip()]
    return lines[:max_scenes]


def render_from_scenes(
    scenes: List[Dict],
    workdir: str,
    output_path: str,
    resolution: Tuple[int, int] = (1280, 720),
    enable_voiceover: bool = True,
    voice_name: str = "kn-IN-SapnaNeural",
    progress_callback=None,
) -> str:
    """Renders final MP4 directly from the user-edited storyboard scenes."""
    width, height = resolution
    clips: List[CompositeVideoClip] = []
    total = len(scenes)

    for idx, sc in enumerate(scenes):
        if progress_callback:
            progress_callback(idx / max(total, 1), f"Rendering scene {idx + 1}/{total}...")

        audio_file = None
        dur = float(sc.get("duration", 4.0))
        narration_text = sc.get("narration", sc.get("caption", ""))

        if enable_voiceover and narration_text.strip():
            candidate_mp3 = os.path.join(workdir, f"voice_{idx}_{int(time.time())}.mp3")
            spoken_dur = synthesize_line_audio(narration_text, voice=voice_name, out_path=candidate_mp3)
            if spoken_dur:
                audio_file = candidate_mp3
                dur = max(dur, spoken_dur + 0.5)

        clip = build_animated_scene(
            img_path=sc["image_path"],
            duration=dur,
            top_title=sc.get("top_title", ""),
            caption=sc.get("caption", ""),
            width=width,
            height=height,
            motion=sc.get("motion", "zoom_in"),
            audio_path=audio_file,
        )
        if idx > 0:
            clip = clip.crossfadein(0.45)
        clips.append(clip)

    if progress_callback:
        progress_callback(0.92, "Encoding final MP4...")

    final_video = concatenate_videoclips(clips, method="compose", padding=-0.45 if len(clips) > 1 else 0)
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
        progress_callback(1.0, "Complete!")
    return output_path
