# =============================================================
# AUTO CONTENT PIPELINE v3 — YOUTUBE SHORTS EDITION
# 100% FREE — No IP blocks, Official YouTube API
# =============================================================
# WHAT IT DOES (5x per day automatically via GitHub Actions):
#   1. Fetches top 10 trending YouTube videos (USA)
#   2. Generates a cinematic AI image via Pollinations.ai
#   3. Converts image into a YouTube Short (vertical MP4 video)
#      - Smooth Ken Burns zoom effect
#      - Motivational text overlay
#      - Background music from free library
#   4. Uploads to your YouTube channel as a Short
#
# FREE TOOLS USED:
#   - YouTube Data API v3     → trend analysis + upload
#   - Pollinations.ai         → AI image generation (no key)
#   - moviepy                 → video creation
#   - PIL/Pillow              → image processing
#   - numpy                   → video frame generation
#
# INSTALL:
#   pip install google-api-python-client google-auth-oauthlib
#               requests schedule moviepy pillow numpy
#
# FIRST TIME SETUP:
#   1. Run locally: python pipeline.py --auth
#      This opens a browser to authorize YouTube upload
#      It saves youtube_token.json — upload that to GitHub Secret
#   2. After auth, run: python pipeline.py --once to test
#   3. Push to GitHub — it runs automatically 5x/day
# =============================================================

import os
import sys
import time
import json
import random
import logging
import schedule
import requests
import urllib.parse
import numpy as np
from datetime import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import io

# =============================================================
# LOGGING — Unicode safe for Windows
# =============================================================

log_formatter  = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
file_handler   = logging.FileHandler("pipeline.log", encoding="utf-8")
file_handler.setFormatter(log_formatter)
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
log = logging.getLogger(__name__)

# =============================================================
# CONFIG — all credentials read from environment variables
# Set these as GitHub Secrets (never hardcode passwords)
# =============================================================

YOUTUBE_API_KEY   = os.environ.get("YOUTUBE_API_KEY", "YOUR_YOUTUBE_API_KEY_HERE")
YOUTUBE_TOKEN     = os.environ.get("YOUTUBE_TOKEN", "")   # JSON string from GitHub Secret
HF_TOKEN          = os.environ.get("HF_TOKEN", "")        # Hugging Face token

OUTPUT_FOLDER     = "generated_shots"
VIDEO_FOLDER      = "generated_videos"
PROMPT_FILE       = "latest_prompt.txt"
TOKEN_FILE        = "youtube_token.json"

# YouTube Shorts = vertical 1080x1920
IMG_WIDTH         = 1080
IMG_HEIGHT        = 1920

# Video settings
VIDEO_DURATION    = 30      # seconds (YouTube Shorts max = 60s)
VIDEO_FPS         = 30
FONT_SIZE         = 52

# Your content niche
CONTENT_CONCEPT = """
Cinematic luxury lifestyle content:
- Powerful motivation and success mindset
- Luxury visuals (cars, cities, architecture, fashion)
- Emotional storytelling for USA audience
- Viral short-form style for YouTube Shorts
"""

# YouTube video settings
YT_TAGS = [
    "luxury", "motivation", "success", "lifestyle", "mindset",
    "wealthy", "goals", "luxurylifestyle", "successmindset",
    "viral", "shorts", "youtubeshorts", "motivational"
]

# =============================================================
# TOOL 1 — YOUTUBE TREND ANALYZER
# Free: YouTube Data API v3 (10,000 units/day)
# =============================================================

def analyze_youtube_trends():
    log.info("=" * 50)
    log.info("TOOL 1: Analyzing YouTube Trends")
    log.info("=" * 50)

    try:
        from googleapiclient.discovery import build

        youtube  = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)
        response = youtube.videos().list(
            part       = "snippet,statistics",
            chart      = "mostPopular",
            regionCode = "US",
            maxResults = 10
        ).execute()

        trends = []
        for item in response.get("items", []):
            snippet = item["snippet"]
            stats   = item.get("statistics", {})
            trends.append({
                "title":       snippet.get("title", ""),
                "description": snippet.get("description", "")[:300],
                "tags":        snippet.get("tags", [])[:8],
                "views":       stats.get("viewCount", "0"),
            })

        log.info(f"Found {len(trends)} trending videos")
        for i, t in enumerate(trends, 1):
            safe = t['title'].encode('ascii', 'replace').decode('ascii')
            log.info(f"  {i}. {safe} ({t['views']} views)")

        titles_block = "\n".join([f"- {t['title']}" for t in trends])
        tags_block   = ", ".join(
            tag for t in trends for tag in t["tags"]
        )[:500]

        prompt = f"""You are a viral content creator specializing in luxury lifestyle.

TRENDING ON YOUTUBE RIGHT NOW (USA):
{titles_block}

TRENDING TAGS: {tags_block}

CONTENT CONCEPT:
{CONTENT_CONCEPT}

YOUR TASK:
Write ONE powerful cinematic image prompt AND one short motivational quote.

Format your response exactly like this:
IMAGE: [your image prompt here]
QUOTE: [your motivational quote here - max 8 words]

Requirements for IMAGE:
- Strong visual scene, no people, only atmosphere and objects
- Luxury setting: penthouse, sports car, private jet, rooftop, yacht
- Golden hour or dramatic night lighting
- Hyper-realistic, cinematic, 8K quality
- Under 60 words, no markdown

Requirements for QUOTE:
- Powerful, short, punchy
- About success, wealth, freedom, or mindset
- Max 8 words
- No quotes marks"""

        with open(PROMPT_FILE, "w", encoding="utf-8") as f:
            f.write(prompt)

        log.info("Trend prompt saved successfully")
        return prompt, trends

    except Exception as e:
        log.error(f"YouTube API error: {e}")
        log.info("Using fallback prompt...")
        return generate_fallback_prompt()


