import os
import tempfile
import streamlit as st
from creator_hub_engine import create_creator_hub_video

st.set_page_config(page_title="Creator Hub — Free AI Script-to-Video Studio", layout="wide")

st.title("Creator Hub — Free Animated Video Studio")
st.markdown(
    "Turn any **script + creative description** into an animated video with **AI-generated scenes**, "
    "**smooth camera motion**, **crisp Kannada/English subtitles**, and **free neural voiceover**—with **zero API keys**."
)

left, right = st.columns([1.2, 1])

with left:
    video_title = st.text_input(
        "Intro Title Banner (Optional — shown on Scene 1)",
        placeholder="e.g., ನನ್ನ ಕಥೆ / My Animated Story",
    )
    description = st.text_area(
        "Visual Style & Creative Description",
        placeholder="Describe the look and mood: e.g., Warm watercolor studio art, golden sunset lighting, inspiring storytelling mood...",
        height=95,
    )
    script = st.text_area(
        "Video Script (Each sentence becomes an animated scene)",
        placeholder="Write your script in Kannada, English, or Hindi. Every sentence automatically gets its own animated scene and synced voiceover...",
        height=175,
    )

with right:
    visual_mode = st.radio(
        "Visual Source (100% Free)",
        options=[
            ("ai_auto", "Auto-Generate AI Scenes from Script & Description (No images needed)"),
            ("hybrid", "Use My Uploaded Images First + AI Generate Remaining Scenes"),
            ("uploaded_only", "Animate Only My Uploaded Images"),
        ],
        format_func=lambda x: x[1],
    )[0]

    uploaded_files = st.file_uploader(
        "Optional Scene Images (PNG / JPG / WEBP)",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )

    aspect = st.selectbox(
        "Video Format",
        ["16:9 YouTube / Landscape (1280x720)", "9:16 Reels / Shorts (720x1280)", "1:1 Instagram Square (1080x1080)"],
    )
    res_map = {
        "16:9 YouTube / Landscape (1280x720)": (1280, 720),
        "9:16 Reels / Shorts (720x1280)": (720, 1280),
        "1:1 Instagram Square (1080x1080)": (1080, 1080),
    }

    enable_vo = st.checkbox("Enable Free Neural Voiceover (Synced per Scene)", value=True)
    voices = {
        "Kannada — Sapna (Female)": "kn-IN-SapnaNeural",
        "Kannada — Gagan (Male)": "kn-IN-GaganNeural",
        "English (India) — Neerja (Female)": "en-IN-NeerjaNeural",
        "English (India) — Prabhat (Male)": "en-IN-PrabhatNeural",
        "Hindi — Swara (Female)": "hi-IN-SwaraNeural",
        "Hindi — Madhur (Male)": "hi-IN-MadhurNeural",
    }
    selected_voice = st.selectbox("Narrator Voice", list(voices.keys()))
    fallback_dur = st.slider("Scene Duration (when voiceover is off)", 2.5, 8.0, 4.0, 0.5)

if st.button("Generate Animated Video", type="primary", use_container_width=True):
    if not script.strip() and not description.strip():
        st.error("Please enter a script or description first.")
    elif visual_mode == "uploaded_only" and not uploaded_files:
        st.error("Please upload at least one image, or switch Visual Source to Auto-Generate AI Scenes.")
    else:
        prog_bar = st.progress(0.0, text="Starting Creator Hub pipeline...")
        with tempfile.TemporaryDirectory() as tmpdir:
            saved_imgs = []
            if uploaded_files:
                for i, uf in enumerate(uploaded_files):
                    ext = os.path.splitext(uf.name)[1] or ".png"
                    p = os.path.join(tmpdir, f"upload_{i}{ext}")
                    with open(p, "wb") as f:
                        f.write(uf.getbuffer())
                    saved_imgs.append(p)

            out_file = os.path.join(tmpdir, "creator_hub_final.mp4")
            try:
                create_creator_hub_video(
                    script=script,
                    description=description,
                    video_title=video_title,
                    workdir=tmpdir,
                    output_path=out_file,
                    uploaded_images=saved_imgs,
                    visual_mode=visual_mode,
                    resolution=res_map[aspect],
                    default_scene_sec=fallback_dur,
                    enable_voiceover=enable_vo,
                    voice_name=voices[selected_voice],
                    progress_callback=lambda pct, msg: prog_bar.progress(pct, text=msg),
                )

                with open(out_file, "rb") as f:
                    mp4_bytes = f.read()

                st.success("Animated video created!")
                st.video(mp4_bytes)
                st.download_button(
                    label="Download Animated Video (.MP4)",
                    data=mp4_bytes,
                    file_name="creator_hub_video.mp4",
                    mime="video/mp4",
                    use_container_width=True,
                )
            except Exception as exc:
                st.error(f"Video generation error: {exc}")
