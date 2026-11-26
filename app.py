import asyncio
import io
import os
import tempfile
import time
import streamlit as st
from PIL import Image, ImageDraw, ImageOps

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
    initial_sidebar_state="expanded",
)

# --- SESSION STATE ---
defaults = {
    "source_script_en": "",
    "kannada_script": "",
    "subtitles_srt": "",
    "pulled_video_path": None,
    "uploaded_media": [],
    "scenes": [],
    "generated_audio": None,
    "final_video": None,
    "edit_settings": {
        "aspect_ratio": "9:16 (Reels/Shorts)",
        "fps": 30,
        "speed": 1.0,
        "opacity": 1.0,
        "rotation": 0,
        "flip_h": False,
        "filter_mode": "None",
        "transition": "Cross Dissolve",
        "easing": "Ease-In-Out",
        "pip_enabled": False,
        "bg_remove_mode": "Off",
        "mask_shape": "None",
        "collage_layout": "Single",
        "reversed": False,
        "freeze_sec": 0.0,
        "voice_enhance": True,
    },
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
    srt_entries = []
    idx = 1
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, pitch=pitch)

    def fmt_time(sec_float: float) -> str:
        ms = int(round(sec_float * 1000))
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        rem_ms = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{rem_ms:03d}"

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buf.write(chunk["data"])
        elif chunk["type"] in ("WordBoundary", "SentenceBoundary"):
            offset_sec = chunk["offset"] / 10_000_000
            dur_sec = chunk["duration"] / 10_000_000
            start_str = fmt_time(offset_sec)
            end_str = fmt_time(offset_sec + max(dur_sec, 0.35))
            word_txt = chunk.get("text", "").strip()
            if word_txt:
                srt_entries.append(f"{idx}\n{start_str} --> {end_str}\n{word_txt}\n")
                idx += 1

    srt_text = "\n".join(srt_entries) if srt_entries else f"1\n00:00:00,000 --> 00:00:05,000\n{text}\n"
    return audio_buf.getvalue(), srt_text


def pull_video_from_link(url: str, out_dir: str):
    ydl_opts = {
        "outtmpl": os.path.join(out_dir, "%(title).60s.%(ext)s"),
        "format": "best[ext=mp4]/best",
        "noplaylist": True,
        "quiet": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if not os.path.exists(filename):
            base, _ = os.path.splitext(filename)
            for ext in (".mp4", ".mkv", ".webm"):
                if os.path.exists(base + ext):
                    filename = base + ext
                    break
        return filename, info.get("title", "Pulled Video")


def apply_image_preview_edits(img: Image.Image, cfg: dict) -> Image.Image:
    out = img.convert("RGB")
    if cfg["rotation"]:
        out = out.rotate(-cfg["rotation"], expand=True)
    if cfg["flip_h"]:
        out = ImageOps.mirror(out)
    if cfg["filter_mode"] == "Grayscale":
        out = ImageOps.grayscale(out).convert("RGB")
    elif cfg["filter_mode"] == "High Contrast":
        out = ImageOps.autocontrast(out)
    elif cfg["filter_mode"] == "Invert":
        out = ImageOps.invert(out)
    if cfg["opacity"] < 1.0:
        bg = Image.new("RGB", out.size, (15, 15, 20))
        out = Image.blend(bg, out, cfg["opacity"])
    return out


st.title("🎬 Creator Hub All-in-One Studio (Kannada First)")

# ==============================================================================
# TOP SECTION: MEDIA PLAYER VIEW (WINDOWS MEDIA PLAYER STYLE)
# ==============================================================================
st.markdown("### 📺 Studio Player & Main Preview Screen")
p_left, p_right = st.columns([3, 1])

with p_left:
    if st.session_state.final_video:
        st.video(st.session_state.final_video)
        st.caption("🟢 Previewing: Rendered Video")
    elif st.session_state.pulled_video_path and os.path.exists(st.session_state.pulled_video_path):
        st.video(st.session_state.pulled_video_path)
        st.caption("📥 Previewing: Pulled Social Media Video")
    elif st.session_state.generated_audio:
        st.audio(st.session_state.generated_audio, format="audio/mp3")
        st.caption("🎙️ Previewing: Kannada Voiceover Audio")
    elif st.session_state.scenes:
        edited_preview = apply_image_preview_edits(st.session_state.scenes[-1], st.session_state.edit_settings)
        st.image(edited_preview, use_container_width=True)
        st.caption("🖼️ Previewing: Latest Scene Frame with Live Editor Adjustments")
    else:
        st.info("🖥️ Screen Area: Paste a video link, drag & drop media, or generate Kannada voiceover & scenes below.")

with p_right:
    st.markdown("#### ⚙️ Quick Player & Output")
    st.session_state.edit_settings["aspect_ratio"] = st.selectbox(
        "Aspect Ratio",
        ["9:16 (Reels/Shorts)", "16:9 (YouTube)", "1:1 (Square/Collage)", "4:5 (Feed)"],
    )
    bg_music = st.file_uploader("Background Music (MP3/WAV)", type=["mp3", "wav"])
    if bg_music:
        st.audio(bg_music)
        st.success("BGM ready for mix")
    if st.session_state.kannada_script:
        st.markdown("**ಕನ್ನಡ Subtitle Preview:**")
        st.write(st.session_state.kannada_script)

st.divider()

# ==============================================================================
# BOTTOM SECTION: ALL-IN-ONE WORKFLOWS & INSHOT-STYLE CONTROLS
# ==============================================================================
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🔗 1. Link Pull & Drag-Drop Media",
    "📜 2. Script & Kannada Converter",
    "🎙️ 3. Kannada Voice & Subtitles",
    "🎨 4. Animation & Scene Studio",
    "✂️ 5. Pro Editor & Collage (InShot Mode)",
    "📥 6. Render & Export Vault",
])

