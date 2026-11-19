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
from moviepy import AudioFileClip, CompositeAudioClip, ImageClip, concatenate_videoclips
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

# Market-style selectable studio presets
BACKDROP_PRESETS = {
    "Midnight Calm (#141824)": "#141824",
    "Deep Slate Wisdom (#1B2232)": "#1B2232",
    "Warm Amber Studio (#2A1F14)": "#2A1F14",
    "Forest Reflection (#12221D)": "#12221D",
    "Royal Navy (#111936)": "#111936",
    "Charcoal Minimal (#18181B)": "#18181B",
}

ANIMATED_CHARACTER_PRESETS = {
    "None (No Character)": {
        "badge": "",
        "accent": (245, 197, 24),
        "outfit": (40, 46, 62),
        "default_voice": "en-US-ChristopherNeural",
    },
    "Calm Mentor (Animated)": {
        "badge": "MENTOR",
        "accent": (245, 197, 24),
        "outfit": (36, 68, 110),
        "default_voice": "en-US-ChristopherNeural",
    },
    "Wise Guide (Animated)": {
        "badge": "GUIDE",
        "accent": (120, 210, 170),
        "outfit": (28, 74, 62),
        "default_voice": "en-IN-PrabhatNeural",
    },
    "Energetic Host (Animated)": {
        "badge": "HOST",
        "accent": (255, 138, 76),
        "outfit": (115, 42, 42),
        "default_voice": "en-US-GuyNeural",
    },
    "Thoughtful Thinker (Animated)": {
        "badge": "THINKER",
        "accent": (155, 180, 255),
        "outfit": (58, 48, 96),
        "default_voice": "en-US-AriaNeural",
    },
}

CHARACTER_MOTION_PRESETS = [
    "Idle Breathing & Bobbing",
    "Speaking Mouth/Ring Pulse",
    "Gentle Float & Drift",
    "Static Pose",
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
    "Clean Typography Card",
    "Stock B-Roll Concept: Sunrise & Calm Path",
    "Stock B-Roll Concept: Journaling & Focus",
    "Stock B-Roll Concept: City Lights & Reflection",
    "Chart / Framework Diagram Card",
]

VIDEO_CLIP_PRESETS = [
    "Static Scene Frame",
    "Slow Ken Burns Drift (Simulated Motion)",
    "Gentle Pulse Zoom (Simulated Motion)",
]

ANIMATION_PRESETS = [
    "Fade In Clean",
    "Slide Up Hook",
    "Typewriter / Line Reveal",
    "Soft Pop Emphasis",
]

