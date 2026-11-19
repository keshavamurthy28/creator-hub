import asyncio
import io
import math
import os
import random
import struct
import tempfile
import textwrap
import time
import wave
from google import genai
from google.genai import types
from gtts import gTTS
from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_audioclips, concatenate_videoclips
from PIL import Image, ImageDraw, ImageFont
import streamlit as st

try:
    import edge_tts
    HAS_EDGE_TTS = True
except Exception:
    HAS_EDGE_TTS = False

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

# Cinematic & Copyright-Safe Studio Presets
BACKDROP_PRESETS = {
    "Cinema Midnight (#0E131F)": "#0E131F",
    "Golden Hour Drama (#2B1D12)": "#2B1D12",
    "Emerald Forest Scene (#0F221C)": "#0F221C",
    "Noir Slate (#171A21)": "#171A21",
    "Twilight Indigo (#161936)": "#161936",
    "Warm Parchment (#262018)": "#262018",
}

SHOT_TYPE_PRESETS = [
    "Wide Establishing Shot",
    "Medium Character Shot",
    "Close-Up Hook Shot",
    "Split Dialogue Shot",
    "Reflective Outro Shot",
]

# Custom-drawn copyright-safe human-like & cartoon characters
CHARACTER_ROSTER = {
    "None (Pure Cinema / B-Roll)": {
        "style": "none",
        "label": "",
        "skin": (245, 197, 24),
        "hair": (40, 46, 62),
        "outfit": (30, 36, 50),
        "default_voice": "en-US-ChristopherNeural",
    },
    "Human-Like Narrator (Realistic Proportions)": {
        "style": "human",
        "label": "NARRATOR",
        "skin": (224, 177, 142),
        "hair": (42, 32, 26),
        "outfit": (34, 58, 92),
        "default_voice": "en-US-ChristopherNeural",
    },
    "Human-Like Storyteller (Warm Expression)": {
        "style": "human",
        "label": "STORYTELLER",
        "skin": (198, 146, 108),
        "hair": (25, 22, 24),
        "outfit": (92, 46, 54),
        "default_voice": "en-US-AriaNeural",
    },
    "Cartoon Sage (Expressive Toon)": {
        "style": "cartoon",
        "label": "CARTOON SAGE",
        "skin": (245, 197, 24),
        "hair": (235, 238, 245),
        "outfit": (28, 82, 68),
        "default_voice": "en-IN-PrabhatNeural",
    },
    "Cartoon Explorer (Energetic Toon)": {
        "style": "cartoon",
        "label": "CARTOON HERO",
        "skin": (255, 158, 92),
        "hair": (35, 45, 85),
        "outfit": (122, 44, 44),
        "default_voice": "en-US-GuyNeural",
    },
    "Cartoon Friend (Gentle Toon)": {
        "style": "cartoon",
        "label": "CARTOON FRIEND",
        "skin": (158, 196, 255),
        "hair": (52, 38, 78),
        "outfit": (56, 46, 98),
        "default_voice": "en-IN-NeerjaNeural",
    },
}

CHARACTER_MOTION_PRESETS = [
    "Expressive Speaking + Blink",
    "Calm Breathing & Head Tilt",
    "Heroic Walk / Float Drift",
    "Static Pose",
]

TRANSITION_PRESETS = [
    "Hard Cut",
    "Smooth Fade In",
]

DUBBING_VOICE_PRESETS = {
    "Calm Mentor — Christopher (US Male)": "en-US-ChristopherNeural",
    "Thoughtful Thinker — Aria (US Female)": "en-US-AriaNeural",
    "Energetic Host — Guy (US Male)": "en-US-GuyNeural",
    "Friendly Narrator — Jenny (US Female)": "en-US-JennyNeural",
    "Warm Indian Male — Prabhat (IN Male)": "en-IN-PrabhatNeural",
    "Warm Indian Female — Neerja (IN Female)": "en-IN-NeerjaNeural",
}

VISUAL_MEDIA_PRESETS = [
    "Cinematic Storyboard Card",
    "Scene Visual: Sunrise & New Beginning",
    "Scene Visual: Quiet Reflection & Focus",
    "Scene Visual: Turning Point & Choice",
    "Scene Visual: Journey & Resolution",
]

VIDEO_CLIP_PRESETS = [
    "Static Cinema Frame",
    "Slow Dolly Zoom (Ken Burns)",
    "Gentle Breath Pulse",
]

SFX_PRESETS = [
    "None",
    "Soft Whoosh (Cut/Transition)",
    "Gentle Chime (Revelation)",
    "Warm Bell (Emotional Beat)",
    "Subtle Pulse (Tension/Hook)",
]

# Session state initialization
if "level_mind_words" not in st.session_state:
    st.session_state["level_mind_words"] = {}
if "all_level_outputs" not in st.session_state:
    st.session_state["all_level_outputs"] = {}
if "movie_script_input" not in st.session_state:
    st.session_state["movie_script_input"] = (
        "SCENE 1: A young beginner stands at a crossroads feeling overwhelmed by noisy advice.\n"
        "SCENE 2: The Cartoon Sage reminds them that peace begins when you choose one honest action today.\n"
        "SCENE 3: With a calm breath and a clear step forward, the journey begins."
    )
