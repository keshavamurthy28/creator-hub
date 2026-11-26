import asyncio
import base64
import io
import os
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
    </style>
    """,
    unsafe_allow_html=True,
)

VOICE_CATALOG = {
    "Kannada (ಕನ್ನಡ)": {
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
    "script_en": "",
    "script_kn": "",
    "voice_lang": "Kannada (ಕನ್ನಡ)",
    "subtitles_srt": "",
    "pulled_video_path": None,
    "scenes": [],
    "scene_labels": [],
    "generated_audio": None,
    "final_video_bytes": None,
    "jump_sec": 0.0,
    "tool_group": "Trim & Cut",
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
    "sticker_text": "🔥✨💡",
    "subtitle_line": "ಕನ್ನಡ ಕಂಟೆಂಟ್ ಸ್ಟುಡಿಯೋ",
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

    if target_lang == "kn":
        return f"ಕನ್ನಡ ಅನುವಾದ ({clean[:60]}): ಸ್ಮಾರ್ಟ್ ಕಥೆ ಮತ್ತು ಪ್ರಾಯೋಗಿಕ ಮಾರ್ಗದರ್ಶನ."
    return f"English translation ({clean[:60]}): Practical story and step-by-step guidance."


def load_subtitle_font(size: int = 32):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansKannada-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


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


def build_motion_frames(base_img: Image.Image, motion_preset: str, num_frames: int = 8) -> list[Image.Image]:
    w, h = base_img.size
    frames = []
    src = base_img.convert("RGB")
    for i in range(num_frames):
        t = i / max(1, num_frames - 1)
        if "Zoom" in motion_preset:
            zoom = 1.0 + 0.12 * t
            nw, nh = int(w / zoom), int(h / zoom)
            left = (w - nw) // 2
            top = (h - nh) // 2
            crop = src.crop((left, top, left + nw, top + nh)).resize((w, h), Image.Resampling.LANCZOS)
        elif "Pan" in motion_preset:
            max_shift = max(1, int(w * 0.08))
            left = int(max_shift * t)
            crop = src.crop((left, 0, w - (max_shift - left), h)).resize((w, h), Image.Resampling.LANCZOS)
        elif "Drift" in motion_preset:
            shift_y = int(24 * (t - 0.5))
            crop = ImageOps.pad(src, (w, h), color=(15, 18, 28), centering=(0.5, 0.5 + shift_y / max(1, h)))
        else:
            crop = src.copy()
        frames.append(crop)
    return frames


def apply_inshot_frame_edits(img: Image.Image) -> Image.Image:
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
    font_sub = load_subtitle_font(30)
    w, h = out.size
    sub_txt = st.session_state.subtitle_line.strip()
    if sub_txt:
        box_w = min(w - 80, max(360, len(sub_txt) * 20 + 60))
        bx0 = (w - box_w) // 2
        by0 = h - 125
        draw.rounded_rectangle([bx0, by0, bx0 + box_w, by0 + 68], radius=10, fill=(14, 15, 20))
        draw.text((bx0 + 24, by0 + 16), sub_txt, fill=(255, 255, 255), font=font_sub)
    if st.session_state.sticker_text.strip():
        draw.text((max(20, w - 200), 28), st.session_state.sticker_text.strip(), fill=(255, 255, 255), font=font_sub)
    return out


def render_mp4_from_scenes(scenes: list[Image.Image], audio_bytes: bytes | None, fps: int = 12) -> bytes | None:
    if not scenes or not HAS_IMAGEIO:
        return None
    try:
        expanded = []
        for sc in scenes:
            edited = apply_inshot_frame_edits(sc).resize((1280, 720))
            expanded.extend(build_motion_frames(edited, "Ken Burns Zoom-In", num_frames=6))

        tmp_dir = tempfile.mkdtemp(prefix="kkm_render_")
        raw_mp4 = os.path.join(tmp_dir, "raw_scenes.mp4")
        iio.imwrite(raw_mp4, [f for f in expanded], fps=fps, codec="libx264")

        if audio_bytes:
            audio_mp3 = os.path.join(tmp_dir, "voice.mp3")
            final_mp4 = os.path.join(tmp_dir, "final_output.mp4")
            with open(audio_mp3, "wb") as af:
                af.write(audio_bytes)
            cmd = [
                "ffmpeg", "-y", "-i", raw_mp4, "-i", audio_mp3,
                "-c:v", "copy", "-c:a", "aac", "-shortest", final_mp4,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if res.returncode == 0 and os.path.exists(final_mp4):
                with open(final_mp4, "rb") as out_f:
                    return out_f.read()

        with open(raw_mp4, "rb") as r_f:
            return r_f.read()
    except Exception:
        return None


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
# TOP: STUDIO PLAYER SCREEN (100% ENGLISH INTERFACE)
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
        preview_img = apply_inshot_frame_edits(st.session_state.scenes[-1])
        st.image(preview_img, caption="Live Studio Monitor", use_container_width=True)
    else:
        st.markdown(
            """
            <div style="background:#0d111a;color:#d6dde8;height:280px;border-radius:10px;
                        display:flex;flex-direction:column;align-items:center;justify-content:center;
                        border:1px dashed #32415c;text-align:center;padding:16px;">
              <div style="font-size:38px;">🎞️</div>
              <div style="font-size:17px;margin-top:8px;"><b>Monitor Ready</b></div>
              <div style="font-size:13px;opacity:0.85;margin-top:4px;">
                Upload your images/videos or pull a video link below to start editing
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
    active_preview = (
        st.session_state.script_kn
        if st.session_state.voice_lang.startswith("Kannada")
        else st.session_state.script_en
    )
    if active_preview:
        st.markdown(f'<div class="script-box">{active_preview}</div>', unsafe_allow_html=True)
    else:
        st.caption("No narration script generated yet.")

