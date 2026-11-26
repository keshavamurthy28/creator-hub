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
    page_title="Creator Hub Studio — English & ಕನ್ನಡ",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- SESSION STATE ---
defaults = {
    "script_en": "",
    "script_kn": "",
    "subtitles_bilingual": "",
    "pulled_video_path": None,
    "scenes": [],
    "scene_labels": [],
    "generated_audio": None,
    "final_video_bytes": None,
    "jump_sec": 0.0,
    "tool_group": "Trim & Cut / ಕತ್ತರಿಸಿ",
    "speed": 1.0,
    "trim_start": 0.0,
    "trim_end": 30.0,
    "split_point": 15.0,
    "opacity": 1.0,
    "rotation": 0,
    "flip_h": False,
    "filter_name": "Original / ಮೂಲ",
    "transition": "Crossfade / ಮಿಶ್ರಣ",
    "easing": "Ease-In-Out / ಮೃದು",
    "sticker_text": "🔥✨💡",
    "overlay_en": "Smart Creator Studio",
    "overlay_kn": "ಸ್ಮಾರ್ಟ್ ಕ್ರಿಯೇಟರ್ ಸ್ಟುಡಿಯೋ",
    "collage_mode": "Single View / ಏಕ ದೃಶ್ಯ",
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


async def generate_kannada_tts_and_bilingual_srt(
    kn_text: str, en_text: str, voice: str, rate: str, pitch: str
):
    audio_buf = io.BytesIO()
    srt_lines = []
    idx = 1
    communicate = edge_tts.Communicate(text=kn_text, voice=voice, rate=rate, pitch=pitch)

    def fmt_srt(sec: float) -> str:
        total_ms = max(0, int(round(sec * 1000)))
        h = total_ms // 3_600_000
        m = (total_ms % 3_600_000) // 60_000
        s = (total_ms % 60_000) // 1000
        ms = total_ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    en_preview = (en_text or "").strip()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buf.write(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            start_s = chunk["offset"] / 10_000_000
            dur_s = max(chunk["duration"] / 10_000_000, 0.35)
            word_kn = chunk.get("text", "").strip()
            if word_kn:
                sub_line = f"{word_kn} | {en_preview[:45]}" if en_preview else word_kn
                srt_lines.append(f"{idx}\n{fmt_srt(start_s)} --> {fmt_srt(start_s + dur_s)}\n{sub_line}\n")
                idx += 1

    if not srt_lines:
        fallback_line = f"{kn_text} | {en_preview}" if en_preview else kn_text
        srt_str = f"1\n00:00:00,000 --> 00:00:05,000\n{fallback_line}\n"
    else:
        srt_str = "\n".join(srt_lines)
    return audio_buf.getvalue(), srt_str


def generate_ai_character_image(prompt_en: str, prompt_kn: str, style: str, api_key: str = "") -> Image.Image:
    combined_prompt = f"{style} character animation scene, expressive character, clean composition, {prompt_en} {prompt_kn}".strip()
    if api_key.strip():
        try:
            encoded = urllib.parse.quote(combined_prompt)
            url = f"https://gen.pollinations.ai/image/{encoded}?model=flux&width=768&height=1280&key={urllib.parse.quote(api_key.strip())}"
            resp = requests.get(url, timeout=25)
            if resp.status_code == 200 and resp.content:
                return Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception:
            pass

    w, h = 768, 1280
    img = Image.new("RGB", (w, h), (24, 21, 40))
    draw = ImageDraw.Draw(img)
    draw.ellipse([-120, 140, 888, 1140], fill=(44, 35, 70))
    draw.ellipse([80, 260, 688, 860], fill=(68, 48, 96))
    draw.ellipse([284, 340, 484, 540], fill=(242, 196, 155))
    draw.pieslice([284, 325, 484, 455], start=180, end=360, fill=(35, 28, 46))
    draw.ellipse([342, 425, 366, 449], fill=(28, 25, 35))
    draw.ellipse([402, 425, 426, 449], fill=(28, 25, 35))
    draw.arc([356, 460, 412, 495], start=15, end=165, fill=(185, 78, 78), width=4)
    draw.rounded_rectangle([210, 550, 558, 940], radius=70, fill=(235, 130, 52))
    draw.text((60, 980), f"Style / ಶೈಲಿ: {style}", fill=(255, 215, 100))
    draw.text((60, 1025), f"EN: {prompt_en[:58]}", fill=(235, 240, 250))
    draw.text((60, 1070), f"KN: {prompt_kn[:58]}", fill=(165, 230, 200))
    return img


def apply_inshot_frame_edits(img: Image.Image) -> Image.Image:
    out = img.convert("RGB")
    if st.session_state.rotation:
        out = out.rotate(-st.session_state.rotation, expand=True)
    if st.session_state.flip_h:
        out = ImageOps.mirror(out)

    fname = st.session_state.filter_name
    if "Vivid" in fname:
        out = ImageEnhance.Color(out).enhance(1.45)
        out = ImageEnhance.Contrast(out).enhance(1.15)
    elif "Warm" in fname:
        r, g, b = out.split()
        r = r.point(lambda x: min(255, int(x * 1.12)))
        b = b.point(lambda x: max(0, int(x * 0.90)))
        out = Image.merge("RGB", (r, g, b))
    elif "Noir" in fname:
        out = ImageOps.grayscale(out).convert("RGB")
    elif "Soft Glow" in fname:
        blurred = out.filter(ImageFilter.GaussianBlur(radius=4))
        out = Image.blend(out, blurred, 0.35)

    if st.session_state.opacity < 1.0:
        dark_bg = Image.new("RGB", out.size, (12, 12, 16))
        out = Image.blend(dark_bg, out, st.session_state.opacity)

    draw = ImageDraw.Draw(out)
    w, h = out.size
    kn_line = st.session_state.overlay_kn.strip()
    en_line = st.session_state.overlay_en.strip()
    if kn_line or en_line:
        draw.rectangle([36, h - 250, w - 36, h - 105], fill=(14, 14, 22))
        if kn_line:
            draw.text((65, h - 220), f"ಕನ್ನಡ: {kn_line}", fill=(255, 220, 90))
        if en_line:
            draw.text((65, h - 170), f"EN: {en_line}", fill=(170, 225, 255))
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
        <button onclick="const v=document.getElementById('studioVid');v.currentTime=Math.max(0,v.currentTime-5);">⏪ -5s / ಹಿಂದಕ್ಕೆ</button>
        <button onclick="const v=document.getElementById('studioVid');v.paused?v.play():v.pause();">⏯️ Play/Pause / ಪ್ಲೇ</button>
        <button onclick="const v=document.getElementById('studioVid');v.currentTime=v.currentTime+5;">⏩ +5s / ಮುಂದಕ್ಕೆ</button>
        <span>Speed / ವೇಗ: {speed}x | Jump / ಜಂಪ್: {start_sec:.1f}s</span>
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
# TOP: MEDIA PLAYER SCREEN (ENGLISH + ಕನ್ನಡ)
# ==============================================================================
st.markdown("## 🎬 Creator Hub Studio — English & ಕನ್ನಡ / ಇಂಗ್ಲಿಷ್ ಮತ್ತು ಕನ್ನಡ ಸ್ಟುಡಿಯೋ")

pollinations_key = ""
try:
    pollinations_key = st.secrets.get("POLLINATIONS_API_KEY", "")
except Exception:
    pollinations_key = os.getenv("POLLINATIONS_API_KEY", "")

with st.sidebar:
    st.markdown("### 🔑 Optional AI Image API / ಐಚ್ಛಿಕ API ಕೀ")
    key_input = st.text_input("Pollinations API Key / API ಕೀ", value=pollinations_key, type="password")
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
        st.image(
            preview_img,
            caption="Live Scene Monitor / ಲೈವ್ ದೃಶ್ಯ ಮಾನಿಟರ್",
            use_container_width=True,
        )
    else:
        st.markdown(
            """
            <div style="background:#111318;color:#d6dde8;height:280px;border-radius:10px;
                        display:flex;flex-direction:column;align-items:center;justify-content:center;
                        border:1px dashed #3b4254;text-align:center;padding:16px;">
              <div style="font-size:36px;">🎞️</div>
              <div style="font-size:16px;margin-top:8px;"><b>Studio Screen Ready / ಸ್ಟುಡಿಯೋ ಸ್ಕ್ರೀನ್ ಸಿದ್ಧವಾಗಿದೆ</b></div>
              <div style="font-size:13px;opacity:0.85;margin-top:4px;">
                Create a character, paste a link, or upload media below • ಕೆಳಗೆ ಕ್ಯಾರೆಕ್ಟರ್ ರಚಿಸಿ, ಲಿಂಕ್ ಹಾಕಿ ಅಥವಾ ವಿಡಿಯೋ ಅಪ್‌ಲೋಡ್ ಮಾಡಿ
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    m1, m2, m3, m4 = st.columns(4)
    if m1.button("📍 0s Hook / ಆರಂಭ"):
        st.session_state.jump_sec = 0.0
        st.rerun()
    if m2.button("📍 5s Scene 1 / ದೃಶ್ಯ 1"):
        st.session_state.jump_sec = 5.0
        st.rerun()
    if m3.button("📍 15s Mid Cut / ಮಧ್ಯ"):
        st.session_state.jump_sec = 15.0
        st.rerun()
    if m4.button("📍 25s CTA / ಮುಕ್ತಾಯ"):
        st.session_state.jump_sec = 25.0
        st.rerun()

with side_col:
    st.markdown("#### 🎙️ Voice & Subtitles / ಧ್ವನಿ ಮತ್ತು ಉಪಶೀರ್ಷಿಕೆ")
    if st.session_state.generated_audio:
        st.audio(st.session_state.generated_audio, format="audio/mp3")
    if st.session_state.script_kn or st.session_state.script_en:
        if st.session_state.script_kn:
            st.success(f"**ಕನ್ನಡ:** {st.session_state.script_kn}")
        if st.session_state.script_en:
            st.info(f"**English:** {st.session_state.script_en}")
    else:
        st.caption("No script generated yet / ಇನ್ನೂ ಸ್ಕ್ರಿಪ್ಟ್ ರಚಿಸಲಾಗಿಲ್ಲ.")

st.divider()

# ==============================================================================
# INSHOT-STYLE EDITING BAR (ENGLISH + ಕನ್ನಡ)
# ==============================================================================
st.markdown("### 🎛️ InShot-Style Editing Bar / ಎಡಿಟಿಂಗ್ ಟೂಲ್‌ಬಾರ್")
b1, b2, b3, b4, b5 = st.columns(5)
if b1.button("✂️ Trim / Split • ಕತ್ತರಿಸಿ"):
    st.session_state.tool_group = "Trim & Cut / ಕತ್ತರಿಸಿ"
if b2.button("⚡ Speed / Ease • ವೇಗ"):
    st.session_state.tool_group = "Speed & Motion / ವೇಗ ಮತ್ತು ಚಲನೆ"
if b3.button("🎨 Filters / Rotate • ಬಣ್ಣ/ತಿರುಗಿಸಿ"):
    st.session_state.tool_group = "Filters & Look / ಫಿಲ್ಟರ್ ಮತ್ತು ನೋಟ"
if b4.button("💬 Text / Sticker • ಅಕ್ಷರ/ಸ್ಟಿಕರ್"):
    st.session_state.tool_group = "Text & Sticker / ಅಕ್ಷರ ಮತ್ತು ಸ್ಟಿಕರ್"
if b5.button("🧩 Collage / Export • ಕೊಲಾಜ್"):
    st.session_state.tool_group = "Collage & Export / ಕೊಲಾಜ್ ಮತ್ತು ರಫ್ತು"

group = st.session_state.tool_group
if "Trim" in group:
    c1, c2, c3 = st.columns(3)
    st.session_state.trim_start = c1.number_input("Pre-Cut Start (s) / ಆರಂಭ (ಸೆ.)", 0.0, 120.0, float(st.session_state.trim_start), 0.5)
    st.session_state.split_point = c2.number_input("Split Point (s) / ವಿಭಜನೆ (ಸೆ.)", 0.0, 120.0, float(st.session_state.split_point), 0.5)
    st.session_state.trim_end = c3.number_input("Trim End (s) / ಅಂತ್ಯ (ಸೆ.)", 1.0, 180.0, float(st.session_state.trim_end), 0.5)
elif "Speed" in group:
    c1, c2, c3 = st.columns(3)
    st.session_state.speed = c1.select_slider("Speed / ವೇಗ", [0.5, 0.75, 1.0, 1.25, 1.5, 2.0], value=st.session_state.speed)
    st.session_state.transition = c2.selectbox("Transition / ಬದಲಾವಣೆ", ["Crossfade / ಮಿಶ್ರಣ", "Slide / ಜಾರು", "Zoom / ಜೂಮ್", "Cut / ಕಟ್"])
    st.session_state.easing = c3.selectbox("Ease Curve / ವಕ್ರರೇಖೆ", ["Linear / ನೇರ", "Ease-In / ಆರಂಭ ಮೃದು", "Ease-Out / ಅಂತ್ಯ ಮೃದು", "Ease-In-Out / ಮೃದು"])
elif "Filters" in group:
    c1, c2, c3, c4 = st.columns(4)
    st.session_state.filter_name = c1.selectbox("Filter / ಫಿಲ್ಟರ್", ["Original / ಮೂಲ", "Vivid / ಪ್ರಖರ", "Warm / ಬೆಚ್ಚಗಿನ", "Noir / B&W / ಕಪ್ಪು-ಬಿಳುಪು", "Soft Glow / ಮೃದು ಹೊಳಪು"])
    st.session_state.rotation = c2.selectbox("Rotate (°) / ತಿರುಗಿಸಿ", [0, 90, 180, 270])
    st.session_state.opacity = c3.slider("Opacity / ಪಾರದರ್ಶಕತೆ", 0.1, 1.0, float(st.session_state.opacity), 0.05)
    st.session_state.flip_h = c4.checkbox("Mirror Flip / ಪ್ರತಿಬಿಂಬ", value=st.session_state.flip_h)
elif "Text" in group:
    c1, c2, c3 = st.columns(3)
    st.session_state.overlay_kn = c1.text_input("Kannada Caption / ಕನ್ನಡ ಶೀರ್ಷಿಕೆ", value=st.session_state.overlay_kn)
    st.session_state.overlay_en = c2.text_input("English Caption / ಇಂಗ್ಲಿಷ್ ಶೀರ್ಷಿಕೆ", value=st.session_state.overlay_en)
    st.session_state.sticker_text = c3.text_input("Stickers / ಸ್ಟಿಕರ್‌ಗಳು", value=st.session_state.sticker_text)
else:
    c1, c2 = st.columns(2)
    st.session_state.collage_mode = c1.selectbox("Collage / ಕೊಲಾಜ್", ["Single View / ಏಕ ದೃಶ್ಯ", "Side-by-Side (2) / ಎರಡು ಭಾಗ", "Grid (4) / ನಾಲ್ಕು ಭಾಗ"])
    st.session_state.bg_remove = c2.checkbox("Clean Background / ಹಿನ್ನೆಲೆ ತೆಗೆದುಹಾಕಿ", value=st.session_state.bg_remove)

st.divider()

# ==============================================================================
# WORKFLOW TABS (ENGLISH + ಕನ್ನಡ IN EVERY TAB)
# ==============================================================================
t1, t2, t3, t4 = st.tabs([
    "🎭 Character & Scene / ಕ್ಯಾರೆಕ್ಟರ್ ಮತ್ತು ದೃಶ್ಯ",
    "📜 Bilingual Script & Voice / ದ್ವಿಭಾಷಾ ಸ್ಕ್ರಿಪ್ಟ್ ಮತ್ತು ಧ್ವನಿ",
    "🔗 Direct Link & Upload / ಲಿಂಕ್ ಮತ್ತು ಅಪ್‌ಲೋಡ್",
    "📥 Exports / ಡೌನ್‌ಲೋಡ್ (TXT, SRT, MP3)",
])

with t1:
    st.subheader("Create Character & Scene / ಕ್ಯಾರೆಕ್ಟರ್ ಮತ್ತು ದೃಶ್ಯ ರಚಿಸಿ")
    p1, p2, p3 = st.columns([2, 2, 1])
    char_en = p1.text_input("Prompt (English) / ವಿವರಣೆ (ಇಂಗ್ಲಿಷ್)", "young entrepreneur explaining smart savings with friendly smile")
    char_kn = p2.text_input("Prompt (Kannada) / ವಿವರಣೆ (ಕನ್ನಡ)", "ಸ್ಮಾರ್ಟ್ ಉಳಿತಾಯದ ಬಗ್ಗೆ ವಿವರಿಸುತ್ತಿರುವ ಯುವ ಉದ್ಯಮಿ")
    char_style = p3.selectbox("Style / ಶೈಲಿ", ["3D Pixar / 3D ಶೈಲಿ", "Anime / ಅನಿಮೆ", "Comic Ink / ಕಾಮಿಕ್", "Flat Vector / ವೆಕ್ಟರ್"])

    if st.button("✨ Generate Scene / ದೃಶ್ಯ ರಚಿಸಿ", type="primary"):
        with st.spinner("Creating scene / ದೃಶ್ಯ ರಚಿಸಲಾಗುತ್ತಿದೆ..."):
            img_scene = generate_ai_character_image(char_en, char_kn, char_style, pollinations_key)
            st.session_state.scenes.append(img_scene)
            st.session_state.scene_labels.append(f"{char_en[:28]} | {char_kn[:28]}")
            st.rerun()

    if st.session_state.scenes:
        cols = st.columns(min(4, len(st.session_state.scenes)))
        for idx, sc in enumerate(st.session_state.scenes[-4:]):
            lbl = st.session_state.scene_labels[-4:][idx]
            with cols[idx]:
                st.image(sc, caption=f"Scene {idx + 1} / ದೃಶ್ಯ {idx + 1}: {lbl}", use_container_width=True)

with t2:
    st.subheader("30s Reel / Story Script (English + ಕನ್ನಡ) & Voiceover")
    idea_en = st.text_input("Topic (English) / ವಿಷಯ (ಇಂಗ್ಲಿಷ್)", "3 smart second-income habits in 30 seconds")
    idea_kn = st.text_input("Topic (Kannada) / ವಿಷಯ (ಕನ್ನಡ)", "30 ಸೆಕೆಂಡ್‌ಗಳಲ್ಲಿ 3 ಸ್ಮಾರ್ಟ್ ಹೆಚ್ಚುವರಿ ಆದಾಯದ ಅಭ್ಯಾಸಗಳು")

    if st.button("📝 Generate Both Scripts / ಎರಡೂ ಸ್ಕ್ರಿಪ್ಟ್ ರಚಿಸಿ"):
        st.session_state.script_en = (
            f"30-Second Guide on '{idea_en}': 1) Pick a practical skill, "
            f"2) Start small consistently, 3) Track weekly results. Follow for more!"
        )
        st.session_state.script_kn = (
            f"'{idea_kn}' ಬಗ್ಗೆ 30 ಸೆಕೆಂಡ್ ಮಾಹಿತಿ: 1) ನಿಮ್ಮ ಕೌಶಲ್ಯ ಆಯ್ಕೆ ಮಾಡಿ, "
            f"2) ಸಣ್ಣ ಮಟ್ಟದಲ್ಲಿ ನಿರಂತರವಾಗಿ ಆರಂಭಿಸಿ, 3) ವಾರಕ್ಕೊಮ್ಮೆ ಪ್ರಗತಿ ಗಮನಿಸಿ. ಹೆಚ್ಚಿನ ಮಾಹಿತಿಗೆ ಫಾಲೋ ಮಾಡಿ!"
        )
        st.rerun()

    s_col1, s_col2 = st.columns(2)
    st.session_state.script_kn = s_col1.text_area(
        "Kannada Script (ಕನ್ನಡ ಸ್ಕ್ರಿಪ್ಟ್ — Main Voice)",
        value=st.session_state.script_kn,
        height=130,
    )
    st.session_state.script_en = s_col2.text_area(
        "English Script (ಇಂಗ್ಲಿಷ್ ಸ್ಕ್ರಿಪ್ಟ್ — Reference & Bilingual SRT)",
        value=st.session_state.script_en,
        height=130,
    )

    v1, v2 = st.columns(2)
    kn_voice = v1.selectbox("Kannada Voice / ಕನ್ನಡ ಧ್ವನಿ", ["kn-IN-SapnaNeural", "kn-IN-GaganNeural"])
    kn_rate = v2.slider("Speed (%) / ವೇಗ (%)", -40, 40, 0)

    if st.button("🎙️ Generate Kannada Voice & Bilingual SRT / ಧ್ವನಿ ಮತ್ತು ಉಪಶೀರ್ಷಿಕೆ ರಚಿಸಿ"):
        if not HAS_EDGE_TTS:
            st.error("Add `edge-tts` to `requirements.txt`.")
        else:
            with st.spinner("Generating Kannada voiceover & bilingual subtitles..."):
                audio_data, srt_data = run_async(
                    generate_kannada_tts_and_bilingual_srt(
                        st.session_state.script_kn or "ನಮಸ್ಕಾರ!",
                        st.session_state.script_en or "Hello!",
                        kn_voice,
                        f"{kn_rate:+d}%",
                        "+0Hz",
                    )
                )
                st.session_state.generated_audio = audio_data
                st.session_state.subtitles_bilingual = srt_data
                st.rerun()

with t3:
    st.subheader("Pull Video from Link / ಲಿಂಕ್‌ನಿಂದ ವಿಡಿಯೋ ಪಡೆಯಿರಿ & Upload / ಅಪ್‌ಲೋಡ್")
    url_in = st.text_input("Direct Video Link / ನೇರ ವಿಡಿಯೋ ಲಿಂಕ್ (YouTube / Instagram / Facebook)")
    if st.button("⬇️ Pull Video / ವಿಡಿಯೋ ತನ್ನಿ"):
        if not HAS_YTDLP:
            st.error("Add `yt-dlp` to `requirements.txt`.")
        elif url_in.strip():
            with st.spinner("Fetching video / ವಿಡಿಯೋ ಪಡೆಯಲಾಗುತ್ತಿದೆ..."):
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
                    st.error(f"Link pull failed / ಲಿಂಕ್ ವಿಫಲವಾಗಿದೆ: {exc}")

    uploads = st.file_uploader(
        "Drag & Drop Images or Videos / ಚಿತ್ರ ಅಥವಾ ವಿಡಿಯೋ ಎಳೆದು ಹಾಕಿ",
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

with t4:
    st.subheader("Download Files / ಫೈಲ್‌ಗಳನ್ನು ಡೌನ್‌ಲೋಡ್ ಮಾಡಿ")
    combined_txt = (
        f"=== KANNADA / ಕನ್ನಡ ===\n{st.session_state.script_kn}\n\n"
        f"=== ENGLISH / ಇಂಗ್ಲಿಷ್ ===\n{st.session_state.script_en}\n"
    )
    d1, d2, d3 = st.columns(3)
    if combined_txt.strip():
        d1.download_button(
            "⬇️ Bilingual Script / ಸ್ಕ್ರಿಪ್ಟ್ (.txt)",
            data=combined_txt.encode("utf-8"),
            file_name="bilingual_script_en_kn.txt",
        )
    if st.session_state.subtitles_bilingual:
        d2.download_button(
            "⬇️ Bilingual Subtitles / ಉಪಶೀರ್ಷಿಕೆ (.srt)",
            data=st.session_state.subtitles_bilingual.encode("utf-8"),
            file_name="bilingual_subtitles_en_kn.srt",
        )
    if st.session_state.generated_audio:
        d3.download_button(
            "⬇️ Kannada Voice / ಕನ್ನಡ ಧ್ವನಿ (.mp3)",
            data=st.session_state.generated_audio,
            file_name="kannada_voiceover.mp3",
            mime="audio/mpeg",
        )
