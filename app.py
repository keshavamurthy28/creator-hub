import os
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from gtts import gTTS
from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    concatenate_videoclips,
)
from PIL import Image, ImageDraw, ImageFont


def find_font(text: str, font_size: int = 44) -> ImageFont.FreeTypeFont:
    """Selects a font capable of rendering Kannada or Latin text without tofu boxes."""
    has_kannada = any("\u0c80" <= ch <= "\u0cff" for ch in text)

    kannada_candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansKannada-Bold.otf",
        "/usr/share/fonts/truetype/lohit-kannada/Lohit-Kannada.ttf",
        "C:/Windows/Fonts/Nirmala.ttf",
        "C:/Windows/Fonts/Tunga.ttf",
        "/System/Library/Fonts/Supplemental/Kannada MN.ttc",
    ]
    latin_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    candidates = (kannada_candidates + latin_candidates) if has_kannada else (latin_candidates + kannada_candidates)

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, font_size)
            except OSError:
                continue

    return ImageFont.load_default()


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> List[str]:
    """Wraps text cleanly by pixel width rather than character count."""
    words = text.split()
    if not words:
        return []

    lines: List[str] = []
    current_line = words[0]

    for word in words[1:]:
        test_line = f"{current_line} {word}"
        bbox = draw.textbbox((0, 0), test_line, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)
    return lines


def render_caption_overlay(
    width: int,
    height: int,
    caption: str,
    position: str = "bottom",
    font_size: int = 38,
) -> np.ndarray:
    """Creates a transparent RGBA caption banner with crisp Kannada/English typography."""
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if not caption.strip():
        return np.array(overlay)

    draw = ImageDraw.Draw(overlay)
    font = find_font(caption, font_size=font_size)
    max_text_width = int(width * 0.88)
    lines = wrap_text(draw, caption.strip(), font, max_text_width)

    line_heights = []
    line_widths = []
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append((bbox[3] - bbox[1]) + 10)

    total_text_h = sum(line_heights)
    pad_x, pad_y = 28, 18
    box_w = min(width - 40, max(line_widths) + pad_x * 2)
    box_h = total_text_h + pad_y * 2

    box_x = (width - box_w) // 2
    if position == "top":
        box_y = 28
    else:
        box_y = height - box_h - 36

    # Semi-transparent dark card with subtle border
    draw.rounded_rectangle(
        [box_x, box_y, box_x + box_w, box_y + box_h],
        radius=16,
        fill=(12, 15, 24, 215),
        outline=(255, 255, 255, 45),
        width=2,
    )

    curr_y = box_y + pad_y
    for line, lw, lh in zip(lines, line_widths, line_heights):
        text_x = box_x + (box_w - lw) // 2
        # Soft drop shadow for readability
        draw.text((text_x + 2, curr_y + 2), line, font=font, fill=(0, 0, 0, 220))
        draw.text((text_x, curr_y), line, font=font, fill=(255, 255, 255, 255))
        curr_y += lh

    return np.array(overlay)


def prepare_base_canvas(img_path: str, width: int, height: int) -> np.ndarray:
    """Fits an image onto a target canvas with blurred background fill so aspect ratios never clip awkwardly."""
    src = Image.open(img_path).convert("RGB")

    # Background: fill frame with zoomed + slightly darkened version
    bg = src.resize((width, height), Image.Resampling.LANCZOS)
    bg_arr = (np.asarray(bg, dtype=np.float32) * 0.45).astype(np.uint8)

    # Foreground: fit inside frame preserving aspect ratio
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
    paste_x = (width - new_w) // 2
    paste_y = (height - new_h) // 2
    canvas.paste(fg, (paste_x, paste_y))
    return np.array(canvas)