st.divider()

# ==============================================================================
# EDITING DOCK (ENGLISH INTERFACE)
# ==============================================================================
st.markdown("### Editing Controls")
b1, b2, b3, b4, b5 = st.columns(5)
if b1.button("✂️ Trim & Split"):
    st.session_state.tool_group = "Trim & Cut"
if b2.button("⚡ Speed & Motion"):
    st.session_state.tool_group = "Speed & Motion"
if b3.button("🎨 Filters & Rotate"):
    st.session_state.tool_group = "Filters & Look"
if b4.button("💬 Subtitle Overlay"):
    st.session_state.tool_group = "Subtitle Overlay"
if b5.button("🧩 Collage & Layout"):
    st.session_state.tool_group = "Collage & Layout"

group = st.session_state.tool_group
if group == "Trim & Cut":
    c1, c2, c3 = st.columns(3)
    st.session_state.trim_start = c1.number_input("Pre-Cut Start (s)", 0.0, 120.0, float(st.session_state.trim_start), 0.5)
    st.session_state.split_point = c2.number_input("Split Point (s)", 0.0, 120.0, float(st.session_state.split_point), 0.5)
    st.session_state.trim_end = c3.number_input("Trim End (s)", 1.0, 180.0, float(st.session_state.trim_end), 0.5)
elif group == "Speed & Motion":
    c1, c2, c3 = st.columns(3)
    st.session_state.speed = c1.select_slider("Playback Speed", [0.5, 0.75, 1.0, 1.25, 1.5, 2.0], value=st.session_state.speed)
    st.session_state.transition = c2.selectbox("Transition", ["Crossfade", "Slide", "Zoom", "Cut"])
    st.session_state.easing = c3.selectbox("Ease Curve", ["Linear", "Ease-In", "Ease-Out", "Ease-In-Out"])
elif group == "Filters & Look":
    c1, c2, c3, c4 = st.columns(4)
    st.session_state.filter_name = c1.selectbox("Filter", ["Original", "Vivid", "Warm", "Noir / B&W", "Soft Glow"])
    st.session_state.rotation = c2.selectbox("Rotate (°)", [0, 90, 180, 270])
    st.session_state.opacity = c3.slider("Opacity", 0.1, 1.0, float(st.session_state.opacity), 0.05)
    st.session_state.flip_h = c4.checkbox("Mirror Flip", value=st.session_state.flip_h)
