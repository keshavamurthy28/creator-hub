import os
import random
import tempfile
import streamlit as st
from creator_hub_hf import (
    generate_hf_scene_image,
    get_preset_scenes,
    render_video_from_scenes,
    split_custom_lines,
    translate_to_kannada,
)

st.set_page_config(page_title="Creator Hub — Video Studio (Hugging Face)", layout="wide")

if "work_dir" not in st.session_state:
    st.session_state.work_dir = tempfile.mkdtemp(prefix="ch_hf_")
if "scenes" not in st.session_state:
    st.session_state.scenes = []
if "video_bytes" not in st.session_state:
    st.session_state.video_bytes = None
if "notes" not in st.session_state:
    st.session_state.notes = []

st.title("Creator Hub — Animated Video Studio")
st.caption("Uses one Hugging Face API token (HF_TOKEN) for AI scene art + free Kannada voiceover, Kannada translation & scene editing.")

# Sidebar: Single API configuration
with st.sidebar:
    st.header("API & Render Settings")
    default_hf = os.getenv("HF_TOKEN", "")
    hf_token = st.text_input("Hugging Face Token (HF_TOKEN)", value=default_hf, type="password", help="Get a token from huggingface.co/settings/tokens")
    hf_model = st.selectbox(
        "Image Model",
        [
            "black-forest-labs/FLUX.1-schnell",
            "stabilityai/stable-diffusion-xl-base-1.0",
        ],
    )
    fmt = st.selectbox("Aspect Ratio", ["16:9 Landscape (1280x720)", "9:16 Reels/Shorts (720x1280)"])
    w, h = (1280, 720) if fmt.startswith("16:9") else (720, 1280)

    enable_audio = st.checkbox("Enable Voiceover", value=True)
    voice = st.selectbox(
        "Narrator Voice",
        [("Kannada — Sapna", "kn-IN-SapnaNeural"), ("Kannada — Gagan", "kn-IN-GaganNeural"), ("English — Neerja", "en-IN-NeerjaNeural")],
        format_func=lambda x: x[0],
    )[1]

mode = st.radio(
    "Story Source",
    ["Hanuman Story (5 Chapters)", "Forest Survival Story (5 Chapters)", "Custom Script"],
    horizontal=True,
)

custom_script = ""
custom_style = ""
if mode == "Custom Script":
    custom_script = st.text_area("Enter Script Lines (English or Kannada)", height=130, placeholder="Write each scene sentence on a new line...")
    custom_style = st.text_input("Visual Style Description", value="2d animated story, expressive characters, cinematic lighting, no text")

if st.button("1. Generate Storyboard Scenes", type="primary", use_container_width=True):
    if mode in ("Hanuman Story (5 Chapters)", "Forest Survival Story (5 Chapters)"):
        raw_items = get_preset_scenes(mode)
    else:
        lines = split_custom_lines(custom_script)
        if not lines:
            st.error("Please enter at least one script line.")
            raw_items = []
        else:
            motions = ["zoom_in", "pan_right", "ken_burns_diag", "zoom_out", "pan_left"]
            raw_items = [
                {
                    "chapter": f"ದೃಶ್ಯ {i + 1} / Scene {i + 1}",
                    "script": ln,
                    "prompt": f"{ln}, {custom_style}",
                    "motion": motions[i % len(motions)],
                    "duration": 4.5,
                }
                for i, ln in enumerate(lines)
            ]

    if raw_items:
        prog = st.progress(0.0, text="Generating scene images...")
        new_scenes = []
        new_notes = []
        for idx, item in enumerate(raw_items):
            prog.progress(idx / len(raw_items), text=f"Scene {idx + 1}/{len(raw_items)}...")
            img_p = os.path.join(st.session_state.work_dir, f"sc_{idx}_{random.randint(1000,9999)}.jpg")
            img_p, err = generate_hf_scene_image(item["prompt"], hf_token=hf_token, model_id=hf_model, width=w, height=h, out_path=img_p)
            if err:
                new_notes.append(err)
            new_scenes.append(
                {
                    "chapter": item["chapter"],
                    "script": item["script"],
                    "subtitle_kn": translate_to_kannada(item["script"]),
                    "prompt": item["prompt"],
                    "motion": item["motion"],
                    "duration": item["duration"],
                    "image_path": img_p,
                }
            )
        prog.progress(1.0, text="Storyboard ready!")
        st.session_state.scenes = new_scenes
        st.session_state.notes = new_notes
        st.session_state.video_bytes = None
        st.rerun()

for n in st.session_state.notes:
    st.info(n)

if st.session_state.scenes:
    st.divider()
    st.subheader("2. Edit Scenes")
    motions = ["zoom_in", "zoom_out", "pan_right", "pan_left", "ken_burns_diag"]

    for i, sc in enumerate(st.session_state.scenes):
        with st.expander(f"{sc['chapter']} — {sc['subtitle_kn'][:45]}", expanded=True):
            c1, c2 = st.columns([1, 1.8])
            with c1:
                st.image(sc["image_path"], use_container_width=True)
                if st.button("Regenerate Scene Image", key=f"regen_{i}", use_container_width=True):
                    np = os.path.join(st.session_state.work_dir, f"re_{i}_{random.randint(1000,99999)}.jpg")
                    np, err = generate_hf_scene_image(sc["prompt"], hf_token=hf_token, model_id=hf_model, width=w, height=h, out_path=np)
                    if err:
                        st.warning(err)
                    st.session_state.scenes[i]["image_path"] = np
                    st.rerun()
            with c2:
                sc["subtitle_kn"] = st.text_area("Kannada Subtitle & Narration", value=sc["subtitle_kn"], height=70, key=f"kn_{i}")
                sc["prompt"] = st.text_input("Image Prompt (English)", value=sc["prompt"], key=f"pr_{i}")
                sc["motion"] = st.selectbox("Camera Motion", motions, index=motions.index(sc["motion"]), key=f"mo_{i}")
                sc["duration"] = st.slider("Duration (sec)", 2.5, 10.0, float(sc["duration"]), 0.5, key=f"du_{i}")

    st.divider()
    if st.button("3. Render Final Video", type="primary", use_container_width=True):
        out_p = os.path.join(st.session_state.work_dir, f"final_{random.randint(1000,9999)}.mp4")
        rprog = st.progress(0.0, text="Rendering final video...")
        vid_p, warns = render_video_from_scenes(
            scenes=st.session_state.scenes,
            workdir=st.session_state.work_dir,
            out_mp4=out_p,
            width=w,
            height=h,
            enable_audio=enable_audio,
            voice=voice,
            progress_cb=lambda p, m: rprog.progress(p, text=m),
        )
        for warn in warns:
            st.warning(warn)
        with open(vid_p, "rb") as f:
            st.session_state.video_bytes = f.read()

    if st.session_state.video_bytes:
        st.success("Your video is ready!")
        st.video(st.session_state.video_bytes)
        st.download_button(
            "Download MP4",
            data=st.session_state.video_bytes,
            file_name="creator_hub_video.mp4",
            mime="video/mp4",
            use_container_width=True,
        )
