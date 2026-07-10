"""
Generates one nursery-rhyme video:
1. Picks a rhyme for today (rotates through rhymes.json by day-of-year)
2. Narrates it with free Edge TTS (no API key needed)
3. Generates a background image with Pollinations.ai (free, no API key needed)
4. Draws captions onto the image with Pillow
5. Combines image + audio into a vertical (9:16) video with MoviePy

Output: final_video.mp4, plus title.txt / description.txt for the uploader.
"""
import asyncio
import json
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip

ROOT = Path(__file__).parent
RHYMES_FILE = ROOT / "rhymes.json"
AUDIO_FILE = ROOT / "audio.mp3"
BG_FILE = ROOT / "bg.jpg"
CAPTIONED_FILE = ROOT / "captioned.jpg"
VIDEO_FILE = ROOT / "final_video.mp4"
TITLE_FILE = ROOT / "title.txt"
DESC_FILE = ROOT / "description.txt"

VOICE = "en-US-AnaNeural"  # free, child-friendly Edge TTS voice
WIDTH, HEIGHT = 720, 1280   # vertical, good for Shorts


def pick_rhyme():
    rhymes = json.loads(RHYMES_FILE.read_text())
    day_index = datetime.now(timezone.utc).timetuple().tm_yday
    return rhymes[day_index % len(rhymes)]


async def make_audio(text: str):
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%")
    await communicate.save(str(AUDIO_FILE))


def make_background(prompt: str):
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}?width={WIDTH}&height={HEIGHT}&nologo=true"
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    BG_FILE.write_bytes(resp.content)


def add_captions(lyrics: str, title: str):
    img = Image.open(BG_FILE).convert("RGB").resize((WIDTH, HEIGHT))
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 34)
    except OSError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    # Semi-transparent caption band at the bottom
    band_h = 380
    overlay = Image.new("RGBA", (WIDTH, band_h), (0, 0, 0, 150))
    img.paste(Image.alpha_composite(img.crop((0, HEIGHT - band_h, WIDTH, HEIGHT)).convert("RGBA"), overlay).convert("RGB"),
              (0, HEIGHT - band_h))
    draw = ImageDraw.Draw(img)

    wrapped = textwrap.fill(lyrics, width=28)
    draw.multiline_text((30, HEIGHT - band_h + 20), wrapped, font=font_body, fill="white", spacing=10)
    draw.text((30, 30), title, font=font_title, fill="white")

    img.save(CAPTIONED_FILE, quality=90)


def make_video():
    audio = AudioFileClip(str(AUDIO_FILE))
    clip = ImageClip(str(CAPTIONED_FILE)).set_duration(audio.duration).set_audio(audio)
    clip = clip.resize(newsize=(WIDTH, HEIGHT))
    clip.write_videofile(str(VIDEO_FILE), fps=24, codec="libx264", audio_codec="aac")


def main():
    rhyme = pick_rhyme()
    print(f"Selected rhyme: {rhyme['title']}")

    asyncio.run(make_audio(rhyme["lyrics"]))
    make_background(rhyme["image_prompt"])
    add_captions(rhyme["lyrics"], rhyme["title"])
    make_video()

    TITLE_FILE.write_text(f"{rhyme['title']} | Nursery Rhymes for Kids 🎵")
    DESC_FILE.write_text(
        f"{rhyme['title']} - a classic nursery rhyme for toddlers and kids.\n\n"
        f"Lyrics: {rhyme['lyrics']}\n\n"
        "#nurseryrhymes #kidssongs #toddlersongs"
    )
    print("Done. Video ready at", VIDEO_FILE)


if __name__ == "__main__":
    main()