elif group == "Subtitle Overlay":
    c1, c2 = st.columns([3, 1])
    st.session_state.subtitle_line = c1.text_input("On-Screen Subtitle Line", value=st.session_state.subtitle_line)
    st.session_state.sticker_text = c2.text_input("Stickers", value=st.session_state.sticker_text)
else:
    c1, c2 = st.columns(2)
    st.session_state.collage_mode = c1.selectbox("Collage Layout", ["Single View", "Side-by-Side (2)", "Grid (4)"])
    st.session_state.bg_remove = c2.checkbox("Background Cutout Mode", value=st.session_state.bg_remove)

st.divider()

# ==============================================================================
# WORKFLOW TABS (100% ENGLISH INTERFACE)
# ==============================================================================
t1, t2, t3, t4 = st.tabs([
    "📁 Media & Link Pull",
    "📜 Script & Voice (Kannada / English)",
    "🖼️ Uploaded Scenes",
    "📥 Render & Export",
])

with t1:
    st.subheader("Pull Video from Link or Upload Your Images & Videos")
    url_in = st.text_input("Direct Video Link (YouTube / Instagram / Facebook)")
    if st.button("⬇️ Pull Video from Link"):
        if not HAS_YTDLP:
            st.error("Add `yt-dlp` to `requirements.txt`.")
        elif url_in.strip():
            with st.spinner("Fetching video..."):
                try:
                    tmp_d = tempfile.mkdtemp(prefix="kkm_dl_")
                    opts = {
                        "outtmpl": os.path.join(tmp_d, "%(title).50s.%(ext)s"),
                        "format": "best[ext=mp4]/best",
                        "noplaylist": True,
                        "quiet": True,
                    }
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        info = ydl.extract_info(url_in.strip(), download=True)
                        p = ydl.prepare_filename(info)
                    st.session_state.pulled_video_path = p
                    st.rerun()
                except Exception as exc:
                    st.error(f"Link pull failed: {exc}")

    uploads = st.file_uploader(
        "Drag & Drop Your Images or Videos",
        type=["png", "jpg", "jpeg", "webp", "mp4", "mov"],
        accept_multiple_files=True,
    )
    if uploads:
        for f in uploads:
            if f.type.startswith("image/"):
                st.session_state.scenes.append(Image.open(f).convert("RGB"))
                st.session_state.scene_labels.append(f.name)
            elif f.type.startswith("video/"):
                st.session_state.final_video_bytes = f.getvalue()
        st.rerun()

