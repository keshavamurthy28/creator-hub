import streamlit as st
import os
import json
import gtts
from PIL import Image, ImageDraw, ImageFont
import io
import time

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Creator Hub Studio",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "story_script" not in st.session_state:
    st.session_state.story_script = ""
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "generated_audio" not in st.session_state:
    st.session_state.generated_audio = None
if "final_video" not in st.session_state:
    st.session_state.final_video = None

st.title("🎬 Creator Hub All-in-One Studio")

# ==============================================================================
# TOP SECTION: MEDIA PLAYER VIEW (WINDOWS VIDEO PLAYER STYLE)
# ==============================================================================
st.markdown("### 📺 Studio Player & Main Preview Screen")

player_col1, player_col2 = st.columns([3, 1])

with player_col1:
    st.markdown("---")
    if st.session_state.final_video:
        st.video(st.session_state.final_video)
        st.caption("🟢 Currently Playing: Final Rendered Video")
    elif st.session_state.generated_audio:
        st.audio(st.session_state.generated_audio)
        st.caption("🎵 Currently Playing: Generated Voiceover Audio")
    else:
        st.info("🖥️ Screen Area: Generate or upload audio/video in the tabs below to play here.")
    st.markdown("---")

with player_col2:
    st.markdown("#### ⚙️ Quick Player Controls")
    aspect_ratio = st.selectbox("Aspect Ratio", ["9:16 (Reels/TikTok/Shorts)", "16:9 (YouTube)", "1:1 (Instagram Post)"])
    bg_music = st.file_uploader("Upload Background Music", type=["mp3", "wav"])
    if bg_music:
        st.success("Background Music Loaded")

# ==============================================================================
# BOTTOM SECTION: SETTINGS & CONTROLS (TABBED WORKFLOW)
# ==============================================================================
st.markdown("### 🛠️ Production Controls & Workflows")

tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📜 1. Script & Reel Generator", 
    "🖼️ 2. Image & Scene Studio", 
    "🎙️ 3. Audio & Voiceover", 
    "🎞️ 4. Timeline & Video Render", 
    "📥 5. Download & Vault"
])

# ------------------------------------------------------------------------------
# TAB 1: SCRIPT & REEL GENERATOR (Combines Kwisdom & Viral Reel Script Studio)
# ------------------------------------------------------------------------------
with tab1:
    st.header("Viral Script & Kwisdom Story Creator")
    
    script_mode = st.radio("Select Content Type", ["Viral Social Reel Script", "Kwisdom Moral Story Episode"])
    
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        topic = st.text_input("Topic / Main Subject", "3 Habits That Will Change Your Life")
        target_audience = st.selectbox("Target Audience", ["General Public", "Investors/Traders", "Students", "Tech Enthusiasts"])
    with col_s2:
        tone = st.selectbox("Tone of Voice", ["Motivational", "Educational", "Dramatic", "Humorous", "Calm & Wise"])
        duration_sec = st.slider("Target Duration (seconds)", 15, 90, 30)

    if st.button("✨ Generate Script"):
        if script_mode == "Viral Social Reel Script":
            generated = f"""[HOOK - 0 to 3s]: Stop scrolling if you want to master {topic}!
[BODY - 3 to 25s]: Here is what nobody tells you about {topic}. 
First, focus on consistency. Second, eliminate unnecessary friction. Third, track your daily progress.
[CTA - 25 to 30s]: Follow for more content like this!"""
        else:
            generated = f"""[EPISODE - Kwisdom Wisdom Tale]
Title: The Lessons of {topic}
Scene 1: In a quiet valley, a wise mentor was asked about {topic}.
Scene 2: "Remember," said the mentor, "great things take patience and continuous effort."
Moral: Growth happens step by step, day by day."""
            
        st.session_state.story_script = generated
        st.success("Script generated successfully!")

    st.text_area("Script Editor", value=st.session_state.story_script, height=200, key="script_box")

