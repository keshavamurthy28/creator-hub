import os
import random
import tempfile
import streamlit as st
from creator_hub_engine import (
    get_free_ai_scene_image,
    render_from_scenes,
    split_script_scenes,
    translate_text,
)

st.set_page_config(page_title="Creator Hub — Kannada & English Animated Video Studio", layout="wide")

if "workspace_dir" not in st.session_state:
    st.session_state.workspace_dir = tempfile.mkdtemp(prefix="creator_hub_")
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "final_video_bytes" not in st.session_state:
    st.session_state.final_video_bytes = None
if "title_text" not in st.session_state:
    st.session_state.title_text = ""
if "script_text" not in st.session_state:
    st.session_state.script_text = ""

st.title("Creator Hub — Animated Video Studio")
st.caption("Free Script-to-Video with English → Kannada Translation, Mixed Kannada/English Subtitles, Neural Voiceover & Scene Editor.")

# ===========================================================================
# STEP 1: SCRIPT, TRANSLATION & SETTINGS
# ===========================================================================
st.subheader("1. Script, Translation & Visual Settings")
col1, col2 = st.columns([1.25, 1])

with col1:
    st.session_state.title_text = st.text_input(
        "Intro Title Banner (Shown on Scene 1)",
        value=st.session_state.title_text,
        placeholder="e.g., Divine Meditation by the River / ನದಿಯ ತೀರದಲ್ಲಿ ಧ್ಯಾನ",
    )
    description = st.text_area(
        "Visual Style & Creative Description (Used for AI image generation)",
        placeholder="e.g., Peaceful river flowing in nature, 40 year old yogi meditating, golden divine aura, cinematic digital art...",
        height=85,
    )
    st.session_state.script_text = st.text_area(
        "Video Script (Each sentence becomes an editable scene)",
        value=st.session_state.script_text,
        placeholder="Write in English or Kannada. Click 'Translate to Kannada' below to convert automatically!",
        height=145,
    )

    tr_col1, tr_col2 = st.columns(2)
    with tr_col1:
        if st.button("Translate Script & Title to Kannada (ಕನ್ನಡ)", use_container_width=True):
            if st.session_state.script_text.strip():
                st.session_state.script_text = translate_text(st.session_state.script_text, target_lang="kn")
            if st.session_state.title_text.strip():
                st.session_state.title_text = translate_text(st.session_state.title_text, target_lang="kn")
            st.rerun()
    with tr_col2:
        if st.button("Translate Script & Title to English", use_container_width=True):
            if st.session_state.script_text.strip():
                st.session_state.script_text = translate_text(st.session_state.script_text, target_lang="en")
            if st.session_state.title_text.strip():
                st.session_state.title_text = translate_text(st.session_state.title_text, target_lang="en")
            st.rerun()

with col2:
    aspect = st.selectbox(
        "Video Format",
        ["16:9 YouTube / Landscape (1280x720)", "9:16 Reels / Shorts (720x1280)", "1:1 Square (1080x1080)"],
    )
    res_map = {
        "16:9 YouTube / Landscape (1280x720)": (1280, 720),
        "9:16 Reels / Shorts (720x1280)": (720, 1280),
        "1:1 Square (1080x1080)": (1080, 1080),
    }
    res_w, res_h = res_map[aspect]

    enable_vo = st.checkbox("Enable Free Neural Voiceover", value=True)
    voices = {
        "Kannada — Sapna (Female)": "kn-IN-SapnaNeural",
        "Kannada — Gagan (Male)": "kn-IN-GaganNeural",
        "English (India) — Neerja (Female)": "en-IN-NeerjaNeural",
        "English (India) — Prabhat (Male)": "en-IN-PrabhatNeural",
        "Hindi — Swara (Female)": "hi-IN-SwaraNeural",
    }
    selected_voice_label = st.selectbox("Narrator Voice", list(voices.keys()))
    selected_voice = voices[selected_voice_label]

    uploaded_files = st.file_uploader(
        "Optional: Upload Your Own Scene Images",
        type=["png", "jpg", "jpeg", "webp"],
        accept_multiple_files=True,
    )

