with t5:
    st.subheader("Image & Video Creation")

    img_col, vid_col = st.columns(2)

    with img_col:
        st.markdown("#### Create Scene Image")
        custom_img_prompt = st.text_input(
            "Scene Visual Prompt",
            "Farmer tending coconut palms and sugarcane field at sunrise",
            key="tab5_img_prompt",
        )
        custom_bg = st.selectbox(
            "Backdrop Tone",
            ["Morning Mist", "Warm Sunset", "Lush Green", "Night Sky"],
            key="tab5_bg",
        )
        if st.button("🖼️ Create Scene Image", key="tab5_create_img"):
            colors = {
                "Morning Mist": ((28, 46, 64), (144, 224, 196)),
                "Warm Sunset": ((58, 32, 26), (255, 186, 92)),
                "Lush Green": ((20, 48, 34), (138, 226, 128)),
                "Night Sky": ((16, 22, 44), (130, 185, 255)),
            }
            bg_rgb, fg_rgb = colors[custom_bg]
            card = Image.new("RGB", (1280, 720), bg_rgb)
            draw = ImageDraw.Draw(card)
            font_sub = load_subtitle_font(30)
            draw.rounded_rectangle([36, 36, 1244, 684], radius=18, outline=fg_rgb, width=3)
            draw.text((72, 76), f"CUSTOM SCENE  |  {custom_bg.upper()}", fill=fg_rgb)
            draw.text((72, 240), custom_img_prompt[:90], fill=(245, 248, 252), font=font_sub)
            st.session_state.scenes.append(card)
            st.session_state.scene_labels.append(custom_img_prompt[:48])
            st.success("Scene image added to timeline.")
            st.rerun()

    with vid_col:
        st.markdown("#### Create Video from Scenes")
        clip_motion = st.selectbox(
            "Clip Motion",
            ["Ken Burns Zoom-In", "Ken Burns Pan-Right", "Parallax Drift", "Static"],
            key="tab5_motion",
        )
        clip_fps = st.select_slider("Video FPS", options=[12, 24, 30], value=12, key="tab5_fps")
        if st.button("🎥 Create Video Now", type="primary", key="tab5_create_vid"):
            if not st.session_state.scenes:
                st.warning("Add or build at least one scene image first.")
            elif not HAS_IMAGEIO:
                st.error("`imageio` / `imageio-ffmpeg` is not installed in this environment.")
            else:
                with st.spinner("Creating video..."):
                    frames = []
                    for sc in st.session_state.scenes:
                        edited = apply_inshot_frame_edits(sc).resize((1280, 720))
                        frames.extend(build_motion_frames(edited, clip_motion, num_frames=8))
                    tmp_dir = tempfile.mkdtemp(prefix="kkm_tab5_vid_")
                    raw_mp4 = os.path.join(tmp_dir, "tab5_video.mp4")
                    iio.imwrite(raw_mp4, frames, fps=clip_fps, codec="libx264")
                    if st.session_state.generated_audio:
                        aud_path = os.path.join(tmp_dir, "voice.mp3")
                        mux_path = os.path.join(tmp_dir, "tab5_muxed.mp4")
                        with open(aud_path, "wb") as af:
                            af.write(st.session_state.generated_audio)
                        res = subprocess.run(
                            ["ffmpeg", "-y", "-i", raw_mp4, "-i", aud_path, "-c:v", "copy", "-c:a", "aac", "-shortest", mux_path],
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        target_file = mux_path if (res.returncode == 0 and os.path.exists(mux_path)) else raw_mp4
                    else:
                        target_file = raw_mp4
                    with open(target_file, "rb") as vf:
                        st.session_state.final_video_bytes = vf.read()
                    st.success("Video created and loaded in the top monitor.")
                    st.rerun()
