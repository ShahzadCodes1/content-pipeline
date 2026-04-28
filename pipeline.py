# =============================================================
# AUTO CONTENT PIPELINE v2 — 100% FREE
# =============================================================
# FIXES IN THIS VERSION:
#   - Unicode logging fix (Windows safe)
#   - Instagram session loaded from GitHub Secret
#   - --once flag for GitHub Actions
#   - Credentials read from environment variables
#   - Smarter retry logic for image generation
#   - Cleaner image prompt (strips markdown bold/headers)
#   - Caption saved correctly to metadata
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
from datetime import datetime
from pathlib import Path

# =============================================================
# LOGGING — Windows Unicode safe
# =============================================================

log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

file_handler   = logging.FileHandler("pipeline.log", encoding="utf-8")
file_handler.setFormatter(log_formatter)

stream_handler = logging.StreamHandler()
stream_handler.setFormatter(log_formatter)
stream_handler.stream = open(
    sys.stdout.fileno(), mode="w", encoding="utf-8", buffering=1
)

logging.basicConfig(level=logging.INFO, handlers=[file_handler, stream_handler])
log = logging.getLogger(__name__)

# =============================================================
# CONFIG — reads from environment (GitHub Actions) or defaults
# =============================================================

YOUTUBE_API_KEY    = os.environ.get("YOUTUBE_API_KEY",    "YOUR_YOUTUBE_API_KEY_HERE")
INSTAGRAM_USER     = os.environ.get("INSTAGRAM_USER",     "your_instagram_username")
INSTAGRAM_PASS     = os.environ.get("INSTAGRAM_PASS",     "your_instagram_password")
INSTAGRAM_SESSION  = os.environ.get("INSTAGRAM_SESSION",  "")  # JSON string from GitHub Secret

OUTPUT_FOLDER      = "generated_shots"
PROMPT_FILE        = "latest_prompt.txt"
SESSION_FILE       = "instagram_session.json"

IMG_WIDTH          = 1080
IMG_HEIGHT         = 1920

CONTENT_CONCEPT = """
Cinematic luxury lifestyle content:
- Powerful motivation and success mindset
- Luxury visuals (cars, cities, architecture, fashion)
- Emotional storytelling for USA audience
- Viral short-form style (Instagram Reels, YouTube Shorts)
"""

CAPTION_TEMPLATE = """{hook}

{motivation}

Follow for daily motivation
#luxury #success #motivation #lifestyle #mindset #viral #wealthy #goals"""

# =============================================================
# TOOL 1 — YOUTUBE TREND ANALYZER
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
                "likes":       stats.get("likeCount", "0"),
            })

        log.info(f"Found {len(trends)} trending videos")
        for i, t in enumerate(trends, 1):
            # ASCII-safe logging for Windows terminal
            safe_title = t['title'].encode('ascii', 'replace').decode('ascii')
            log.info(f"  {i}. {safe_title} ({t['views']} views)")

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
Write ONE powerful cinematic image prompt based on what is trending.

Requirements:
- Strong visual scene, no people, only atmosphere and objects
- Luxury setting: penthouse, sports car, private jet, rooftop, yacht
- Golden hour or dramatic night lighting
- Hyper-realistic, cinematic, 8K quality
- Emotionally powerful — wealth, freedom, success
- Under 80 words
- No markdown, no bold text, no headers, just the prompt

Only output the image prompt. Nothing else."""

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
        "A matte black Lamborghini parked on a rain-soaked highway at night, neon city reflections on wet asphalt, cinematic 8K ultra-realistic photography",
        "Aerial view of a luxury penthouse infinity pool in Dubai at golden hour, glass skyscrapers, warm amber light, cinematic wide angle 8K",
        "Private jet interior at sunset, cream leather seats, champagne glass catching light, clouds below through oval window, luxury cinematic photography",
        "Empty modern mansion living room at dawn, floor-to-ceiling windows, city skyline, minimalist luxury interior, cinematic lighting 8K",
        "Black Rolls Royce on a foggy mountain road at sunrise, ultra-realistic cinematic photography, dramatic atmosphere"
    ]
    prompt = random.choice(scenes)
    with open(PROMPT_FILE, "w", encoding="utf-8") as f:
        f.write(prompt)
    return prompt, []


# =============================================================
# TOOL 2 — AI CONTENT GENERATOR (Pollinations.ai — free)
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
            log.warning("No prompt file found. Using fallback.")
            trend_prompt, _ = generate_fallback_prompt()

    log.info("Generating image prompt via Pollinations text AI...")
    image_prompt = generate_text_prompt(trend_prompt)

    safe_prompt = image_prompt.encode('ascii', 'replace').decode('ascii')
    log.info(f"Image prompt: {safe_prompt[:200]}")

    log.info("Generating image via Pollinations FLUX model...")
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

    timestamp   = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(OUTPUT_FOLDER, f"content_{timestamp}.jpg")

    result  = generate_image(image_prompt, output_path)
    caption = generate_caption(image_prompt)

    meta_path = output_path.replace(".jpg", "_meta.txt")
    with open(meta_path, "w", encoding="utf-8") as f:
        f.write(f"TIMESTAMP: {timestamp}\n")
        f.write(f"IMAGE PROMPT:\n{image_prompt}\n\n")
        f.write(f"CAPTION:\n{caption}\n")

    log.info(f"Content saved: {output_path}")
    return result, caption


def generate_text_prompt(trend_prompt: str) -> str:
    try:
        clean   = trend_prompt.strip()[:1500]
        encoded = urllib.parse.quote(clean)
        url     = f"https://text.pollinations.ai/{encoded}?model=openai&seed={random.randint(1,9999)}"

        r = requests.get(url, timeout=45)
        r.raise_for_status()

        # Strip markdown formatting that Pollinations sometimes adds
        text = r.text.strip()
        for prefix in ["**Cinematic Image Prompt**", "**Cinematic image prompt**",
                       "**Image Prompt**", "**Prompt:**", "**"]:
            text = text.replace(prefix, "")
        text = text.strip().lstrip("*#\n ")

        return text[:400] if len(text) > 400 else text

    except Exception as e:
        log.error(f"Pollinations text error: {e}")
        lines = [l.strip() for l in trend_prompt.split("\n") if len(l.strip()) > 30]
        return lines[0] if lines else "Cinematic luxury penthouse at golden hour, 8K ultra-realistic"


def generate_image(prompt: str, output_path: str, retries: int = 3) -> str | None:
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
            r = requests.get(url, timeout=90)

            if r.status_code == 200 and len(r.content) > 10000:
                with open(output_path, "wb") as f:
                    f.write(r.content)
                log.info(f"Image saved ({len(r.content)//1024}KB): {output_path}")
                return output_path
            else:
                log.warning(f"Bad response: {r.status_code}, size: {len(r.content)}")

        except requests.Timeout:
            log.warning(f"Timeout on attempt {attempt}")
        except Exception as e:
            log.error(f"Image error: {e}")

        if attempt < retries:
            wait = 10 * attempt
            log.info(f"Retrying in {wait}s...")
            time.sleep(wait)

    log.error("All image generation attempts failed")
    return None


def generate_caption(image_prompt: str) -> str:
    try:
        caption_request = f"""Write a short viral Instagram caption for luxury lifestyle content.