if "video_scenes" not in st.session_state:
    st.session_state["video_scenes"] = [
        {
            "spot": 1,
            "title": "Scene 1 — The Crossroads",
            "shot_type": "Wide Establishing Shot",
            "duration": 7,
            "transition": "Smooth Fade In",
            "text": "A young beginner stands at a crossroads feeling overwhelmed by noisy advice.",
            "dialogue_mode": False,
            "character_b": "Cartoon Friend (Gentle Toon)",
            "dub_voice_b": "Warm Indian Female — Neerja (IN Female)",
            "text_b": "Where should I start when everything feels urgent?",
            "dub_audio_b_bytes": None,
            "backdrop_name": "Cinema Midnight (#0E131F)",
            "bg_color": "#0E131F",
            "character": "Human-Like Narrator (Realistic Proportions)",
            "char_motion": "Expressive Speaking + Blink",
            "enable_dubbing": True,
            "dub_voice_label": "Calm Mentor — Christopher (US Male)",
            "dub_rate": "+0%",
            "dub_audio_bytes": None,
            "visual_preset": "Scene Visual: Sunrise & New Beginning",
            "video_preset": "Slow Dolly Zoom (Ken Burns)",
            "sfx": "Subtle Pulse (Tension/Hook)",
            "image_bytes": None,
            "image_name": None,
            "audio_bytes": None,
            "audio_name": None,
            "audio_volume": 0.9,
        },
        {
            "spot": 2,
            "title": "Scene 2 — The Inner Shift",
            "shot_type": "Medium Character Shot",
            "duration": 8,
            "transition": "Smooth Fade In",
            "text": "Peace begins when you choose one honest action today and let go of noise.",
            "dialogue_mode": True,
            "character_b": "Cartoon Explorer (Energetic Toon)",
            "dub_voice_b": "Energetic Host — Guy (US Male)",
            "text_b": "One small step every single day changes the whole story.",
            "dub_audio_b_bytes": None,
            "backdrop_name": "Golden Hour Drama (#2B1D12)",
            "bg_color": "#2B1D12",
            "character": "Cartoon Sage (Expressive Toon)",
            "char_motion": "Expressive Speaking + Blink",
            "enable_dubbing": True,
            "dub_voice_label": "Warm Indian Male — Prabhat (IN Male)",
            "dub_rate": "+0%",
            "dub_audio_bytes": None,
            "visual_preset": "Scene Visual: Quiet Reflection & Focus",
            "video_preset": "Gentle Breath Pulse",
            "sfx": "Gentle Chime (Revelation)",
            "image_bytes": None,
            "image_name": None,
            "audio_bytes": None,
            "audio_name": None,
            "audio_volume": 0.9,
        },
    ]
if "global_score_bytes" not in st.session_state:
    st.session_state["global_score_bytes"] = None
if "global_score_name" not in st.session_state:
    st.session_state["global_score_name"] = None
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
        return (14, 19, 31)
    return tuple(int(cleaned[i : i + 2], 16) for i in (0, 2, 4))


async def _edge_tts_to_bytes(text: str, voice: str, rate: str) -> bytes:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    return buf.getvalue()


def synthesize_character_dubbing(text: str, voice_code: str, rate: str = "+0%") -> bytes:
    cleaned_text = " ".join(text.strip().split())
    if not cleaned_text:
        return b""

    if HAS_EDGE_TTS:
        try:
            loop = asyncio.new_event_loop()
            try:
                audio_bytes = loop.run_until_complete(_edge_tts_to_bytes(cleaned_text, voice_code, rate))
            finally:
                loop.close()
            if audio_bytes:
                return audio_bytes
        except Exception:
            pass

    tts = gTTS(text=cleaned_text, lang="en")
    out_buf = io.BytesIO()
    tts.write_to_fp(out_buf)
    return out_buf.getvalue()


def synthesize_sfx_wav(sfx_choice: str, out_wav_path: str) -> bool:
    if not sfx_choice or sfx_choice == "None":
        return False

    sample_rate = 22050
    duration = 0.65
    num_samples = int(sample_rate * duration)

    with wave.open(out_wav_path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)

        frames = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            env = math.sin(math.pi * min(1.0, t / duration))

            if "Whoosh" in sfx_choice:
                freq = 180 + 420 * (t / duration)
                val = env * (0.45 * math.sin(2 * math.pi * freq * t) + 0.25 * random.uniform(-1, 1))
            elif "Chime" in sfx_choice:
                val = env * (0.45 * math.sin(2 * math.pi * 587.33 * t) + 0.25 * math.sin(2 * math.pi * 880.0 * t))
            elif "Bell" in sfx_choice:
                decay = math.exp(-3.5 * t)
                val = decay * (0.5 * math.sin(2 * math.pi * 440.0 * t) + 0.2 * math.sin(2 * math.pi * 1318.5 * t))
            else:
                val = env * 0.4 * math.sin(2 * math.pi * 220.0 * t)

            sample_int = max(-32767, min(32767, int(val * 32767)))
            frames.extend(struct.pack("<h", sample_int))

        wf.writeframes(frames)
    return True


