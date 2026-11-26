import asyncio
import base64
import io
import os
import tempfile
import urllib.parse
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps
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

st.set_page_config(
    page_title="Creator Hub Studio — Kannada Edition",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- SESSION STATE ---
defaults = {
    "kannada_script": "",
    "subtitles_srt": "",
    "pulled_video_path": None,
    "scenes": [],
    "scene_captions": [],
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
    "kannada_overlay": "ಕನ್ನಡ ಕಂಟೆಂಟ್ ಸ್ಟುಡಿಯೋ",
    "collage_mode": "Single View",
    "bg_remove": False,
    "voice_enhance": True,
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


async def generate_kannada_tts_and_srt(text: str, voice: str, rate: str, pitch: str):
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
            dur_s = max(chunk["duration"] / 10_000_000, 0.35)
            word = chunk.get("text", "").strip()
            if word:
                srt_lines.append(f"{idx}\n{fmt_srt(start_s)} --> {fmt_srt(start_s + dur_s)}\n{word}\n")
                idx += 1

    srt_str = "\n".join(srt_lines) if srt_lines else f"1\n00:00:00,000 --> 00:00:05,000\n{text}\n"
    return audio_buf.getvalue(), srt_str


def generate_ai_character_image(prompt: str, style: str, api_key: str = "") -> Image.Image:
    """Calls Pollinations image API when key is provided; falls back to styled character art."""
    full_prompt = f"{style} character animation scene, expressive character, clean composition, {prompt}"
    if api_key.strip():
        try:
            encoded = urllib.parse.quote(full_prompt)
            url = f"https://gen.pollinations.ai/image/{encoded}?model=flux&width=768&height=1280&key={urllib.parse.quote(api_key.strip())}"
            resp = requests.get(url, timeout=25)
            if resp.status_code == 200 and resp.content:
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception:
            pass

    # Styled fallback character illustration (never a plain blue screen)
    w, h = 768, 1280
    img = Image.new("RGB", (w, h), (26, 22, 42))
    draw = ImageDraw.Draw(img)
    # Warm radial-like backdrop bands
    draw.ellipse([-120, 140, 888, 1140], fill=(45, 36, 72))
    draw.ellipse([80, 260, 688, 860], fill=(68, 48, 96))
    # Character silhouette + stylized head/shoulders
    draw.ellipse([284, 340, 484, 540], fill=(242, 196, 155))  # Head
    draw.pieslice([284, 325, 484, 455], start=180, end=360, fill=(35, 28, 46))  # Hair
    draw.ellipse([342, 425, 366, 449], fill=(28, 25, 35))  # Left eye
    draw.ellipse([402, 425, 426, 449], fill=(28, 25, 35))  # Right eye
    draw.arc([356, 460, 412, 495], start=15, end=165, fill=(185, 78, 78), width=4)  # Smile
    draw.rounded_rectangle([210, 550, 558, 940], radius=70, fill=(235, 130, 52))  # Outfit
    draw.text((70, 990), f"Style: {style}", fill=(255, 215, 100))
    draw.text((70, 1040), f"Prompt: {prompt[:58]}", fill=(235, 235, 245))
    draw.text((70, 1090), "Tip: Add Pollinations API key for live Flux character art", fill=(160, 215, 255))
    return img


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
    w, h = out.size
    if st.session_state.kannada_overlay.strip():
        draw.rectangle([40, h - 220, w - 40, h - 110], fill=(15, 15, 22))
        draw.text((70, h - 180), st.session_state.kannada_overlay.strip(), fill=(255, 220, 90))
    if st.session_state.sticker_text.strip():
        draw.text((w - 220, 70), st.session_state.sticker_text.strip(), fill=(255, 255, 255))
    return out


def render_video_player_html(video_bytes: bytes, start_sec: float, speed: float):
    b64_vid = base64.b64encode(video_bytes).decode("utf-8")
    html = f"""
    <div style="background:#111318;padding:12px;border-radius:10px;border:1px solid #2b303c;">
      <video id="studioVid" controls style="width:100%;max-height:420px;border-radius:8px;background:#000;">
        <source src="data:video/mp4;base64,{b64_vid}" type="video/mp4">
      </video>
      <div style="display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;align-items:center;color:#cfd6e4;font-family:sans-serif;font-size:13px;">
        <button onclick="const v=document.getElementById('studioVid');v.currentTime=Math.max(0,v.currentTime-5);">⏪ -5s</button>
        <button onclick="const v=document.getElementById('studioVid');v.paused?v.play():v.pause();">⏯️ Play/Pause</button>
        <button onclick="const v=document.getElementById('studioVid');v.currentTime=v.currentTime+5;">⏩ +5s</button>
        <span>Speed: {speed}x | Jump Target: {start_sec:.1f}s</span>
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
    components.html(html, height=495)


# ==============================================================================
# TOP: MEDIA PLAYER SCREEN (LIKE WINDOWS MEDIA PLAYER / VIDEO STUDIO MONITOR)
# ==============================================================================
st.markdown("## 🎬 Creator Hub Studio — Kannada Edition")

pollinations_key = ""
try:
    pollinations_key = st.secrets.get("POLLINATIONS_API_KEY", "")
except Exception:
    pollinations_key = os.getenv("POLLINATIONS_API_KEY", "")

with st.sidebar:
    st.markdown("### 🔑 Optional AI Image API")
    key_input = st.text_input("Pollinations API Key", value=pollinations_key, type="password")
    if key_input:
        pollinations_key = key_input

screen_col, side_col = st.columns([3, 1])

with screen_col:
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
        st.image(preview_img, caption="Live Scene Monitor (Generate or upload MP4 to use interactive scrubber)", use_container_width=True)
    else:
        st.markdown(
            """
            <div style="background:#111318;color:#d6dde8;height:280px;border-radius:10px;
                        display:flex;flex-direction:column;align-items:center;justify-content:center;
                        border:1px dashed #3b4254;">
              <div style="font-size:36px;">🎞️</div>
              <div style="font-size:16px;margin-top:8px;"><b>Studio Screen Ready</b></div>
              <div style="font-size:13px;opacity:0.8;margin-top:4px;">
                Create a character/scene, paste a video link, or upload a video below
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Quick timeline marker jump buttons (just like chapter/cut markers below a player)
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

with side_col:
    st.markdown("#### 🎙️ Kannada Voice & Subtitles")
    if st.session_state.generated_audio:
        st.audio(st.session_state.generated_audio, format="audio/mp3")
    if st.session_state.kannada_script:
        st.info(st.session_state.kannada_script)
    else:
        st.caption("No Kannada script generated yet.")

st.divider()

# ==============================================================================
# BELOW SCREEN: INSHOT-STYLE QUICK TOOLBAR + WORKSPACE TABS
# ==============================================================================
st.markdown("### 🎛️ InShot-Style Editing Bar")
b1, b2, b3, b4, b5 = st.columns(5)
if b1.button("✂️ Trim / Split"):
    st.session_state.tool_group = "Trim & Cut"
if b2.button("⚡ Speed / Ease"):
    st.session_state.tool_group = "Speed & Motion"
if b3.button("🎨 Filters / Rotate"):
    st.session_state.tool_group = "Filters & Look"
if b4.button("💬 Kannada / Sticker"):
    st.session_state.tool_group = "Kannada & Sticker"
if b5.button("🧩 Collage / Export"):
    st.session_state.tool_group = "Collage & Export"

group = st.session_state.tool_group
if group == "Trim & Cut":
    c1, c2, c3 = st.columns(3)
    st.session_state.trim_start = c1.number_input("Pre-Cut Start (s)", 0.0, 120.0, float(st.session_state.trim_start), 0.5)
    st.session_state.split_point = c2.number_input("Split Point (s)", 0.0, 120.0, float(st.session_state.split_point), 0.5)
    st.session_state.trim_end = c3.number_input("Trim End (s)", 1.0, 180.0, float(st.session_state.trim_end), 0.5)
elif group == "Speed & Motion":
    c1, c2, c3 = st.columns(3)
    st.session_state.speed = c1.select_slider("Playback / Clip Speed", [0.5, 0.75, 1.0, 1.25, 1.5, 2.0], value=st.session_state.speed)
    st.session_state.transition = c2.selectbox("Transition", ["Crossfade", "Slide", "Zoom", "Cut"])
    st.session_state.easing = c3.selectbox("Ease Curve", ["Linear", "Ease-In", "Ease-Out", "Ease-In-Out"])
elif group == "Filters & Look":
    c1, c2, c3, c4 = st.columns(4)
    st.session_state.filter_name = c1.selectbox("Filter", ["Original", "Vivid", "Warm", "Noir / B&W", "Soft Glow"])
    st.session_state.rotation = c2.selectbox("Rotate (°)", [0, 90, 180, 270])
    st.session_state.opacity = c3.slider("Opacity", 0.1, 1.0, float(st.session_state.opacity), 0.05)
    st.session_state.flip_h = c4.checkbox("Mirror Flip", value=st.session_state.flip_h)
elif group == "Kannada & Sticker":
    c1, c2 = st.columns(2)
    st.session_state.kannada_overlay = c1.text_input("ಕನ್ನಡ Subtitle / Caption Line", value=st.session_state.kannada_overlay)
    st.session_state.sticker_text = c2.text_input("Stickers / Emojis", value=st.session_state.sticker_text)
else:
    c1, c2 = st.columns(2)
    st.session_state.collage_mode = c1.selectbox("Collage Layout", ["Single View", "Side-by-Side (2)", "Grid (4)"])
    st.session_state.bg_remove = c2.checkbox("Clean Background / Cutout Mode", value=st.session_state.bg_remove)

st.divider()

# ==============================================================================
# WORKFLOW TABS (CREATE CHARACTERS, PULL LINK, DRAG & DROP, KANNADA TTS)
# ==============================================================================
t1, t2, t3, t4 = st.tabs([
    "🎭 AI Character & Animations",
    "📜 Kannada Script & Voice (TTS)",
    "🔗 Direct Link Pull & Upload",
    "📥 Exports (Script, SRT, MP3)",
])

with t1:
    st.subheader("Create Character & Animated Scenes from Short Prompts")
    p1, p2 = st.columns([2, 1])
    with p1:
        char_prompt = st.text_input(
            "Short Character / Scene Prompt",
            "young Kannada entrepreneur explaining smart savings with friendly smile",
        )
    with p2:
        char_style = st.selectbox("Character Style", ["3D Pixar Style", "Anime Story", "Flat Vector", "Comic Ink"])

    if st.button("✨ Generate Character Scene", type="primary"):
        with st.spinner("Creating character scene..."):
            scene_img = generate_ai_character_image(char_prompt, char_style, pollinations_key)
            st.session_state.scenes.append(scene_img)
            st.session_state.scene_captions.append(char_prompt)
            st.success("Character scene added to top monitor!")
            st.rerun()

    if st.session_state.scenes:
        cols = st.columns(min(4, len(st.session_state.scenes)))
        for idx, sc in enumerate(st.session_state.scenes[-4:]):
            with cols[idx]:
                st.image(sc, caption=f"Scene {idx + 1}", use_container_width=True)

with t2:
    st.subheader("30s Second-Income Reel / Story Script & Kannada Voiceover")
    idea = st.text_input("Topic (30-Second Reel / Wisdom Story)", "3 second-income habits in 30 seconds")
    if st.button("📝 Generate Kannada Script"):
        st.session_state.kannada_script = (
            f"ಕೇವಲ 30 ಸೆಕೆಂಡ್‌ಗಳಲ್ಲಿ '{idea}' ಬಗ್ಗೆ ಮುಖ್ಯ ಮಾಹಿತಿ! "
            f"ಮೊದಲನೆಯದಾಗಿ ನಿಮ್ಮ ಕೌಶಲ್ಯವನ್ನು ಗುರುತಿಸಿ, ಎರಡನೆಯದಾಗಿ ಸಣ್ಣ ಪ್ರಮಾಣದಲ್ಲಿ ಆರಂಭಿಸಿ, "
            f"ಮೂರನೆಯದಾಗಿ ಪ್ರತಿದಿನ ಮುಂದುವರಿಸಿ. ಕನ್ನಡ ಕಂಟೆಂಟ್‌ಗಾಗಿ ಸಬ್‌ಸ್ಕ್ರೈಬ್ ಮಾಡಿ!"
        )
        st.rerun()

    st.session_state.kannada_script = st.text_area(
        "ಕನ್ನಡ ಸ್ಕ್ರಿಪ್ಟ್ (Edit Kannada Script)",
        value=st.session_state.kannada_script,
        height=130,
    )

    v1, v2 = st.columns(2)
    kn_voice = v1.selectbox("Kannada Voice", ["kn-IN-SapnaNeural", "kn-IN-GaganNeural"])
    kn_rate = v2.slider("Speed (%)", -40, 40, 0)

    if st.button("🎙️ Generate Kannada Voice & SRT Subtitles"):
        if not HAS_EDGE_TTS:
            st.error("Add `edge-tts` to `requirements.txt`.")
        else:
            with st.spinner("Generating Kannada voiceover & subtitles..."):
                audio_data, srt_data = run_async(
                    generate_kannada_tts_and_srt(
                        st.session_state.kannada_script,
                        kn_voice,
                        f"{kn_rate:+d}%",
                        "+0Hz",
                    )
                )
                st.session_state.generated_audio = audio_data
                st.session_state.subtitles_srt = srt_data
                st.success("Kannada voiceover & subtitles ready!")
                st.rerun()

with t3:
    st.subheader("Pull from Direct Link (No Search) or Drag & Drop Media")
    url_in = st.text_input("Direct Video Link (YouTube / Instagram / Facebook)")
    if st.button("⬇️ Pull Video from Link"):
        if not HAS_YTDLP:
            st.error("Add `yt-dlp` to `requirements.txt`.")
        elif url_in.strip():
            with st.spinner("Downloading video from link..."):
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
                    st.success("Video loaded into top player!")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Link pull failed: {exc}")

    uploads = st.file_uploader(
        "Drag & drop your images or MP4 videos",
        type=["png", "jpg", "jpeg", "webp", "mp4", "mov"],
        accept_multiple_files=True,
    )
    if uploads:
        for f in uploads:
            if f.type.startswith("image/"):
                st.session_state.scenes.append(Image.open(f).convert("RGB"))
            elif f.type.startswith("video/"):
                st.session_state.final_video_bytes = f.getvalue()
        st.success(f"Loaded {len(uploads)} file(s).")
        st.rerun()

with t4:
    st.subheader("Download Kannada Script, Subtitles & Voiceover")
    d1, d2, d3 = st.columns(3)
    if st.session_state.kannada_script:
        d1.download_button(
            "⬇️ Kannada Script (.txt)",
            data=st.session_state.kannada_script.encode("utf-8"),
            file_name="kannada_script.txt",
        )
    if st.session_state.subtitles_srt:
        d2.download_button(
            "⬇️ Kannada Subtitles (.srt)",
            data=st.session_state.subtitles_srt.encode("utf-8"),
            file_name="kannada_subtitles.srt",
        )
    if st.session_state.generated_audio:
        d3.download_button(
            "⬇️ Kannada Voice (.mp3)",
            data=st.session_state.generated_audio,
            file_name="kannada_voice.mp3",
            mime="audio/mpeg",
        )
