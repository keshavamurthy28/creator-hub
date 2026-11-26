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


def translate_to_kannada(text: str) -> str:
    clean = text.strip()
    if not clean:
        return ""
    # Already has Kannada script
    if any("\u0c80" <= ch <= "\u0cff" for ch in clean):
        return clean
    try:
        translated = GoogleTranslator(source="auto", target="kn").translate(clean)
        return translated or clean
    except Exception:
        return clean


def translate_to_english(text: str) -> str:
    clean = text.strip()
    if not clean:
        return ""
    try:
        translated = GoogleTranslator(source="auto", target="en").translate(clean)
        return translated or clean
    except Exception:
        return clean


def _load_font(paths: List[str], size: int) -> ImageFont.FreeTypeFont:
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def get_fonts(size: int) -> Tuple[ImageFont.FreeTypeFont, ImageFont.FreeTypeFont]:
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
        "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/Tunga.ttf",
        "/System/Library/Fonts/Supplemental/Kannada MN.ttc",
    ]
    return _load_font(latin_paths, size), _load_font(kannada_paths, size)


def split_runs(text: str) -> List[Tuple[str, bool]]:
    if not text:
        return []
    runs: List[Tuple[str, bool]] = []
    buf = [text[0]]
    is_kn_prev = "\u0c80" <= text[0] <= "\u0cff"
    for ch in text[1:]:
        is_kn = "\u0c80" <= ch <= "\u0cff"
        if is_kn == is_kn_prev:
            buf.append(ch)
        else:
            runs.append(("".join(buf), is_kn_prev))
            buf = [ch]
            is_kn_prev = is_kn
    runs.append(("".join(buf), is_kn_prev))
    return runs


def measure_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    lat_font: ImageFont.FreeTypeFont,
    kn_font: ImageFont.FreeTypeFont,
) -> Tuple[int, int]:
    w_sum = 0
    h_max = 0
    for seg, is_kn in split_runs(text):
        fnt = kn_font if is_kn else lat_font
        bb = draw.textbbox((0, 0), seg, font=fnt)
        w_sum += bb[2] - bb[0]
        h_max = max(h_max, bb[3] - bb[1])
    return w_sum, h_max


def draw_line(
    draw: ImageDraw.ImageDraw,
    xy: Tuple[int, int],
    text: str,
    lat_font: ImageFont.FreeTypeFont,
    kn_font: ImageFont.FreeTypeFont,
    fill: Tuple[int, int, int, int],
) -> None:
    x, y = xy
    for seg, is_kn in split_runs(text):
        fnt = kn_font if is_kn else lat_font
        draw.text((x, y), seg, font=fnt, fill=fill)
        bb = draw.textbbox((0, 0), seg, font=fnt)
        x += bb[2] - bb[0]


def wrap_line(
    draw: ImageDraw.ImageDraw,
    text: str,
    lat_font: ImageFont.FreeTypeFont,
    kn_font: ImageFont.FreeTypeFont,
    max_w: int,
) -> List[str]:
    words = text.split()
    if not words:
        return []
    lines: List[str] = []
    curr = words[0]
    for w in words[1:]:
        candidate = f"{curr} {w}"
        lw, _ = measure_line(draw, candidate, lat_font, kn_font)
        if lw <= max_w:
            curr = candidate
        else:
            lines.append(curr)
            curr = w
    lines.append(curr)
    return lines


def make_subtitle_frame(
    width: int,
    height: int,
    subtitle: str,
    scene_label: str = "",
) -> np.ndarray:
    layer = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if scene_label.strip():
        s_lat, s_kn = get_fonts(max(20, int(height * 0.032)))
        lw, lh = measure_line(draw, scene_label.strip(), s_lat, s_kn)
        pw, ph = lw + 32, lh + 16
        px, py = 28, 24
        draw.rounded_rectangle([px, py, px + pw, py + ph], radius=10, fill=(10, 14, 24, 195))
        draw_line(draw, (px + 16, py + 7), scene_label.strip(), s_lat, s_kn, (255, 205, 75, 255))

    if subtitle.strip():
        c_lat, c_kn = get_fonts(max(30, int(height * 0.048)))
        lines = wrap_line(draw, subtitle.strip(), c_lat, c_kn, int(width * 0.86))
        widths, heights = [], []
        for ln in lines:
            lw, lh = measure_line(draw, ln, c_lat, c_kn)
            widths.append(lw)
            heights.append(lh + 14)

        box_w = min(width - 40, max(widths) + 56)
        box_h = sum(heights) + 28
        bx = (width - box_w) // 2
        by = height - box_h - 32

        draw.rounded_rectangle(
            [bx, by, bx + box_w, by + box_h],
            radius=16,
            fill=(8, 10, 18, 228),
            outline=(255, 200, 60, 140),
            width=2,
        )
        cy = by + 14
        for ln, lw, lh in zip(lines, widths, heights):
            tx = bx + (box_w - lw) // 2
            draw_line(draw, (tx + 2, cy + 2), ln, c_lat, c_kn, (0, 0, 0, 235))
            draw_line(draw, (tx, cy), ln, c_lat, c_kn, (255, 255, 255, 255))
            cy += lh

    return np.array(layer)