def _draw_movie_character(
    draw: ImageDraw.Draw,
    char_key: str,
    motion_mode: str,
    cx: int,
    cy: int,
    t_sec: float,
    font,
    is_active_speaker: bool = True,
):
    info = CHARACTER_ROSTER.get(char_key, CHARACTER_ROSTER["None (Pure Cinema / B-Roll)"])
    style = info["style"]
    if style == "none":
        return

    bob_y = 0
    drift_x = 0
    mouth_open = False
    blink_closed = False

    if "Speaking" in motion_mode:
        bob_y = int(5 * math.sin(2 * math.pi * 2.2 * t_sec))
        mouth_open = is_active_speaker and (math.sin(2 * math.pi * 5.0 * t_sec) > 0.05)
        blink_closed = (int(t_sec * 10) % 28) == 0
    elif "Breathing" in motion_mode:
        bob_y = int(8 * math.sin(2 * math.pi * 1.2 * t_sec))
        blink_closed = (int(t_sec * 10) % 35) == 0
    elif "Walk" in motion_mode:
        bob_y = int(9 * abs(math.sin(2 * math.pi * 1.8 * t_sec)))
        drift_x = int(14 * math.sin(2 * math.pi * 0.6 * t_sec))
        mouth_open = is_active_speaker and (math.sin(2 * math.pi * 4.0 * t_sec) > 0.2)

    px = cx + drift_x
    py = cy + bob_y
    skin = info["skin"]
    hair = info["hair"]
    outfit = info["outfit"]

    scale = 1.08 if is_active_speaker else 0.92
    r_head = int(42 * scale)

    if mouth_open:
        glow_r = r_head + 14
        draw.ellipse((px - glow_r, py - glow_r, px + glow_r, py + glow_r), outline=skin, width=3)

    if style == "human":
        # Human-like torso & shoulders
        torso_w = int(68 * scale)
        torso_h = int(64 * scale)
        draw.rounded_rectangle(
            (px - torso_w, py + r_head - 4, px + torso_w, py + r_head + torso_h),
            radius=20,
            fill=outfit,
            outline=(230, 235, 245),
            width=2,
        )
        # Neck
        draw.rectangle((px - 12, py + r_head - 12, px + 12, py + r_head + 6), fill=skin)
        # Head
        draw.ellipse((px - r_head, py - r_head, px + r_head, py + r_head), fill=skin, outline=(240, 240, 240), width=2)
        # Hair cap
        draw.pieslice((px - r_head, py - r_head - 6, px + r_head, py + r_head - 4), start=180, end=360, fill=hair)
    else:
        # Cartoon stylized body & larger expressive head
        body_w = int(62 * scale)
        draw.pieslice((px - body_w, py + r_head - 6, px + body_w, py + r_head + 68), start=180, end=360, fill=outfit, outline=skin, width=3)
        draw.ellipse((px - r_head - 4, py - r_head - 4, px + r_head + 4, py + r_head + 4), fill=skin, outline=(255, 255, 255), width=3)
        draw.pieslice((px - r_head - 4, py - r_head - 10, px + r_head + 4, py - 4), start=180, end=360, fill=hair)

    # Eyes + blink
    eye_y = py - 4
    if blink_closed:
        draw.line((px - 20, eye_y, px - 8, eye_y), fill=(20, 24, 36), width=2)
        draw.line((px + 8, eye_y, px + 20, eye_y), fill=(20, 24, 36), width=2)
    else:
        draw.ellipse((px - 20, eye_y - 6, px - 7, eye_y + 7), fill=(255, 255, 255))
        draw.ellipse((px + 7, eye_y - 6, px + 20, eye_y + 7), fill=(255, 255, 255))
        draw.ellipse((px - 16, eye_y - 3, px - 10, eye_y + 4), fill=(20, 24, 36))
        draw.ellipse((px + 10, eye_y - 3, px + 16, eye_y + 4), fill=(20, 24, 36))

    # Mouth animation
    mouth_y = py + 18
    if mouth_open:
        draw.ellipse((px - 11, mouth_y - 6, px + 11, mouth_y + 9), fill=(110, 28, 36))
    else:
        draw.arc((px - 14, mouth_y - 6, px + 14, mouth_y + 8), start=15, end=165, fill=(20, 24, 36), width=3)

    draw.text((px - 58, py + r_head + 74), info["label"], fill=skin, font=font)