# --- TAB 1: DIRECT LINK PULL (NO SEARCH) + DRAG & DROP UPLOAD ---
with tab1:
    st.subheader("Pull Video from Link (YouTube / Instagram / Facebook / Reels)")
    st.caption("Paste a direct public link—no search bar. Use only content you own or have rights to adapt.")
    link_url = st.text_input("Paste Direct Video / Reel URL", placeholder="https://www.instagram.com/reel/... or https://youtu.be/...")

    col_l1, col_l2 = st.columns([1, 3])
    with col_l1:
        pull_btn = st.button("⬇️ Fetch from Link", type="primary")
    with col_l2:
        if not HAS_YTDLP:
            st.warning("Install `yt-dlp` in `requirements.txt` to enable direct link fetching.")

    if pull_btn and link_url.strip():
        if not HAS_YTDLP:
            st.error("`yt-dlp` is not installed.")
        else:
            with st.spinner("Fetching video from link..."):
                try:
                    tmp_dir = tempfile.mkdtemp(prefix="kkm_pull_")
                    vid_path, vid_title = pull_video_from_link(link_url.strip(), tmp_dir)
                    st.session_state.pulled_video_path = vid_path
                    st.success(f"Fetched: {vid_title}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Could not pull link (platforms may block cloud IPs, require login cookies, or restrict access): {e}")

    st.divider()
    st.subheader("Drag & Drop Your Images & Videos (Any Source Language)")
    dropped_files = st.file_uploader(
        "Drag and drop or browse images and videos",
        type=["png", "jpg", "jpeg", "webp", "mp4", "mov", "mkv", "webm"],
        accept_multiple_files=True,
    )
    if dropped_files:
        st.session_state.uploaded_media = dropped_files
        st.success(f"{len(dropped_files)} file(s) loaded into workspace.")
        for f in dropped_files:
            if f.type.startswith("image/"):
                img = Image.open(f)
                if st.button(f"➕ Add '{f.name}' to Scenes", key=f"add_{f.name}"):
                    st.session_state.scenes.append(img)
                    st.toast(f"Added {f.name} to Scene Studio")
            elif f.type.startswith("video/"):
                if st.button(f"📺 Load '{f.name}' into Top Player", key=f"play_{f.name}"):
                    tfile = tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(f.name)[1] or ".mp4")
                    tfile.write(f.getvalue())
                    tfile.flush()
                    st.session_state.final_video = tfile.name
                    st.rerun()