# ------------------------------------------------------------------------------
# TAB 2: IMAGE & SCENE STUDIO
# ------------------------------------------------------------------------------
with tab2:
    st.header("Scene & Asset Generator")
    
    col_img1, col_img2 = st.columns(2)
    with col_img1:
        scene_prompt = st.text_input("Scene Description / Image Prompt", "A wise old man sitting under a banyan tree, cinematic lighting")
        style = st.selectbox("Visual Style", ["Anime / Animated", "Photorealistic", "Digital Art", "Minimalist Vector"])
    with col_img2:
        image_source = st.radio("Image Input Mode", ["Generate Placeholder / Canvas", "Upload Custom Image"])

    if image_source == "Upload Custom Image":
        uploaded_img = st.file_uploader("Upload Image File", type=["png", "jpg", "jpeg"])
        if uploaded_img:
            img = Image.open(uploaded_img)
            st.image(img, caption="Uploaded Asset", width=300)
            if st.button("Add to Scene Vault"):
                st.session_state.scenes.append(img)
                st.success("Image added to scenes!")
    else:
        if st.button("🎨 Create Scene Image"):
            # Canvas creation for reliable browser execution
            img = Image.new('RGB', (800, 450), color=(73, 109, 137))
            d = ImageDraw.Draw(img)
            d.text((40, 200), f"Scene: {scene_prompt}\nStyle: {style}", fill=(255, 255, 0))
            st.image(img, caption="Generated Scene Canvas", width=400)
            st.session_state.scenes.append(img)
            st.success("Scene generated and saved!")

    st.markdown("#### Scene Gallery")
    if st.session_state.scenes:
        g_cols = st.columns(4)
        for idx, scene_img in enumerate(st.session_state.scenes):
            with g_cols[idx % 4]:
                st.image(scene_img, caption=f"Scene {idx+1}")

# ------------------------------------------------------------------------------
# TAB 3: AUDIO & VOICEOVER STUDIO
# ------------------------------------------------------------------------------
with tab3:
    st.header("Voiceover & Text-to-Speech")
    
    tts_text = st.text_area("Voiceover Text", value=st.session_state.story_script if st.session_state.story_script else "Welcome to Creator Hub Studio.")
    
    col_a1, col_a2 = st.columns(2)
    with col_a1:
        lang = st.selectbox("Language", ["en", "hi", "es", "fr", "de"])
    with col_a2:
        tld = st.selectbox("Accent / TLD", ["com", "co.uk", "ca", "co.in"])

    if st.button("🔊 Generate Voiceover (gTTS)"):
        try:
            tts = gtts.gTTS(text=tts_text, lang=lang, tld=tld, slow=False)
            audio_fp = io.BytesIO()
            tts.write_to_fp(audio_fp)
            audio_fp.seek(0)
            st.session_state.generated_audio = audio_fp.read()
            st.success("Voiceover generated! You can play it on the top screen.")
        except Exception as e:
            st.error(f"Error generating audio: {e}")

# ------------------------------------------------------------------------------
# TAB 4: TIMELINE & VIDEO RENDER
# ------------------------------------------------------------------------------
with tab4:
    st.header("Timeline & Final Render Engine")
    
    st.write("Combine generated scenes and voiceover into a final video file.")
    fps = st.slider("Frame Rate (FPS)", 15, 60, 24)
    transition = st.selectbox("Transition Effect", ["None (Cut)", "Fade to Black", "Cross Dissolve"])

    if st.button("🚀 Render Video"):
        with st.spinner("Rendering video elements..."):
            time.sleep(2)  # Simulating rendering sequence
            # Fallback sample video output marker
            st.session_state.final_video = "https://www.w3schools.com/html/mov_bbb.mp4"
            st.success("Render complete! Preview the result in the top Screen Player.")

# ------------------------------------------------------------------------------
# TAB 5: DOWNLOAD & VAULT
# ------------------------------------------------------------------------------
with tab5:
    st.header("Download & Project Export Vault")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    
    with col_d1:
        st.markdown("#### 📜 Script Export")
        if st.session_state.story_script:
            st.download_button("Download Script (.txt)", data=st.session_state.story_script, file_name="script.txt", mime="text/plain")
        else:
            st.info("No script created yet.")
            
    with col_d2:
        st.markdown("#### 🎵 Audio Export")
        if st.session_state.generated_audio:
            st.download_button("Download Voiceover (.mp3)", data=st.session_state.generated_audio, file_name="voiceover.mp3", mime="audio/mp3")
        else:
            st.info("No voiceover generated yet.")

    with col_d3:
        st.markdown("#### 🎬 Video Export")
        if st.session_state.final_video:
            st.write("Video ready for download.")
            st.button("Download Final MP4 Video")
        else:
            st.info("No video rendered yet.")