def create_scene_frame_image(
    scene: dict,
    width: int,
    height: int,
    temp_dir: str,
    t_sec: float = 0.0,
    src_img_path: str | None = None,
    frame_idx: int = 0,
) -> str:
    bg_rgb = hex_to_rgb(scene.get("bg_color", "#0E131F"))
    canvas = Image.new("RGB", (width, height), bg_rgb)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    # Subtle letterbox cinema bars top & bottom for movie feel
    bar_h = 28
    draw.rectangle((0, 0, width, bar_h), fill=(5, 7, 12))
    draw.rectangle((0, height - bar_h, width, height), fill=(5, 7, 12))

    char_name = scene.get("character", "None (Pure Cinema / B-Roll)")
    dialogue_on = bool(scene.get("dialogue_mode", False))
    char_b_name = scene.get("character_b", "Cartoon Friend (Gentle Toon)")
    has_character = (char_name != "None (Pure Cinema / B-Roll)") or (
        dialogue_on and char_b_name != "None (Pure Cinema / B-Roll)"
    )

    shot_type = scene.get("shot_type", "Medium Character Shot")
    visual_tag = scene.get("visual_preset", "Cinematic Storyboard Card")
    spot_label = f"SPOT {scene['spot']} — {scene.get('title', 'Scene')} [{shot_type}]"
    draw.text((60, bar_h + 10), spot_label, fill=(245, 197, 24), font=font)
    draw.text((60, bar_h + 28), f"Visual: {visual_tag}", fill=(185, 195, 215), font=font)

    right_reserve = 370 if dialogue_on else (290 if has_character else 60)

    if src_img_path and os.path.exists(src_img_path):
        uploaded_img = Image.open(src_img_path).convert("RGB")
        max_w = max(240, width - right_reserve - 100)
        max_h = int(height * 0.40)
        uploaded_img.thumbnail((max_w, max_h))
        x_pos = 60
        y_pos = bar_h + 56
        canvas.paste(uploaded_img, (x_pos, y_pos))
        text_y_start = y_pos + uploaded_img.height + 24
    else:
        box_top = bar_h + 56
        box_bottom = int(height * 0.43)
        box_right = max(260, width - right_reserve)
        draw.rectangle((60, box_top, box_right, box_bottom), outline=(245, 197, 24), width=2)
        draw.text((80, box_top + 16), f"Cinema Frame: {visual_tag}", fill=(245, 197, 24), font=font)
        draw.text((80, box_top + 38), f"Camera: {scene.get('video_preset', 'Static Cinema Frame')}", fill=(215, 220, 230), font=font)
        text_y_start = box_bottom + 24

    motion_mode = scene.get("char_motion", "Expressive Speaking + Blink")
    dur = max(2, int(scene.get("duration", 7)))
    speaking_b_now = dialogue_on and (t_sec >= dur * 0.5)

    if dialogue_on:
        _draw_movie_character(
            draw,
            char_name,
            motion_mode,
            cx=width - 280,
            cy=int(height * 0.34),
            t_sec=t_sec,
            font=font,
            is_active_speaker=not speaking_b_now,
        )
        _draw_movie_character(
            draw,
            char_b_name,
            motion_mode,
            cx=width - 115,
            cy=int(height * 0.34),
            t_sec=t_sec + 0.35,
            font=font,
            is_active_speaker=speaking_b_now,
        )
    elif has_character:
        _draw_movie_character(
            draw,
            char_name,
            motion_mode,
            cx=width - 175,
            cy=int(height * 0.34),
            t_sec=t_sec,
            font=font,
            is_active_speaker=True,
        )

    combined_script = scene.get("text", "")
    if dialogue_on and scene.get("text_b", "").strip():
        combined_script = f"A: {scene.get('text', '')}   |   B: {scene.get('text_b', '')}"

    wrap_width = 56 if (width >= 1200 and has_character) else (68 if width >= 1200 else 44)
    wrapped_lines = textwrap.wrap(combined_script, width=wrap_width)
    cur_y = text_y_start
    for line in wrapped_lines[:9]:
        if cur_y > height - bar_h - 30:
            break
        draw.text((60, cur_y), line, fill=(248, 248, 248), font=font)
        cur_y += 22

    out_frame_path = os.path.join(temp_dir, f"frame_spot_{scene['spot']}_{frame_idx}.png")
    canvas.save(out_frame_path)
    return out_frame_path


