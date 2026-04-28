# =============================================================
# AUTO CONTENT PIPELINE — 100% FREE TOOLS ONLY
# =============================================================
# TOOLS USED (all free, no paid APIs):
#   - YouTube Data API v3       → Free (10,000 units/day)
#   - Pollinations.ai           → Free text + image AI (no key)
#   - instagrapi                → Free Instagram uploader
#   - google-api-python-client  → Free YouTube uploader
#   - schedule                  → Free Python scheduler
#
# INSTALL:
#   pip install google-api-python-client google-auth-oauthlib
#               instagrapi requests schedule
#
# SETUP:
#   1. Get free YouTube API key from console.cloud.google.com
#   2. Fill in CONFIG section below
#   3. mkdir generated_shots
#   4. python pipeline.py
# =============================================================

import os
import time
import random
import logging
import schedule
import requests
import urllib.parse
from datetime import datetime
from pathlib import Path

# =============================================================
# LOGGING
# =============================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("pipeline.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)

# =============================================================
# CONFIG — FILL THESE IN
# =============================================================

YOUTUBE_API_KEY   = "AIzaSyBqspCLcFjEPq2rhnObHPctW58q26Y2syE"   # Free from console.cloud.google.com
INSTAGRAM_USER    = "grind_station_65"
INSTAGRAM_PASS    = "#Shahary279"

OUTPUT_FOLDER     = "generated_shots"
PROMPT_FILE       = "latest_prompt.txt"
SESSION_FILE      = "instagram_session.json"

# Image dimensions (1080x1920 = vertical Reels/Shorts format)
IMG_WIDTH         = 1080
IMG_HEIGHT        = 1920

# Your content niche — customize this
CONTENT_CONCEPT = """
Cinematic luxury lifestyle content:
- Powerful motivation and success mindset
- Luxury visuals (cars, cities, architecture, fashion)
- Emotional storytelling for USA audience
- Viral short-form style (Instagram Reels, YouTube Shorts)
"""

# Caption template
CAPTION_TEMPLATE = """{hook}

{motivation}

Follow for daily motivation 🔥
#luxury #success #motivation #lifestyle #mindset #viral #wealthy #goals"""

# =============================================================
# TOOL 1 — YOUTUBE TREND ANALYZER
# Free: YouTube Data API v3, 10,000 quota units/day
# A videos.list call = 1 unit. Safe to run 100+ times/day.
# =============================================================

def analyze_youtube_trends():
    log.info("=" * 50)
    log.info("TOOL 1: Analyzing YouTube Trends")
    log.info("=" * 50)

    try:
        from googleapiclient.discovery import build

        youtube = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

        response = youtube.videos().list(
            part="snippet,statistics",
            chart="mostPopular",
            regionCode="US",
            maxResults=10
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
                "likes":       stats.get("likeCount", "0"),
                "category":    snippet.get("categoryId", "")
            })

        log.info(f"Found {len(trends)} trending videos")
        for i, t in enumerate(trends, 1):
            log.info(f"  {i}. {t['title']} ({t['views']} views)")

        # Build the prompt for AI generator
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
Based on what's trending, write ONE powerful cinematic image prompt.

Requirements:
- Opens with a strong visual scene (no people, just atmosphere)
- Luxury setting: penthouse, sports car, private jet, rooftop city, yacht, etc.
- Golden hour or dramatic night lighting
- Hyper-realistic, cinematic, 8K quality
- Emotionally powerful — wealth, freedom, success
- Under 80 words

