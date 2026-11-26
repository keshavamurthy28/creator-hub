import os
import random
import tempfile
import streamlit as st
from video_engine import (
    fetch_scene_image,
    render_story_video,
    split_into_story_beats,
    translate_to_kannada,
)

st.set_page_config(page_title="Creator Hub — Kannada Animated Story Studio", layout="wide")

if "work_dir" not in st.session_state:
    st.session_state.work_dir = tempfile.mkdtemp(prefix="ch_story_")
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "video_bytes" not in st.session_state:
    st.session_state.video_bytes = None
if "render_warnings" not in st.session_state:
    st.session_state.render_warnings = []

DEFAULT_SCRIPT = (
    "Flight landed in forest due to problem and few dies because of that.\n"
    "Few survives and overcome the hurdle finally and come back.\n"
    "How they fight animals.\n"
    "How they find food for survival.\n"
    "How they learn skills."
)

st.title("Creator Hub — Kannada Animated Story Studio")
st.caption("Creates multi-scene animated videos with Kannada subtitles, Kannada voiceover, AI visuals, and full scene editing.")

left, right = st.columns([1.3, 1])

with left:
    script_input = st.text_area(
        "Story Script (One sentence/line per scene — English or Kannada)",
        value=DEFAULT_SCRIPT,
        height=160,
    )
    style_desc = st.text_area(
        "Visual Style & Animation Mood (Used to generate rich scene illustrations)",
        value="2d animated adventure story, dense tropical forest, dramatic lighting, expressive characters, cinematic atmosphere",
        height=85,
    )

with right:
    fmt = st.selectbox(
        "Aspect Ratio & Resolution",
        ["16:9 Landscape (1280x720)", "9:16 Reels/Shorts (720x1280)", "1:1 Square (1080x1080)"],
    )
    res_map = {
        "16:9 Landscape (1280x720)": (1280, 720),
        "9:16 Reels/Shorts (720x1280)": (720, 1280),
        "1:1 Square (1080x1080)": (1080, 1080),
    }
    res_w, res_h = res_map[fmt]

    enable_audio = st.checkbox("Generate Voiceover Audio", value=True)
    voice_choice = st.selectbox(
        "Voiceover Language & Voice",
        [
            ("Kannada — Sapna (Female)", "kn-IN-SapnaNeural"),
            ("Kannada — Gagan (Male)", "kn-IN-GaganNeural"),
            ("English (India) — Neerja", "en-IN-NeerjaNeural"),
        ],
        format_func=lambda x: x[0],
    )[1]

    always_kn_subs = st.checkbox("Always show Kannada subtitles (auto-translates English lines)", value=True)

if st.button("1. Generate Storyboard & Kannada Subtitles", type="primary", use_container_width=True):
    beats = split_into_story_beats(script_input)
    if not beats:
        st.error("Please write at least one line in the script.")
    else:
        motions = ["zoom_in", "pan_right", "ken_burns_diag", "zoom_out", "pan_left"]
        built_scenes = []
        prog = st.progress(0.0, text="Preparing scenes...")

        for idx, beat in enumerate(beats):
            prog.progress(idx / len(beats), text=f"Generating scene {idx + 1}/{len(beats)}...")
            kn_text = translate_to_kannada(beat) if always_kn_subs else beat
            visual_prompt = f"{beat}. Story setting: {style_desc}"
            img_path = os.path.join(st.session_state.work_dir, f"sc_{idx}_{random.randint(1000,9999)}.jpg")
            fetch_scene_image(
                visual_prompt=visual_prompt,
                width=res_w,
                height=res_h,
                out_path=img_path,
                seed=500 + idx * 41,
            )
            built_scenes.append(
                {
                    "scene_label": f"ದೃಶ್ಯ {idx + 1} / Scene {idx + 1}",
                    "raw_line": beat,
                    "subtitle_kn": kn_text,
                    "narration_kn": kn_text,
                    "visual_prompt": visual_prompt,
                    "motion": motions[idx % len(motions)],
                    "duration": 5.0,
                    "image_path": img_path,
                }
            )

        prog.progress(1.0, text="Storyboard created!")
        st.session_state.scenes = built_scenes
        st.session_state.video_bytes = None
        st.rerun()