def render_scenes_to_mp4(scenes: list, resolution_choice: str, global_score_bytes: bytes | None = None, global_score_name: str | None = None) -> bytes:
    if resolution_choice == "Vertical Shorts (1080x1920)":
        w, h = 1080, 1920
    else:
        w, h = 1280, 720

    clips = []
    total_duration = sum(max(2, int(s.get("duration", 6))) for s in scenes)

    with tempfile.TemporaryDirectory() as tmpdir:
        for scene in scenes:
            dur = max(2, int(scene.get("duration", 6)))
            char_name = scene.get("character", "None (Pure Cinema / B-Roll)")
            char_b_name = scene.get("character_b", "None (Pure Cinema / B-Roll)")
            dialogue_on = bool(scene.get("dialogue_mode", False))
            motion_mode = scene.get("char_motion", "Expressive Speaking + Blink")
            has_any_char = (char_name != "None (Pure Cinema / B-Roll)") or (
                dialogue_on and char_b_name != "None (Pure Cinema / B-Roll)"
            )
            has_animated_char = has_any_char and ("Static" not in motion_mode)

            src_img_path = None
            if scene.get("image_bytes"):
                src_img_path = os.path.join(tmpdir, f"src_img_{scene['spot']}.png")
                with open(src_img_path, "wb") as f:
                    f.write(scene["image_bytes"])

            if has_animated_char:
                sample_fps = 5
                num_samples = max(4, dur * sample_fps)
                sampled_paths = []
                for k in range(num_samples):
                    t_cur = k / sample_fps
                    f_path = create_scene_frame_image(
                        scene,
                        w,
                        h,
                        tmpdir,
                        t_sec=t_cur,
                        src_img_path=src_img_path,
                        frame_idx=k,
                    )
                    sampled_paths.append(f_path)
                per_frame_dur = dur / len(sampled_paths)
                loaded_frames = [ImageClip(p).with_duration(per_frame_dur) for p in sampled_paths]
                img_clip = concatenate_videoclips(loaded_frames, method="compose")
            else:
                frame_file = create_scene_frame_image(
                    scene,
                    w,
                    h,
                    tmpdir,
                    t_sec=0.0,
                    src_img_path=src_img_path,
                    frame_idx=0,
                )
                img_clip = ImageClip(frame_file).with_duration(dur)

            v_preset = scene.get("video_preset", "")
            if "Ken Burns" in v_preset:
                img_clip = img_clip.resized(lambda t: 1.0 + 0.012 * t)
            elif "Pulse" in v_preset:
                img_clip = img_clip.resized(lambda t: 1.0 + 0.015 * math.sin(math.pi * min(1.0, t / dur)))

            audio_layers = []
            vol = float(scene.get("audio_volume", 0.9))

            dub_clips_for_spot = []
            if scene.get("enable_dubbing") and scene.get("text", "").strip():
                dub_bytes = scene.get("dub_audio_bytes")
                if not dub_bytes:
                    voice_code = DUBBING_VOICE_PRESETS.get(
                        scene.get("dub_voice_label", ""),
                        CHARACTER_ROSTER.get(char_name, {}).get("default_voice", "en-US-ChristopherNeural"),
                    )
                    dub_bytes = synthesize_character_dubbing(
                        scene.get("text", ""),
                        voice_code=voice_code,
                        rate=scene.get("dub_rate", "+0%"),
                    )
                    scene["dub_audio_bytes"] = dub_bytes

                if dub_bytes:
                    dub_path = os.path.join(tmpdir, f"dub_a_spot_{scene['spot']}.mp3")
                    with open(dub_path, "wb") as df:
                        df.write(dub_bytes)
                    try:
                        d_clip_a = AudioFileClip(dub_path).with_volume_scaled(vol)
                        dub_clips_for_spot.append(d_clip_a)
                    except Exception:
                        pass

            if dialogue_on and scene.get("enable_dubbing") and scene.get("text_b", "").strip():
                dub_b_bytes = scene.get("dub_audio_b_bytes")
                if not dub_b_bytes:
                    voice_b_code = DUBBING_VOICE_PRESETS.get(
                        scene.get("dub_voice_b", ""),
                        CHARACTER_ROSTER.get(char_b_name, {}).get("default_voice", "en-US-AriaNeural"),
                    )
                    dub_b_bytes = synthesize_character_dubbing(
                        scene.get("text_b", ""),
                        voice_code=voice_b_code,
                        rate=scene.get("dub_rate", "+0%"),
                    )
                    scene["dub_audio_b_bytes"] = dub_b_bytes

                if dub_b_bytes:
                    dub_b_path = os.path.join(tmpdir, f"dub_b_spot_{scene['spot']}.mp3")
                    with open(dub_b_path, "wb") as dfb:
                        dfb.write(dub_b_bytes)
                    try:
                        d_clip_b = AudioFileClip(dub_b_path).with_volume_scaled(vol)
                        dub_clips_for_spot.append(d_clip_b)
                    except Exception:
                        pass

            if dub_clips_for_spot:
                combined_dub = (
                    dub_clips_for_spot[0]
                    if len(dub_clips_for_spot) == 1
                    else concatenate_audioclips(dub_clips_for_spot)
                )
                if combined_dub.duration > dur:
                    combined_dub = combined_dub.subclipped(0, dur)
                audio_layers.append(combined_dub)

            if scene.get("audio_bytes"):
                ext = ".wav" if (scene.get("audio_name") or "").lower().endswith(".wav") else ".mp3"
                custom_aud_path = os.path.join(tmpdir, f"custom_audio_spot_{scene['spot']}{ext}")
                with open(custom_aud_path, "wb") as af:
                    af.write(scene["audio_bytes"])
                try:
                    c_clip = AudioFileClip(custom_aud_path).with_volume_scaled(vol * 0.7 if audio_layers else vol)
                    if c_clip.duration > dur:
                        c_clip = c_clip.subclipped(0, dur)
                    audio_layers.append(c_clip)
                except Exception:
                    pass

            sfx_wav = os.path.join(tmpdir, f"sfx_spot_{scene['spot']}.wav")
            if synthesize_sfx_wav(scene.get("sfx", "None"), sfx_wav):
                try:
                    s_clip = AudioFileClip(sfx_wav).with_volume_scaled(min(1.5, vol * 0.8))
                    if s_clip.duration > dur:
                        s_clip = s_clip.subclipped(0, dur)
                    audio_layers.append(s_clip)
                except Exception:
                    pass

            if audio_layers:
                mixed_audio = audio_layers[0] if len(audio_layers) == 1 else CompositeAudioClip(audio_layers)
                img_clip = img_clip.with_audio(mixed_audio)

            clips.append(img_clip)

        final_video = concatenate_videoclips(clips, method="compose")

        # Optional movie-wide background score / music bed
        if global_score_bytes:
            g_ext = ".wav" if (global_score_name or "").lower().endswith(".wav") else ".mp3"
            score_path = os.path.join(tmpdir, f"movie_score{g_ext}")
            with open(score_path, "wb") as sf:
                sf.write(global_score_bytes)
            try:
                bg_music = AudioFileClip(score_path).with_volume_scaled(0.22)
                if bg_music.duration < total_duration and bg_music.duration > 0:
                    repeats = math.ceil(total_duration / bg_music.duration)
                    bg_music = concatenate_audioclips([bg_music] * repeats)
                bg_music = bg_music.subclipped(0, total_duration)
                if final_video.audio is not None:
                    final_video = final_video.with_audio(CompositeAudioClip([final_video.audio, bg_music]))
                else:
                    final_video = final_video.with_audio(bg_music)
            except Exception:
                pass

        out_mp4 = os.path.join(tmpdir, "final_youtube_movie.mp4")
        has_audio = final_video.audio is not None
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