Image shows: {image_prompt[:200]}

Format — exactly two lines:
Line 1: One powerful hook (max 10 words)
Line 2: One motivational statement about success or freedom (max 15 words)

Only output the two lines. No hashtags. No quotes. No labels."""

        encoded = urllib.parse.quote(caption_request)
        r       = requests.get(f"https://text.pollinations.ai/{encoded}?model=openai", timeout=30)
        lines   = [l.strip() for l in r.text.strip().split("\n") if l.strip()]

        hook       = lines[0] if len(lines) > 0 else "The life you want is waiting."
        motivation = lines[1] if len(lines) > 1 else "Build it every single day."

        return CAPTION_TEMPLATE.format(hook=hook, motivation=motivation)

    except Exception:
        return CAPTION_TEMPLATE.format(
            hook="The life you want is closer than you think.",
            motivation="Every successful person started exactly where you are."
        )


# =============================================================
# TOOL 3 — AUTO PUBLISHER (Instagram via instagrapi)
# =============================================================

def upload_latest_content():
    log.info("=" * 50)
    log.info("TOOL 3: Publishing Content")
    log.info("=" * 50)

    image_path, caption = pick_latest_content()

    if not image_path:
        log.warning("No content found in generated_shots/")
        return False

    log.info(f"Selected: {image_path}")
    return upload_to_instagram(image_path, caption)


def pick_latest_content():
    if not os.path.exists(OUTPUT_FOLDER):
        return None, None

    images = [
        os.path.join(OUTPUT_FOLDER, f) for f in os.listdir(OUTPUT_FOLDER)
        if f.endswith((".jpg", ".jpeg", ".png")) and "_meta" not in f
    ]

    if not images:
        return None, None

    images.sort(key=os.path.getctime, reverse=True)
    latest    = images[0]
    meta_path = latest.rsplit(".", 1)[0] + "_meta.txt"
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
    try:
        from instagrapi import Client

        cl = Client()

        # Priority 1: session from GitHub Secret (environment variable)
        if INSTAGRAM_SESSION:
            log.info("Instagram: loading session from GitHub Secret...")
            settings = json.loads(INSTAGRAM_SESSION)
            cl.set_settings(settings)
            cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
            log.info("Instagram: session loaded from secret")

        # Priority 2: session from local file
        elif os.path.exists(SESSION_FILE):
            log.info("Instagram: loading session from local file...")
            cl.load_settings(SESSION_FILE)
            cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
            log.info("Instagram: session loaded from file")

        # Priority 3: fresh login (may be blocked on new IPs)
        else:
            log.info("Instagram: attempting fresh login...")
            time.sleep(5)
            cl.login(INSTAGRAM_USER, INSTAGRAM_PASS)
            log.info("Instagram: fresh login successful")

        # Save updated session
        cl.dump_settings(SESSION_FILE)

        # Upload photo
        media = cl.photo_upload(path=image_path, caption=caption)
        log.info(f"Instagram: posted successfully! Media ID: {media.pk}")
        return True

    except ImportError:
        log.error("instagrapi not installed. Run: pip install instagrapi")
        return False
    except Exception as e:
        log.error(f"Instagram upload failed: {e}")
        return False


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
        trend_prompt, trends = analyze_youtube_trends()
        time.sleep(2)

        image_path, caption = generate_ai_content(trend_prompt)
        time.sleep(2)

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
# ENTRY POINT
# GitHub Actions: python pipeline.py --once
# Local:         python pipeline.py
# =============================================================

if __name__ == "__main__":
    Path(OUTPUT_FOLDER).mkdir(exist_ok=True)

    if "--once" in sys.argv:
        # GitHub Actions mode — run once and exit cleanly
        log.info("Running in GitHub Actions mode (--once)")
        full_pipeline()

    else:
        # Local mode — optional immediate run + daily scheduler
        log.info("Auto Content Pipeline starting...")
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
