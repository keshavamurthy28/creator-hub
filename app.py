import os
import tempfile
import textwrap
import time
from google import genai
from google.genai import types
from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="YouTube Creator Growth Studio",
    page_icon="🎬",
    layout="wide",
)

st.markdown(
    """
    <style>
    .level-header {
        color: #F5C518;
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize session state stores
if "level_mind_words" not in st.session_state:
    st.session_state["level_mind_words"] = {}
if "all_level_outputs" not in st.session_state:
    st.session_state["all_level_outputs"] = {}
if "video_scenes" not in st.session_state:
    st.session_state["video_scenes"] = [
        {
            "spot": 1,
            "title": "Opening Hook",
            "duration": 6,
            "text": "Most beginners stay stuck in life wisdom because they consume advice without applying one habit.",
            "bg_color": "#141824",
            "image_bytes": None,
            "image_name": None,
            "audio_bytes": None,
            "audio_name": None,
            "audio_volume": 0.6,
        },
        {
            "spot": 2,
            "title": "Core Lesson",
            "duration": 8,
            "text": "Pick one practical mindset shift this week, test it daily, and track what actually changes.",
            "bg_color": "#1B2232",
            "image_bytes": None,
            "image_name": None,
            "audio_bytes": None,
            "audio_name": None,
            "audio_volume": 0.6,
        },
    ]
if "rendered_video_bytes" not in st.session_state:
    st.session_state["rendered_video_bytes"] = None

# 2. Sidebar - API Key, Channel Profile & Level Navigation
with st.sidebar:
    st.title("🎬 Creator Control Panel")

    default_api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    if default_api_key:
        st.success("Gemini API Key loaded from Secrets")
        api_key = default_api_key
    else:
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="Paste API key or add to Streamlit Secrets",
        )

    preferred_model = st.selectbox(
        "Primary Gemini Model",
        ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-4-hydrogen"],
        index=0,
    )

    st.divider()
    st.markdown("Customize your channel details below:")
    channel_topic = st.text_input(
        "Channel Niche / Topic",
        placeholder="e.g., Personal Finance, Life Wisdom",
    )
    target_audience = st.text_input(
        "Target Audience",
        placeholder="e.g., Beginners, Young Professionals",
    )
    video_format = st.selectbox(
        "Primary Format",
        ["Long-form Videos", "YouTube Shorts", "Both Long-form & Shorts"],
    )

    st.divider()

    level_keys = [
        "Level 1: Full Channel Plan",
        "Level 2: Pick a Niche",
        "Level 3: Viral Scripts, Hooks & Thumbnails",
        "Level 4: Growth & Algorithm",
        "Level 5: Produce Videos 3x Faster",
        "Level 6: Monetization Plan",
        "Level 7: Read Analytics Like a Pro",
    ]

    selected_level = st.radio(
        "Select Your Creator Level:",
        level_keys,
    )

context_addon = ""
if channel_topic or target_audience:
    context_addon = (
        f"\n\nMy Channel Context:\n"
        f"- Niche/Topic: {channel_topic or 'Not specified'}\n"
        f"- Target Audience: {target_audience or 'General audience'}\n"
        f"- Format: {video_format}"
    )

# 3. Data Dictionary for All 7 Levels
levels_data = {
    "Level 1: Full Channel Plan": {
        "title": "1. Your Full Channel Plan",
        "role": "Expert YouTube Strategist & Monetization Consultant",
        "goal": "Build a complete roadmap from zero to monetization.",
        "mind_placeholder": "Type raw thoughts about your available time, budget, language, comfort on camera, or long-term vision...",
        "prompt": (
            "Act as an expert YouTube strategist and monetization consultant. Develop a comprehensive plan for launching a YouTube channel from scratch and working toward monetization.\n"
            "Evaluate my niche, target audience, competitors, available resources, and long-term goals.\n"
            "Create a detailed strategy covering channel positioning, content pillars, video formats, publishing schedules, audience growth, viewer retention, monetization opportunities, and a practical weekly action plan."
        ),
    },
    "Level 2: Pick a Niche": {
        "title": "2. Pick a Niche",
        "role": "YouTube Market Researcher & Channel Strategist",
        "goal": "Find a profitable niche and generate 100 ranked video ideas.",
        "mind_placeholder": "Type sub-topics you naturally enjoy thinking/talking about, specific struggles people face, or angles you want to avoid...",
        "prompt": (
            "Act as an experienced YouTube market researcher and channel strategist.\n"
            "Help me choose a profitable YouTube niche with strong audience demand and long-term growth potential.\n"
            "Evaluate competition, search opportunities, monetization potential, content sustainability, and ways to stand out.\n"
            "Develop a unique channel identity, define my ideal viewer, recommend content categories, and generate 100 video ideas ranked by their potential to attract an audience."
        ),
    },
    "Level 3: Viral Scripts, Hooks & Thumbnails": {
        "title": "3. Create Viral Scripts, Hooks, and Thumbnails",
        "role": "Elite YouTube Content Strategist & Video Producer",
        "goal": "Maximize Click-Through Rate (CTR) and average view duration.",
        "mind_placeholder": "Type raw hook lines, story examples, emotional angles, or specific points you want woven into the script...",
        "prompt": (
            "Act as an elite YouTube content strategist and video producer.\n"
            "Develop a complete content creation framework designed to improve click-through rates and audience retention.\n"
            "Generate compelling video ideas, attention-grabbing hooks, engaging titles, thumbnail concepts, opening sequences, storytelling structures, retention strategies, calls to action, and complete video scripts.\n"
            "Explain why each concept could attract viewers, maintain their attention, and encourage them to watch until the end."
        ),
    },
    "Level 4: Growth & Algorithm": {
        "title": "4. Understand YouTube Growth and Algorithm",
        "role": "YouTube Growth Strategist",
        "goal": "Master impressions, CTR, watch time, and converting viewers into subscribers.",
        "mind_placeholder": "Type questions about impressions, browse vs. search traffic, upload rhythm, or where viewers usually drop off...",
        "prompt": (
            "Act as a YouTube growth strategist with expertise in content discovery and audience behavior.\n"
            "Explain how YouTube growth works, including impressions, click-through rates, watch time, audience retention, returning viewers, suggested videos, search traffic, and recommendation systems.\n"
            "Build a practical growth strategy covering upload frequency, content testing, performance optimization, audience engagement, and methods for converting viewers into subscribers."
        ),
    },
    "Level 5: Produce Videos 3x Faster": {
        "title": "5. Produce Videos 3x Faster",
        "role": "Professional YouTube Production Manager",
        "goal": "Build an AI-assisted workflow and repurpose content across Shorts/Reels.",
        "mind_placeholder": "Type which part slows you down most (scripting, voiceover, editing, thumbnails, or Shorts repurposing) and tools you prefer...",
        "prompt": (
            "Act as a professional YouTube production manager.\n"
            "Design an AI-assisted workflow that helps me create high-quality YouTube videos more efficiently.\n"
            "Develop streamlined processes for topic research, scriptwriting, voiceovers, filming, editing, thumbnail design, publishing, performance analysis, and repurposing content for YouTube Shorts, TikTok, Instagram Reels, and other platforms.\n"
            "Recommend useful AI tools, repeatable workflows, production templates, and quality-control checklists to reduce unnecessary work while maintaining content quality."
        ),
    },
    "Level 6: Monetization Plan": {
        "title": "6. Build Your Monetization Plan",
        "role": "Creator Business Strategist",
        "goal": "Diversify revenue beyond ads (affiliates, sponsorships, digital products).",
        "mind_placeholder": "Type income ideas you like (guides, templates, books, coaching, sponsorships) and your timeline expectations...",
        "prompt": (
            "Act as a creator business strategist specializing in YouTube monetization.\n"
            "Develop a comprehensive revenue strategy for my YouTube channel.\n"
            "Include preparation for the YouTube Partner Program, advertising revenue, affiliate marketing, brand sponsorships, digital products, online courses, paid memberships, newsletters, communities, and additional income opportunities.\n"
            "Explain the requirements, advantages, limitations, and ideal timing for introducing each monetization method as my channel develops."
        ),
    },
    "Level 7: Read Analytics Like a Pro": {
        "title": "7. Read Your Analytics Like a Pro",
        "role": "Experienced YouTube Data Analyst",
        "goal": "Diagnose underperforming videos and build weekly/monthly review frameworks.",
        "mind_placeholder": "Type observations from your recent videos, retention dips, comment feedback, or what surprised you in analytics...",
        "prompt": (
            "Act as an experienced YouTube data analyst.\n"
            "Create a comprehensive system for monitoring, evaluating, and improving my channel's performance.\n"
            "Analyze essential metrics, including impressions, click-through rate (CTR), average view duration, audience retention, subscriber conversion, traffic sources, engagement, and revenue.\n"
            "Develop weekly and monthly performance review frameworks to identify successful content patterns, understand why certain videos underperform, and recommend specific improvements.\n"
            "Help me use these insights to make better content decisions and build a more effective long-term growth strategy."
        ),
    },
}


def build_prompt_for_level(lvl_key: str, current_mind_text: str = "") -> str:
    lvl_info = levels_data[lvl_key]
    details = ""

    if lvl_key == "Level 3: Viral Scripts, Hooks & Thumbnails":
        v_topic = st.session_state.get(f"video_topic_{lvl_key}", "")
        if v_topic:
            details += f"\n- Specific Video Topic: {v_topic}"

    elif lvl_key == "Level 7: Read Analytics Like a Pro":
        c_val = st.session_state.get("analytics_ctr", 4.5)
        a_val = st.session_state.get("analytics_avd", "")
        v_val = st.session_state.get("analytics_views", 500)
        details += (
            f"\n- Current Metrics: CTR is {c_val}%, "
            f"Avg View Duration is {a_val or 'N/A'}, Avg Views: {v_val}"
        )

    saved_mind = current_mind_text if current_mind_text else st.session_state["level_mind_words"].get(lvl_key, "")
    if saved_mind.strip():
        details += f"\n- My Mind Words / Personal Notes for This Level:\n{saved_mind.strip()}"

    return lvl_info["prompt"] + context_addon + details


def generate_with_fallback(client: genai.Client, prompt_text: str, primary_model: str, status_box):
    all_models = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-4-hydrogen"]
    ordered_models = [primary_model] + [m for m in all_models if m != primary_model]

    last_err = None
    for m_name in ordered_models:
        for attempt in range(2):
            status_box.write(f"Running `{m_name}` (attempt {attempt + 1}/2)...")
            try:
                res = client.models.generate_content(
                    model=m_name,
                    contents=prompt_text,
                )
                return res.text, m_name, None
            except Exception as exc:
                last_err = exc
                status_box.write(f"`{m_name}` attempt {attempt + 1} issue: {exc}")
                if attempt == 0:
                    time.sleep(1)
                    continue
                break
    return None, None, last_err


def hex_to_rgb(hex_str: str):
    cleaned = hex_str.lstrip("#")
    if len(cleaned) != 6:
        return (20, 24, 36)
    return tuple(int(cleaned[i : i + 2], 16) for i in (0, 2, 4))


def create_scene_frame_image(scene: dict, width: int, height: int, temp_dir: str) -> str:
    bg_rgb = hex_to_rgb(scene.get("bg_color", "#141824"))
    canvas = Image.new("RGB", (width, height), bg_rgb)

    if scene.get("image_bytes"):
        img_path = os.path.join(temp_dir, f"src_img_{scene['spot']}.png")
        with open(img_path, "wb") as f:
            f.write(scene["image_bytes"])
        uploaded_img = Image.open(img_path).convert("RGB")
        # Fit uploaded image nicely in upper/center area
        max_w = int(width * 0.78)
        max_h = int(height * 0.48)
        uploaded_img.thumbnail((max_w, max_h))
        x_pos = (width - uploaded_img.width) // 2
        y_pos = int(height * 0.14)
        canvas.paste(uploaded_img, (x_pos, y_pos))
        text_y_start = y_pos + uploaded_img.height + 36
    else:
        text_y_start = int(height * 0.28)

    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    spot_label = f"Spot {scene['spot']} — {scene.get('title', 'Scene')}"
    draw.text((60, 40), spot_label, fill=(245, 197, 24), font=font)

    wrapped_lines = textwrap.wrap(scene.get("text", ""), width=55)
    cur_y = text_y_start
    for line in wrapped_lines[:10]:
        if cur_y > height - 60:
            break
        draw.text((60, cur_y), line, fill=(245, 245, 245), font=font)
        cur_y += 22

    out_frame_path = os.path.join(temp_dir, f"frame_spot_{scene['spot']}.png")
    canvas.save(out_frame_path)
    return out_frame_path


def render_scenes_to_mp4(scenes: list, resolution_choice: str) -> bytes:
    if resolution_choice == "Vertical Shorts (1080x1920)":
        w, h = 1080, 1920
    else:
        w, h = 1280, 720

    clips = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for scene in scenes:
            dur = max(2, int(scene.get("duration", 6)))
            frame_file = create_scene_frame_image(scene, w, h, tmpdir)
            img_clip = ImageClip(frame_file).with_duration(dur)

            if scene.get("audio_bytes"):
                ext = ".wav" if (scene.get("audio_name") or "").lower().endswith(".wav") else ".mp3"
                aud_path = os.path.join(tmpdir, f"audio_spot_{scene['spot']}{ext}")
                with open(aud_path, "wb") as af:
                    af.write(scene["audio_bytes"])
                try:
                    aud_clip = AudioFileClip(aud_path)
                    vol = float(scene.get("audio_volume", 0.6))
                    aud_clip = aud_clip.with_volume_scaled(vol)
                    if aud_clip.duration > dur:
                        aud_clip = aud_clip.subclipped(0, dur)
                    img_clip = img_clip.with_audio(aud_clip)
                except Exception:
                    pass

            clips.append(img_clip)

        final_video = concatenate_videoclips(clips, method="compose")
        out_mp4 = os.path.join(tmpdir, "final_youtube_video.mp4")
        has_audio = any(s.get("audio_bytes") for s in scenes)
        final_video.write_videofile(
            out_mp4,
            fps=24,
            codec="libx264",
            audio_codec="aac" if has_audio else None,
            logger=None,
        )

        with open(out_mp4, "rb") as vf:
            mp4_data = vf.read()

        final_video.close()
        for c in clips:
            c.close()

        return mp4_data


# 4. Main Display Area
current_data = levels_data[selected_level]

st.markdown(f'<div class="level-header">{current_data["title"]}</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.info(f"**AI Persona:** {current_data['role']}")
with col2:
    st.success(f"**Primary Objective:** {current_data['goal']}")

# Level-Specific Extra Inputs + Per-Level "My Mind Words" Box
st.subheader("🎯 Customize This Level")

if selected_level == "Level 3: Viral Scripts, Hooks & Thumbnails":
    st.text_input(
        "Specific Video Topic for Script/Hook:",
        placeholder="e.g., 5 Habits That Changed My Life",
        key=f"video_topic_{selected_level}",
    )

elif selected_level == "Level 7: Read Analytics Like a Pro":
    c1, c2, c3 = st.columns(3)
    c1.number_input("Current CTR (%)", min_value=0.0, max_value=100.0, value=4.5, step=0.1, key="analytics_ctr")
    c2.text_input("Avg View Duration", placeholder="e.g., 3:45 out of 10:00", key="analytics_avd")
    c3.number_input("Avg Views per Video", min_value=0, value=500, step=50, key="analytics_views")

existing_mind_words = st.session_state["level_mind_words"].get(selected_level, "")
mind_words = st.text_area(
    "💭 My Mind Words (Type any raw thoughts, ideas, or custom notes for this level — auto-updates the prompt)",
    value=existing_mind_words,
    height=110,
    placeholder=current_data["mind_placeholder"],
    key=f"mind_words_input_{selected_level}",
)
st.session_state["level_mind_words"][selected_level] = mind_words

# 5. Live Prompt Preview & Automated Generation Controls
final_prompt = build_prompt_for_level(selected_level, mind_words)

with st.expander("📋 View / Copy Auto-Updated Prompt", expanded=False):
    st.code(final_prompt, language="markdown")

btn_col1, btn_col2 = st.columns(2)
run_single = btn_col1.button("🚀 Generate Selected Level", type="primary", use_container_width=True)
run_all_seven = btn_col2.button("⚡ Automate All 7 Levels Now", use_container_width=True)

if run_single:
    if not api_key:
        st.error("Please enter a Gemini API key or add `GEMINI_API_KEY` to your Streamlit Secrets.")
    else:
        with st.status(f"Generating {current_data['title']}...", expanded=True) as status:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=25000),
            )
            out_text, used_m, err = generate_with_fallback(client, final_prompt, preferred_model, status)
            if out_text:
                status.update(label=f"Completed {current_data['title']} using {used_m}!", state="complete", expanded=False)
                st.session_state["all_level_outputs"][selected_level] = {
                    "title": current_data["title"],
                    "model": used_m,
                    "content": out_text,
                }
                st.session_state["last_output"] = out_text
                st.session_state["last_level"] = f"{current_data['title']} ({used_m})"
            else:
                status.update(label="Generation failed", state="error", expanded=True)
                st.error(f"Could not complete generation. Details: {err}")

if run_all_seven:
    if not api_key:
        st.error("Please enter a Gemini API key or add `GEMINI_API_KEY` to your Streamlit Secrets.")
    else:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=25000),
        )
        progress_bar = st.progress(0.0)
        with st.status("Automating all 7 YouTube Creator levels back-to-back...", expanded=True) as status:
            for idx, lvl_key in enumerate(level_keys, start=1):
                lvl_title = levels_data[lvl_key]["title"]
                status.write(f"--- Starting {lvl_title} ({idx}/7) ---")
                lvl_prompt = build_prompt_for_level(lvl_key)
                out_text, used_m, err = generate_with_fallback(client, lvl_prompt, preferred_model, status)

                if out_text:
                    st.session_state["all_level_outputs"][lvl_key] = {
                        "title": lvl_title,
                        "model": used_m,
                        "content": out_text,
                    }
                    st.session_state["last_output"] = out_text
                    st.session_state["last_level"] = f"{lvl_title} ({used_m})"
                    status.write(f"✅ Finished {lvl_title} via `{used_m}`")
                else:
                    status.write(f"⚠️ Skipped {lvl_title} due to error: {err}")

                progress_bar.progress(idx / len(level_keys))

            completed_count = len(st.session_state["all_level_outputs"])
            status.update(
                label=f"Automation complete! {completed_count}/7 levels generated.",
                state="complete",
                expanded=False,
            )

# 6. Combined Full Playbook Download + Outputs Display
all_outputs = st.session_state.get("all_level_outputs", {})
if all_outputs:
    combined_md_parts = [
        "# Complete 7-Level YouTube Creator Playbook",
        f"- **Channel Niche / Topic:** {channel_topic or 'Not specified'}",
        f"- **Target Audience:** {target_audience or 'General audience'}",
        f"- **Primary Format:** {video_format}",
        "",
        "---",
    ]
    for lvl_key in level_keys:
        if lvl_key in all_outputs:
            item = all_outputs[lvl_key]
            combined_md_parts.append(f"\n## {item['title']} *(Model: {item['model']})*\n")
            combined_md_parts.append(item["content"])
            combined_md_parts.append("\n---\n")

    combined_markdown = "\n".join(combined_md_parts)

    st.divider()
    st.subheader("📦 Complete Automated Playbook")
    st.download_button(
        label=f"⬇️ Download All {len(all_outputs)} Completed Levels (.md)",
        data=combined_markdown,
        file_name="youtube_7_level_complete_playbook.md",
        mime="text/markdown",
        type="primary",
    )

if "last_output" in st.session_state:
    st.subheader(f"✨ Latest Output: {st.session_state.get('last_level', selected_level)}")
    st.markdown(st.session_state["last_output"])
    st.download_button(
        label="⬇️ Download Latest Level (.md)",
        data=st.session_state["last_output"],
        file_name=f"{selected_level.lower().replace(' ', '_').replace(':', '')}.md",
        mime="text/markdown",
    )

# 7. Filter, Select, Edit & Assemble Video Spots
st.divider()
st.subheader("🎞️ Video Scene & Media Studio (Filter, Edit, Insert Media & Export .mp4)")

available_levels = list(all_outputs.keys())
if available_levels:
    filter_query = st.text_input(
        "Filter Generated Levels by Keyword:",
        placeholder="e.g., hook, script, retention, pillar, monetization",
    )
    filtered_levels = [
        k
        for k in available_levels
        if not filter_query.strip()
        or filter_query.lower() in k.lower()
        or filter_query.lower() in all_outputs[k]["content"].lower()
    ]

    if filtered_levels:
        chosen_source_level = st.selectbox("Select Generated Level to Inspect or Split into Spots:", filtered_levels)
        source_text = all_outputs[chosen_source_level]["content"]
        st.text_area("Editable Source Draft (Edit text before turning into spots):", value=source_text, height=160, key="editable_source_draft")

        split_col1, split_col2 = st.columns(2)
        if split_col1.button("➕ Add New Spot at End"):
            next_spot_num = len(st.session_state["video_scenes"]) + 1
            st.session_state["video_scenes"].append(
                {
                    "spot": next_spot_num,
                    "title": f"Spot {next_spot_num}",
                    "duration": 6,
                    "text": st.session_state.get("editable_source_draft", "")[:240],
                    "bg_color": "#141824",
                    "image_bytes": None,
                    "image_name": None,
                    "audio_bytes": None,
                    "audio_name": None,
                    "audio_volume": 0.6,
                }
            )
            st.rerun()

        if split_col2.button("✂️ Auto-Create 3 Spots from Editable Draft"):
            raw_draft = st.session_state.get("editable_source_draft", "").strip()
            chunks = [p.strip() for p in raw_draft.split("\n\n") if p.strip()]
            picked_chunks = chunks[:3] if len(chunks) >= 3 else (raw_draft or "Life wisdom point").split(". ")[:3]
            new_scenes = []
            for idx, part in enumerate(picked_chunks, start=1):
                new_scenes.append(
                    {
                        "spot": idx,
                        "title": f"Scene {idx} ({chosen_source_level.split(':')[0]})",
                        "duration": 7,
                        "text": part[:350],
                        "bg_color": "#141824" if idx % 2 == 1 else "#1D2436",
                        "image_bytes": None,
                        "image_name": None,
                        "audio_bytes": None,
                        "audio_name": None,
                        "audio_volume": 0.6,
                    }
                )
            if new_scenes:
                st.session_state["video_scenes"] = new_scenes
                st.rerun()
    else:
        st.warning("No generated levels match your filter keyword.")
else:
    st.info("Generate at least one level above to filter and pull text into video spots—or edit your starter spots directly below.")

# Spot-by-Spot Editor (Text, Image & Audio/Song/SFX at Specific Spots)
st.markdown("### 🧩 Spot-by-Spot Timeline Editor")
for idx, scene in enumerate(st.session_state["video_scenes"]):
    with st.expander(f"Spot {idx + 1}: {scene.get('title', 'Scene')} ({scene.get('duration', 6)}s)", expanded=(idx == 0)):
        sc1, sc2, sc3 = st.columns([2, 1, 1])
        scene["title"] = sc1.text_input("Spot Label", value=scene.get("title", f"Spot {idx + 1}"), key=f"spot_title_{idx}")
        scene["duration"] = sc2.number_input("Duration (sec)", min_value=2, max_value=60, value=int(scene.get("duration", 6)), key=f"spot_dur_{idx}")
        scene["bg_color"] = sc3.text_input("Background Hex", value=scene.get("bg_color", "#141824"), key=f"spot_bg_{idx}")

        scene["text"] = st.text_area("On-Screen / Narration Text for This Spot", value=scene.get("text", ""), height=90, key=f"spot_text_{idx}")

        m1, m2, m3 = st.columns([2, 2, 1])
        img_file = m1.file_uploader(f"Insert Image at Spot {idx + 1}", type=["png", "jpg", "jpeg"], key=f"spot_img_{idx}")
        if img_file is not None:
            scene["image_bytes"] = img_file.getvalue()
            scene["image_name"] = img_file.name

        aud_file = m2.file_uploader(f"Insert Song / Sound / Voice at Spot {idx + 1}", type=["mp3", "wav", "m4a"], key=f"spot_aud_{idx}")
        if aud_file is not None:
            scene["audio_bytes"] = aud_file.getvalue()
            scene["audio_name"] = aud_file.name

        scene["audio_volume"] = m3.slider("Audio Vol", min_value=0.0, max_value=1.5, value=float(scene.get("audio_volume", 0.6)), step=0.1, key=f"spot_vol_{idx}")

        if scene.get("image_name"):
            st.caption(f"🖼️ Attached Image: `{scene['image_name']}`")
        if scene.get("audio_name"):
            st.caption(f"🎵 Attached Audio: `{scene['audio_name']}`")

        if len(st.session_state["video_scenes"]) > 1:
            if st.button(f"🗑️ Remove Spot {idx + 1}", key=f"del_spot_{idx}"):
                st.session_state["video_scenes"].pop(idx)
                st.rerun()

# Re-number spots cleanly
for i, s in enumerate(st.session_state["video_scenes"], start=1):
    s["spot"] = i

# Render & Download Final Video
st.markdown("### 🎬 Finalize, Preview & Download Video")
res_choice = st.selectbox("Output Format:", ["Landscape Long-Form (1280x720)", "Vertical Shorts (1080x1920)"])

if st.button("🎥 Render Final Video (.mp4)", type="primary"):
    with st.status("Rendering your video spots, images, and audio...", expanded=True) as v_status:
        try:
            mp4_bytes = render_scenes_to_mp4(st.session_state["video_scenes"], res_choice)
            st.session_state["rendered_video_bytes"] = mp4_bytes
            v_status.update(label="Video rendered successfully!", state="complete", expanded=False)
        except Exception as v_err:
            v_status.update(label="Video rendering failed", state="error", expanded=True)
            st.error(f"Could not render video: {v_err}")

if st.session_state.get("rendered_video_bytes"):
    st.video(st.session_state["rendered_video_bytes"])
    st.download_button(
        label="⬇️ Download Final Video (.mp4)",
        data=st.session_state["rendered_video_bytes"],
        file_name="youtube_creator_final_video.mp4",
        mime="video/mp4",
        type="primary",
    )

# Progress Tracker
st.divider()
level_number = int(selected_level.split(":")[0].replace("Level ", ""))
st.write(f"**Creator Journey Progress:** Level {level_number} of 7")
st.progress(level_number / 7)