def build_movie_scenes_from_script(script_text: str) -> list:
    raw_lines = [
        line.strip().lstrip("#*-0123456789. ").strip()
        for line in script_text.splitlines()
        if len(line.strip()) > 15 and not line.strip().startswith("---")
    ]
    if not raw_lines:
        raw_lines = [
            "Opening scene introduces the main character and central life question.",
            "Mid-scene turning point shares practical wisdom and perspective.",
            "Closing scene ends with calm resolution and a clear takeaway.",
        ]

    picked = raw_lines[:6]
    b_keys = list(BACKDROP_PRESETS.keys())
    char_keys = [k for k in CHARACTER_ROSTER.keys() if k != "None (Pure Cinema / B-Roll)"]
    voice_keys = list(DUBBING_VOICE_PRESETS.keys())

    scenes = []
    for idx, line in enumerate(picked, start=1):
        b_name = b_keys[(idx - 1) % len(b_keys)]
        c_a = char_keys[(idx - 1) % len(char_keys)]
        c_b = char_keys[idx % len(char_keys)]
        scenes.append(
            {
                "spot": idx,
                "title": f"Movie Scene {idx}",
                "shot_type": SHOT_TYPE_PRESETS[(idx - 1) % len(SHOT_TYPE_PRESETS)],
                "duration": 7,
                "transition": "Smooth Fade In",
                "text": line[:340],
                "dialogue_mode": (idx % 2 == 0),
                "character_b": c_b,
                "dub_voice_b": voice_keys[idx % len(voice_keys)],
                "text_b": "What is the deeper meaning behind that moment?",
                "dub_audio_b_bytes": None,
                "backdrop_name": b_name,
                "bg_color": BACKDROP_PRESETS[b_name],
                "character": c_a,
                "char_motion": CHARACTER_MOTION_PRESETS[(idx - 1) % len(CHARACTER_MOTION_PRESETS)],
                "enable_dubbing": True,
                "dub_voice_label": voice_keys[(idx - 1) % len(voice_keys)],
                "dub_rate": "+0%",
                "dub_audio_bytes": None,
                "visual_preset": VISUAL_MEDIA_PRESETS[(idx - 1) % len(VISUAL_MEDIA_PRESETS)],
                "video_preset": VIDEO_CLIP_PRESETS[(idx - 1) % len(VIDEO_CLIP_PRESETS)],
                "sfx": SFX_PRESETS[idx % len(SFX_PRESETS)],
                "image_bytes": None,
                "image_name": None,
                "audio_bytes": None,
                "audio_name": None,
                "audio_volume": 0.9,
            }
        )
    return scenes


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

# 7. Movie Director & Scene Editing Studio
st.divider()
st.subheader("🎥 AI Movie & Story Studio (Script-to-Movie, Copyright-Safe Human/Cartoon Characters, Dubbing & Editing)")

available_levels = list(all_outputs.keys())
if available_levels:
    filter_query = st.text_input(
        "Filter Generated Levels by Keyword:",
        placeholder="e.g., script, hook, story, retention, niche",
    )
    filtered_levels = [
        k
        for k in available_levels
        if not filter_query.strip()
        or filter_query.lower() in k.lower()
        or filter_query.lower() in all_outputs[k]["content"].lower()
    ]
    if filtered_levels:
        chosen_lvl = st.selectbox("Pull Script/Ideas from Generated Level:", filtered_levels)
        if st.button("📥 Load Selected Level Text into Movie Script"):
            st.session_state["movie_script_input"] = all_outputs[chosen_lvl]["content"][:2000]
            st.rerun()

script_input = st.text_area(
    "🎬 Movie / Story Script (Each line or scene becomes a movie shot when converted)",
    value=st.session_state["movie_script_input"],
    height=130,
    key="script_editor_box",
)
st.session_state["movie_script_input"] = script_input

ms_col1, ms_col2, ms_col3 = st.columns(3)
if ms_col1.button("🎬 Convert Script into Movie Scenes", type="primary", use_container_width=True):
    st.session_state["video_scenes"] = build_movie_scenes_from_script(script_input)
    st.rerun()

if ms_col2.button("➕ Add New Movie Scene", use_container_width=True):
    next_n = len(st.session_state["video_scenes"]) + 1
    b_keys = list(BACKDROP_PRESETS.keys())
    char_keys = list(CHARACTER_ROSTER.keys())
    voice_keys = list(DUBBING_VOICE_PRESETS.keys())
    b_pick = b_keys[(next_n - 1) % len(b_keys)]
    st.session_state["video_scenes"].append(
        {
            "spot": next_n,
            "title": f"Movie Scene {next_n}",
            "shot_type": SHOT_TYPE_PRESETS[(next_n - 1) % len(SHOT_TYPE_PRESETS)],
            "duration": 7,
            "transition": "Smooth Fade In",
            "text": "Write the next beat of your movie story here.",
            "dialogue_mode": False,
            "character_b": char_keys[2],
            "dub_voice_b": voice_keys[1],
            "text_b": "Reply or follow-up dialogue line.",
            "dub_audio_b_bytes": None,
            "backdrop_name": b_pick,
            "bg_color": BACKDROP_PRESETS[b_pick],
            "character": char_keys[1],
            "char_motion": CHARACTER_MOTION_PRESETS[0],
            "enable_dubbing": True,
            "dub_voice_label": voice_keys[0],
            "dub_rate": "+0%",
            "dub_audio_bytes": None,
            "visual_preset": VISUAL_MEDIA_PRESETS[0],
            "video_preset": VIDEO_CLIP_PRESETS[1],
            "sfx": SFX_PRESETS[0],
            "image_bytes": None,
            "image_name": None,
            "audio_bytes": None,
            "audio_name": None,
            "audio_volume": 0.9,
        }
    )
    st.rerun()

score_upload = ms_col3.file_uploader("🎼 Movie Background Music / Score (All Scenes)", type=["mp3", "wav", "m4a"], key="global_score_uploader")
if score_upload is not None:
    st.session_state["global_score_bytes"] = score_upload.getvalue()
    st.session_state["global_score_name"] = score_upload.name

if st.session_state.get("global_score_name"):
    st.caption(f"🎼 Active Movie Score: `{st.session_state['global_score_name']}`")

# Movie Timeline & Scene Editor
st.markdown("### 🧩 Movie Timeline Editor (Shots, Human/Cartoon Characters, Dialogue Dubbing & Media)")
char_keys = list(CHARACTER_ROSTER.keys())
voice_keys = list(DUBBING_VOICE_PRESETS.keys())
b_keys = list(BACKDROP_PRESETS.keys())

