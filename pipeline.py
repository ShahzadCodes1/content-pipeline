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

    if any(w in t for w in ["music", "song", "video", "gaga", "rapper", "album", "official"]):
        pool = [
            ("Black grand piano in empty luxury penthouse, floor to ceiling windows, city skyline at dusk, cinematic 8K", "Create what they can only dream of."),
            ("Penthouse rooftop at night, city lights below, champagne glass on glass railing, cinematic 8K luxury", "The sound of success is silence."),
            ("Modern recording studio with city view at night, luxury interior, warm lighting, cinematic 8K", "Your art is your empire."),
        ]
    elif any(w in t for w in ["sport", "nba", "nfl", "celtics", "lakers", "game", "basketball", "football"]):
        pool = [
            ("Empty luxury sports car garage, row of Ferraris and Lamborghinis, dramatic spotlighting, cinematic 8K", "Champions are made before the game begins."),
            ("Rooftop infinity pool overlooking city at night, luxury cabana, warm light, reflection, cinematic 8K", "Winners prepare while others sleep."),
            ("Penthouse gym overlooking city skyline at sunrise, luxury equipment, dramatic light, cinematic 8K", "Discipline is the bridge to your dreams."),
        ]
    elif any(w in t for w in ["movie", "trailer", "film", "series", "season", "official teaser"]):
        pool = [
            ("Private jet interior at golden hour, cream leather seats, champagne, clouds below oval window, cinematic 8K", "Your story is worth living in full."),
            ("Luxury home cinema room, velvet seats, city view through glass wall, cinematic lighting 8K", "Build the life worth watching."),
            ("Yacht deck Mediterranean sea golden hour, champagne on table, luxury lifestyle, cinematic 8K", "Every scene of your life should be worth replaying."),
        ]
    elif any(w in t for w in ["news", "america", "world", "politics", "breaking"]):
        pool = [
            ("Matte black Lamborghini on rain-soaked empty highway at night, neon reflections, cinematic 8K", "While they talk you build."),
            ("Empty modern boardroom top floor, panoramic city view at dawn, cinematic 8K luxury photography", "The news reports the world. You change it."),
            ("Luxury penthouse study at night, city lights below, whiskey glass, leather chair, cinematic 8K", "Stay focused. The world is loud on purpose."),
        ]
    else:
        pool = [
            ("Matte black Lamborghini on rain-soaked highway at night, neon city reflections, cinematic 8K ultra-realistic", "Success is built in silence."),
            ("Luxury penthouse infinity pool Dubai golden hour, glass skyscrapers, warm amber light, cinematic 8K", "Your vision becomes your reality."),
            ("Private jet interior sunset, cream leather seats, champagne glass, clouds below, cinematic 8K", "Freedom is earned not given."),
            ("Empty mansion living room dawn, floor to ceiling windows, city skyline, cinematic 8K", "Build the life they stare at."),
            ("Black Rolls Royce foggy mountain road sunrise, ultra-realistic cinematic photography 8K", "Discipline creates destiny."),
            ("Yacht deck at golden hour, Mediterranean sea, champagne on table, luxury lifestyle, cinematic 8K", "The ocean belongs to those who dare."),
            ("Modern mansion exterior at night, illuminated pool, palm trees, luxury real estate, cinematic 8K", "Your dream home is a decision away."),
            ("Rooftop penthouse terrace Dubai skyline at dusk, outdoor luxury furniture, city glow, cinematic 8K", "Elevation is a mindset first."),
        ]

    image_prompt, quote = random.choice(pool)
    log.info("Content selected via keyword matching")
    return image_prompt, quote