def generate_fallback_scene_art(visual_prompt: str, width: int, height: int, out_path: str) -> str:
    """Rich scene illustration fallback with sky, horizon/forest silhouettes, and light rays."""
    seed = int(hashlib.sha256(visual_prompt.encode("utf-8")).hexdigest()[:8], 16)
    rng = random.Random(seed)

    sky_top = rng.choice([(18, 28, 56), (25, 35, 45), (42, 24, 48), (16, 42, 52)])
    sky_bot = rng.choice([(215, 115, 65), (95, 150, 130), (235, 165, 75), (75, 135, 175)])

    y = np.linspace(0, 1, height, dtype=np.float32)[:, None]
    arr = np.zeros((height, width, 3), dtype=np.float32)
    for c in range(3):
        arr[:, :, c] = sky_top[c] * (1 - y) + sky_bot[c] * y

    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).convert("RGBA")
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Sun / glow orb
    sun_x = rng.randint(int(width * 0.2), int(width * 0.8))
    sun_y = rng.randint(int(height * 0.22), int(height * 0.5))
    sun_r = int(min(width, height) * 0.11)
    draw.ellipse([sun_x - sun_r, sun_y - sun_r, sun_x + sun_r, sun_y + sun_r], fill=(255, 225, 150, 120))
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=16))
    img = Image.alpha_composite(img, overlay)

    # Forest silhouette & mountain ridge at bottom
    fg = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    fdraw = ImageDraw.Draw(fg)
    base_y = int(height * 0.68)
    fdraw.polygon([(0, height), (0, base_y), (width // 2, base_y - int(height * 0.12)), (width, base_y), (width, height)], fill=(18, 28, 24, 210))

    tree_x = 0
    while tree_x < width:
        tw = rng.randint(24, 52)
        th = rng.randint(55, 130)
        ty = base_y + rng.randint(-10, 25)
        fdraw.polygon([(tree_x, ty), (tree_x + tw // 2, ty - th), (tree_x + tw, ty)], fill=(10, 18, 14, 245))
        tree_x += rng.randint(16, 36)

    Image.alpha_composite(img, fg).convert("RGB").save(out_path, quality=92)
    return out_path


def fetch_scene_image(visual_prompt: str, width: int, height: int, out_path: str, seed: int) -> str:
    eng = translate_to_english(visual_prompt)
    prompt = f"{eng}, 2d animated movie scene, dramatic storytelling, expressive characters, rich environment, no text, no watermark"
    encoded = urllib.parse.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&seed={seed}&nologo=true"
    try:
        resp = requests.get(url, timeout=25)
        if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("image/"):
            with open(out_path, "wb") as f:
                f.write(resp.content)
            return out_path
    except Exception:
        pass
    return generate_fallback_scene_art(prompt, width, height, out_path)


async def _run_edge_tts(text: str, voice: str, out_mp3: str) -> None:
    comm = edge_tts.Communicate(text=text, voice=voice)
    await comm.save(out_mp3)


def generate_kannada_or_voice(text: str, voice: str, out_mp3: str) -> Tuple[Optional[str], float]:
    clean = text.strip()
    if not clean:
        return None, 0.0

    spoken = clean
    if voice.startswith("kn-IN"):
        spoken = translate_to_kannada(clean)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_run_edge_tts(spoken, voice, out_mp3))
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


def prepare_frame(img_path: str, width: int, height: int) -> np.ndarray:
    src = Image.open(img_path).convert("RGB")
    bg = src.resize((width, height), Image.Resampling.LANCZOS).filter(ImageFilter.GaussianBlur(radius=12))
    bg_arr = (np.asarray(bg, dtype=np.float32) * 0.5).astype(np.uint8)

    sr = src.width / src.height
    dr = width / height
    if sr > dr:
        nw, nh = width, int(width / sr)
    else:
        nh, nw = height, int(height * sr)

    fg = src.resize((nw, nh), Image.Resampling.LANCZOS)
    canvas = Image.fromarray(bg_arr)
    canvas.paste(fg, ((width - nw) // 2, (height - nh) // 2))
    return np.array(canvas)


def build_animated_scene_clip(
    scene: Dict,
    width: int,
    height: int,
    audio_path: Optional[str],
    audio_dur: float,
) -> CompositeVideoClip:
    base = prepare_frame(scene["image_path"], width, height)
    min_dur = float(scene.get("duration", 4.5))
    duration = max(min_dur, audio_dur + 0.5) if audio_dur > 0 else min_dur
    motion = scene.get("motion", "zoom_in")

    def frame_at(t: float) -> np.ndarray:
        p = np.clip(t / max(duration, 0.01), 0.0, 1.0)
        ease = p * p * (3.0 - 2.0 * p)

        if motion == "zoom_in":
            scale, cx, cy = 1.0 + 0.16 * ease, 0.5, 0.5
        elif motion == "zoom_out":
            scale, cx, cy = 1.16 - 0.16 * ease, 0.5, 0.5
        elif motion == "pan_right":
            scale, cx, cy = 1.14, 0.42 + 0.16 * ease, 0.5
        elif motion == "pan_left":
            scale, cx, cy = 1.14, 0.58 - 0.16 * ease, 0.5
        else:
            scale, cx, cy = 1.04 + 0.12 * ease, 0.45 + 0.10 * ease, 0.46 + 0.08 * ease

        cw = int(round(width / scale))
        ch = int(round(height / scale))
        x1 = max(0, min(width - cw, int(round(cx * width - cw / 2))))
        y1 = max(0, min(height - ch, int(round(cy * height - ch / 2))))

        crop = base[y1 : y1 + ch, x1 : x1 + cw]
        return np.array(Image.fromarray(crop).resize((width, height), Image.Resampling.BILINEAR))

    anim_bg = ImageClip(base).set_duration(duration).fl(lambda gf, t: frame_at(t), apply_to=[]).set_fps(24)

    sub_arr = make_subtitle_frame(
        width=width,
        height=height,
        subtitle=scene.get("subtitle_kn", ""),
        scene_label=scene.get("scene_label", ""),
    )
    sub_clip = ImageClip(sub_arr, ismask=False).set_duration(duration).crossfadein(min(0.3, duration * 0.2))

    comp = CompositeVideoClip([anim_bg, sub_clip], size=(width, height)).set_duration(duration)
    if audio_path and os.path.exists(audio_path):
        comp = comp.set_audio(AudioFileClip(audio_path))
    return comp


def split_into_story_beats(text: str) -> List[str]:
    parts = [p.strip() for p in re.split(r"(?<=[.!?।])\s+|\n+", text.strip()) if p.strip()]
    return parts


def render_story_video(
    scenes: List[Dict],
    workdir: str,
    out_mp4: str,
    resolution: Tuple[int, int] = (1280, 720),
    enable_audio: bool = True,
    voice: str = "kn-IN-SapnaNeural",
    progress_cb=None,
) -> Tuple[str, List[str]]:
    """Returns (output_mp4_path, warnings_list)."""
    warnings: List[str] = []
    width, height = resolution
    clips: List[CompositeVideoClip] = []
    total = len(scenes)

    for i, sc in enumerate(scenes):
        if progress_cb:
            progress_cb(i / max(total, 1), f"Rendering scene {i + 1}/{total}...")

        audio_file = None
        audio_dur = 0.0
        narration_src = sc.get("narration_kn") or sc.get("subtitle_kn") or sc.get("raw_line", "")

        if enable_audio and narration_src.strip():
            mp3_path = os.path.join(workdir, f"scene_audio_{i}_{int(time.time()*1000)}.mp3")
            audio_file, audio_dur = generate_kannada_or_voice(narration_src, voice=voice, out_mp3=mp3_path)
            if not audio_file:
                warnings.append(f"Scene {i + 1}: Voiceover could not be generated (check internet connection for TTS).")

        clip = build_animated_scene_clip(
            scene=sc,
            width=width,
            height=height,
            audio_path=audio_file,
            audio_dur=audio_dur,
        )
        if i > 0:
            clip = clip.crossfadein(0.45)
        clips.append(clip)

    if progress_cb:
        progress_cb(0.9, "Combining scenes & encoding video...")

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
        progress_cb(1.0, "Video ready!")
    return out_mp4, warnings