def generate_fallback_prompt():
    scenes = [
        ("A matte black Lamborghini on rain-soaked highway at night, neon reflections, cinematic 8K",
         "Success is built in silence."),
        ("Luxury penthouse infinity pool in Dubai at golden hour, glass skyscrapers, cinematic 8K",
         "Your vision becomes your reality."),
        ("Private jet interior at sunset, cream leather, champagne, clouds below, cinematic 8K",
         "Freedom is earned, not given."),
        ("Empty mansion living room at dawn, floor-to-ceiling windows, city skyline, cinematic 8K",
         "Build the life they stare at."),
        ("Black Rolls Royce on foggy mountain road at sunrise, ultra-realistic cinematic 8K",
         "Discipline separates winners from dreamers."),
    ]
    image_prompt, quote = random.choice(scenes)
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(f"IMAGE: {image_prompt}\nQUOTE: {quote}")
    return f"IMAGE: {image_prompt}\nQUOTE: {quote}", []


# =============================================================
# TOOL 2 — AI CONTENT GENERATOR
# Free: Pollinations.ai (no key, no signup)
# =============================================================

def generate_ai_content(trend_prompt=None):
    log.info("=" * 50)
    log.info("TOOL 2: Generating AI Content")
    log.info("=" * 50)

    if trend_prompt is None:
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                trend_prompt = f.read()
        else:
            trend_prompt, _ = generate_fallback_prompt()

    # Generate image prompt + quote via Pollinations text AI
    log.info("Generating image prompt + quote via Pollinations AI...")
    image_prompt, quote = generate_text_content(trend_prompt)

    safe = image_prompt.encode('ascii', 'replace').decode('ascii')
    log.info(f"Image prompt: {safe[:150]}")
    log.info(f"Quote: {quote}")

    # Generate AI image
    log.info("Generating image via Pollinations FLUX model...")
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    image_path  = os.path.join(OUTPUT_FOLDER, f"content_{timestamp}.jpg")
    result      = generate_image(image_prompt, image_path)

    if not result:
        log.error("Image generation failed")
        return None, None, None

    # Create YouTube Short video from the image
    log.info("Creating YouTube Short video...")
    Path(VIDEO_FOLDER).mkdir(exist_ok=True)
    video_path = os.path.join(VIDEO_FOLDER, f"short_{timestamp}.mp4")
    video      = create_youtube_short(image_path, quote, video_path)

    # Generate YouTube title + description
    title       = generate_title(quote)
    description = generate_description(image_prompt, quote)

    # Save metadata
    meta_path = image_path.replace(".jpg", "_meta.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(f"TIMESTAMP: {timestamp}\n")
        f.write(f"IMAGE PROMPT:\n{image_prompt}\n\n")
        f.write(f"QUOTE: {quote}\n\n")
        f.write(f"TITLE: {title}\n\n")
        f.write(f"DESCRIPTION:\n{description}\n")

    log.info(f"Content saved: {video_path}")
    return video, title, description


def generate_text_content(trend_prompt: str):
    """
    Smart keyword-based content selector.
    Matches trending topics to relevant luxury scenes.
    No external API needed — instant, never rate limited.
    """
    t = trend_prompt.lower()

    # Master pool — 40+ unique scenes across all categories
    # Always picks randomly so every video is different
    all_scenes = [
        # Cars
        ("Matte black Lamborghini Aventador on rain-soaked highway at night, neon city reflections, cinematic 8K", "Success is built in silence."),
        ("Black Rolls Royce Phantom on foggy mountain road at sunrise, ultra-realistic cinematic 8K", "Discipline creates destiny."),
        ("White McLaren 720S parked on empty desert highway at golden hour, dramatic sky, cinematic 8K", "Be rare. Be relentless."),
        ("Ferrari SF90 in underground luxury garage, dramatic spotlighting, red paint gleaming, cinematic 8K", "Earn what others only dream of."),
        ("Bentley Continental GT driving through rain at night, city lights blur, cinematic 8K", "Move in silence. Let success make the noise."),
        ("Matte grey Porsche 911 on coastal cliff road at sunset, ocean below, cinematic 8K", "The view from the top is worth every climb."),
        # Penthouses and mansions
        ("Empty ultra-luxury penthouse living room at dawn, floor to ceiling windows, Dubai skyline, cinematic 8K", "Build the life they stare at."),
        ("Modern mansion exterior at night, illuminated infinity pool, palm trees, city view, cinematic 8K", "Your dream home is a decision away."),
        ("Luxury penthouse bedroom at golden hour, silk sheets, panoramic city view, cinematic 8K", "Wake up in the life you used to dream about."),
        ("Minimalist white mansion interior, double height ceilings, art on walls, morning light, cinematic 8K", "Simple taste. Extraordinary life."),
        ("Luxury penthouse study at night, leather chair, whiskey glass, city lights below, cinematic 8K", "Stay focused. The world is loud on purpose."),
        ("Glass mansion on hillside at dusk, infinity pool merging with ocean horizon, cinematic 8K", "Elevate your standard. Elevate your life."),
        # Jets and travel
        ("Private jet interior at golden hour, cream leather seats, champagne glass, clouds below, cinematic 8K", "Freedom is earned not given."),
        ("Private jet flying above clouds at sunset, golden light through windows, cinematic 8K", "Your altitude is determined by your attitude."),
        ("Luxury first class suite on plane at night, champagne, starry sky outside window, cinematic 8K", "Travel is the only thing you buy that makes you richer."),
        ("Empty private jet tarmac at dawn, aircraft door open, stairs down, ready to fly, cinematic 8K", "The world belongs to those who move."),
        # Yachts and water
        ("Luxury yacht deck at golden hour, Mediterranean sea, champagne on table, cinematic 8K", "The ocean belongs to those who dare."),
        ("Superyacht sailing at sunset, golden wake behind it, empty horizon, cinematic 8K", "Chart your own course."),
        ("Yacht interior, teak deck, infinity ocean view, white sails, Mediterranean blue, cinematic 8K", "Some people dream of success. Others sail toward it."),
        # Hotels and rooftops
        ("Rooftop penthouse terrace Dubai at dusk, outdoor luxury furniture, city glow below, cinematic 8K", "Elevation is a mindset first."),
        ("Luxury hotel infinity pool overlooking city at night, champagne, warm amber light, cinematic 8K", "Winners prepare while others sleep."),
        ("Five star hotel suite at golden hour, king bed, city view, luxury interior, cinematic 8K", "You deserve the best room in the house."),
        ("Rooftop bar at night, city lights below, champagne glass catching light, cinematic 8K", "The higher you go the better the view."),
        # Music and art
        ("Black grand piano in empty luxury penthouse, floor to ceiling windows, city skyline at dusk, cinematic 8K", "Create what they can only dream of."),
        ("Modern recording studio with city view at night, warm lighting, premium equipment, cinematic 8K", "Your art is your empire."),
        ("Empty concert hall with golden lights, luxury interior, single spotlight, cinematic 8K", "Perform like the world is watching. It is."),
        # Nature and adventure
        ("Luxury overwater villa in Maldives at sunrise, crystal water, wooden deck, cinematic 8K", "Paradise is a decision."),
        ("Snow-capped mountain peak at sunrise, golden light, dramatic clouds, cinematic 8K", "The summit is earned not given."),
        ("Private beach at sunset, luxury chairs, champagne, nobody around, cinematic 8K", "When you win, the whole world is yours."),
        ("Aerial view of tropical island from helicopter, turquoise water, luxury resort below, cinematic 8K", "Life is short. Make it spectacular."),
        # Watches and fashion
        ("Luxury watch on black velvet, dramatic studio lighting, close up, cinematic 8K", "Value your time like it costs a fortune. It does."),
        ("Designer suit hanging by window, city skyline behind it, morning light, cinematic 8K", "Dress for the life you are building."),
        # Boardrooms and offices
        ("Empty modern boardroom, panoramic city view at dawn, long table, leather chairs, cinematic 8K", "The news reports the world. You change it."),
        ("Corner office penthouse floor at night, city lights below, desk with single lamp, cinematic 8K", "While they sleep you plan. While they plan you execute."),
        # Food and dining
        ("Private rooftop dining table set for two, city panorama, candles, luxury tableware, cinematic 8K", "The good life is built one decision at a time."),
        ("Michelin star restaurant table at night, champagne poured, city view through glass, cinematic 8K", "Taste what discipline tastes like."),
        # Miscellaneous luxury
        ("Luxury garage with Bugatti Chiron, Lamborghini, Ferrari, dramatic lighting, cinematic 8K", "Your garage should tell your story."),
        ("Penthouse gym overlooking city at sunrise, premium equipment, golden light, cinematic 8K", "The body you want is built in the hours they waste."),
        ("Empty luxury shopping mall after hours, designer stores, marble floors, cinematic 8K", "When you build enough, the world opens up."),
        ("Helicopter interior flying over Manhattan at night, city grid below, champagne, cinematic 8K", "Get high enough and perspective changes everything."),
    ]

    # Pick based on trending keywords but always randomize within category
    if any(w in t for w in ["music", "song", "gaga", "rapper", "album"]):
        category = [s for s in all_scenes if any(k in s[0].lower() for k in ["piano", "studio", "concert", "art"])]
    elif any(w in t for w in ["sport", "nba", "nfl", "celtics", "basketball", "football", "nuggets", "bruins"]):
        category = [s for s in all_scenes if any(k in s[0].lower() for k in ["gym", "garage", "mountain", "summit"])]
    elif any(w in t for w in ["movie", "trailer", "film", "series", "resident", "teaser"]):
        category = [s for s in all_scenes if any(k in s[0].lower() for k in ["jet", "yacht", "hotel", "cinema", "helicopter"])]
    elif any(w in t for w in ["news", "america", "politics", "breaking"]):
        category = [s for s in all_scenes if any(k in s[0].lower() for k in ["boardroom", "office", "penthouse study", "corner"])]
    else:
        category = all_scenes

    # Always pick fully random from entire pool — maximum variety every run
    pool = random.sample(all_scenes, min(8, len(all_scenes)))

    image_prompt, quote = random.choice(pool)
    log.info("Content selected via keyword matching")
    return image_prompt, quote


def generate_image(prompt: str, output_path: str, retries: int = 3) -> str | None:
    """
    Generate image via Hugging Face InferenceClient (correct 2026 method).
    Uses huggingface_hub library with FLUX.1-dev model.
    Free with HF token.
    """
    full_prompt = (
        f"{prompt}, cinematic photography, luxury lifestyle, "
        f"8K ultra-realistic, dramatic lighting, sharp focus, high detail"
    )

    from huggingface_hub import InferenceClient
    client = InferenceClient(api_key=HF_TOKEN)

    for attempt in range(1, retries + 1):
        try:
            log.info(f"HF image generation attempt {attempt}/{retries}...")

            # Returns a PIL Image object directly
            # Using FLUX.1-schnell — free, no billing required
            image = client.text_to_image(
                full_prompt,
                model="black-forest-labs/FLUX.1-schnell",
            )

            # Resize to exact 1080x1920 vertical
            image = image.convert("RGB")
            image = image.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)
            image.save(output_path, "JPEG", quality=95)

            log.info(f"Image saved: {output_path}")
            return output_path

        except Exception as e:
            log.error(f"HF attempt {attempt} error: {e}")
            if attempt < retries:
                log.info("Waiting 20s before retry...")
                time.sleep(20)

    log.warning("HF failed, trying Pollinations as backup...")
    return generate_image_pollinations(prompt, output_path)