# ===========================================================================
# SCENE EDITOR
# ===========================================================================
if st.session_state.scenes:
    st.divider()
    st.subheader("2. Edit Scenes (Kannada Subtitles, Voice Text, Visual Prompt, Image & Motion)")

    motion_opts = ["zoom_in", "zoom_out", "pan_right", "pan_left", "ken_burns_diag"]
    delete_idx = None
    swap_idx = None

    for idx, sc in enumerate(st.session_state.scenes):
        with st.expander(f"Scene {idx + 1}: {sc['subtitle_kn']}", expanded=True):
            c1, c2 = st.columns([1, 1.8])

            with c1:
                if os.path.exists(sc["image_path"]):
                    st.image(sc["image_path"], use_container_width=True)

                b_regen, b_kn = st.columns(2)
                with b_regen:
                    if st.button("New AI Image", key=f"img_btn_{idx}", use_container_width=True):
                        np_path = os.path.join(st.session_state.work_dir, f"regen_{idx}_{random.randint(1000,99999)}.jpg")
                        fetch_scene_image(
                            visual_prompt=sc["visual_prompt"],
                            width=res_w,
                            height=res_h,
                            out_path=np_path,
                            seed=random.randint(1, 999999),
                        )
                        st.session_state.scenes[idx]["image_path"] = np_path
                        st.rerun()
                with b_kn:
                    if st.button("Re-Translate KN", key=f"kn_btn_{idx}", use_container_width=True):
                        kn = translate_to_kannada(sc["subtitle_kn"] or sc["raw_line"])
                        st.session_state.scenes[idx]["subtitle_kn"] = kn
                        st.session_state.scenes[idx]["narration_kn"] = kn
                        st.rerun()

                up = st.file_uploader("Upload Custom Image", type=["png", "jpg", "jpeg", "webp"], key=f"up_{idx}")
                if up is not None:
                    ext = os.path.splitext(up.name)[1] or ".png"
                    up_path = os.path.join(st.session_state.work_dir, f"custom_{idx}_{random.randint(1000,9999)}{ext}")
                    with open(up_path, "wb") as f:
                        f.write(up.getbuffer())
                    st.session_state.scenes[idx]["image_path"] = up_path

            with c2:
                sc["subtitle_kn"] = st.text_area("Kannada Subtitle on Video", value=sc["subtitle_kn"], height=70, key=f"sub_{idx}")
                sc["narration_kn"] = st.text_area("Kannada Voiceover Text", value=sc["narration_kn"], height=65, key=f"nar_{idx}")
                sc["visual_prompt"] = st.text_input("Scene Image Prompt (English works best)", value=sc["visual_prompt"], key=f"vp_{idx}")

                m_col, d_col = st.columns(2)
                with m_col:
                    sc["motion"] = st.selectbox(
                        "Camera Animation",
                        motion_opts,
                        index=motion_opts.index(sc["motion"]) if sc["motion"] in motion_opts else 0,
                        key=f"mot_{idx}",
                    )
                with d_col:
                    sc["duration"] = st.slider("Minimum Scene Seconds", 2.0, 12.0, float(sc["duration"]), 0.5, key=f"dur_{idx}")

                o1, o2, o3 = st.columns(3)
                with o1:
                    if idx > 0 and st.button("Move Up", key=f"up_b_{idx}", use_container_width=True):
                        swap_idx = (idx, idx - 1)
                with o2:
                    if idx < len(st.session_state.scenes) - 1 and st.button("Move Down", key=f"dn_b_{idx}", use_container_width=True):
                        swap_idx = (idx, idx + 1)
                with o3:
                    if len(st.session_state.scenes) > 1 and st.button("Remove Scene", key=f"rm_b_{idx}", use_container_width=True):
                        delete_idx = idx

    if swap_idx:
        a, b = swap_idx
        st.session_state.scenes[a], st.session_state.scenes[b] = st.session_state.scenes[b], st.session_state.scenes[a]
        st.rerun()
    if delete_idx is not None:
        st.session_state.scenes.pop(delete_idx)
        st.rerun()

    # =======================================================================
    # RENDER VIDEO
    # =======================================================================
    st.divider()
    if st.button("3. Render Animated Video with Kannada Voice & Subtitles", type="primary", use_container_width=True):
        out_path = os.path.join(st.session_state.work_dir, f"output_{random.randint(1000,9999)}.mp4")
        r_prog = st.progress(0.0, text="Rendering video...")
        vid_file, warns = render_story_video(
            scenes=st.session_state.scenes,
            workdir=st.session_state.work_dir,
            out_mp4=out_path,
            resolution=(res_w, res_h),
            enable_audio=enable_audio,
            voice=voice_choice,
            progress_cb=lambda p, msg: r_prog.progress(p, text=msg),
        )
        with open(vid_file, "rb") as f:
            st.session_state.video_bytes = f.read()
        st.session_state.render_warnings = warns

    for w in st.session_state.render_warnings:
        st.warning(w)

    if st.session_state.video_bytes:
        st.success("Final video rendered!")
        st.video(st.session_state.video_bytes)
        st.download_button(
            label="Download MP4",
            data=st.session_state.video_bytes,
            file_name="forest_survival_kannada.mp4",
            mime="video/mp4",
            use_container_width=True,
        )