for idx, scene in enumerate(st.session_state["video_scenes"]):
    dub_badge = "Dub ON" if scene.get("enable_dubbing") else "Dub OFF"
    dial_badge = " | 2-Char Dialogue" if scene.get("dialogue_mode") else ""
    with st.expander(
        f"Scene {idx + 1}: {scene.get('title', 'Scene')} ({scene.get('duration', 7)}s) — {scene.get('character', 'None')} | {dub_badge}{dial_badge}",
        expanded=(idx == 0),
    ):
        sc1, sc2, sc3, sc4 = st.columns([2, 2, 1, 1])
        scene["title"] = sc1.text_input("Scene Title", value=scene.get("title", f"Scene {idx + 1}"), key=f"spot_title_{idx}")

        cur_shot = scene.get("shot_type", SHOT_TYPE_PRESETS[0])
        sh_idx = SHOT_TYPE_PRESETS.index(cur_shot) if cur_shot in SHOT_TYPE_PRESETS else 0
        scene["shot_type"] = sc2.selectbox("Camera Shot Type", SHOT_TYPE_PRESETS, index=sh_idx, key=f"spot_shot_{idx}")

        scene["duration"] = sc3.number_input("Duration (sec)", min_value=2, max_value=60, value=int(scene.get("duration", 7)), key=f"spot_dur_{idx}")

        cur_b = scene.get("backdrop_name", b_keys[0])
        b_idx = b_keys.index(cur_b) if cur_b in b_keys else 0
        chosen_backdrop = sc4.selectbox("Backdrop / Mood", b_keys, index=b_idx, key=f"spot_backdrop_{idx}")
        scene["backdrop_name"] = chosen_backdrop
        scene["bg_color"] = BACKDROP_PRESETS[chosen_backdrop]

        c_col1, c_col2, c_col3, c_col4 = st.columns([2, 2, 2, 1])
        cur_char = scene.get("character", char_keys[1])
        c_idx = char_keys.index(cur_char) if cur_char in char_keys else 0
        scene["character"] = c_col1.selectbox("Character A (Human / Cartoon)", char_keys, index=c_idx, key=f"spot_char_{idx}")

        cur_motion = scene.get("char_motion", CHARACTER_MOTION_PRESETS[0])
        m_idx = CHARACTER_MOTION_PRESETS.index(cur_motion) if cur_motion in CHARACTER_MOTION_PRESETS else 0
        scene["char_motion"] = c_col2.selectbox("Character Animation", CHARACTER_MOTION_PRESETS, index=m_idx, key=f"spot_motion_{idx}")

        cur_voice = scene.get("dub_voice_label", voice_keys[0])
        v_idx = voice_keys.index(cur_voice) if cur_voice in voice_keys else 0
        scene["dub_voice_label"] = c_col3.selectbox("Character A Dubbing Voice", voice_keys, index=v_idx, key=f"spot_voice_{idx}")

        scene["enable_dubbing"] = c_col4.checkbox("Dub Script", value=bool(scene.get("enable_dubbing", True)), key=f"spot_dub_on_{idx}")

        p1, p2, p3, p4 = st.columns(4)
        vis_idx = VISUAL_MEDIA_PRESETS.index(scene["visual_preset"]) if scene.get("visual_preset") in VISUAL_MEDIA_PRESETS else 0
        scene["visual_preset"] = p1.selectbox("Scene Visual Preset", VISUAL_MEDIA_PRESETS, index=vis_idx, key=f"spot_vis_{idx}")

        vid_idx = VIDEO_CLIP_PRESETS.index(scene["video_preset"]) if scene.get("video_preset") in VIDEO_CLIP_PRESETS else 0
        scene["video_preset"] = p2.selectbox("Camera Motion Preset", VIDEO_CLIP_PRESETS, index=vid_idx, key=f"spot_vid_{idx}")

        cur_tr = scene.get("transition", TRANSITION_PRESETS[0])
        tr_idx = TRANSITION_PRESETS.index(cur_tr) if cur_tr in TRANSITION_PRESETS else 0
        scene["transition"] = p3.selectbox("Scene Transition", TRANSITION_PRESETS, index=tr_idx, key=f"spot_trans_{idx}")

        rate_options = ["-15%", "+0%", "+15%", "+25%"]
        cur_rate = scene.get("dub_rate", "+0%")
        r_idx = rate_options.index(cur_rate) if cur_rate in rate_options else 1
        scene["dub_rate"] = p4.selectbox("Voice Pace", rate_options, index=r_idx, key=f"spot_rate_{idx}")

        scene["text"] = st.text_area("Character A Script / Narration", value=scene.get("text", ""), height=85, key=f"spot_text_{idx}")

        scene["dialogue_mode"] = st.checkbox(
            "Enable 2-Character Dialogue in This Scene",
            value=bool(scene.get("dialogue_mode", False)),
            key=f"spot_dial_on_{idx}",
        )

        if scene["dialogue_mode"]:
            db1, db2 = st.columns(2)
            cur_cb = scene.get("character_b", char_keys[3] if len(char_keys) > 3 else char_keys[1])
            cb_idx = char_keys.index(cur_cb) if cur_cb in char_keys else 1
            scene["character_b"] = db1.selectbox("Character B (Human / Cartoon)", char_keys, index=cb_idx, key=f"spot_char_b_{idx}")

            cur_vb = scene.get("dub_voice_b", voice_keys[1] if len(voice_keys) > 1 else voice_keys[0])
            vb_idx = voice_keys.index(cur_vb) if cur_vb in voice_keys else 0
            scene["dub_voice_b"] = db2.selectbox("Character B Voice", voice_keys, index=vb_idx, key=f"spot_voice_b_{idx}")

            scene["text_b"] = st.text_area(
                "Character B Dialogue Line",
                value=scene.get("text_b", ""),
                height=75,
                key=f"spot_text_b_{idx}",
            )

        if st.button(f"🎙️ Generate & Preview Dubbing for Scene {idx + 1}", key=f"prev_dub_{idx}"):
            v_code_a = DUBBING_VOICE_PRESETS.get(scene["dub_voice_label"], "en-US-ChristopherNeural")
            dub_data_a = synthesize_character_dubbing(scene["text"], v_code_a, scene["dub_rate"])
            if dub_data_a:
                scene["dub_audio_bytes"] = dub_data_a
                st.success(f"Generated Character A dubbing using {scene['dub_voice_label']}!")
            else:
                st.warning("Could not generate Character A dubbing for empty text.")

            if scene["dialogue_mode"] and scene.get("text_b", "").strip():
                v_code_b = DUBBING_VOICE_PRESETS.get(scene.get("dub_voice_b", ""), "en-US-AriaNeural")
                dub_data_b = synthesize_character_dubbing(scene["text_b"], v_code_b, scene["dub_rate"])
                if dub_data_b:
                    scene["dub_audio_b_bytes"] = dub_data_b
                    st.success(f"Generated Character B dubbing using {scene.get('dub_voice_b')}!")

        if scene.get("dub_audio_bytes"):
            st.caption("Character A Dubbing Preview:")
            st.audio(scene["dub_audio_bytes"], format="audio/mp3")
        if scene.get("dialogue_mode") and scene.get("dub_audio_b_bytes"):
            st.caption("Character B Dubbing Preview:")
            st.audio(scene["dub_audio_b_bytes"], format="audio/mp3")

        m1, m2, m3, m4 = st.columns([2, 2, 2, 1])
        sfx_idx = SFX_PRESETS.index(scene["sfx"]) if scene.get("sfx") in SFX_PRESETS else 0
        scene["sfx"] = m1.selectbox("Sound Effect (SFX)", SFX_PRESETS, index=sfx_idx, key=f"spot_sfx_{idx}")

        img_file = m2.file_uploader(f"Insert Image at Scene {idx + 1}", type=["png", "jpg", "jpeg"], key=f"spot_img_{idx}")
        if img_file is not None:
            scene["image_bytes"] = img_file.getvalue()
            scene["image_name"] = img_file.name

        aud_file = m3.file_uploader(f"Insert Scene Song / SFX Audio {idx + 1}", type=["mp3", "wav", "m4a"], key=f"spot_aud_{idx}")
        if aud_file is not None:
            scene["audio_bytes"] = aud_file.getvalue()
            scene["audio_name"] = aud_file.name

        scene["audio_volume"] = m4.slider("Audio Vol", min_value=0.0, max_value=1.5, value=float(scene.get("audio_volume", 0.9)), step=0.1, key=f"spot_vol_{idx}")

        act1, act2, act3 = st.columns(3)
        if idx > 0 and act1.button("⬆️ Move Up", key=f"up_spot_{idx}"):
            st.session_state["video_scenes"][idx - 1], st.session_state["video_scenes"][idx] = (
                st.session_state["video_scenes"][idx],
                st.session_state["video_scenes"][idx - 1],
            )
            st.rerun()
        if idx < len(st.session_state["video_scenes"]) - 1 and act2.button("⬇️ Move Down", key=f"dn_spot_{idx}"):
            st.session_state["video_scenes"][idx + 1], st.session_state["video_scenes"][idx] = (
                st.session_state["video_scenes"][idx],
                st.session_state["video_scenes"][idx + 1],
            )
            st.rerun()
        if len(st.session_state["video_scenes"]) > 1 and act3.button("🗑️ Remove Scene", key=f"del_spot_{idx}"):
            st.session_state["video_scenes"].pop(idx)
            st.rerun()

