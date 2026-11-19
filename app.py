import os
import time
import streamlit as st
from google import genai
from google.genai import types

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

    # Put gemini-3.5-flash-lite first by default to avoid gemini-3.8-flash 503/504 stalls
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

# Progress Tracker
st.divider()
level_number = int(selected_level.split(":")[0].replace("Level ", ""))
st.write(f"**Creator Journey Progress:** Level {level_number} of 7")
st.progress(level_number / 7)