if st.button("Build Editable Storyboard Scenes", type="primary", use_container_width=True):
    raw_script = st.session_state.script_text.strip() or description.strip()
    if not raw_script:
        st.error("Please enter a script or description first.")
    else:
        beats = split_script_scenes(raw_script)
        saved_uploads = []
        if uploaded_files:
            for i, uf in enumerate(uploaded_files):
                ext = os.path.splitext(uf.name)[1] or ".png"
                p = os.path.join(st.session_state.workspace_dir, f"up_{i}_{random.randint(100,999)}{ext}")
                with open(p, "wb") as f:
                    f.write(uf.getbuffer())
                saved_uploads.append(p)

        motions = ["zoom_in", "pan_right", "ken_burns_diag", "zoom_out", "pan_left"]
        new_scenes = []
        prog = st.progress(0.0, text="Generating initial storyboard scenes...")
        for idx, beat in enumerate(beats):
            prog.progress(idx / len(beats), text=f"Preparing scene {idx + 1}/{len(beats)}...")
            if idx < len(saved_uploads):
                img_p = saved_uploads[idx]
            else:
                img_p = os.path.join(st.session_state.workspace_dir, f"scene_{idx}_{random.randint(1000,9999)}.jpg")
                get_free_ai_scene_image(
                    scene_prompt=f"{beat}. {description}",
                    style_desc=description or "cinematic digital art",
                    width=res_w,
                    height=res_h,
                    out_path=img_p,
                    seed=random.randint(1, 99999),
                )
            new_scenes.append(
                {
                    "top_title": st.session_state.title_text.strip() if idx == 0 else "",
                    "caption": beat,
                    "narration": beat,
                    "duration": 4.0,
                    "motion": motions[idx % len(motions)],
                    "image_path": img_p,
                    "visual_prompt": f"{beat}. {description}",
                }
            )
        prog.progress(1.0, text="Storyboard ready!")
        st.session_state.scenes = new_scenes
        st.rerun()