def animate_scene(
    img_path: str,
    duration: float,
    caption: str,
    width: int = 1280,
    height: int = 720,
    motion_type: str = "zoom_in",
    caption_pos: str = "bottom",
) -> CompositeVideoClip:
    """Applies smooth Ken Burns camera movement + animated caption overlay to a single scene."""
    base_frame = prepare_base_canvas(img_path, width, height)

    def make_frame(t: float) -> np.ndarray:
        progress = np.clip(t / max(duration, 0.01), 0.0, 1.0)
        # Smooth ease-in-out curve
        ease = progress * progress * (3 - 2 * progress)

        if motion_type == "zoom_in":
            scale = 1.0 + 0.12 * ease
            cx, cy = 0.5, 0.5
        elif motion_type == "zoom_out":
            scale = 1.12 - 0.12 * ease
            cx, cy = 0.5, 0.5
        elif motion_type == "pan_right":
            scale = 1.10
            cx, cy = 0.42 + 0.16 * ease, 0.5
        else:  # pan_left
            scale = 1.10
            cx, cy = 0.58 - 0.16 * ease, 0.5

        crop_w = int(round(width / scale))
        crop_h = int(round(height / scale))
        x1 = int(round(cx * width - crop_w / 2))
        y1 = int(round(cy * height - crop_h / 2))
        x1 = max(0, min(width - crop_w, x1))
        y1 = max(0, min(height - crop_h, y1))

        cropped = base_frame[y1 : y1 + crop_h, x1 : x1 + crop_w]
        resized = Image.fromarray(cropped).resize((width, height), Image.Resampling.BILINEAR)
        return np.array(resized)

    bg_clip = ImageClip(base_frame).set_duration(duration).fl(lambda gf, t: make_frame(t), apply_to=[])
    bg_clip = bg_clip.set_fps(24)

    layers = [bg_clip]
    if caption.strip():
        overlay_arr = render_caption_overlay(width, height, caption, position=caption_pos)
        # Fade caption in smoothly over first 0.35s
        cap_clip = (
            ImageClip(overlay_arr, ismask=False)
            .set_duration(duration)
            .crossfadein(min(0.35, duration / 3))
        )
        layers.append(cap_clip)

    return CompositeVideoClip(layers, size=(width, height)).set_duration(duration)


def split_script_into_beats(script: str, num_scenes: int) -> List[str]:
    """Splits a script into sentences/beats aligned with the number of uploaded visuals."""
    sentences = [s.strip() for s in re.split(r"(?<=[.!?।])\s+|\n+", script.strip()) if s.strip()]
    if not sentences:
        return ["" for _ in range(num_scenes)]

    if len(sentences) == num_scenes:
        return sentences

    # Group sentences into `num_scenes` buckets
    buckets: List[List[str]] = [[] for _ in range(num_scenes)]
    for idx, sent in enumerate(sentences):
        bucket_idx = min(idx * num_scenes // len(sentences), num_scenes - 1)
        buckets[bucket_idx].append(sent)

    return [" ".join(b) for b in buckets]


def generate_voiceover(text: str, lang: str, out_path: str) -> Optional[str]:
    """Generates narration audio using gTTS if enabled."""
    clean = text.strip()
    if not clean:
        return None
    tts = gTTS(text=clean, lang=lang)
    tts.save(out_path)
    return out_path


def build_animated_video(
    image_paths: List[str],
    script: str = "",
    description: str = "",
    output_path: str = "creator_hub_output.mp4",
    resolution: Tuple[int, int] = (1280, 720),
    seconds_per_scene: float = 4.5,
    crossfade_dur: float = 0.6,
    enable_voiceover: bool = False,
    voice_lang: str = "kn",
) -> str:
    """Builds the final animated MP4 video from images, script, and creative description."""
    if not image_paths:
        raise ValueError("Please provide at least one image to animate.")

    width, height = resolution
    beats = split_script_into_beats(script if script.strip() else description, len(image_paths))
    motions = ["zoom_in", "pan_right", "zoom_out", "pan_left"]

    scene_clips: List[CompositeVideoClip] = []
    for idx, (img_path, beat) in enumerate(zip(image_paths, beats)):
        motion = motions[idx % len(motions)]
        clip = animate_scene(
            img_path=img_path,
            duration=seconds_per_scene,
            caption=beat,
            width=width,
            height=height,
            motion_type=motion,
            caption_pos="bottom",
        )
        if idx > 0 and crossfade_dur > 0:
            clip = clip.crossfadein(crossfade_dur)
        scene_clips.append(clip)

    final_video = concatenate_videoclips(scene_clips, method="compose", padding=-crossfade_dur if len(scene_clips) > 1 else 0)

    if enable_voiceover and script.strip():
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tmp_audio:
            audio_file = generate_voiceover(script, lang=voice_lang, out_path=tmp_audio.name)
            if audio_file and os.path.exists(audio_file):
                narration = AudioFileClip(audio_file)
                # Adjust video duration if narration is longer than planned visuals
                if narration.duration > final_video.duration:
                    final_video = final_video.set_duration(narration.duration + 0.4)
                final_video = final_video.set_audio(narration)

    final_video.write_videofile(
        output_path,
        fps=24,
        codec="libx264",
        audio_codec="aac",
        preset="medium",
        threads=4,
        logger=None,
    )
    return output_path
    