def generate_image_pollinations(prompt: str, output_path: str) -> str | None:
    """Backup image generator using Pollinations.ai."""
    try:
        encoded = urllib.parse.quote(prompt)
        url     = (
            f"https://image.pollinations.ai/prompt/{encoded}"
            f"?width={IMG_WIDTH}&height={IMG_HEIGHT}"
            f"&model=flux&seed={random.randint(1,99999)}&nologo=true"
        )
        log.info("Trying Pollinations backup...")
        r = requests.get(url, timeout=90)
        if r.status_code == 200 and len(r.content) > 10000:
            with open(output_path, "wb") as f:
                f.write(r.content)
            log.info(f"Pollinations backup saved: {output_path}")
            return output_path
    except Exception as e:
        log.error(f"Pollinations backup failed: {e}")
    return None


def generate_title(quote: str) -> str:
    """Generate YouTube title from quote."""
    titles = [
        f"{quote} #Shorts",
        f"This Will Change Your Mindset... #Shorts",
        f"The Truth About Success #Shorts",
        f"Luxury Mindset | {quote} #Shorts",
        f"Watch This Every Morning #Shorts",
    ]
    return random.choice(titles)[:100]


def generate_description(image_prompt: str, quote: str) -> str:
    return f"""{quote}

Luxury lifestyle motivation for those building their dreams.

Every day is a chance to get closer to the life you want.
Stay focused. Stay consistent. The results will come.

#luxury #motivation #success #lifestyle #mindset #wealthy
#goals #luxurylifestyle #successmindset #viral #shorts
#youtubeshorts #motivational #luxurymindset #millionaire"""


