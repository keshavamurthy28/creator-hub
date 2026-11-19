import os
import time
import streamlit as st
from google import genai

# 1. Page Configuration
st.set_page_config(
    page_title="YouTube Creator Growth Studio",
    page_icon="🎬",
    layout="wide"
)

st.markdown("""
    <style>
    .level-header {
        color: #F5C518;
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Sidebar - API Key, Channel Profile & Level Navigation
with st.sidebar:
    st.title("🎬 Creator Control Panel")

    # Check Streamlit secrets or environment variable first, with optional manual fallback
    default_api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    if default_api_key:
        st.success("Gemini API Key loaded from Secrets")
        api_key = default_api_key
    else:
        api_key = st.text_input(
            "Gemini API Key",
            type="password",
            placeholder="Paste API key or add to Streamlit Secrets"
        )

    st.divider()
    st.markdown("Customize your channel details below:")
    channel_topic = st.text_input("Channel Niche / Topic", placeholder="e.g., Personal Finance, Life Wisdom")
    target_audience = st.text_input("Target Audience", placeholder="e.g., Beginners, Young Professionals")
    video_format = st.selectbox("Primary Format", ["Long-form Videos", "YouTube Shorts", "Both Long-form & Shorts"])

    st.divider()

    selected_level = st.radio(
        "Select Your Creator Level:",
        [
            "Level 1: Full Channel Plan",
            "Level 2: Pick a Niche",
            "Level 3: Viral Scripts, Hooks & Thumbnails",
            "Level 4: Growth & Algorithm",
            "Level 5: Produce Videos 3x Faster",
            "Level 6: Monetization Plan",
            "Level 7: Read Analytics Like a Pro"
        ]
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
        "prompt": (
            "Act as an expert YouTube strategist and monetization consultant. Develop a comprehensive plan for launching a YouTube channel from scratch and working toward monetization.\n"
            "Evaluate my niche, target audience, competitors, available resources, and long-term goals.\n"
            "Create a detailed strategy covering channel positioning, content pillars, video formats, publishing schedules, audience growth, viewer retention, monetization opportunities, and a practical weekly action plan."
        )
    },
    "Level 2: Pick a Niche": {
        "title": "2. Pick a Niche",
        "role": "YouTube Market Researcher & Channel Strategist",
        "goal": "Find a profitable niche and generate 100 ranked video ideas.",
        "prompt": (
            "Act as an experienced YouTube market researcher and channel strategist.\n"
            "Help me choose a profitable YouTube niche with strong audience demand and long-term growth potential.\n"
            "Evaluate competition, search opportunities, monetization potential, content sustainability, and ways to stand out.\n"
            "Develop a unique channel identity, define my ideal viewer, recommend content categories, and generate 100 video ideas ranked by their potential to attract an audience."
        )
    },
    "Level 3: Viral Scripts, Hooks & Thumbnails": {
        "title": "3. Create Viral Scripts, Hooks, and Thumbnails",
        "role": "Elite YouTube Content Strategist & Video Producer",
        "goal": "Maximize Click-Through Rate (CTR) and average view duration.",
        "prompt": (
            "Act as an elite YouTube content strategist and video producer.\n"
            "Develop a complete content creation framework designed to improve click-through rates and audience retention.\n"
            "Generate compelling video ideas, attention-grabbing hooks, engaging titles, thumbnail concepts, opening sequences, storytelling structures, retention strategies, calls to action, and complete video scripts.\n"
            "Explain why each concept could attract viewers, maintain their attention, and encourage them to watch until the end."
        )
    },
    "Level 4: Growth & Algorithm": {
        "title": "4. Understand YouTube Growth and Algorithm",
        "role": "YouTube Growth Strategist",
        "goal": "Master impressions, CTR, watch time, and converting viewers into subscribers.",
        "prompt": (
            "Act as a YouTube growth strategist with expertise in content discovery and audience behavior.\n"
            "Explain how YouTube growth works, including impressions, click-through rates, watch time, audience retention, returning viewers, suggested videos, search traffic, and recommendation systems.\n"
            "Build a practical growth strategy covering upload frequency, content testing, performance optimization, audience engagement, and methods for converting viewers into subscribers."
        )
    },
    "Level 5: Produce Videos 3x Faster": {
        "title": "5. Produce Videos 3x Faster",
        "role": "Professional YouTube Production Manager",
        "goal": "Build an AI-assisted workflow and repurpose content across Shorts/Reels.",
        "prompt": (
            "Act as a professional YouTube production manager.\n"
            "Design an AI-assisted workflow that helps me create high-quality YouTube videos more efficiently.\n"
            "Develop streamlined processes for topic research, scriptwriting, voiceovers, filming, editing, thumbnail design, publishing, performance analysis, and repurposing content for YouTube Shorts, TikTok, Instagram Reels, and other platforms.\n"
            "Recommend useful AI tools, repeatable workflows, production templates, and quality-control checklists to reduce unnecessary work while maintaining content quality."
        )
    },
    "Level 6: Monetization Plan": {
        "title": "6. Build Your Monetization Plan",
        "role": "Creator Business Strategist",
        "goal": "Diversify revenue beyond ads (affiliates, sponsorships, digital products).",
        "prompt": (
            "Act as a creator business strategist specializing in YouTube monetization.\n"
            "Develop a comprehensive revenue strategy for my YouTube channel.\n"
            "Include preparation for the YouTube Partner Program, advertising revenue, affiliate marketing, brand sponsorships, digital products, online courses, paid memberships, newsletters, communities, and additional income opportunities.\n"
            "Explain the requirements, advantages, limitations, and ideal timing for introducing each monetization method as my channel develops."
        )
    },
    "Level 7: Read Analytics Like a Pro": {
        "title": "7. Read Your Analytics Like a Pro",
        "role": "Experienced YouTube Data Analyst",
        "goal": "Diagnose underperforming videos and build weekly/monthly review frameworks.",
        "prompt": (
            "Act as an experienced YouTube data analyst.\n"
            "Create a comprehensive system for monitoring, evaluating, and improving my channel's performance.\n"
            "Analyze essential metrics, including impressions, click-through rate (CTR), average view duration, audience retention, subscriber conversion, traffic sources, engagement, and revenue.\n"
            "Develop weekly and monthly performance review frameworks to identify successful content patterns, understand why certain videos underperform, and recommend specific improvements.\n"
            "Help me use these insights to make better content decisions and build a more effective long-term growth strategy."
        )
    }
}

# 4. Main Display Area
current_data = levels_data[selected_level]

st.markdown(f'<div class="level-header">{current_data["title"]}</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    st.info(f"**AI Persona:** {current_data['role']}")
with col2:
    st.success(f"**Primary Objective:** {current_data['goal']}")

# Level-Specific Extra Inputs
extra_details = ""
st.subheader("🎯 Customize This Level")

if selected_level == "Level 3: Viral Scripts, Hooks & Thumbnails":
    video_topic = st.text_input("Specific Video Topic for Script/Hook:", placeholder="e.g., 5 Habits That Changed My Life")
    if video_topic:
        extra_details = f"\n- Specific Video Topic: {video_topic}"

elif selected_level == "Level 7: Read Analytics Like a Pro":
    c1, c2, c3 = st.columns(3)
    ctr = c1.number_input("Current CTR (%)", min_value=0.0, max_value=100.0, value=4.5, step=0.1)
    avd = c2.text_input("Avg View Duration", placeholder="e.g., 3:45 out of 10:00")
    views = c3.number_input("Avg Views per Video", min_value=0, value=500, step=50)
    extra_details = f"\n- Current Metrics: CTR is {ctr}%, Avg View Duration is {avd or 'N/A'}, Avg Views: {views}"

# 5. Prompt Preview & Live AI Generation (with retry & model fallback)
final_prompt = current_data["prompt"] + context_addon + extra_details

with st.expander("📋 View / Copy Raw Prompt"):
    st.code(final_prompt, language="markdown")

if st.button("🚀 Generate AI Response Now", type="primary"):
    if not api_key:
        st.error("Please enter a Gemini API key or add `GEMINI_API_KEY` to your Streamlit Secrets.")
    else:
        models_to_try = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-4-hydrogen"]
        response_text = None
        last_error = None
        used_model = None

        with st.spinner("Generating your YouTube strategy with Gemini..."):
            client = genai.Client(api_key=api_key)

            for model_name in models_to_try:
                for attempt in range(2):
                    try:
                        response = client.models.generate_content(
                            model=model_name,
                            contents=final_prompt,
                        )
                        response_text = response.text
                        used_model = model_name
                        break
                    except Exception as e:
                        last_error = e
                        if "503" in str(e) or "UNAVAILABLE" in str(e):
                            time.sleep(2)
                            continue
                        break
                if response_text:
                    break

        if response_text:
            st.session_state["last_output"] = response_text
            st.session_state["last_level"] = f"{current_data['title']} ({used_model})"
        else:
            st.error(f"All models are temporarily busy. Please try again in a moment. Details: {last_error}")

if "last_output" in st.session_state:
    st.subheader(f"✨ Output: {st.session_state.get('last_level', selected_level)}")
    st.markdown(st.session_state["last_output"])
    st.download_button(
        label="⬇️ Download Response (.md)",
        data=st.session_state["last_output"],
        file_name=f"{selected_level.lower().replace(' ', '_').replace(':', '')}.md",
        mime="text/markdown"
    )

# Progress Tracker
st.divider()
level_number = int(selected_level.split(":")[0].replace("Level ", ""))
st.write(f"**Creator Journey Progress:** Level {level_number} of 7")
st.progress(level_number / 7)