# ===========================================================================
# STEP 2: SCENE-BY-SCENE VIDEO EDITOR
# ===========================================================================
if st.session_state.scenes:
    st.divider()
    st.subheader("2. Scene Editor (Edit Subtitles, Voice Text, Motion, Order & Images)")

    motions_list = ["zoom_in", "zoom_out", "pan_right", "pan_left", "ken_burns_diag"]
    to_delete = None
    swap_pair = None

    for idx, sc in enumerate(st.session_state.scenes):
        with st.expander(f"Scene {idx + 1}: {sc['caption'][:55]}...", expanded=True):
            c_img, c_edit = st.columns([1, 1.7])

            with c_img:
                if os.path.exists(sc["image_path"]):
                    st.image(sc["image_path"], use_container_width=True)

                b1, b2 = st.columns(2)
                with b1:
                    if st.button("Regenerate AI Art", key=f"regen_{idx}", use_container_width=True):
                        new_p = os.path.join(
                            st.session_state.workspace_dir, f"regen_{idx}_{random.randint(1000,99999)}.jpg"
                        )
                        get_free_ai_scene_image(
                            scene_prompt=sc["visual_prompt"],
                            style_desc=description or "cinematic digital art",
                            width=res_w,
                            height=res_h,
                            out_path=new_p,
                            seed=random.randint(1, 999999),
                        )
                        st.session_state.scenes[idx]["image_path"] = new_p
                        st.rerun()
                with b2:
                    if st.button("Translate to ಕನ್ನಡ", key=f"tr_sc_{idx}", use_container_width=True):
                        kn_line = translate_text(sc["caption"], target_lang="kn")
                        st.session_state.scenes[idx]["caption"] = kn_line
                        st.session_state.scenes[idx]["narration"] = kn_line
                        if sc["top_title"].strip():
                            st.session_state.scenes[idx]["top_title"] = translate_text(sc["top_title"], target_lang="kn")
                        st.rerun()

                rep_file = st.file_uploader(
                    "Replace Scene Image", type=["png", "jpg", "jpeg", "webp"], key=f"rep_img_{idx}"
                )
                if rep_file is not None:
                    ext = os.path.splitext(rep_file.name)[1] or ".png"
                    rep_path = os.path.join(
                        st.session_state.workspace_dir, f"custom_{idx}_{random.randint(1000,9999)}{ext}"
                    )
                    with open(rep_path, "wb") as f:
                        f.write(rep_file.getbuffer())
                    st.session_state.scenes[idx]["image_path"] = rep_path

            with c_edit:
                sc["top_title"] = st.text_input("Top Title Banner (Optional)", value=sc["top_title"], key=f"top_{idx}")
                sc["caption"] = st.text_area("Subtitle Text (Shown on Video)", value=sc["caption"], height=70, key=f"cap_{idx}")
                sc["narration"] = st.text_area(
                    "Voiceover Text (Spoken by Narrator)", value=sc["narration"], height=65, key=f"nar_{idx}"
                )

                m1, m2 = st.columns(2)
                with m1:
                    sc["motion"] = st.selectbox(
                        "Camera Animation",
                        motions_list,
                        index=motions_list.index(sc["motion"]) if sc["motion"] in motions_list else 0,
                        key=f"mot_{idx}",
                    )
                with m2:
                    sc["duration"] = st.slider(
                        "Min Duration (sec)", 2.0, 12.0, float(sc["duration"]), 0.5, key=f"dur_{idx}"
                    )

                act1, act2, act3 = st.columns(3)
                with act1:
                    if idx > 0 and st.button("Move Up", key=f"up_{idx}", use_container_width=True):
                        swap_pair = (idx, idx - 1)
                with act2:
                    if idx < len(st.session_state.scenes) - 1 and st.button("Move Down", key=f"dn_{idx}", use_container_width=True):
                        swap_pair = (idx, idx + 1)
                with act3:
                    if len(st.session_state.scenes) > 1 and st.button("Delete Scene", key=f"del_{idx}", use_container_width=True):
                        to_delete = idx

    if swap_pair:
        i, j = swap_pair
        st.session_state.scenes[i], st.session_state.scenes[j] = st.session_state.scenes[j], st.session_state.scenes[i]
        st.rerun()
    if to_delete is not None:
        st.session_state.scenes.pop(to_delete)
        st.rerun()

    if st.button("+ Add New Blank Scene", use_container_width=True):
        blank_p = os.path.join(st.session_state.workspace_dir, f"blank_{random.randint(1000,9999)}.jpg")
        get_free_ai_scene_image("serene cinematic landscape", "digital art", res_w, res_h, blank_p, random.randint(1, 99999))
        st.session_state.scenes.append(
            {
                "top_title": "",
                "caption": "ಹೊಸ ದೃಶ್ಯ / New scene text",
                "narration": "ಹೊಸ ದೃಶ್ಯ",
                "duration": 4.0,
                "motion": "zoom_in",
                "image_path": blank_p,
                "visual_prompt": "serene cinematic landscape",
            }
        )
        st.rerun()

    # =======================================================================
    # STEP 3: RENDER FINAL VIDEO
    # =======================================================================
    st.divider()
    if st.button("Render Final Animated Video", type="primary", use_container_width=True):
        out_mp4 = os.path.join(st.session_state.workspace_dir, f"final_{random.randint(1000,9999)}.mp4")
        r_prog = st.progress(0.0, text="Starting video render...")
        render_from_scenes(
            scenes=st.session_state.scenes,
            workdir=st.session_state.workspace_dir,
            output_path=out_mp4,
            resolution=(res_w, res_h),
            enable_voiceover=enable_vo,
            voice_name=selected_voice,
            progress_callback=lambda p, msg: r_prog.progress(p, text=msg),
        )
        with open(out_mp4, "rb") as f:
            st.session_state.final_video_bytes = f.read()

    if st.session_state.final_video_bytes:
        st.success("Your edited animated video is ready!")
        st.video(st.session_state.final_video_bytes)
        st.download_button(
            label="Download MP4 Video",
            data=st.session_state.final_video_bytes,
            file_name="creator_hub_kannada_animated.mp4",
            mime="video/mp4",
            use_container_width=True,
        )