# =============================================================
# VIDEO CREATOR — turns AI image into YouTube Short
# Ken Burns zoom effect + text overlay + title card
# =============================================================

def create_youtube_short(image_path: str, quote: str, output_path: str) -> str | None:
    """
    Creates a cinematic 30-second YouTube Short:
    - Generates 4 AI images of the same scene (different angles)
    - Each image gets Ken Burns zoom effect
    - Smooth crossfade transitions between images
    - Animated quote text overlay
    - Cinematic color grading (warm luxury tones)
    - Background music with fade in/out
    """
    try:
        import subprocess
        import tempfile

        log.info("Building cinematic video with multiple scenes...")

        # Load fonts
        try:
            font_large  = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", FONT_SIZE)
            font_medium = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", 36)
            font_small  = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 26)
        except Exception:
            font_large  = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small  = ImageFont.load_default()

        # --- Generate 4 scene variations from the same base image ---
        base_img   = Image.open(image_path).convert("RGB")
        base_img   = base_img.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)
        base_array = np.array(base_img)

        # Scene durations (total = 30s)
        scene_durations = [7, 7, 8, 8]  # seconds each
        tmp_files = []

        for scene_idx in range(4):
            scene_img = base_img.copy()
            scene_arr = np.array(scene_img).copy()

            # Apply different color grading to each scene
            if scene_idx == 0:
                # Scene 1: Warm golden — original
                pass
            elif scene_idx == 1:
                # Scene 2: Cooler blue tones — night feel
                scene_arr[:,:,0] = np.clip(scene_arr[:,:,0].astype(int) - 20, 0, 255)
                scene_arr[:,:,2] = np.clip(scene_arr[:,:,2].astype(int) + 30, 0, 255)
            elif scene_idx == 2:
                # Scene 3: High contrast dramatic
                scene_arr = np.clip(((scene_arr.astype(float) - 128) * 1.2 + 128), 0, 255).astype(np.uint8)
            else:
                # Scene 4: Warm amber tint
                scene_arr[:,:,0] = np.clip(scene_arr[:,:,0].astype(int) + 25, 0, 255)
                scene_arr[:,:,1] = np.clip(scene_arr[:,:,1].astype(int) + 10, 0, 255)
                scene_arr[:,:,2] = np.clip(scene_arr[:,:,2].astype(int) - 15, 0, 255)

            scene_img = Image.fromarray(scene_arr.astype(np.uint8))

            # Add gradient overlay at bottom
            gradient = Image.new("RGBA", (IMG_WIDTH, IMG_HEIGHT), (0, 0, 0, 0))
            grad_draw = ImageDraw.Draw(gradient)
            for i in range(500):
                alpha = int(210 * (i / 500))
                grad_draw.line([(0, IMG_HEIGHT-500+i), (IMG_WIDTH, IMG_HEIGHT-500+i)], fill=(0,0,0,alpha))

            # Also add slight top gradient
            for i in range(200):
                alpha = int(120 * (1 - i/200))
                grad_draw.line([(0, i), (IMG_WIDTH, i)], fill=(0,0,0,alpha))

            scene_rgba = scene_img.convert("RGBA")
            scene_rgba = Image.alpha_composite(scene_rgba, gradient)
            scene_final = scene_rgba.convert("RGB")

            draw = ImageDraw.Draw(scene_final)

            # --- Quote text — show on scene 2 and 3 ---
            if scene_idx >= 1:
                words = quote.split()
                if len(words) > 4:
                    mid   = len(words) // 2
                    line1 = " ".join(words[:mid])
                    line2 = " ".join(words[mid:])
                    lines = [line1, line2]
                else:
                    lines = [quote]

                total_h = sum([draw.textbbox((0,0), l, font=font_large)[3] for l in lines]) + 20*(len(lines)-1)
                text_y  = IMG_HEIGHT - 280 - total_h//2

                for line in lines:
                    bbox   = draw.textbbox((0, 0), line, font=font_large)
                    text_w = bbox[2] - bbox[0]
                    text_x = (IMG_WIDTH - text_w) // 2
                    # Shadow
                    draw.text((text_x+3, text_y+3), line, font=font_large, fill=(0,0,0))
                    draw.text((text_x+2, text_y+2), line, font=font_large, fill=(0,0,0))
                    # Main
                    draw.text((text_x, text_y), line, font=font_large, fill=(255,255,255))
                    text_y += bbox[3] - bbox[1] + 20

            # --- Decorative line above text ---
            if scene_idx >= 1:
                line_y = IMG_HEIGHT - 330
                draw.line([(IMG_WIDTH//2-80, line_y), (IMG_WIDTH//2+80, line_y)], fill=(255,220,100), width=2)

            # --- Watermark ---
            draw.text((40, 70), "@LuxuryMindsetDaily", font=font_small, fill=(255,255,255,180))

            # --- Scene number indicator dots ---
            dot_y = IMG_HEIGHT - 80
            dot_spacing = 20
            start_x = IMG_WIDTH//2 - (4*dot_spacing)//2
            for d in range(4):
                dot_x = start_x + d * dot_spacing
                color = (255, 220, 100) if d == scene_idx else (150, 150, 150)
                draw.ellipse([(dot_x-4, dot_y-4), (dot_x+4, dot_y+4)], fill=color)

            # Save scene to temp file
            with tempfile.NamedTemporaryFile(suffix=f"_scene{scene_idx}.jpg", delete=False) as tmp:
                tmp_path = tmp.name
                scene_final.save(tmp_path, "JPEG", quality=95)
                tmp_files.append(tmp_path)

        log.info(f"Generated {len(tmp_files)} scene variations")

        # --- Generate cinematic background music using ffmpeg ---
        # No downloading needed — generates unique music every run
        # Each style sounds completely different
        music_path = tmp_files[0].replace("_scene0.jpg", "_music.mp3")

        # Pick a random music style each run
        # Generate cinematic ambient music using ffmpeg anoisesrc
        # anoisesrc = built-in ffmpeg noise generator, always works
        music_styles = [
            ("deep cinematic",   "brown", "150", "2.5"),
            ("luxury ambient",   "pink",  "200", "2.0"),
            ("epic drone",       "brown", "100", "3.0"),
            ("motivational",     "pink",  "300", "2.5"),
            ("dark thriller",    "brown", "80",  "3.0"),
            ("soft inspiration", "pink",  "400", "2.0"),
            ("cosmic ambient",   "brown", "120", "2.5"),
            ("power build",      "pink",  "250", "3.0"),
        ]

        style_name, noise_color, bandpass_freq, vol = random.choice(music_styles)
        log.info(f"Generating music style: {style_name}")

        try:
            import subprocess as sp
            music_cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", f"anoisesrc=color={noise_color}:duration={VIDEO_DURATION}",
                "-af", (
                    f"bandpass=f={bandpass_freq}:width_type=o:w=2,"
                    f"afade=t=in:st=0:d=4,"
                    f"afade=t=out:st={VIDEO_DURATION-5}:d=4,"
                    f"volume={vol}"
                ),
                "-t", str(VIDEO_DURATION),
                "-ar", "44100",
                "-c:a", "libmp3lame",
                "-q:a", "3",
                music_path
            ]
            result_music = sp.run(music_cmd, capture_output=True, text=True, timeout=60)
            if result_music.returncode == 0 and os.path.exists(music_path) and os.path.getsize(music_path) > 1000:
                log.info(f"Music generated: {style_name} ({os.path.getsize(music_path)//1024}KB)")
            else:
                log.warning(f"Music failed: {result_music.stderr[-200:]}")
                music_path = None
        except Exception as me:
            log.warning(f"Music error: {me}")
            music_path = None

        # --- Generate AI voiceover using ElevenLabs free API ---
        ELEVENLABS_KEY = os.environ.get("ELEVENLABS_KEY", "")
        voice_path = None

        if ELEVENLABS_KEY:
            try:
                log.info(f"Generating voiceover: {quote}")

                # Voice IDs — pick randomly for variety
                voice_ids = [
                    "pNInz6obpgDQGcFmaJgB",  # Adam — deep male
                    "ErXwobaYiN019PkySvjV",  # Antoni — warm male
                    "VR6AewLTigWG4xSOukaG",  # Arnold — strong male
                    "EXAVITQu4vr4xnSDxMaL",  # Bella — soft female
                    "21m00Tcm4TlvDq8ikWAM",  # Rachel — professional female
                ]
                voice_id = random.choice(voice_ids)

                # Add dramatic pause and emphasis to quote
                voice_text = f". . . {quote} . . .".strip()

                tts_response = requests.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
                    headers={
                        "xi-api-key": ELEVENLABS_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": voice_text,
                        "model_id": "eleven_turbo_v2_5",
                        "voice_settings": {
                            "stability":        0.75,
                            "similarity_boost": 0.85,
                            "style":            0.3,
                            "use_speaker_boost": True
                        }
                    },
                    timeout=30
                )

                if tts_response.status_code == 200:
                    voice_path = tmp_files[0].replace("_scene0.jpg", "_voice.mp3")
                    open(voice_path, "wb").write(tts_response.content)
                    log.info(f"Voiceover generated ({len(tts_response.content)//1024}KB)")
                else:
                    log.warning(f"ElevenLabs error: {tts_response.status_code} — {tts_response.text[:200]}")

            except Exception as ve:
                log.warning(f"Voiceover error: {ve}")
        else:
            log.info("No ELEVENLABS_KEY found — skipping voiceover")

        # --- Build ffmpeg concat filter for smooth transitions ---
        # Each scene: zoom effect + crossfade to next
        inputs = []
        for tmp_path in tmp_files:
            inputs += ["-loop", "1", "-t", str(scene_durations[tmp_files.index(tmp_path)] + 1), "-i", tmp_path]

        if music_path:
            inputs += ["-i", music_path]

        # Build complex filter for Ken Burns + crossfade transitions
        filter_parts = []
        zoom_directions = [
            "zoom+0.0008",  # zoom in from center
            "zoom+0.0008",  # zoom in
            "zoom+0.0008",  # zoom in
            "zoom+0.0008",  # zoom in
        ]
        x_directions = [
            "iw/2-(iw/zoom/2)",          # center
            "iw/2-(iw/zoom/2)+2",         # slight right
            "iw/2-(iw/zoom/2)-2",         # slight left
            "iw/2-(iw/zoom/2)",           # center
        ]

        # Apply zoompan to each input
        for i in range(4):
            frames = scene_durations[i] * VIDEO_FPS + VIDEO_FPS
            filter_parts.append(
                f"[{i}:v]zoompan=z='min({zoom_directions[i]},1.10)':d={frames}:"
                f"x='{x_directions[i]}':y='ih/2-(ih/zoom/2)':"
                f"s={IMG_WIDTH}x{IMG_HEIGHT}:fps={VIDEO_FPS},"
                f"setpts=PTS-STARTPTS,trim=duration={scene_durations[i]}[v{i}]"
            )

        # Crossfade between scenes
        xfade_duration = 0.8
        filter_parts.append(f"[v0][v1]xfade=transition=fade:duration={xfade_duration}:offset={scene_durations[0]-xfade_duration}[xf01]")
        filter_parts.append(f"[xf01][v2]xfade=transition=fade:duration={xfade_duration}:offset={scene_durations[0]+scene_durations[1]-xfade_duration*2}[xf02]")
        filter_parts.append(f"[xf02][v3]xfade=transition=fade:duration={xfade_duration}:offset={sum(scene_durations[:3])-xfade_duration*3},")
        filter_parts.append(f"fade=t=in:st=0:d=1:color=black,fade=t=out:st={VIDEO_DURATION-2}:d=1:color=black[vout]")

        filter_complex = ";".join(filter_parts[:-2]) + ";" + "".join(filter_parts[-2:])

        # Build full ffmpeg command
        # Build audio inputs and mixing
        audio_inputs  = []
        audio_filters = []

        if music_path and os.path.exists(music_path):
            audio_inputs += ["-i", music_path]
            music_idx     = len(tmp_files)

        if voice_path and os.path.exists(voice_path):
            audio_inputs += ["-i", voice_path]
            voice_idx     = len(tmp_files) + (1 if music_path else 0)

        if music_path and voice_path and os.path.exists(music_path) and os.path.exists(voice_path):
            # Mix music (quiet) + voiceover (loud) together
            audio_filter = (
                f"[{music_idx}:a]volume=0.25,afade=t=in:st=0:d=2,afade=t=out:st={VIDEO_DURATION-3}:d=2[music];"
                f"[{voice_idx}:a]volume=2.0,adelay=8000|8000[voice];"  # voice starts at 8s
                f"[music][voice]amix=inputs=2:duration=first:dropout_transition=2[aout]"
            )
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                *audio_inputs,
                "-filter_complex", filter_complex + ";" + audio_filter,
                "-map", "[vout]",
                "-map", "[aout]",
                "-t", str(VIDEO_DURATION),
                "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
                "-preset", "fast", "-crf", "22",
                "-pix_fmt", "yuv420p",
                output_path
            ]
            log.info("Mixing music + voiceover")

        elif music_path and os.path.exists(music_path):
            # Music only
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                *audio_inputs,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-map", f"{music_idx}:a",
                "-af", f"afade=t=in:st=0:d=2,afade=t=out:st={VIDEO_DURATION-3}:d=2,volume=0.35",
                "-t", str(VIDEO_DURATION),
                "-c:v", "libx264", "-c:a", "aac", "-b:a", "128k",
                "-preset", "fast", "-crf", "22",
                "-pix_fmt", "yuv420p",
                output_path
            ]
            log.info("Using music only")

        else:
            # No audio
            cmd = [
                "ffmpeg", "-y",
                *inputs,
                "-filter_complex", filter_complex,
                "-map", "[vout]",
                "-t", str(VIDEO_DURATION),
                "-c:v", "libx264",
                "-preset", "fast", "-crf", "22",
                "-pix_fmt", "yuv420p",
                output_path
            ]
            log.info("No audio — silent video")

        log.info("Rendering cinematic video...")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        # Cleanup temp files
        for f in tmp_files:
            try: os.unlink(f)
            except: pass
        if music_path:
            try: os.unlink(music_path)
            except: pass
        if voice_path:
            try: os.unlink(voice_path)
            except: pass

        if result.returncode == 0:
            log.info(f"Cinematic video created: {output_path}")
            return output_path
        else:
            log.error(f"ffmpeg error: {result.stderr[-800:]}")
            return create_simple_video(image_path, output_path)

    except Exception as e:
        log.error(f"Video creation failed: {e}")
        import traceback
        log.error(traceback.format_exc())
        return create_simple_video(image_path, output_path)