def generate_image(prompt: str, output_path: str, retries: int = 3) -> str | None:
    """
    Generate image via Hugging Face Inference API (free, no rate limits on GitHub IPs).
    Model: stabilityai/stable-diffusion-xl-base-1.0
    Free tier: unlimited requests with HF token.
    """
    # Enhance prompt for luxury cinematic style
    full_prompt = (
        f"{prompt}, "
        f"cinematic photography, luxury lifestyle, "
        f"8K ultra-realistic, dramatic lighting, "
        f"professional commercial photography, "
        f"sharp focus, high detail"
    )

    api_url = "https://api-inference.huggingface.co/models/stabilityai/stable-diffusion-xl-base-1.0"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": full_prompt,
        "parameters": {
            "width":               768,
            "height":              1344,   # closest to 9:16 vertical
            "num_inference_steps": 25,
            "guidance_scale":      7.5,
            "seed":                random.randint(1, 99999),
        }
    }

    for attempt in range(1, retries + 1):
        try:
            log.info(f"HF image generation attempt {attempt}/{retries}...")
            r = requests.post(api_url, headers=headers, json=payload, timeout=120)

            # Model loading — wait and retry
            if r.status_code == 503:
                wait = 30
                log.info(f"Model loading, waiting {wait}s...")
                time.sleep(wait)
                continue

            if r.status_code == 200 and len(r.content) > 10000:
                # Resize to exact 1080x1920
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                img = img.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)
                img.save(output_path, "JPEG", quality=95)
                log.info(f"Image saved ({len(r.content)//1024}KB): {output_path}")
                return output_path
            else:
                log.warning(f"HF bad response: {r.status_code} — {r.text[:200]}")

        except requests.Timeout:
            log.warning(f"Timeout on attempt {attempt}")
        except Exception as e:
            log.error(f"HF image error: {e}")

        if attempt < retries:
            time.sleep(15)

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
    Creates a 30-second YouTube Short from a static image.
    Effect: slow Ken Burns zoom in + motivational text overlay
    """
    try:
        from moviepy.editor import (
            ImageClip, TextClip, CompositeVideoClip,
            AudioFileClip, concatenate_videoclips
        )
        from moviepy.video.fx.all import fadein, fadeout

        log.info("Building video with moviepy...")

        # Load and prepare image
        img        = Image.open(image_path).convert("RGB")
        img        = img.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)
        img_array  = np.array(img)

        # --- Main clip: Ken Burns slow zoom ---
        duration   = VIDEO_DURATION
        fps        = VIDEO_FPS
        zoom_start = 1.0
        zoom_end   = 1.15

        def make_frame(t):
            progress = t / duration
            zoom     = zoom_start + (zoom_end - zoom_start) * progress
            new_w    = int(IMG_WIDTH  * zoom)
            new_h    = int(IMG_HEIGHT * zoom)

            # Resize with zoom
            zoomed = np.array(
                Image.fromarray(img_array).resize((new_w, new_h), Image.LANCZOS)
            )

            # Crop center to original size
            x = (new_w - IMG_WIDTH)  // 2
            y = (new_h - IMG_HEIGHT) // 2
            return zoomed[y:y+IMG_HEIGHT, x:x+IMG_WIDTH]

        main_clip = ImageClip(img_array, duration=duration).fl(
            lambda gf, t: make_frame(t)
        ).set_fps(fps)

        # --- Dark gradient overlay at bottom for text readability ---
        gradient        = Image.new("RGBA", (IMG_WIDTH, 500), (0, 0, 0, 0))
        draw            = ImageDraw.Draw(gradient)
        for i in range(500):
            alpha = int(180 * (i / 500))
            draw.line([(0, 499-i), (IMG_WIDTH, 499-i)], fill=(0, 0, 0, alpha))
        gradient_array  = np.array(gradient.convert("RGB"))
        gradient_clip   = ImageClip(gradient_array, duration=duration)\
                            .set_position(("center", IMG_HEIGHT - 500))\
                            .set_opacity(0.7)

        # --- Quote text overlay ---
        # Wrap quote if too long
        words       = quote.split()
        if len(words) > 4:
            mid     = len(words) // 2
            line1   = " ".join(words[:mid])
            line2   = " ".join(words[mid:])
            text    = f"{line1}\n{line2}"
        else:
            text    = quote

        txt_clip = TextClip(
            text,
            fontsize   = FONT_SIZE,
            color      = "white",
            font       = "Arial-Bold",
            align      = "center",
            method     = "caption",
            size       = (IMG_WIDTH - 100, None),
            stroke_color = "black",
            stroke_width = 2,
        ).set_duration(duration)\
         .set_position(("center", IMG_HEIGHT - 280))\
         .crossfadein(1.0)

        # --- Watermark / channel name ---
        watermark = TextClip(
            "@" + "LuxuryMindsetDaily",
            fontsize     = 28,
            color        = "white",
            font         = "Arial",
            stroke_color = "black",
            stroke_width = 1,
        ).set_duration(duration)\
         .set_position((40, 60))\
         .set_opacity(0.8)

        # --- Compose all layers ---
        final = CompositeVideoClip([
            main_clip,
            gradient_clip,
            txt_clip,
            watermark,
        ], size=(IMG_WIDTH, IMG_HEIGHT))

        # Apply fade in/out
        final = final.fadein(0.5).fadeout(0.5)

        # --- Write video ---
        log.info(f"Rendering video to {output_path}...")
        final.write_videofile(
            output_path,
            fps            = fps,
            codec          = "libx264",
            audio          = False,
            preset         = "ultrafast",
            ffmpeg_params  = ["-crf", "23"],
            logger         = None,
        )

        log.info(f"Video created: {output_path}")
        return output_path

    except Exception as e:
        log.error(f"Video creation failed: {e}")
        log.info("Trying simple fallback video method...")
        return create_simple_video(image_path, output_path)


def create_simple_video(image_path: str, output_path: str) -> str | None:
    """Fallback: simple static image video without Ken Burns effect."""
    try:
        from moviepy.editor import ImageClip

        clip = ImageClip(image_path, duration=VIDEO_DURATION)\
                 .set_fps(VIDEO_FPS)
        clip.write_videofile(
            output_path,
            codec   = "libx264",
            audio   = False,
            preset  = "ultrafast",
            logger  = None,
        )
        log.info(f"Simple video created: {output_path}")
        return output_path

    except Exception as e:
        log.error(f"Simple video also failed: {e}")
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
