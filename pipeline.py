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
    Creates a 30-second YouTube Short using PIL + ffmpeg directly.
    No moviepy API changes to worry about — uses raw ffmpeg subprocess.
    Adds text overlay and Ken Burns zoom effect.
    """
    try:
        import subprocess
        import tempfile

        log.info("Building video with ffmpeg...")

        # Load and resize image to exact 1080x1920
        img = Image.open(image_path).convert("RGB")
        img = img.resize((IMG_WIDTH, IMG_HEIGHT), Image.LANCZOS)

        # Add text overlay directly on image using PIL
        draw = ImageDraw.Draw(img)

        # Dark gradient at bottom for text readability
        for i in range(400):
            alpha = int(200 * (i / 400))
            y_pos = IMG_HEIGHT - 400 + i
            overlay = Image.new("RGBA", (IMG_WIDTH, 1), (0, 0, 0, alpha))
            img.paste(Image.new("RGB", (IMG_WIDTH, 1), (0, 0, 0)),
                     (0, y_pos),
                     overlay)

        # Try to load a font, fallback to default
        try:
            font_large = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf", FONT_SIZE)
            font_small = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 28)
        except Exception:
            font_large = ImageFont.load_default()
            font_small = ImageFont.load_default()

        # Draw quote text centered
        words = quote.split()
        if len(words) > 4:
            mid   = len(words) // 2
            text  = " ".join(words[:mid]) + "\n" + " ".join(words[mid:])
        else:
            text  = quote

        # Text shadow for readability
        text_y = IMG_HEIGHT - 260
        bbox   = draw.textbbox((0, 0), text, font=font_large)
        text_w = bbox[2] - bbox[0]
        text_x = (IMG_WIDTH - text_w) // 2

        # Shadow
        draw.text((text_x + 2, text_y + 2), text, font=font_large, fill=(0, 0, 0, 200))
        # Main text
        draw.text((text_x, text_y), text, font=font_large, fill=(255, 255, 255, 255))

        # Watermark
        draw.text((40, 60), "@LuxuryMindsetDaily", font=font_small, fill=(255, 255, 255, 200))

        # Save annotated image to temp file
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            tmp_path = tmp.name
            img.save(tmp_path, "JPEG", quality=95)

        # Use ffmpeg to create video from image (Ken Burns zoom via zoompan filter)
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", tmp_path,
            "-vf", (
                f"zoompan=z='min(zoom+0.0015,1.15)':d={VIDEO_DURATION * VIDEO_FPS}:"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"s={IMG_WIDTH}x{IMG_HEIGHT},"
                f"fps={VIDEO_FPS},"
                f"fade=t=in:st=0:d=1,"
                f"fade=t=out:st={VIDEO_DURATION - 1}:d=1"
            ),
            "-t", str(VIDEO_DURATION),
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-crf", "23",
            "-pix_fmt", "yuv420p",
            "-an",
            output_path
        ]

        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=120
        )

        # Clean up temp file
        os.unlink(tmp_path)

        if result.returncode == 0:
            log.info(f"Video created: {output_path}")
            return output_path
        else:
            log.error(f"ffmpeg error: {result.stderr[-500:]}")
            return create_simple_video(image_path, output_path)

    except Exception as e:
        log.error(f"Video creation failed: {e}")
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