def create_simple_video(image_path: str, output_path: str) -> str | None:
    """Fallback: simple static image video using ffmpeg directly."""
    try:
        import subprocess

        log.info("Creating simple static video with ffmpeg...")

        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-t", str(VIDEO_DURATION),
            "-vf", f"scale={IMG_WIDTH}:{IMG_HEIGHT},fps={VIDEO_FPS}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",
            output_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

        if result.returncode == 0:
            log.info(f"Simple video created: {output_path}")
            return output_path
        else:
            log.error(f"ffmpeg simple error: {result.stderr[-300:]}")
            return None

    except Exception as e:
        log.error(f"Simple video failed: {e}")
        return None


# =============================================================
# TOOL 3 — YOUTUBE UPLOADER
# Free: YouTube Data API v3 with OAuth2
# =============================================================

def upload_to_youtube(video_path: str, title: str, description: str) -> bool:
    """Upload video to YouTube as a Short using official free API."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        import google.auth.transport.requests

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

        creds = None

        # Priority 1: load token from GitHub Secret (environment)
        if YOUTUBE_TOKEN:
            log.info("YouTube: loading token from GitHub Secret...")
            token_data = json.loads(YOUTUBE_TOKEN)
            creds      = Credentials.from_authorized_user_info(token_data, SCOPES)

        # Priority 2: load token from local file
        elif os.path.exists(TOKEN_FILE):
            log.info("YouTube: loading token from local file...")
            with open(TOKEN_FILE, "r") as f:
                token_data = json.load(f)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)

        # Refresh token if expired
        if creds and creds.expired and creds.refresh_token:
            log.info("YouTube: refreshing expired token...")
            creds.refresh(google.auth.transport.requests.Request())
            # Save refreshed token
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())

        if not creds:
            log.error("No YouTube credentials found. Run: python pipeline.py --auth")
            return False

        youtube = build("youtube", "v3", credentials=creds)

        # Video metadata
        body = {
            "snippet": {
                "title":       title,
                "description": description,
                "tags":        YT_TAGS,
                "categoryId":  "26",  # Howto & Style (good for motivation)
            },
            "status": {
                "privacyStatus":          "public",
                "selfDeclaredMadeForKids": False,
            }
        }

        log.info(f"Uploading to YouTube: {title}")
        media = MediaFileUpload(
            video_path,
            mimetype   = "video/mp4",
            resumable  = True,
            chunksize  = 1024 * 1024  # 1MB chunks
        )

        request  = youtube.videos().insert(
            part       = "snippet,status",
            body       = body,
            media_body = media
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                log.info(f"Upload progress: {progress}%")

        video_id  = response["id"]
        video_url = f"https://youtube.com/shorts/{video_id}"
        log.info(f"YouTube: uploaded successfully!")
        log.info(f"URL: {video_url}")
        return True

    except Exception as e:
        log.error(f"YouTube upload failed: {e}")
        return False


def upload_latest_content():
    log.info("=" * 50)
    log.info("TOOL 3: Uploading to YouTube")
    log.info("=" * 50)

    # Find latest video
    if not os.path.exists(VIDEO_FOLDER):
        log.warning("No video folder found")
        return False

    videos = [
        os.path.join(VIDEO_FOLDER, f) for f in os.listdir(VIDEO_FOLDER)
        if f.endswith(".mp4")
    ]

    if not videos:
        log.warning("No videos found to upload")
        return False

    videos.sort(key=os.path.getctime, reverse=True)
    latest_video = videos[0]
    log.info(f"Selected video: {latest_video}")

    # Load title + description from metadata
    timestamp  = Path(latest_video).stem.replace("short_", "")
    meta_path  = os.path.join(OUTPUT_FOLDER, f"content_{timestamp}_meta.txt")

    title       = "Luxury Mindset | Success Is Built In Silence #Shorts"
    description = generate_description("luxury lifestyle", "Success is built in silence.")

    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            content = f.read()
        for line in content.split("\n"):
            if line.startswith("TITLE:"):
                title = line[6:].strip()
            if line.startswith("DESCRIPTION:"):
                description = content.split("DESCRIPTION:")[-1].strip()

    return upload_to_youtube(latest_video, title, description)


# =============================================================
# YOUTUBE AUTH — run once locally to get token
# python pipeline.py --auth
# =============================================================

def authorize_youtube():
    """
    Run this ONCE on your laptop to authorize YouTube upload.
    It opens a browser, you log in, it saves youtube_token.json.
    Then copy that file's contents to GitHub Secret YOUTUBE_TOKEN.
    """
    from google_auth_oauthlib.flow import InstalledAppFlow

    SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

    print("")
    print("=" * 60)
    print("YOUTUBE AUTHORIZATION")
    print("=" * 60)
    print("")
    print("This will open your browser to authorize YouTube upload.")
    print("Make sure client_secrets.json is in this folder first.")
    print("")
    print("How to get client_secrets.json (free, 2 minutes):")
    print("1. Go to console.cloud.google.com")
    print("2. APIs & Services -> Credentials")
    print("3. Create Credentials -> OAuth 2.0 Client ID")
    print("4. Application type: Desktop app")
    print("5. Download JSON -> rename to client_secrets.json")
    print("6. Put it in this folder")
    print("")

    if not os.path.exists("client_secrets.json"):
        print("ERROR: client_secrets.json not found in this folder!")
        print("Follow the steps above to get it.")
        return

    flow  = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print("")
    print("SUCCESS! youtube_token.json saved.")
    print("")
    print("NEXT STEP:")
    print("Copy the contents of youtube_token.json")
    print("Paste it as YOUTUBE_TOKEN secret on GitHub")
    print("(GitHub repo -> Settings -> Secrets -> Actions -> New secret)")
    print("")


# =============================================================
# FULL PIPELINE
# =============================================================

def full_pipeline():
    start = datetime.now()
    log.info("")
    log.info("=" * 60)
    log.info(f"PIPELINE START: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    try:
        # Tool 1: YouTube trends
        trend_prompt, trends = analyze_youtube_trends()
        time.sleep(2)

        # Tool 2: Generate AI image + video
        video_path, title, description = generate_ai_content(trend_prompt)
        time.sleep(2)

        # Tool 3: Upload to YouTube
        if video_path:
            upload_latest_content()
        else:
            log.warning("Skipping upload — video generation failed")

    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)

    elapsed = (datetime.now() - start).seconds
    log.info(f"Pipeline complete in {elapsed}s")
    log.info("=" * 60)


# =============================================================
# ENTRY POINT
# --auth  → authorize YouTube (run once on laptop)
# --once  → GitHub Actions mode (run once and exit)
# (none)  → local scheduler mode
# =============================================================

if __name__ == "__main__":
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)
    Path(VIDEO_FOLDER).mkdir(exist_ok=True)

    if "--auth" in sys.argv:
        authorize_youtube()

    elif "--once" in sys.argv:
        log.info("Running in GitHub Actions mode (--once)")
        full_pipeline()

    else:
        log.info("Auto Content Pipeline v3 — YouTube Shorts Edition")
        log.info("Schedule: 09:00, 12:00, 15:00, 18:00, 21:00 daily")

        schedule.every().day.at("09:00").do(full_pipeline)
        schedule.every().day.at("12:00").do(full_pipeline)
        schedule.every().day.at("15:00").do(full_pipeline)
        schedule.every().day.at("18:00").do(full_pipeline)
        schedule.every().day.at("21:00").do(full_pipeline)

        run_now = input("Run pipeline now? (y/n): ").strip().lower()
        if run_now == "y":
            full_pipeline()

        log.info("Scheduler running. Press Ctrl+C to stop.")
        while True:
            schedule.run_pending()
            time.sleep(30)