SFX_PRESETS = [
    "None",
    "Soft Whoosh (Transition)",
    "Gentle Chime (Insight)",
    "Warm Bell (Key Takeaway)",
    "Subtle Pulse (Hook)",
]

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
            "duration": 7,
            "text": "Most beginners stay stuck in life wisdom because they consume advice without applying one habit.",
            "backdrop_name": "Midnight Calm (#141824)",
            "bg_color": "#141824",
            "character": "Calm Mentor (Animated)",
            "char_motion": "Speaking Mouth/Ring Pulse",
            "enable_dubbing": True,
            "dub_voice_label": "Calm Mentor — Christopher (US Male)",
            "dub_rate": "+0%",
            "dub_audio_bytes": None,
            "visual_preset": "Stock B-Roll Concept: Sunrise & Calm Path",
            "video_preset": "Slow Ken Burns Drift (Simulated Motion)",
            "animation": "Slide Up Hook",
            "sfx": "Subtle Pulse (Hook)",
            "image_bytes": None,
            "image_name": None,
            "audio_bytes": None,
            "audio_name": None,
            "audio_volume": 0.85,
        },
        {
            "spot": 2,
            "title": "Core Lesson",
            "duration": 8,
            "text": "Pick one practical mindset shift this week, test it daily, and track what actually changes.",
            "backdrop_name": "Deep Slate Wisdom (#1B2232)",
            "bg_color": "#1B2232",
            "character": "Thoughtful Thinker (Animated)",
            "char_motion": "Idle Breathing & Bobbing",
            "enable_dubbing": True,
            "dub_voice_label": "Thoughtful Thinker — Aria (US Female)",
            "dub_rate": "+0%",
            "dub_audio_bytes": None,
            "visual_preset": "Stock B-Roll Concept: Journaling & Focus",
            "video_preset": "Gentle Pulse Zoom (Simulated Motion)",
            "animation": "Fade In Clean",
            "sfx": "Gentle Chime (Insight)",
            "image_bytes": None,
            "image_name": None,
            "audio_bytes": None,
            "audio_name": None,
            "audio_volume": 0.85,
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

    # Fallback to gTTS if edge-tts is unavailable or blocked
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


def create_scene_frame_image(
    scene: dict,
    width: int,
    height: int,
    temp_dir: str,
    t_sec: float = 0.0,
    src_img_path: str | None = None,
    frame_idx: int = 0,
) -> str:
    bg_rgb = hex_to_rgb(scene.get("bg_color", "#141824"))
    canvas = Image.new("RGB", (width, height), bg_rgb)
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.load_default()

    char_name = scene.get("character", "None (No Character)")
    char_info = ANIMATED_CHARACTER_PRESETS.get(char_name, ANIMATED_CHARACTER_PRESETS["None (No Character)"])
    has_character = char_name != "None (No Character)"

    visual_tag = scene.get("visual_preset", "Clean Typography Card")
    anim_tag = scene.get("animation", "Fade In Clean")
    spot_label = f"Spot {scene['spot']} — {scene.get('title', 'Scene')} | {anim_tag}"
    draw.text((60, 36), spot_label, fill=(245, 197, 24), font=font)
    draw.text((60, 56), f"Visual: {visual_tag} | Character: {char_name}", fill=(180, 190, 210), font=font)

    if src_img_path and os.path.exists(src_img_path):
        uploaded_img = Image.open(src_img_path).convert("RGB")
        max_w = int(width * 0.62)
        max_h = int(height * 0.44)
        uploaded_img.thumbnail((max_w, max_h))
        x_pos = (width - uploaded_img.width) // 2 - (95 if has_character else 0)
        x_pos = max(60, x_pos)
        y_pos = 95
        canvas.paste(uploaded_img, (x_pos, y_pos))
        text_y_start = y_pos + uploaded_img.height + 28
    else:
        box_top = 95
        box_bottom = int(height * 0.45)
        box_right = width - (290 if has_character else 60)
        draw.rectangle((60, box_top, max(260, box_right), box_bottom), outline=(245, 197, 24), width=2)
        draw.text((80, box_top + 18), f"Media Preset: {visual_tag}", fill=(245, 197, 24), font=font)
        draw.text((80, box_top + 42), f"Motion: {scene.get('video_preset', 'Static Scene Frame')}", fill=(210, 215, 225), font=font)
        text_y_start = box_bottom + 28

    # Draw animated character avatar if enabled
    if has_character:
        motion_mode = scene.get("char_motion", "Idle Breathing & Bobbing")
        bob_y = 0
        drift_x = 0
        mouth_open = False

        if "Bobbing" in motion_mode:
            bob_y = int(10 * math.sin(2 * math.pi * 1.4 * t_sec))
        elif "Pulse" in motion_mode:
            bob_y = int(5 * math.sin(2 * math.pi * 2.0 * t_sec))
            mouth_open = math.sin(2 * math.pi * 4.5 * t_sec) > 0.1
        elif "Float" in motion_mode:
            bob_y = int(8 * math.sin(2 * math.pi * 1.1 * t_sec))
            drift_x = int(12 * math.cos(2 * math.pi * 0.7 * t_sec))

        cx = width - 175 + drift_x
        cy = int(height * 0.36) + bob_y
        r = 72
        accent_rgb = char_info["accent"]
        outfit_rgb = char_info["outfit"]

        # Outer pulse ring when speaking
        if mouth_open:
            draw.ellipse((cx - r - 10, cy - r - 10, cx + r + 10, cy + r + 10), outline=accent_rgb, width=3)

        # Shoulders / outfit
        draw.pieslice((cx - r, cy + 12, cx + r, cy + r + 48), start=180, end=360, fill=outfit_rgb, outline=accent_rgb, width=2)
        # Head
        draw.ellipse((cx - 42, cy - 52, cx + 42, cy + 32), fill=accent_rgb, outline=(255, 255, 255), width=2)
        # Eyes
        draw.ellipse((cx - 20, cy - 18, cx - 8, cy - 6), fill=(20, 24, 36))
        draw.ellipse((cx + 8, cy - 18, cx + 20, cy - 6), fill=(20, 24, 36))
        # Animated mouth
        if mouth_open:
            draw.ellipse((cx - 10, cy + 6, cx + 10, cy + 20), fill=(20, 24, 36))
        else:
            draw.line((cx - 12, cy + 12, cx + 12, cy + 12), fill=(20, 24, 36), width=3)

        draw.text((cx - 65, cy + r + 24), f"{char_info['badge']} ({motion_mode.split()[0]})", fill=accent_rgb, font=font)

    wrap_width = 68 if width >= 1200 else 48
    wrapped_lines = textwrap.wrap(scene.get("text", ""), width=wrap_width)
    cur_y = text_y_start
    for line in wrapped_lines[:10]:
        if cur_y > height - 50:
            break
        draw.text((60, cur_y), line, fill=(245, 245, 245), font=font)
        cur_y += 22

    out_frame_path = os.path.join(temp_dir, f"frame_spot_{scene['spot']}_{frame_idx}.png")
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
            char_name = scene.get("character", "None (No Character)")
            motion_mode = scene.get("char_motion", "Idle Breathing & Bobbing")
            has_animated_char = (char_name != "None (No Character)") and ("Static" not in motion_mode)

            src_img_path = None
            if scene.get("image_bytes"):
                src_img_path = os.path.join(tmpdir, f"src_img_{scene['spot']}.png")
                with open(src_img_path, "wb") as f:
                    f.write(scene["image_bytes"])

            if has_animated_char:
                # Sample animated frames at 6 fps for smooth motion while keeping cloud render times practical
                sample_fps = 6
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
                img_clip = ImageClip(sampled_paths[0]).with_duration(dur)
                # Build animated clip via make_frame
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

            # Optional camera/motion preset
            v_preset = scene.get("video_preset", "")
            if "Ken Burns" in v_preset:
                img_clip = img_clip.resized(lambda t: 1.0 + 0.012 * t)
            elif "Pulse Zoom" in v_preset:
                img_clip = img_clip.resized(lambda t: 1.0 + 0.015 * math.sin(math.pi * min(1.0, t / dur)))

            audio_layers = []
            vol = float(scene.get("audio_volume", 0.85))

            # 1) Character dubbing audio (pre-generated or auto-synthesized when enabled)
            dub_bytes = scene.get("dub_audio_bytes")
            if not dub_bytes and scene.get("enable_dubbing") and scene.get("text", "").strip():
                voice_code = DUBBING_VOICE_PRESETS.get(
                    scene.get("dub_voice_label", ""),
                    ANIMATED_CHARACTER_PRESETS.get(char_name, {}).get("default_voice", "en-US-ChristopherNeural"),
                )
                dub_bytes = synthesize_character_dubbing(
                    scene.get("text", ""),
                    voice_code=voice_code,
                    rate=scene.get("dub_rate", "+0%"),
                )
                scene["dub_audio_bytes"] = dub_bytes

            if dub_bytes:
                dub_path = os.path.join(tmpdir, f"dub_spot_{scene['spot']}.mp3")
                with open(dub_path, "wb") as df:
                    df.write(dub_bytes)
                try:
                    d_clip = AudioFileClip(dub_path).with_volume_scaled(vol)
                    if d_clip.duration > dur:
                        d_clip = d_clip.subclipped(0, dur)
                    audio_layers.append(d_clip)
                except Exception:
                    pass

            # 2) Custom uploaded song/audio at this spot
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

            # 3) Built-in SFX preset
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
        out_mp4 = os.path.join(tmpdir, "final_youtube_video.mp4")
        has_audio = any(
            s.get("dub_audio_bytes")
            or s.get("enable_dubbing")
            or s.get("audio_bytes")
            or (s.get("sfx") and s.get("sfx") != "None")
            for s in scenes
        )
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


def build_auto_draft_scenes(draft_text: str, source_label: str) -> list:
    clean_lines = [
        line.strip().lstrip("#*-0123456789. ").strip()
        for line in draft_text.splitlines()
        if len(line.strip()) > 35 and not line.strip().startswith("---")
    ]
    if not clean_lines:
        clean_lines = [
            "Start with a relatable beginner struggle in the first 30 seconds.",
            "Share one simple life wisdom habit that creates calm and clarity.",
            "Give a clear step-by-step action viewers can try today.",
        ]

    picked = clean_lines[:4]
    backdrop_cycle = list(BACKDROP_PRESETS.keys())
    char_cycle = [k for k in ANIMATED_CHARACTER_PRESETS.keys() if k != "None (No Character)"]
    motion_cycle = CHARACTER_MOTION_PRESETS
    voice_cycle = list(DUBBING_VOICE_PRESETS.keys())
    vis_cycle = VISUAL_MEDIA_PRESETS
    vid_cycle = VIDEO_CLIP_PRESETS
    anim_cycle = ANIMATION_PRESETS
    sfx_cycle = [s for s in SFX_PRESETS if s != "None"]

    built = []
    for idx, line in enumerate(picked, start=1):
        b_name = backdrop_cycle[(idx - 1) % len(backdrop_cycle)]
        built.append(
            {
                "spot": idx,
                "title": f"Auto Spot {idx} ({source_label.split(':')[0]})",
                "duration": 7,
                "text": line[:320],
                "backdrop_name": b_name,
                "bg_color": BACKDROP_PRESETS[b_name],
                "character": char_cycle[(idx - 1) % len(char_cycle)],
                "char_motion": motion_cycle[(idx - 1) % len(motion_cycle)],
                "enable_dubbing": True,
                "dub_voice_label": voice_cycle[(idx - 1) % len(voice_cycle)],
                "dub_rate": "+0%",
                "dub_audio_bytes": None,
                "visual_preset": vis_cycle[(idx - 1) % len(vis_cycle)],
                "video_preset": vid_cycle[(idx - 1) % len(vid_cycle)],
                "animation": anim_cycle[(idx - 1) % len(anim_cycle)],
                "sfx": sfx_cycle[(idx - 1) % len(sfx_cycle)],
                "image_bytes": None,
                "image_name": None,
                "audio_bytes": None,
                "audio_name": None,
                "audio_volume": 0.85,
            }
        )
    return built


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

# 7. Filter, Select, Edit & Assemble Video Spots with Animated Characters & Voice Dubbing
st.divider()
st.subheader("🎞️ Complete Creator Studio (Filter, Animated Characters, Voice Dubbing, Presets & .mp4)")

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
        chosen_source_level = st.selectbox("Select Generated Level to Inspect or Build Video From:", filtered_levels)
        source_text = all_outputs[chosen_source_level]["content"]
        st.text_area("Editable Source Draft (Edit text before turning into spots):", value=source_text, height=160, key="editable_source_draft")

        a_col1, a_col2, a_col3 = st.columns(3)
        if a_col1.button("✨ Auto-Build Best Draft Spots", type="primary", use_container_width=True):
            st.session_state["video_scenes"] = build_auto_draft_scenes(
                st.session_state.get("editable_source_draft", source_text),
                chosen_source_level,
            )
            st.rerun()

        if a_col2.button("➕ Add New Spot at End", use_container_width=True):
            next_spot_num = len(st.session_state["video_scenes"]) + 1
            default_bg = list(BACKDROP_PRESETS.keys())[0]
            st.session_state["video_scenes"].append(
                {
                    "spot": next_spot_num,
                    "title": f"Spot {next_spot_num}",
                    "duration": 7,
                    "text": st.session_state.get("editable_source_draft", "")[:240],
                    "backdrop_name": default_bg,
                    "bg_color": BACKDROP_PRESETS[default_bg],
                    "character": "Calm Mentor (Animated)",
                    "char_motion": "Idle Breathing & Bobbing",
                    "enable_dubbing": True,
                    "dub_voice_label": list(DUBBING_VOICE_PRESETS.keys())[0],
                    "dub_rate": "+0%",
                    "dub_audio_bytes": None,
                    "visual_preset": VISUAL_MEDIA_PRESETS[0],
                    "video_preset": VIDEO_CLIP_PRESETS[0],
                    "animation": ANIMATION_PRESETS[0],
                    "sfx": SFX_PRESETS[0],
                    "image_bytes": None,
                    "image_name": None,
                    "audio_bytes": None,
                    "audio_name": None,
                    "audio_volume": 0.85,
                }
            )
            st.rerun()

        if a_col3.button("✂️ Split Draft into 3 Spots", use_container_width=True):
            raw_draft = st.session_state.get("editable_source_draft", "").strip()
            chunks = [p.strip() for p in raw_draft.split("\n\n") if p.strip()]
            picked_chunks = chunks[:3] if len(chunks) >= 3 else (raw_draft or "Life wisdom point").split(". ")[:3]
            new_scenes = []
            bg_list = list(BACKDROP_PRESETS.keys())
            char_list = [k for k in ANIMATED_CHARACTER_PRESETS.keys() if k != "None (No Character)"]
            voice_list = list(DUBBING_VOICE_PRESETS.keys())
            for idx, part in enumerate(picked_chunks, start=1):
                b_name = bg_list[(idx - 1) % len(bg_list)]
                new_scenes.append(
                    {
                        "spot": idx,
                        "title": f"Scene {idx} ({chosen_source_level.split(':')[0]})",
                        "duration": 7,
                        "text": part[:350],
                        "backdrop_name": b_name,
                        "bg_color": BACKDROP_PRESETS[b_name],
                        "character": char_list[(idx - 1) % len(char_list)],
                        "char_motion": CHARACTER_MOTION_PRESETS[idx % len(CHARACTER_MOTION_PRESETS)],
                        "enable_dubbing": True,
                        "dub_voice_label": voice_list[(idx - 1) % len(voice_list)],
                        "dub_rate": "+0%",
                        "dub_audio_bytes": None,
                        "visual_preset": VISUAL_MEDIA_PRESETS[idx % len(VISUAL_MEDIA_PRESETS)],
                        "video_preset": VIDEO_CLIP_PRESETS[idx % len(VIDEO_CLIP_PRESETS)],
                        "animation": ANIMATION_PRESETS[idx % len(ANIMATION_PRESETS)],
                        "sfx": SFX_PRESETS[idx % len(SFX_PRESETS)],
                        "image_bytes": None,
                        "image_name": None,
                        "audio_bytes": None,
                        "audio_name": None,
                        "audio_volume": 0.85,
                    }
                )
            if new_scenes:
                st.session_state["video_scenes"] = new_scenes
                st.rerun()
    else:
        st.warning("No generated levels match your filter keyword.")
else:
    st.info("Generate at least one level above to filter and pull text into video spots—or build starter spots below.")
    if st.button("✨ Auto-Build Starter Spots from Channel Topic"):
        sample_draft = (
            f"Why {target_audience or 'beginners'} struggle with {channel_topic or 'life wisdom'} at first.\n\n"
            f"A simple daily habit to apply {channel_topic or 'life wisdom'} without overwhelm.\n\n"
            "Your small action step for this week."
        )
        st.session_state["video_scenes"] = build_auto_draft_scenes(sample_draft, selected_level)
        st.rerun()

# Spot-by-Spot Timeline Editor
st.markdown("### 🧩 Spot-by-Spot Timeline Editor (Animated Characters, Dubbing & Media)")
char_keys = list(ANIMATED_CHARACTER_PRESETS.keys())
voice_keys = list(DUBBING_VOICE_PRESETS.keys())
b_keys = list(BACKDROP_PRESETS.keys())

for idx, scene in enumerate(st.session_state["video_scenes"]):
    dub_badge = "Dub ON" if scene.get("enable_dubbing") else "Dub OFF"
    with st.expander(
        f"Spot {idx + 1}: {scene.get('title', 'Scene')} ({scene.get('duration', 7)}s) — {scene.get('character', 'None')} | {dub_badge}",
        expanded=(idx == 0),
    ):
        sc1, sc2, sc3 = st.columns([2, 1, 1])
        scene["title"] = sc1.text_input("Spot Label", value=scene.get("title", f"Spot {idx + 1}"), key=f"spot_title_{idx}")
        scene["duration"] = sc2.number_input("Duration (sec)", min_value=2, max_value=60, value=int(scene.get("duration", 7)), key=f"spot_dur_{idx}")

        cur_b = scene.get("backdrop_name", b_keys[0])
        b_idx = b_keys.index(cur_b) if cur_b in b_keys else 0
        chosen_backdrop = sc3.selectbox("Backdrop Preset", b_keys, index=b_idx, key=f"spot_backdrop_{idx}")
        scene["backdrop_name"] = chosen_backdrop
        scene["bg_color"] = BACKDROP_PRESETS[chosen_backdrop]

        c_col1, c_col2, c_col3, c_col4 = st.columns([2, 2, 2, 1])
        cur_char = scene.get("character", char_keys[1])
        c_idx = char_keys.index(cur_char) if cur_char in char_keys else 0
        scene["character"] = c_col1.selectbox("Animated Character", char_keys, index=c_idx, key=f"spot_char_{idx}")

        cur_motion = scene.get("char_motion", CHARACTER_MOTION_PRESETS[0])
        m_idx = CHARACTER_MOTION_PRESETS.index(cur_motion) if cur_motion in CHARACTER_MOTION_PRESETS else 0
        scene["char_motion"] = c_col2.selectbox("Character Motion", CHARACTER_MOTION_PRESETS, index=m_idx, key=f"spot_motion_{idx}")

        cur_voice = scene.get("dub_voice_label", voice_keys[0])
        v_idx = voice_keys.index(cur_voice) if cur_voice in voice_keys else 0
        scene["dub_voice_label"] = c_col3.selectbox("Character Dubbing Voice", voice_keys, index=v_idx, key=f"spot_voice_{idx}")

        scene["enable_dubbing"] = c_col4.checkbox("Dub Script", value=bool(scene.get("enable_dubbing", True)), key=f"spot_dub_on_{idx}")

        p1, p2, p3, p4 = st.columns(4)
        vis_idx = VISUAL_MEDIA_PRESETS.index(scene["visual_preset"]) if scene.get("visual_preset") in VISUAL_MEDIA_PRESETS else 0
        scene["visual_preset"] = p1.selectbox("Image / Visual Preset", VISUAL_MEDIA_PRESETS, index=vis_idx, key=f"spot_vis_{idx}")

        vid_idx = VIDEO_CLIP_PRESETS.index(scene["video_preset"]) if scene.get("video_preset") in VIDEO_CLIP_PRESETS else 0
        scene["video_preset"] = p2.selectbox("Video / Motion Preset", VIDEO_CLIP_PRESETS, index=vid_idx, key=f"spot_vid_{idx}")

        anim_idx = ANIMATION_PRESETS.index(scene["animation"]) if scene.get("animation") in ANIMATION_PRESETS else 0
        scene["animation"] = p3.selectbox("Text Animation Preset", ANIMATION_PRESETS, index=anim_idx, key=f"spot_anim_{idx}")

        rate_options = ["-15%", "+0%", "+15%", "+25%"]
        cur_rate = scene.get("dub_rate", "+0%")
        r_idx = rate_options.index(cur_rate) if cur_rate in rate_options else 1
        scene["dub_rate"] = p4.selectbox("Voice Speed", rate_options, index=r_idx, key=f"spot_rate_{idx}")

        scene["text"] = st.text_area("Script / Narration Text for Dubbing & Screen", value=scene.get("text", ""), height=90, key=f"spot_text_{idx}")

        if st.button(f"🎙️ Generate & Preview Dubbing for Spot {idx + 1}", key=f"prev_dub_{idx}"):
            v_code = DUBBING_VOICE_PRESETS.get(scene["dub_voice_label"], "en-US-ChristopherNeural")
            dub_data = synthesize_character_dubbing(scene["text"], v_code, scene["dub_rate"])
            if dub_data:
                scene["dub_audio_bytes"] = dub_data
                st.success(f"Generated dubbing using {scene['dub_voice_label']}!")
            else:
                st.warning("Could not generate dubbing audio for empty text.")

        if scene.get("dub_audio_bytes"):
            st.audio(scene["dub_audio_bytes"], format="audio/mp3")

        m1, m2, m3, m4 = st.columns([2, 2, 2, 1])
        sfx_idx = SFX_PRESETS.index(scene["sfx"]) if scene.get("sfx") in SFX_PRESETS else 0
        scene["sfx"] = m1.selectbox("Sound Effect Preset", SFX_PRESETS, index=sfx_idx, key=f"spot_sfx_{idx}")

        img_file = m2.file_uploader(f"Custom Image (Spot {idx + 1})", type=["png", "jpg", "jpeg"], key=f"spot_img_{idx}")
        if img_file is not None:
            scene["image_bytes"] = img_file.getvalue()
            scene["image_name"] = img_file.name

        aud_file = m3.file_uploader(f"Custom Song / Audio (Spot {idx + 1})", type=["mp3", "wav", "m4a"], key=f"spot_aud_{idx}")
        if aud_file is not None:
            scene["audio_bytes"] = aud_file.getvalue()
            scene["audio_name"] = aud_file.name

        scene["audio_volume"] = m4.slider("Audio Vol", min_value=0.0, max_value=1.5, value=float(scene.get("audio_volume", 0.85)), step=0.1, key=f"spot_vol_{idx}")

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
    with st.status("Rendering animated characters, voice dubbing, visuals, and .mp4...", expanded=True) as v_status:
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