Only output the image prompt. Nothing else."""

        # Save prompt to file
        with open(PROMPT_FILE, "w", encoding="utf-8") as f:
            f.write(prompt)

        log.info("Trend prompt saved successfully")
        return prompt, trends

    except Exception as e:
        log.error(f"YouTube API error: {e}")
        log.info("Using fallback prompt...")
        fallback = generate_fallback_prompt()
        return fallback, []


def generate_fallback_prompt():
    """Used when YouTube API fails — random luxury prompt."""
    scenes = [
        "A black Lamborghini parked on a rain-soaked empty highway at night, neon city lights reflecting on the wet asphalt, cinematic 8K ultra-realistic photography",
        "Aerial view of a luxury penthouse infinity pool in Dubai at golden hour, glass skyscrapers, warm amber light, cinematic wide angle 8K",
        "Private jet interior at sunset, leather seats, champagne glass, clouds below through oval window, luxury cinematic photography",
        "Empty modern mansion living room at dawn, floor-to-ceiling windows, city skyline, minimalist luxury interior design, cinematic lighting 8K",
        "Black Rolls Royce driving through foggy mountain road at sunrise, ultra-realistic cinematic photography, dramatic atmosphere"
    ]
    prompt = random.choice(scenes)
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(f"Generate this image: {prompt}")
    return prompt, []


# =============================================================
# TOOL 2 — AI CONTENT GENERATOR
# Free: Pollinations.ai — no API key, no signup, no limits
# Text model: Mistral / Image model: FLUX
# =============================================================

def generate_ai_content(trend_prompt=None):
    log.info("=" * 50)
    log.info("TOOL 2: Generating AI Content")
    log.info("=" * 50)

    # Step 2a: Read prompt from file if not passed directly
    if trend_prompt is None:
        if os.path.exists(PROMPT_FILE):
            with open(PROMPT_FILE, "r", encoding="utf-8") as f:
                trend_prompt = f.read()
        else:
            log.warning("No prompt file found. Using fallback.")
            trend_prompt, _ = generate_fallback_prompt()

    # Step 2b: Use Pollinations text API to generate image prompt
    log.info("Generating image prompt via Pollinations text AI...")
    image_prompt = generate_text_prompt(trend_prompt)
    log.info(f"Image prompt: {image_prompt}")

    # Step 2c: Generate actual image via Pollinations image API
    log.info("Generating image via Pollinations FLUX model...")
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_FOLDER, f"content_{timestamp}.jpg")

    result = generate_image(image_prompt, output_path)

    # Step 2d: Generate caption
    caption = generate_caption(image_prompt)

    # Step 2e: Save metadata
    meta_path = output_path.replace(".jpg", "_meta.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(f"TIMESTAMP: {timestamp}\n")
        f.write(f"IMAGE PROMPT:\n{image_prompt}\n\n")
        f.write(f"CAPTION:\n{caption}\n")

    log.info(f"Content saved: {output_path}")
    return result, caption


def generate_text_prompt(trend_prompt: str) -> str:
    """
    Calls Pollinations.ai free text API.
    Model: Mistral (default) or openai
    No key required.
    """
    try:
        clean_prompt = trend_prompt.strip()[:1500]  # keep under limit
        encoded      = urllib.parse.quote(clean_prompt)
        url          = f"https://text.pollinations.ai/{encoded}?model=openai&seed={random.randint(1, 9999)}"

        response = requests.get(url, timeout=45)
        response.raise_for_status()

        image_prompt = response.text.strip()

        # Trim if too long
        if len(image_prompt) > 400:
            image_prompt = image_prompt[:400]

        return image_prompt

    except Exception as e:
        log.error(f"Pollinations text API error: {e}")
        # Fallback: use a slice of the trend prompt as image prompt
        lines = [l.strip() for l in trend_prompt.split("\n") if l.strip()]
        return next((l for l in lines if len(l) > 30), "Cinematic luxury penthouse at golden hour, 8K")


def generate_image(prompt: str, output_path: str, retries: int = 3) -> str | None:
    """
    Calls Pollinations.ai free image API.
    Model: flux (best quality, free)
    Returns local file path or None.
    """
    encoded = urllib.parse.quote(prompt)
    seed    = random.randint(1, 99999)
    url     = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width={IMG_WIDTH}&height={IMG_HEIGHT}"
        f"&model=flux&seed={seed}&enhance=true&nologo=true"
    )

    for attempt in range(1, retries + 1):
        try:
            log.info(f"Image generation attempt {attempt}/{retries}...")
            response = requests.get(url, timeout=90)

            if response.status_code == 200 and len(response.content) > 10000:
                with open(output_path, "wb") as f:
                    f.write(response.content)
                log.info(f"Image saved ({len(response.content) // 1024}KB): {output_path}")
                return output_path
            else:
                log.warning(f"Bad response: {response.status_code}, size: {len(response.content)}")

        except requests.Timeout:
            log.warning(f"Timeout on attempt {attempt}")
        except Exception as e:
            log.error(f"Image generation error: {e}")

        if attempt < retries:
            wait = 10 * attempt
            log.info(f"Retrying in {wait}s...")
            time.sleep(wait)

    log.error("All image generation attempts failed")
    return None


def generate_caption(image_prompt: str) -> str:
    """Generate a viral caption using Pollinations text API."""
    try:
        caption_prompt = f"""Write a short viral Instagram caption for luxury lifestyle content.
