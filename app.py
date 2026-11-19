import streamlit as st

# 1. Page Configuration
st.set_page_config(
    page_title="YouTube Creator Growth Studio",
    page_icon="🎬",
    layout="wide"
)

# Custom styling for dark-gold theme inspired by your screenshot
st.markdown("""
    <style>
    .level-header {
        color: #F5C518;
        font-size: 28px;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .prompt-box {
        background-color: #1E1E1E;
        padding: 20px;
        border-radius: 10px;
        border-left: 5px solid #F5C518;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Sidebar - Channel Profile & Level Navigation
with st.sidebar:
    st.title("🎬 Creator Control Panel")
    st.markdown("Customize your channel details below to automatically inject them into every level's prompt.")
    
    channel_topic = st.text_input("Channel Niche / Topic", placeholder="e.g., Stock Market, Life Wisdom, Tech")
    target_audience = st.text_input("Target Audience", placeholder="e.g., Beginners in India, Young Professionals")
    video_format = st.selectbox("Primary Format", ["Long-form Videos", "YouTube Shorts", "Both Long-form & Shorts"])
    
    st.divider()
    
    # Navigation across the 7 Levels from the screenshot
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

# Helper function to format user context
context_addon = ""
if channel_topic or target_audience:
    context_addon = f"\n\nMy Channel Context:\n- Niche/Topic: {channel_topic or 'Not specified'}\n- Target Audience: {target_audience or 'General audience'}\n- Format: {video_format}"

# 3. Data Dictionary containing all 7 Prompts from your screenshot
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

# Level-Specific Extra Inputs (Makes the app truly interactive!)
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

# 5. Final Generated Prompt Output
st.subheader("📋 Ready-to-Use Prompt")
st.caption("Click the copy icon in the top-right corner of the box below, then paste it into Gemini or ChatGPT.")

final_prompt = current_data["prompt"] + context_addon + extra_details
st.code(final_prompt, language="markdown")

# Progress Tracker at the bottom
st.divider()
level_number = int(selected_level.split(":")[0].replace("Level ", ""))
st.write(f"**Creator Journey Progress:** Level {level_number} of 7")
st.progress(level_number / 7)