# --- TAB 2: SCRIPT WRITING (30s VIRAL REEL + KWISDOM STORY + KANNADA MAIN) ---
with tab2:
    st.subheader("Script Writing & Kannada Adaptation")
    mode = st.selectbox(
        "Format",
        [
            "30-Second Second Income / Viral Reel",
            "Kwisdom Moral & Wisdom Story",
            "Translate / Adapt Foreign Script into Kannada",
        ],
    )
    c1, c2 = st.columns(2)
    with c1:
        topic = st.text_input("Topic / Idea (English or Kannada)", "3 smart side-income habits in 30 seconds")
        hook_style = st.selectbox("Opening Hook", ["Curiosity Gap", "Myth Buster", "Step-by-Step Formula", "Story Lesson"])
    with c2:
        pacing = st.selectbox("Pacing", ["Fast 30s Reel", "Calm Storyteller", "Energetic Creator"])
        auto_kannada_sample = st.text_area(
            "Kannada Script (Main Output — Edit freely in Kannada)",
            value=st.session_state.kannada_script,
            height=160,
            placeholder="ಇಲ್ಲಿ ನಿಮ್ಮ ಕನ್ನಡ ಸ್ಕ್ರಿಪ್ಟ್ ಬರೆಯಿರಿ ಅಥವಾ ರಚಿಸಿ...",
        )

    if st.button("✨ Generate Drafts"):
        st.session_state.source_script_en = (
            f"[{mode} | {hook_style} | {pacing}]\n"
            f"Hook (0-3s): Stop scrolling! Here is how {topic} works.\n"
            f"Core (3-25s): Focus on clear value, consistency, and practical steps.\n"
            f"CTA (25-30s): Save this reel and follow for more in Kannada."
        )
        st.session_state.kannada_script = (
            f"ಗಮನಿಸಿ! '{topic}' ಬಗ್ಗೆ ನೀವು ತಿಳಿಯಲೇಬೇಕಾದ ಮುಖ್ಯ ವಿಷಯ ಇಲ್ಲಿದೆ. "
            f"ಮೊದಲನೆಯದಾಗಿ ಸರಿಯಾದ ಯೋಜನೆ ಮತ್ತು ನಿರಂತರ ಪ್ರಯತ್ನ ಬಹಳ ಮುಖ್ಯ. "
            f"ಸಣ್ಣ ಹೆಜ್ಜೆಗಳಿಂದ ದೊಡ್ಡ ಬದಲಾವಣೆ ಸಾಧ್ಯ. ಹೆಚ್ಚಿನ ಕನ್ನಡ ವಿಡಿಯೋಗಳಿಗಾಗಿ ಫಾಲೋ ಮಾಡಿ!"
        )
        st.rerun()
    elif auto_kannada_sample != st.session_state.kannada_script:
        st.session_state.kannada_script = auto_kannada_sample

    if st.session_state.source_script_en:
        st.text_area("Reference / Foreign Script Notes", value=st.session_state.source_script_en, height=110)