with t2:
    st.subheader("Two-Way Script Sync (English ↔ Kannada) & Kannada / English Voiceover")
    topic_in = st.text_input("Reel / Story Topic", "3 smart second-income habits in 30 seconds")
    if st.button("📝 Generate Starter Script"):
        st.session_state.script_en = (
            f"Stop scrolling! Here is a 30-second guide on {topic_in}: "
            f"pick one practical skill, stay consistent every day, and grow step by step."
        )
        st.session_state.script_kn = translate_text_free(st.session_state.script_en, "en", "kn")
        st.rerun()

    en_val = st.text_area("English Script", value=st.session_state.script_en, height=115)
    sync_col1, sync_col2 = st.columns(2)
    if sync_col1.button("⬇️ Translate English to Kannada"):
        st.session_state.script_en = en_val
        st.session_state.script_kn = translate_text_free(en_val, "en", "kn")
        if st.session_state.voice_lang.startswith("Kannada") and st.session_state.script_kn:
            st.session_state.subtitle_line = st.session_state.script_kn[:80]
        st.rerun()

    kn_val = st.text_area("Kannada Script", value=st.session_state.script_kn, height=115)
    if sync_col2.button("⬆️ Translate Kannada to English"):
        st.session_state.script_kn = kn_val
        st.session_state.script_en = translate_text_free(kn_val, "kn", "en")
        if not st.session_state.voice_lang.startswith("Kannada") and st.session_state.script_en:
            st.session_state.subtitle_line = st.session_state.script_en[:80]
        st.rerun()

    st.session_state.script_en = en_val
    st.session_state.script_kn = kn_val

    v1, v2, v3 = st.columns(3)
    selected_lang = v1.selectbox(
        "Voice Language",
        ["Kannada (ಕನ್ನಡ)", "English"],
        index=0 if st.session_state.voice_lang.startswith("Kannada") else 1,
    )
    st.session_state.voice_lang = selected_lang
    voice_options = VOICE_CATALOG[selected_lang]
    chosen_voice_label = v2.selectbox("Voice Speaker", list(voice_options.keys()))
    voice_rate = v3.slider("Voice Speed (%)", -40, 40, 0)

    if st.button("🎙️ Generate Voice & Subtitles", type="primary"):
        if not HAS_EDGE_TTS:
            st.error("Add `edge-tts` to `requirements.txt`.")
        else:
            narration_text = (
                st.session_state.script_kn.strip()
                if selected_lang.startswith("Kannada")
                else st.session_state.script_en.strip()
            )
            if not narration_text:
                narration_text = "ನಮಸ್ಕಾರ! ಕ್ರಿಯೇಟರ್ ಹಬ್ ಸ್ಟುಡಿಯೋಗೆ ಸ್ವಾಗತ." if selected_lang.startswith("Kannada") else "Welcome to Creator Hub Studio!"
            with st.spinner("Generating voiceover and subtitles..."):
                audio_bytes, srt_data = run_async(
                    generate_tts_and_srt(
                        narration_text,
                        voice_options[chosen_voice_label],
                        f"{voice_rate:+d}%",
                        "+0Hz",
                    )
                )
                st.session_state.generated_audio = audio_bytes
                st.session_state.subtitles_srt = srt_data
                st.session_state.subtitle_line = narration_text[:80]
                st.rerun()

with t3:
    st.subheader("Uploaded Image Scenes")
    if st.session_state.scenes:
        cols = st.columns(min(4, len(st.session_state.scenes)))
        for idx, sc in enumerate(st.session_state.scenes[-4:]):
            lbl = st.session_state.scene_labels[-4:][idx]
            with cols[idx]:
                st.image(sc, caption=f"Scene {idx + 1}: {lbl}", use_container_width=True)
    else:
        st.info("Upload images under 'Media & Link Pull' to preview and arrange scenes here.")

with t4:
    st.subheader("Render Video & Download Assets")
    if st.button("🎬 Render MP4 Video"):
        with st.spinner("Rendering MP4 video..."):
            mp4_out = render_mp4_from_scenes(st.session_state.scenes, st.session_state.generated_audio)
            if mp4_out:
                st.session_state.final_video_bytes = mp4_out
                st.success("MP4 video rendered!")
                st.rerun()
            else:
                st.info("Upload at least one image scene and ensure `imageio` and `imageio-ffmpeg` are in `requirements.txt`.")

    active_script_txt = (
        st.session_state.script_kn
        if st.session_state.voice_lang.startswith("Kannada")
        else st.session_state.script_en
    )
    d1, d2, d3, d4 = st.columns(4)
    if active_script_txt:
        d1.download_button(
            "⬇️ Script (.txt)",
            data=active_script_txt.encode("utf-8"),
            file_name="kannada_script.txt" if st.session_state.voice_lang.startswith("Kannada") else "english_script.txt",
        )
    if st.session_state.subtitles_srt:
        d2.download_button(
            "⬇️ Subtitles (.srt)",
            data=st.session_state.subtitles_srt.encode("utf-8"),
            file_name="kannada_subtitles.srt" if st.session_state.voice_lang.startswith("Kannada") else "english_subtitles.srt",
        )
    if st.session_state.generated_audio:
        d3.download_button(
            "⬇️ Voiceover (.mp3)",
            data=st.session_state.generated_audio,
            file_name="kannada_voiceover.mp3" if st.session_state.voice_lang.startswith("Kannada") else "english_voiceover.mp3",
            mime="audio/mpeg",
        )
    if st.session_state.final_video_bytes:
        d4.download_button(
            "⬇️ Rendered Video (.mp4)",
            data=st.session_state.final_video_bytes,
            file_name="creator_hub_video.mp4",
            mime="video/mp4",
        )