Image shows: {image_prompt[:200]}

Format:
Line 1: One powerful hook sentence (max 10 words)
Line 2: One motivational statement about success/wealth/freedom (max 15 words)

Only output the two lines. No hashtags. No quotes."""

        encoded  = urllib.parse.quote(caption_prompt)
        url      = f"https://text.pollinations.ai/{encoded}?model=openai"
        response = requests.get(url, timeout=30)
        lines    = response.text.strip().split("\n")
        lines    = [l.strip() for l in lines if l.strip()]

        hook       = lines[0] if len(lines) > 0 else "The life you want is waiting."
        motivation = lines[1] if len(lines) > 1 else "Build it or someone else will."

        caption = CAPTION_TEMPLATE.format(hook=hook, motivation=motivation)
        return caption

    except Exception:
        return CAPTION_TEMPLATE.format(
            hook="The life you want is closer than you think.",
            motivation="Every successful person started exactly where you are."
        )


# =============================================================
# TOOL 3 — AUTO PUBLISHER
# Free: instagrapi (Instagram) + YouTube Data API v3 (YouTube)
# =============================================================

def upload_latest_content():
    log.info("=" * 50)
    log.info("TOOL 3: Publishing Content")
    log.info("=" * 50)

    # Find latest generated image
    image_path, caption = pick_latest_content()

    if not image_path:
        log.warning("No content found in generated_shots/")
        return False

    log.info(f"Selected: {image_path}")

    success = False

    # Upload to Instagram
    time.sleep(5)
    ig_ok = upload_to_instagram(image_path, caption)
    if ig_ok:
        success = True

    # Optional: Upload to YouTube (requires OAuth setup)
    # yt_ok = upload_to_youtube(image_path, caption)

    return success


def pick_latest_content():
    """Returns (image_path, caption) for the most recent generated shot."""
    folder = OUTPUT_FOLDER
    if not os.path.exists(folder):
        return None, None

    images = [
        os.path.join(folder, f) for f in os.listdir(folder)
        if f.endswith((".jpg", ".jpeg", ".png")) and "_meta" not in f
    ]

    if not images:
        return None, None

    # Sort by creation time, newest first
    images.sort(key=os.path.getctime, reverse=True)
    latest = images[0]

    # Try to load caption from metadata file
    meta_path = latest.replace(".jpg", "_meta.txt").replace(".png", "_meta.txt")
    caption   = ""

    if os.path.exists(meta_path):
        with open(meta_path, "r", encoding="utf-8") as f:
            content = f.read()
        if "CAPTION:" in content:
            caption = content.split("CAPTION:")[-1].strip()

    if not caption:
        caption = CAPTION_TEMPLATE.format(
            hook="The life you want is waiting.",
            motivation="Build it every single day."
        )

    return latest, caption


def upload_to_instagram(image_path: str, caption: str) -> bool:
    """
    Uploads image to Instagram using instagrapi (free, no API key).
    pip install instagrapi
    """
    try:
        from instagrapi import Client
        from instagrapi.exceptions import LoginRequired, BadPassword

        cl = Client()

        # Use saved session to avoid repeated logins (reduces ban risk)
        if os.path.exists(SESSION_FILE):
            try:
                cl.load_settings(SESSION_FILE)
                cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
                log.info("Instagram: loaded existing session")
            except Exception:
                log.info("Instagram: session expired, re-logging in...")
                cl = Client()
                cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
        else:
            cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
            log.info("Instagram: logged in successfully")

        # Save session for next run
        cl.dump_settings(SESSION_FILE)

        # Upload as photo post
        media = cl.photo_upload(
            path      = image_path,
            caption   = caption,
            extra_data = {"custom_accessibility_caption": "luxury lifestyle content"}
        )

        log.info(f"Instagram: posted successfully! Media ID: {media.pk}")
        return True

    except ImportError:
        log.error("instagrapi not installed. Run: pip install instagrapi")
        return False
    except Exception as e:
        log.error(f"Instagram upload failed: {e}")
        return False


def upload_to_youtube(video_path: str, title: str, description: str = "") -> bool:
    """
    Uploads video to YouTube as Shorts using official free API.
    Requires: OAuth2 credentials from console.cloud.google.com
    NOTE: Only works with video files. For images, skip this.
    """
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        from google_auth_oauthlib.flow import InstalledAppFlow

        SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

        flow    = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
        creds   = flow.run_local_server(port=0)
        youtube = build("youtube", "v3", credentials=creds)

        body = {
            "snippet": {
                "title":       title[:100],
                "description": description[:5000],
                "tags":        ["luxury", "motivation", "success", "lifestyle", "#Shorts"],
                "categoryId":  "22"  # People & Blogs
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media_body = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True)

        request  = youtube.videos().insert(part="snippet,status", body=body, media_body=media_body)
        response = request.execute()

        log.info(f"YouTube: uploaded! Video ID: {response['id']}")
        return True

    except Exception as e:
        log.error(f"YouTube upload failed: {e}")
        return False


# =============================================================
# FULL PIPELINE — chains all 3 tools
# =============================================================

def full_pipeline():
    start = datetime.now()
    log.info("")
    log.info("=" * 60)
    log.info(f"PIPELINE START: {start.strftime('%Y-%m-%d %H:%M:%S')}")
    log.info("=" * 60)

    try:
        # Tool 1: Analyze trends
        trend_prompt, trends = analyze_youtube_trends()
        time.sleep(2)

        # Tool 2: Generate AI content
        image_path, caption = generate_ai_content(trend_prompt)
        time.sleep(2)

        # Tool 3: Publish
        if image_path:
            upload_latest_content()
        else:
            log.warning("Skipping upload — image generation failed")

    except Exception as e:
        log.error(f"Pipeline error: {e}", exc_info=True)

    elapsed = (datetime.now() - start).seconds
    log.info(f"Pipeline complete in {elapsed}s")
    log.info("=" * 60)


# =============================================================
# SCHEDULER — runs 5 times per day
# =============================================================

if __name__ == "__main__":
    log.info("Auto Content Pipeline starting...")
    log.info("Schedule: 09:00, 12:00, 15:00, 18:00, 21:00 daily")

    # Create output folder
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

    # Schedule 5 times per day
    schedule.every().day.at("09:00").do(full_pipeline)
    schedule.every().day.at("12:00").do(full_pipeline)
    schedule.every().day.at("15:00").do(full_pipeline)
    schedule.every().day.at("18:00").do(full_pipeline)
    schedule.every().day.at("21:00").do(full_pipeline)

    # Optional: run once immediately on start
    run_now = input("Run pipeline now? (y/n): ").strip().lower()
    if run_now == "y":
        full_pipeline()

    log.info("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)