# --- TAB 3: KANNADA VOICEOVER & SUBTITLES ---
with tab3:
    st.subheader("Kannada Voiceover (`edge-tts`) & Subtitles (`.srt`)")
    kn_text = st.text_area(
        "Kannada Narration Text",
        value=st.session_state.kannada_script or "ನಮಸ್ಕಾರ! ಕ್ರಿಯೇಟರ್ ಹಬ್ ಸ್ಟುಡಿಯೋಗೆ ಸ್ವಾಗತ.",
        height=140,
    )
    v_col1, v_col2, v_col3 = st.columns(3)
    with v_col1:
        kn_voice = st.selectbox("Kannada Neural Voice", ["kn-IN-SapnaNeural", "kn-IN-GaganNeural"])
    with v_col2:
        rate_pct = st.slider("Speaking Speed (%)", -50, 50, 0)
    with v_col3:
        pitch_hz = st.slider("Pitch (Hz)", -30, 30, 0)

    if st.button("🎙️ Generate Kannada Voice & Subtitles", type="primary"):
        if not HAS_EDGE_TTS:
            st.error("Install `edge-tts` in `requirements.txt` to synthesize Kannada speech.")
        elif not kn_text.strip():
            st.warning("Enter Kannada text first.")
        else:
            with st.spinner("Generating Kannada audio and subtitle timings..."):
                try:
                    rate_str = f"{rate_pct:+d}%"
                    pitch_str = f"{pitch_hz:+d}Hz"
                    audio_bytes, srt_out = run_async(
                        generate_kannada_tts_and_srt(kn_text.strip(), kn_voice, rate_str, pitch_str)
                    )
                    st.session_state.generated_audio = audio_bytes
                    st.session_state.subtitles_srt = srt_out
                    st.session_state.kannada_script = kn_text.strip()
                    st.success("Kannada voiceover and subtitles generated! Play audio on the top screen.")
                except Exception as e:
                    st.error(f"TTS generation error: {e}")

    if st.session_state.generated_audio:
        st.audio(st.session_state.generated_audio, format="audio/mp3")
    if st.session_state.subtitles_srt:
        st.text_area("Generated Kannada Subtitles (SRT)", value=st.session_state.subtitles_srt, height=160)

# --- TAB 4: ANIMATION & SCENE STUDIO ---
with tab4:
    st.subheader("Animation & Scene Builder")
    sc_col1, sc_col2 = st.columns(2)
    with sc_col1:
        scene_desc = st.text_input("Scene Description", "Warm golden sunrise over hills, clean modern motion graphic")
        anim_style = st.selectbox(
            "Animation Motion Preset",
            ["Ken Burns Zoom-In", "Ken Burns Pan-Right", "Slide Up", "Bounce Pop", "Parallax Drift", "Fade Pulse"],
        )
    with sc_col2:
        palette = st.selectbox("Color Theme", ["Deep Indigo & Gold", "Emerald & Cream", "Crimson & Charcoal", "Ocean Teal"])
        caption_overlay = st.text_input("On-Screen Kannada Title", "ಕನ್ನಡ ಕಂಟೆಂಟ್ ಸ್ಟುಡಿಯೋ")

    if st.button("🎨 Create Scene Frame"):
        palettes = {
            "Deep Indigo & Gold": ((22, 27, 64), (255, 204, 77)),
            "Emerald & Cream": ((16, 66, 52), (250, 244, 225)),
            "Crimson & Charcoal": ((30, 30, 36), (255, 92, 92)),
            "Ocean Teal": ((12, 56, 78), (120, 235, 220)),
        }
        bg_c, fg_c = palettes[palette]
        frame = Image.new("RGB", (1080, 1920), color=bg_c)
        draw = ImageDraw.Draw(frame)
        draw.rectangle([70, 220, 1010, 1700], outline=fg_c, width=6)
        draw.text((120, 320), f"Motion: {anim_style}", fill=fg_c)
        draw.text((120, 400), f"Prompt: {scene_desc[:60]}", fill=(240, 240, 240))
        draw.text((120, 500), f"Title: {caption_overlay}", fill=fg_c)
        st.session_state.scenes.append(frame)
        st.success(f"Scene #{len(st.session_state.scenes)} added!")

    if st.session_state.scenes:
        st.markdown("#### Scene Frames")
        cols = st.columns(min(4, len(st.session_state.scenes)))
        for i, sc in enumerate(st.session_state.scenes[-4:]):
            with cols[i]:
                st.image(sc, caption=f"Frame {i + 1}", use_container_width=True)

