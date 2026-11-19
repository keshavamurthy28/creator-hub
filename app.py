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

# Initialize per-level mind words storage in session state
if "level_mind_words" not in st.session_state:
    st.session_state["level_mind_words"] = {}

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
        ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-4-hydrogen"],
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

# 4. Main Display Area
current_data = levels_data[selected_level]

st.markdown(f'<div class="level-header">{current_data["title"]}</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.info(f"**AI Persona:** {current_data['role']}")
with col2:
    st.success(f"**Primary Objective:** {current_data['goal']}")

# Level-Specific Extra Inputs + Per-Level "My Mind Words" Box
extra_details = ""
st.subheader("🎯 Customize This Level")

if selected_level == "Level 3: Viral Scripts, Hooks & Thumbnails":
    video_topic = st.text_input(
        "Specific Video Topic for Script/Hook:",
        placeholder="e.g., 5 Habits That Changed My Life",
        key=f"video_topic_{selected_level}",
    )
    if video_topic:
        extra_details += f"\n- Specific Video Topic: {video_topic}"

elif selected_level == "Level 7: Read Analytics Like a Pro":
    c1, c2, c3 = st.columns(3)
    ctr = c1.number_input("Current CTR (%)", min_value=0.0, max_value=100.0, value=4.5, step=0.1, key="analytics_ctr")
    avd = c2.text_input("Avg View Duration", placeholder="e.g., 3:45 out of 10:00", key="analytics_avd")
    views = c3.number_input("Avg Views per Video", min_value=0, value=500, step=50, key="analytics_views")
    extra_details += (
        f"\n- Current Metrics: CTR is {ctr}%, "
        f"Avg View Duration is {avd or 'N/A'}, Avg Views: {views}"
    )

# Common "My Mind Words" input available on EVERY level and remembered per level
existing_mind_words = st.session_state["level_mind_words"].get(selected_level, "")
mind_words = st.text_area(
    "💭 My Mind Words (Type any raw thoughts, ideas, or custom notes for this level — auto-updates the prompt)",
    value=existing_mind_words,
    height=110,
    placeholder=current_data["mind_placeholder"],
    key=f"mind_words_input_{selected_level}",
)
st.session_state["level_mind_words"][selected_level] = mind_words

if mind_words.strip():
    extra_details += f"\n- My Mind Words / Personal Notes for This Level:\n{mind_words.strip()}"

# 5. Live Auto-Updating Prompt Preview & AI Generation
final_prompt = current_data["prompt"] + context_addon + extra_details

with st.expander("📋 View / Copy Auto-Updated Prompt", expanded=True):
    st.code(final_prompt, language="markdown")

if st.button("🚀 Generate AI Response Now", type="primary"):
    if not api_key:
        st.error("Please enter a Gemini API key or add `GEMINI_API_KEY` to your Streamlit Secrets.")
    else:
        fallback_models = [
            m for m in ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-4-hydrogen"]
            if m != preferred_model
        ]
        models_to_try = [preferred_model] + fallback_models
        response_text = None
        last_error = None
        used_model = None

        with st.status("Generating your YouTube strategy with Gemini...", expanded=True) as status:
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(timeout=20000),
            )

            for model_name in models_to_try:
                for attempt in range(2):
                    st.write(f"Trying `{model_name}` (attempt {attempt + 1}/2)...")
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=final_prompt,
                        )
                        response_text = response.text
                        used_model = model_name
                        status.update(
                            label=f"Completed using {model_name}!",
                            state="complete",
                            expanded=False,
                        )
                        break
                    except Exception as e:
                        last_error = e
                        st.write(f"Attempt {attempt + 1} on `{model_name}` hit an issue: {e}")
                        if attempt == 0:
                            time.sleep(1)
                            continue
                        break
                if response_text:
                    break

            if not response_text:
                status.update(label="Generation failed", state="error", expanded=True)

        if response_text:
            st.session_state["last_output"] = response_text
            st.session_state["last_level"] = f"{current_data['title']} ({used_model})"
        else:
            st.error(f"Could not complete generation. Details: {last_error}")

if "last_output" in st.session_state:
    st.subheader(f"✨ Output: {st.session_state.get('last_level', selected_level)}")
    st.markdown(st.session_state["last_output"])
    st.download_button(
        label="⬇️ Download Response (.md)",
        data=st.session_state["last_output"],
        file_name=f"{selected_level.lower().replace(' ', '_').replace(':', '')}.md",
        mime="text/markdown",
    )

# Progress Tracker
st.divider()
level_number = int(selected_level.split(":")[0].replace("Level ", ""))
st.write(f"**Creator Journey Progress:** Level {level_number} of 7")
st.progress(level_number / 7)
