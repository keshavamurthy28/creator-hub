import asyncio
import base64
import io
import os
import re
import subprocess
import tempfile
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
import requests

try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False

try:
    import yt_dlp
    HAS_YTDLP = True
except ImportError:
    HAS_YTDLP = False

try:
    import imageio.v3 as iio
    HAS_IMAGEIO = True
except ImportError:
    HAS_IMAGEIO = False

st.set_page_config(
    page_title="Creator Hub Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
      .stApp {
        background-color: #0b0e14;
        color: #eef2f7;
      }
      .studio-monitor {
        background: linear-gradient(180deg, #131824 0%, #0e121b 100%);
        border: 1px solid #263042;
        border-radius: 14px;
        padding: 14px;
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.45);
      }
      .script-box {
        background: #121722;
        border: 1px solid #2b3850;
        border-radius: 10px;
        padding: 12px;
        color: #ffe082;
        font-size: 15px;
      }
      .scene-row {
        background: #121722;
        border: 1px solid #232d42;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 8px;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

VOICE_CATALOG = {
    "Kannada": {
        "Sapna (Female, India)": "kn-IN-SapnaNeural",
        "Gagan (Male, India)": "kn-IN-GaganNeural",
    },
    "English": {
        "Neerja (Female, India)": "en-IN-NeerjaNeural",
        "Prabhat (Male, India)": "en-IN-PrabhatNeural",
        "Aria (Female, US)": "en-US-AriaNeural",
        "Guy (Male, US)": "en-US-GuyNeural",
    },
}

# --- SESSION STATE ---
defaults = {
    "draft_input": "",
    "scene_items": [],
    "finalized_story": "",
    "script_en": "",
    "script_kn": "",
    "voice_lang": "Kannada",
    "subtitles_srt": "",
    "pulled_video_path": None,
    "scenes": [],
    "scene_labels": [],
    "generated_audio": None,
    "final_video_bytes": None,
    "jump_sec": 0.0,
    "anim_preset": "Ken Burns Zoom-In",
    "anim_frames": 10,
    "anim_fps": 12,
    "edit_mode": "Motion & Speed",
    "speed": 1.0,
    "trim_start": 0.0,
    "trim_end": 30.0,
    "split_point": 15.0,
    "opacity": 1.0,
    "rotation": 0,
    "flip_h": False,
    "filter_name": "Original",
    "transition": "Crossfade",
    "easing": "Ease-In-Out",
    "sticker_text": "✨🎬",
    "subtitle_line": "",
    "collage_mode": "Single View",
    "bg_remove": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            new_loop = asyncio.new_event_loop()
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def translate_text_free(text: str, source_lang: str, target_lang: str) -> str:
    clean = (text or "").strip()
    if not clean:
        return ""
    try:
        resp = requests.get(
            "https://api.mymemory.translated.net/get",
            params={"q": clean[:480], "langpair": f"{source_lang}|{target_lang}"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            translated = data.get("responseData", {}).get("translatedText", "")
            if translated and "MYMEMORY WARNING" not in translated.upper():
                return translated.strip()
    except Exception:
        pass
    return clean


def load_font(size: int = 30, prefer_kannada: bool = False):
    kn_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansKannada-Regular.otf",
    ]
    latin_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    ordered = (kn_paths + latin_paths) if prefer_kannada else (latin_paths + kn_paths)
    for path in ordered:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def has_kannada_font() -> bool:
    for path in (
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
    ):
        if os.path.exists(path):
            return True
    return False


def develop_scenes_from_draft(draft_text: str, target_scenes: int = 6) -> list[dict]:
    """Develops raw draft thoughts into structured scene writing entries up to target_scenes."""
    raw = (draft_text or "").strip()
    if not raw:
        raw = "A villager tends coconut palms and sugarcane in the morning and builds a peaceful life."

    raw_sentences = [
        s.strip(" .!?,;:-")
        for s in re.split(r"[.!?\n।]+", raw)
        if s.strip(" .!?,;:-")
    ]
    if not raw_sentences:
        raw_sentences = [raw]

    beats: list[str] = []
    for sent in raw_sentences:
        clauses = [
            c.strip()
            for c in re.split(r"\s+(?:and|then|while|with|but|ಮತ್ತು|ಹಾಗೂ|ನಂತರ)\s+", sent)
            if c.strip()
        ]
        if len(clauses) > 1 and len(beats) + len(clauses) <= target_scenes:
            beats.extend(clauses)
        else:
            beats.append(sent)

    progression = [
        "Opening scene setting the mood and location",
        "Main character introduced in action",
        "Key daily activity and hands-on effort",
        "Close-up visual detail of the environment",
        "Challenge or turning point in the moment",
        "Steady progress and determination",
        "Supporting detail or interaction",
        "Emotional shift and clarity",
        "Positive outcome taking shape",
        "Warm resolution and reflection",
        "Closing visual beat",
        "Final concluding frame",
    ]

    idx = 0
    while len(beats) < target_scenes:
        base = beats[idx % len(beats)]
        note = progression[len(beats) % len(progression)]
        beats.append(f"{base} — {note}")
        idx += 1

    beats = beats[:target_scenes]
    items = []
    for i, b in enumerate(beats):
        items.append({
            "scene_no": i + 1,
            "narration": b,
            "visual_prompt": f"Animated scene {i + 1}: {b}",
            "motion": st.session_state.anim_preset,
        })
    return items


def render_scene_frame(scene_info: dict, total_scenes: int) -> Image.Image:
    """Creates a clean animated scene frame without broken Kannada glyph boxes."""
    w, h = 1280, 720
    idx = max(0, int(scene_info.get("scene_no", 1)) - 1)
    palettes = [
        ((16, 32, 54), (92, 214, 168)),
        ((24, 42, 46), (255, 202, 98)),
        ((32, 26, 56), (132, 198, 255)),
        ((46, 33, 22), (255, 174, 96)),
    ]
    bg, accent = palettes[idx % len(palettes)]
    img = Image.new("RGB", (w, h), bg)
    draw = ImageDraw.Draw(img)
    font_title = load_font(34, prefer_kannada=False)
    font_body = load_font(28, prefer_kannada=False)

    draw.rounded_rectangle([32, 32, w - 32, h - 32], radius=18, outline=accent, width=3)
    draw.rectangle([52, 52, w - 52, 114], fill=(12, 16, 26))
    draw.text(
        (72, 68),
        f"SCENE {scene_info.get('scene_no', 1)} / {total_scenes}   •   MOTION: {scene_info.get('motion', 'Zoom')}",
        fill=accent,
        font=font_title,
    )

    desc = scene_info.get("visual_prompt") or scene_info.get("narration") or ""
    # Safe ASCII display on canvas so missing Kannada fonts never draw boxes
    safe_desc = desc.encode("ascii", "ignore").decode("ascii").strip()
    if not safe_desc:
        safe_desc = f"Scene {scene_info.get('scene_no', 1)} Story Frame"

    words = safe_desc.split()
    lines, cur = [], ""
    for word in words:
        test = f"{cur} {word}".strip()
        if len(test) <= 56:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)

    y = 195
    for line in lines[:5]:
        draw.rounded_rectangle([72, y - 6, w - 72, y + 42], radius=8, fill=(14, 20, 32))
        draw.text((90, y + 2), line, fill=(242, 246, 252), font=font_body)
        y += 58

    draw.text((72, h - 82), "Animated Frame Ready  |  Kannada & English Voice/Subtitles Supported", fill=(180, 198, 220), font=font_body)
    return img


def sync_storyboard_to_scenes(items: list[dict]):
    st.session_state.scene_items = items
    st.session_state.scenes = [render_scene_frame(it, len(items)) for it in items]
    st.session_state.scene_labels = [
        f"Scene {it['scene_no']}: {it['narration'][:36]}" for it in items
    ]
    story_lines = [f"Scene {it['scene_no']}: {it['narration']}" for it in items]
    st.session_state.finalized_story = "\n".join(story_lines)


def build_animated_frames(base_img: Image.Image, preset: str, num_frames: int = 10) -> list[Image.Image]:
    w, h = base_img.size
    frames = []
    src = base_img.convert("RGB")
    for i in range(max(2, num_frames)):
        t = i / max(1, num_frames - 1)
        if st.session_state.easing == "Ease-In":
            e = t * t
        elif st.session_state.easing == "Ease-Out":
            e = 1.0 - (1.0 - t) * (1.0 - t)
        elif st.session_state.easing == "Ease-In-Out":
            e = 3 * t * t - 2 * t * t * t
        else:
            e = t

        if "Zoom-In" in preset:
            zoom = 1.0 + 0.14 * e
            nw, nh = int(w / zoom), int(h / zoom)
            left = (w - nw) // 2
            top = (h - nh) // 2
            fr = src.crop((left, top, left + nw, top + nh)).resize((w, h), Image.Resampling.LANCZOS)
        elif "Zoom-Out" in preset:
            zoom = 1.14 - 0.14 * e
            nw, nh = int(w / zoom), int(h / zoom)
            left = (w - nw) // 2
            top = (h - nh) // 2
            fr = src.crop((left, top, left + nw, top + nh)).resize((w, h), Image.Resampling.LANCZOS)
        elif "Pan" in preset:
            shift_max = max(2, int(w * 0.08))
            left = int(shift_max * e)
            fr = src.crop((left, 0, w - (shift_max - left), h)).resize((w, h), Image.Resampling.LANCZOS)
        elif "Drift" in preset:
            dy = int(28 * (e - 0.5))
            fr = ImageOps.pad(src, (w, h), color=(14, 18, 28), centering=(0.5, 0.5 + dy / max(1, h)))
        elif "Pulse" in preset:
            factor = 1.0 + 0.18 * abs(e - 0.5) * 2.0
            fr = ImageEnhance.Brightness(src).enhance(factor)
        else:
            fr = src.copy()
        frames.append(fr)
    return frames


def apply_frame_edits(img: Image.Image) -> Image.Image:
    out = img.convert("RGB")
    if st.session_state.rotation:
        out = out.rotate(-st.session_state.rotation, expand=True)
    if st.session_state.flip_h:
        out = ImageOps.mirror(out)

    fname = st.session_state.filter_name
    if fname == "Vivid":
        out = ImageEnhance.Color(out).enhance(1.45)
        out = ImageEnhance.Contrast(out).enhance(1.15)
    elif fname == "Warm":
        r, g, b = out.split()
        r = r.point(lambda x: min(255, int(x * 1.12)))
        b = b.point(lambda x: max(0, int(x * 0.90)))
        out = Image.merge("RGB", (r, g, b))
    elif fname == "Noir / B&W":
        out = ImageOps.grayscale(out).convert("RGB")
    elif fname == "Soft Glow":
        blurred = out.filter(ImageFilter.GaussianBlur(radius=4))
        out = Image.blend(out, blurred, 0.35)

    if st.session_state.opacity < 1.0:
        dark_bg = Image.new("RGB", out.size, (12, 12, 16))
        out = Image.blend(dark_bg, out, st.session_state.opacity)

    draw = ImageDraw.Draw(out)
    w, h = out.size
    sub_txt = st.session_state.subtitle_line.strip()
    if sub_txt:
        if has_kannada_font() or sub_txt.isascii():
            font_sub = load_font(28, prefer_kannada=True)
            box_w = min(w - 80, max(360, len(sub_txt) * 18 + 60))
            bx0 = (w - box_w) // 2
            by0 = h - 120
            draw.rounded_rectangle([bx0, by0, bx0 + box_w, by0 + 64], radius=10, fill=(14, 15, 20))
            draw.text((bx0 + 22, by0 + 16), sub_txt[:75], fill=(255, 255, 255), font=font_sub)

    sticker_ascii = st.session_state.sticker_text.encode("ascii", "ignore").decode("ascii").strip()
    if sticker_ascii:
        draw.text((max(20, w - 180), 42), sticker_ascii, fill=(255, 230, 120), font=load_font(26, prefer_kannada=False))
    return out


async def generate_tts_and_srt(text: str, voice: str, rate: str, pitch: str):
    audio_buf = io.BytesIO()
    srt_lines = []
    idx = 1
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)

    def fmt_srt(sec: float) -> str:
        total_ms = max(0, int(round(sec * 1000)))
        h = total_ms // 3_600_000
        m = (total_ms % 3_600_000) // 60_000
        s = (total_ms % 60_000) // 1000
        ms = total_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buf.write(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            start_s = chunk["offset"] / 10_000_000
            dur_s = max(chunk["duration"] / 10_000_000, 0.4)
            token = chunk.get("text", "").strip()
            if token:
                srt_lines.append(f"{idx}\n{fmt_srt(start_s)} --> {fmt_srt(start_s + dur_s)}\n{token}\n")
                idx += 1

    srt_str = "\n".join(srt_lines) if srt_lines else f"1\n00:00:00,000 --> 00:00:05,000\n{text}\n"
    return audio_buf.getvalue(), srt_str


def render_final_mp4(scenes: list[Image.Image], audio_bytes: bytes | None) -> tuple[bytes | None, str]:
    if not scenes:
        return None, "Add or generate at least one scene first."
    if not HAS_IMAGEIO:
        return None, "`imageio` / `imageio-ffmpeg` is not available in this environment."
    try:
        all_frames = []
        for sc in scenes:
            edited = apply_frame_edits(sc).resize((1280, 720), Image.Resampling.LANCZOS)
            all_frames.extend(
                build_animated_frames(edited, st.session_state.anim_preset, num_frames=st.session_state.anim_frames)
            )
        if st.session_state.transition == "Crossfade" and len(all_frames) > 4:
            all_frames = all_frames[::1]  # Smooth sequence

        tmp_dir = tempfile.mkdtemp(prefix="kkm_studio_render_")
        raw_mp4 = os.path.join(tmp_dir, "raw_video.mp4")
        iio.imwrite(raw_mp4, all_frames, fps=st.session_state.anim_fps, codec="libx264")

        if audio_bytes:
            aud_path = os.path.join(tmp_dir, "voiceover.mp3")
            mux_mp4 = os.path.join(tmp_dir, "final_video.mp4")
            with open(aud_path, "wb") as af:
                af.write(audio_bytes)
            res = subprocess.run(
                ["ffmpeg", "-y", "-i", raw_mp4, "-i", aud_path, "-c:v", "copy", "-c:a", "aac", "-shortest", mux_mp4],
                capture_output=True,
                text=True,
                timeout=90,
            )
            if res.returncode == 0 and os.path.exists(mux_mp4):
                with open(mux_mp4, "rb") as out_f:
                    return out_f.read(), "Rendered MP4 with voiceover audio."

        with open(raw_mp4, "rb") as r_f:
            return r_f.read(), "Rendered MP4 video."
    except Exception as exc:
        return None, f"Render error: {exc}"


def render_video_player_html(video_bytes: bytes, start_sec: float, speed: float):
    b64_vid = base64.b64encode(video_bytes).decode("utf-8")
    html = f"""
    <div style="background:#0f141e;padding:12px;border-radius:12px;border:1px solid #283449;">
      <video id="studioVid" controls style="width:100%;max-height:430px;border-radius:8px;background:#000;">
        <source src="data:video/mp4;base64,{b64_vid}" type="video/mp4">
      </video>
      <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;align-items:center;color:#d6e0f0;font-family:sans-serif;font-size:13px;">
        <button onclick="const v=document.getElementById('studioVid');v.currentTime=Math.max(0,v.currentTime-5);">⏪ -5s</button>
        <button onclick="const v=document.getElementById('studioVid');v.paused?v.play():v.pause();">⏯️ Play / Pause</button>
        <button onclick="const v=document.getElementById('studioVid');v.currentTime=v.currentTime+5;">⏩ +5s</button>
        <span>Speed: {speed}x | Marker: {start_sec:.1f}s</span>
      </div>
    </div>
    <script>
      const vid = document.getElementById('studioVid');
      vid.addEventListener('loadedmetadata', () => {{
        vid.playbackRate = {speed};
        if ({start_sec} > 0 && {start_sec} < vid.duration) {{
          vid.currentTime = {start_sec};
        }}
      }});
    </script>
    """
    components.html(html, height=505)


# ==============================================================================
# TOP: STUDIO PLAYER SCREEN
# ==============================================================================
st.markdown("## 🎬 Creator Hub Studio")

screen_col, side_col = st.columns([3.1, 1.1])

with screen_col:
    st.markdown('<div class="studio-monitor">', unsafe_allow_html=True)
    if st.session_state.final_video_bytes:
        render_video_player_html(
            st.session_state.final_video_bytes,
            st.session_state.jump_sec,
            st.session_state.speed,
        )
    elif st.session_state.pulled_video_path and os.path.exists(st.session_state.pulled_video_path):
        with open(st.session_state.pulled_video_path, "rb") as vf:
            render_video_player_html(vf.read(), st.session_state.jump_sec, st.session_state.speed)
    elif st.session_state.scenes:
        preview_img = apply_frame_edits(st.session_state.scenes[-1])
        st.image(
            preview_img,
            caption=f"Live Scene Monitor ({len(st.session_state.scenes)} scene(s))",
            use_container_width=True,
        )
    else:
        st.markdown(
            """
            <div style="background:#0d111a;color:#d6dde8;height:280px;border-radius:10px;
                        display:flex;flex-direction:column;align-items:center;justify-content:center;
                        border:1px dashed #32415c;text-align:center;padding:16px;">
              <div style="font-size:38px;">🎞️</div>
              <div style="font-size:17px;margin-top:8px;"><b>Monitor Ready</b></div>
              <div style="font-size:13px;opacity:0.85;margin-top:4px;">
                Start in Script, Video, Voice, or Render tabs below
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    m1, m2, m3, m4 = st.columns(4)
    if m1.button("📍 0s Hook"):
        st.session_state.jump_sec = 0.0
        st.rerun()
    if m2.button("📍 5s Scene 1"):
        st.session_state.jump_sec = 5.0
        st.rerun()
    if m3.button("📍 15s Mid Cut"):
        st.session_state.jump_sec = 15.0
        st.rerun()
    if m4.button("📍 25s CTA"):
        st.session_state.jump_sec = 25.0
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

with side_col:
    st.markdown("#### Voiceover & Script")
    if st.session_state.generated_audio:
        st.audio(st.session_state.generated_audio, format="audio/mp3")
    active_script = (
        st.session_state.script_kn if st.session_state.voice_lang == "Kannada" else st.session_state.script_en
    )
    if active_script:
        st.markdown(f'<div class="script-box">{active_script}</div>', unsafe_allow_html=True)
    elif st.session_state.finalized_story:
        st.markdown(f'<div class="script-box">{st.session_state.finalized_story}</div>', unsafe_allow_html=True)
    else:
        st.caption("Develop and finalize your story in the Script tab.")

st.divider()

# ==============================================================================
# 4 CORE WORKFLOW TABS (SCRIPT • VIDEO • VOICE • RENDER & DOWNLOAD)
# ==============================================================================
tab_script, tab_video, tab_voice, tab_render = st.tabs([
    "1. Script & Story Builder",
    "2. Video & Animation Studio",
    "3. Voice & Subtitles",
    "4. Render & Download",
])

# --- TAB 1: SCRIPT TAB (DRAFT -> SCENE WRITING -> CORRECTION & FINALIZE) ---
with tab_script:
    st.subheader("Draft Story to Scene Writing & Finalization")
    st.session_state.draft_input = st.text_area(
        "Your Draft or Thinking (English or Kannada)",
        value=st.session_state.draft_input,
        height=110,
        placeholder="Write your raw idea or draft story here...",
    )

    sc_col1, sc_col2, sc_col3 = st.columns([2, 1, 1])
    desired_scenes = sc_col1.slider(
        "Number of Scenes",
        min_value=1,
        max_value=12,
        value=max(1, len(st.session_state.scene_items) if st.session_state.scene_items else 6),
    )
    if sc_col2.button("✍️ Develop Scenes", type="primary"):
        items = develop_scenes_from_draft(st.session_state.draft_input, target_scenes=desired_scenes)
        sync_storyboard_to_scenes(items)
        st.rerun()

    if sc_col3.button("➕ Add Scene"):
        current_items = list(st.session_state.scene_items)
        if not current_items:
            current_items = develop_scenes_from_draft(st.session_state.draft_input, target_scenes=1)
        else:
            next_num = len(current_items) + 1
            current_items.append({
                "scene_no": next_num,
                "narration": f"Scene {next_num} continuation from draft",
                "visual_prompt": f"Animated scene {next_num}: {st.session_state.draft_input[:60]}",
                "motion": st.session_state.anim_preset,
            })
        sync_storyboard_to_scenes(current_items)
        st.rerun()

    if st.session_state.scene_items:
        st.markdown("#### Scene-by-Scene Writing & Corrections")
        updated_items = []
        for idx, item in enumerate(st.session_state.scene_items):
            st.markdown('<div class="scene-row">', unsafe_allow_html=True)
            r1, r2 = st.columns([2, 2])
            new_narr = r1.text_input(
                f"Scene {idx + 1} Story / Narration",
                value=item["narration"],
                key=f"sc_narr_{idx}",
            )
            new_vis = r2.text_input(
                f"Scene {idx + 1} Animation / Visual Description",
                value=item["visual_prompt"],
                key=f"sc_vis_{idx}",
            )
            updated_items.append({
                "scene_no": idx + 1,
                "narration": new_narr,
                "visual_prompt": new_vis,
                "motion": item.get("motion", st.session_state.anim_preset),
            })
            st.markdown("</div>", unsafe_allow_html=True)

        if st.button("✅ Save Corrections & Finalize Story", type="primary"):
            sync_storyboard_to_scenes(updated_items)
            st.session_state.script_en = st.session_state.finalized_story
            st.session_state.script_kn = translate_text_free(st.session_state.finalized_story, "en", "kn")
            st.success("Story finalized and synced to scenes and scripts.")
            st.rerun()

    st.divider()
    st.markdown("#### Finalized Story & Two-Way Translation (English ↔ Kannada)")
    f_col1, f_col2 = st.columns(2)
    st.session_state.script_en = f_col1.text_area("English Story Script", value=st.session_state.script_en, height=120)
    st.session_state.script_kn = f_col2.text_area("Kannada Story Script", value=st.session_state.script_kn, height=120)

    t_b1, t_b2 = st.columns(2)
    if t_b1.button("⬇️ Sync English → Kannada"):
        st.session_state.script_kn = translate_text_free(st.session_state.script_en, "en", "kn")
        st.rerun()
    if t_b2.button("⬆️ Sync Kannada → English"):
        st.session_state.script_en = translate_text_free(st.session_state.script_kn, "kn", "en")
        st.rerun()

# --- TAB 2: VIDEO & ANIMATION TAB (UPLOAD, URL, ANIMATED DESCRIPTION + TAB EDITS) ---
with tab_video:
    st.subheader("Source Media & Animation Creator")
    v_in1, v_in2 = st.columns(2)

    with v_in1:
        st.markdown("##### Pull Video from URL")
        url_in = st.text_input("Direct Video URL", placeholder="https://...")
        if st.button("⬇️ Fetch Video URL"):
            if not HAS_YTDLP:
                st.error("Add `yt-dlp` to `requirements.txt`.")
            elif url_in.strip():
                with st.spinner("Fetching video..."):
                    try:
                        tmp_d = tempfile.mkdtemp(prefix="kkm_vid_")
                        opts = {
                            "outtmpl": os.path.join(tmp_d, "%(title).50s.%(ext)s"),
                            "format": "best[ext=mp4]/best",
                            "noplaylist": True,
                            "quiet": True,
                        }
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info = ydl.extract_info(url_in.strip(), download=True)
                            st.session_state.pulled_video_path = ydl.prepare_filename(info)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Could not fetch URL: {exc}")

    with v_in2:
        st.markdown("##### Upload Images or Videos")
        media_files = st.file_uploader(
            "Drag & Drop Images or Videos",
            type=["png", "jpg", "jpeg", "webp", "mp4", "mov"],
            accept_multiple_files=True,
            key="tab2_media_upload",
        )
        if media_files:
            for f in media_files:
                if f.type.startswith("image/"):
                    img_obj = Image.open(f).convert("RGB")
                    st.session_state.scenes.append(img_obj)
                    st.session_state.scene_labels.append(f.name)
                elif f.type.startswith("video/"):
                    st.session_state.final_video_bytes = f.getvalue()
            st.rerun()

    st.divider()
    st.markdown("##### Create Animated Scene from Description")
    a_col1, a_col2, a_col3 = st.columns([2, 1, 1])
    anim_desc = a_col1.text_input(
        "Animated Image / Video Description",
        value=st.session_state.scene_items[0]["visual_prompt"] if st.session_state.scene_items else "Animated scene with smooth camera movement",
    )
    st.session_state.anim_preset = a_col2.selectbox(
        "Animation Style",
        ["Ken Burns Zoom-In", "Ken Burns Pan-Right", "Parallax Drift", "Ken Burns Zoom-Out", "Pulse", "Static"],
    )
    st.session_state.anim_frames = a_col3.slider("Animation Frames per Scene", 4, 24, int(st.session_state.anim_frames))

    if st.button("🎞️ Create Animated Scene", type="primary"):
        next_no = len(st.session_state.scenes) + 1
        new_entry = {"scene_no": next_no, "narration": anim_desc, "visual_prompt": anim_desc, "motion": st.session_state.anim_preset}
        frame_img = render_scene_frame(new_entry, max(next_no, len(st.session_state.scene_items) or 1))
        st.session_state.scenes.append(frame_img)
        st.session_state.scene_labels.append(f"Anim {next_no}: {anim_desc[:32]}")
        st.rerun()

    st.divider()
    st.markdown("##### Video & Animation Editing Tools")
    em1, em2, em3, em4 = st.columns(4)
    if em1.button("⚡ Motion & Speed"):
        st.session_state.edit_mode = "Motion & Speed"
    if em2.button("✂️ Trim & Split"):
        st.session_state.edit_mode = "Trim & Split"
    if em3.button("🎨 Filters & Transform"):
        st.session_state.edit_mode = "Filters & Transform"
    if em4.button("💬 Overlays & Collage"):
        st.session_state.edit_mode = "Overlays & Collage"

    if st.session_state.edit_mode == "Motion & Speed":
        ec1, ec2, ec3 = st.columns(3)
        st.session_state.speed = ec1.select_slider("Playback Speed", [0.5, 0.75, 1.0, 1.25, 1.5, 2.0], value=st.session_state.speed)
        st.session_state.easing = ec2.selectbox("Animation Easing", ["Ease-In-Out", "Ease-In", "Ease-Out", "Linear"])
        st.session_state.transition = ec3.selectbox("Scene Transition", ["Crossfade", "Slide", "Zoom", "Cut"])
    elif st.session_state.edit_mode == "Trim & Split":
        ec1, ec2, ec3 = st.columns(3)
        st.session_state.trim_start = ec1.number_input("Start (s)", 0.0, 180.0, float(st.session_state.trim_start), 0.5)
        st.session_state.split_point = ec2.number_input("Split (s)", 0.0, 180.0, float(st.session_state.split_point), 0.5)
        st.session_state.trim_end = ec3.number_input("End (s)", 1.0, 240.0, float(st.session_state.trim_end), 0.5)
    elif st.session_state.edit_mode == "Filters & Transform":
        ec1, ec2, ec3, ec4 = st.columns(4)
        st.session_state.filter_name = ec1.selectbox("Filter", ["Original", "Vivid", "Warm", "Noir / B&W", "Soft Glow"])
        st.session_state.rotation = ec2.selectbox("Rotate (°)", [0, 90, 180, 270])
        st.session_state.opacity = ec3.slider("Opacity", 0.1, 1.0, float(st.session_state.opacity), 0.05)
        st.session_state.flip_h = ec4.checkbox("Mirror Flip", value=st.session_state.flip_h)
    else:
        ec1, ec2, ec3 = st.columns(3)
        st.session_state.subtitle_line = ec1.text_input("Subtitle Overlay Text", value=st.session_state.subtitle_line)
        st.session_state.sticker_text = ec2.text_input("Badge / Sticker", value=st.session_state.sticker_text)
        st.session_state.collage_mode = ec3.selectbox("Layout", ["Single View", "Side-by-Side (2)", "Grid (4)"])

    if st.session_state.scenes:
        st.markdown("##### Scene Strip")
        strip_cols = st.columns(min(4, len(st.session_state.scenes)))
        for idx, sc in enumerate(st.session_state.scenes[-4:]):
            lbl = st.session_state.scene_labels[-4:][idx]
            with strip_cols[idx]:
                st.image(apply_frame_edits(sc), caption=lbl, use_container_width=True)

# --- TAB 3: VOICE TAB (UPLOAD, BUILT-IN KANNADA/ENGLISH, FROM URL) ---
with tab_voice:
    st.subheader("Voiceover & Subtitles (Built-In Kannada / English, Upload, or URL)")
    v_src1, v_src2 = st.columns(2)

    with v_src1:
        st.markdown("##### Upload Voiceover Audio")
        up_audio = st.file_uploader("Upload MP3 / WAV Audio", type=["mp3", "wav", "m4a", "ogg"], key="tab3_audio_up")
        if up_audio is not None:
            st.session_state.generated_audio = up_audio.getvalue()
            st.success("Uploaded audio loaded for playback and rendering.")

    with v_src2:
        st.markdown("##### Pull Audio from URL")
        aud_url = st.text_input("Direct Audio / Media URL", placeholder="https://...")
        if st.button("⬇️ Fetch Audio URL"):
            if not HAS_YTDLP:
                st.error("Add `yt-dlp` to `requirements.txt`.")
            elif aud_url.strip():
                with st.spinner("Fetching audio..."):
                    try:
                        tmp_d = tempfile.mkdtemp(prefix="kkm_aud_")
                        opts = {
                            "outtmpl": os.path.join(tmp_d, "audio.%(ext)s"),
                            "format": "bestaudio/best",
                            "noplaylist": True,
                            "quiet": True,
                        }
                        with yt_dlp.YoutubeDL(opts) as ydl:
                            info = ydl.extract_info(aud_url.strip(), download=True)
                            dl_path = ydl.prepare_filename(info)
                        with open(dl_path, "rb") as af:
                            st.session_state.generated_audio = af.read()
                        st.success("Audio pulled from URL.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Audio URL pull failed: {exc}")

    st.divider()
    st.markdown("##### Built-In Neural Voice Generator (Kannada & English)")
    vc1, vc2, vc3 = st.columns(3)
    chosen_lang = vc1.selectbox(
        "Voice Language",
        ["Kannada", "English"],
        index=0 if st.session_state.voice_lang == "Kannada" else 1,
    )
    st.session_state.voice_lang = chosen_lang
    speakers = VOICE_CATALOG[chosen_lang]
    chosen_speaker = vc2.selectbox("Voice Speaker", list(speakers.keys()))
    v_rate = vc3.slider("Speaking Rate (%)", -40, 40, 0)

    default_tts_text = (
        st.session_state.script_kn.strip()
        if chosen_lang == "Kannada"
        else st.session_state.script_en.strip()
    )
    tts_text = st.text_area("Narration Text for Voice & Subtitles", value=default_tts_text, height=115)

    if st.button("🎙️ Generate Voice & Subtitles", type="primary"):
        if not HAS_EDGE_TTS:
            st.error("Add `edge-tts` to `requirements.txt`.")
        else:
            clean_tts = tts_text.strip() or (
                "ನಮಸ್ಕಾರ! ಕ್ರಿಯೇಟರ್ ಹಬ್ ಸ್ಟುಡಿಯೋಗೆ ಸ್ವಾಗತ." if chosen_lang == "Kannada" else "Welcome to Creator Hub Studio."
            )
            with st.spinner("Generating voiceover and subtitles..."):
                audio_bytes, srt_out = run_async(
                    generate_tts_and_srt(
                        clean_tts,
                        speakers[chosen_speaker],
                        f"{v_rate:+d}%",
                        "+0Hz",
                    )
                )
                st.session_state.generated_audio = audio_bytes
                st.session_state.subtitles_srt = srt_out
                if chosen_lang == "Kannada":
                    st.session_state.script_kn = clean_tts
                else:
                    st.session_state.script_en = clean_tts
                st.session_state.subtitle_line = clean_tts[:80]
                st.rerun()

    if st.session_state.generated_audio:
        st.audio(st.session_state.generated_audio, format="audio/mp3")
    if st.session_state.subtitles_srt:
        st.text_area("Generated Subtitles (SRT)", value=st.session_state.subtitles_srt, height=130)

# --- TAB 4: RENDER & DOWNLOAD TAB ---
with tab_render:
    st.subheader("Render Final Video & Download Assets")
    rc1, rc2 = st.columns(2)
    st.session_state.anim_fps = rc1.select_slider("Export FPS", options=[12, 24, 30], value=int(st.session_state.anim_fps))
    st.session_state.transition = rc2.selectbox(
        "Export Transition Mode",
        ["Crossfade", "Slide", "Zoom", "Cut"],
        index=["Crossfade", "Slide", "Zoom", "Cut"].index(st.session_state.transition),
    )

    if st.button("🎬 Render MP4 Video", type="primary"):
        with st.spinner("Rendering MP4 video..."):
            mp4_bytes, render_msg = render_final_mp4(st.session_state.scenes, st.session_state.generated_audio)
            if mp4_bytes:
                st.session_state.final_video_bytes = mp4_bytes
                st.success(render_msg)
                st.rerun()
            else:
                st.warning(render_msg)

    st.divider()
    dl1, dl2, dl3, dl4 = st.columns(4)
    script_export = (
        st.session_state.script_kn
        if st.session_state.voice_lang == "Kannada"
        else (st.session_state.script_en or st.session_state.finalized_story)
    )
    if script_export:
        dl1.download_button(
            "⬇️ Download Script (.txt)",
            data=script_export.encode("utf-8"),
            file_name="kannada_script.txt" if st.session_state.voice_lang == "Kannada" else "english_script.txt",
        )
    if st.session_state.subtitles_srt:
        dl2.download_button(
            "⬇️ Download Subtitles (.srt)",
            data=st.session_state.subtitles_srt.encode("utf-8"),
            file_name="kannada_subtitles.srt" if st.session_state.voice_lang == "Kannada" else "english_subtitles.srt",
        )
    if st.session_state.generated_audio:
        dl3.download_button(
            "⬇️ Download Voiceover (.mp3)",
            data=st.session_state.generated_audio,
            file_name="voiceover.mp3",
            mime="audio/mpeg",
        )
    if st.session_state.final_video_bytes:
        dl4.download_button(
            "⬇️ Download Video (.mp4)",
            data=st.session_state.final_video_bytes,
            file_name="creator_hub_video.mp4",
            mime="video/mp4",
        )