# --- TAB 5: INSHOT-STYLE FULL TOOLSET & COLLAGE ---
with tab5:
    st.subheader("InShot-Style Editing Controls & Collage Maker (Unlimited Mode)")
    cfg = st.session_state.edit_settings

    e1, e2, e3, e4 = st.columns(4)
    with e1:
        cfg["speed"] = st.slider("Speed", 0.25, 4.0, float(cfg["speed"]), 0.25)
        cfg["opacity"] = st.slider("Opacity", 0.05, 1.0, float(cfg["opacity"]), 0.05)
        cfg["rotation"] = st.selectbox("Rotate", [0, 90, 180, 270], index=[0, 90, 180, 270].index(cfg["rotation"]))
        cfg["flip_h"] = st.checkbox("Mirror / Flip", value=cfg["flip_h"])
    with e2:
        cfg["filter_mode"] = st.selectbox("Filter", ["None", "Grayscale", "High Contrast", "Invert"])
        cfg["transition"] = st.selectbox("Transition", ["Cross Dissolve", "Slide Left", "Zoom Cut", "Wipe", "None"])
        cfg["easing"] = st.selectbox("Ease Curve", ["Linear", "Ease-In", "Ease-Out", "Ease-In-Out"])
        cfg["reversed"] = st.checkbox("Reverse Clip", value=cfg["reversed"])
    with e3:
        cfg["pip_enabled"] = st.checkbox("PiP (Picture-in-Picture)", value=cfg["pip_enabled"])
        cfg["bg_remove_mode"] = st.selectbox("AI Cut / BG Remove", ["Off", "Auto Cutout", "Chroma Key"])
        cfg["mask_shape"] = st.selectbox("Mask", ["None", "Circle", "Rectangle", "Heart/Star"])
        cfg["freeze_sec"] = st.number_input("Freeze Frame (sec)", min_value=0.0, max_value=10.0, value=float(cfg["freeze_sec"]), step=0.5)
    with e4:
        cfg["collage_layout"] = st.selectbox("Collage Grid", ["Single", "2-Split Vertical", "2-Split Horizontal", "4-Grid"])
        cfg["voice_enhance"] = st.checkbox("Voice Enhance & Noise Clean", value=cfg["voice_enhance"])
        st.text_input("Sticker / Emoji Pack", "🔥✨💡🎯")
        st.text_input("Trim / Split / Pre-Cut Range", "00:00 - 00:30")

    if st.button("📸 Capture Frame / Apply Edits to Top Screen"):
        if st.session_state.scenes:
            edited = apply_image_preview_edits(st.session_state.scenes[-1], cfg)
            st.session_state.scenes.append(edited)
        st.success("Editing parameters updated and previewed on the top screen.")
        st.rerun()

# --- TAB 6: RENDER & EXPORT VAULT ---
with tab6:
    st.subheader("Final Render & Download Vault")
    r_col1, r_col2 = st.columns(2)
    with r_col1:
        st.session_state.edit_settings["fps"] = st.select_slider("Render FPS", options=[24, 30, 60], value=st.session_state.edit_settings["fps"])
        if st.button("🚀 Build Project Package", type="primary"):
            with st.spinner("Preparing project timeline..."):
                time.sleep(0.5)
                st.success("Project assets, Kannada script, audio, and SRT subtitles are ready below.")

    with r_col2:
        if st.session_state.kannada_script:
            st.download_button(
                "⬇️ Download Kannada Script (.txt)",
                data=st.session_state.kannada_script.encode("utf-8"),
                file_name="kannada_script.txt",
                mime="text/plain",
            )
        if st.session_state.subtitles_srt:
            st.download_button(
                "⬇️ Download Kannada Subtitles (.srt)",
                data=st.session_state.subtitles_srt.encode("utf-8"),
                file_name="kannada_subtitles.srt",
                mime="application/x-subrip",
            )
        if st.session_state.generated_audio:
            st.download_button(
                "⬇️ Download Kannada Voiceover (.mp3)",
                data=st.session_state.generated_audio,
                file_name="kannada_voiceover.mp3",
                mime="audio/mpeg",
            )