# Re-number spots cleanly
for i, s in enumerate(st.session_state["video_scenes"], start=1):
    s["spot"] = i

# Render & Download Final Movie
st.markdown("### 🎬 Finalize, Preview & Download Movie (.mp4)")
res_choice = st.selectbox("Output Format:", ["Landscape Long-Form (1280x720)", "Vertical Shorts (1080x1920)"])

if st.button("🎥 Render Final Movie (.mp4)", type="primary"):
    with st.status("Rendering movie scenes, human/cartoon characters, dialogue dubbing, music & .mp4...", expanded=True) as v_status:
        try:
            mp4_bytes = render_scenes_to_mp4(
                st.session_state["video_scenes"],
                res_choice,
                global_score_bytes=st.session_state.get("global_score_bytes"),
                global_score_name=st.session_state.get("global_score_name"),
            )
            st.session_state["rendered_video_bytes"] = mp4_bytes
            v_status.update(label="Movie rendered successfully!", state="complete", expanded=False)
        except Exception as v_err:
            v_status.update(label="Movie rendering failed", state="error", expanded=True)
            st.error(f"Could not render movie: {v_err}")

if st.session_state.get("rendered_video_bytes"):
    st.video(st.session_state["rendered_video_bytes"])
    st.download_button(
        label="⬇️ Download Final Movie (.mp4)",
        data=st.session_state["rendered_video_bytes"],
        file_name="youtube_creator_final_movie.mp4",
        mime="video/mp4",
        type="primary",
    )

# Progress Tracker
st.divider()
level_number = int(selected_level.split(":")[0].replace("Level ", ""))
st.write(f"**Creator Journey Progress:** Level {level_number} of 7")
st.progress(level_number / 7)
