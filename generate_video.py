"""
Generates one nursery-rhyme video:
1. Picks a rhyme for today (rotates through rhymes.json by day-of-year)
2. Narrates it with free Edge TTS (no API key needed)
3. Normalizes the narration loudness with ffmpeg
4. Generates several background images with Pollinations.ai (free, no API key)
5. Draws per-line captions onto each image with Pillow
6. Applies a Ken Burns pan to each image and stitches them into a vertical
   (9:16) video synced to the narration, with optional background music.

Output: final_video.mp4, plus title.txt / description.txt for the uploader.
"""
import asyncio
import json
import subprocess
import textwrap
from datetime import datetime, timezone
from pathlib import Path

import requests
import edge_tts
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, CompositeAudioClip, concatenate_videoclips
from moviepy.audio.fx.all import audio_loop, volumex

ROOT = Path(__file__).parent
RHYMES_FILE = ROOT / "rhymes.json"
RAW_AUDIO_FILE = ROOT / "audio_raw.mp3"
AUDIO_FILE = ROOT / "audio.mp3"
VIDEO_FILE = ROOT / "final_video.mp4"
TITLE_FILE = ROOT / "title.txt"
DESC_FILE = ROOT / "description.txt"
BG_MUSIC_FILE = ROOT / "assets" / "bg_music.mp3"  # optional, add your own royalty-free track here

VOICE = "en-US-AnaNeural"  # free, child-friendly Edge TTS voice
WIDTH, HEIGHT = 720, 1280   # vertical, good for Shorts
NUM_IMAGES = 4               # background images per video
PAN_ZOOM_MARGIN = 0.18       # how much extra image size to allow panning across


def pick_rhyme():
    """Rotates through rhymes.json. Uses day-of-year plus an hour bucket so that
    the 3 daily runs (Pakistan ~2 UTC, UK ~6 UTC, US ~11 UTC) each get a
    different rhyme instead of repeating the same one."""
    rhymes = json.loads(RHYMES_FILE.read_text())
    now = datetime.now(timezone.utc)
    day_index = now.timetuple().tm_yday
    if now.hour < 4:
        hour_bucket = 0   # Pakistan run
    elif now.hour < 9:
        hour_bucket = 1   # UK run
    else:
        hour_bucket = 2   # US run
    index = day_index * 3 + hour_bucket
    return rhymes[index % len(rhymes)]


async def make_audio(text: str):
    communicate = edge_tts.Communicate(text, VOICE, rate="-10%")
    await communicate.save(str(RAW_AUDIO_FILE))


def normalize_audio():
    """Loudness-normalize + fade the narration using ffmpeg (already installed in CI)."""
    subprocess.run(
        [
            "ffmpeg", "-y", "-i", str(RAW_AUDIO_FILE),
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.3",
            "-ar", "44100",
            str(AUDIO_FILE),
        ],
        check=True,
        capture_output=True,
    )


def split_lines(lyrics: str, n: int):
    """Split lyrics into n roughly-even chunks for per-image captions."""
    raw_lines = [l.strip() for l in lyrics.splitlines() if l.strip()]
    if len(raw_lines) < n:
        # fall back to splitting the whole text evenly by words
        words = lyrics.split()
        chunk = max(1, len(words) // n)
        raw_lines = [" ".join(words[i:i + chunk]) for i in range(0, len(words), chunk)]
    # pad or trim to exactly n chunks
    if len(raw_lines) > n:
        merged = raw_lines[:n - 1] + [" ".join(raw_lines[n - 1:])]
        raw_lines = merged
    while len(raw_lines) < n:
        raw_lines.append("")
    return raw_lines[:n]


def fetch_background(prompt: str, seed: int, out_path: Path):
    url = (
        f"https://image.pollinations.ai/prompt/{requests.utils.quote(prompt)}"
        f"?width={WIDTH}&height={HEIGHT}&nologo=true&seed={seed}"
    )
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)


def caption_image(bg_path: Path, line_text: str, title: str, show_title: bool, out_path: Path):
    img = Image.open(bg_path).convert("RGB").resize(
        (int(WIDTH * (1 + PAN_ZOOM_MARGIN)), int(HEIGHT * (1 + PAN_ZOOM_MARGIN)))
    )
    draw = ImageDraw.Draw(img)
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 46)
        font_body = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 38)
    except OSError:
        font_title = ImageFont.load_default()
        font_body = ImageFont.load_default()

    w, h = img.size
    band_h = 220
    overlay = Image.new("RGBA", (w, band_h), (0, 0, 0, 150))
    band = Image.alpha_composite(img.crop((0, h - band_h, w, h)).convert("RGBA"), overlay).convert("RGB")
    img.paste(band, (0, h - band_h))
    draw = ImageDraw.Draw(img)

    wrapped = textwrap.fill(line_text, width=26)
    draw.multiline_text((30, h - band_h + 25), wrapped, font=font_body, fill="white", spacing=10, align="left")

    if show_title:
        title_overlay = Image.new("RGBA", (w, 110), (0, 0, 0, 130))
        top_band = Image.alpha_composite(img.crop((0, 0, w, 110)).convert("RGBA"), title_overlay).convert("RGB")
        img.paste(top_band, (0, 0))
        draw = ImageDraw.Draw(img)
        draw.text((30, 25), title, font=font_title, fill="white")

    img.save(out_path, quality=92)


def ken_burns_clip(image_path: Path, duration: float):
    """Oversized image panned across the frame for a simple, cheap Ken Burns effect."""
    clip = ImageClip(str(image_path)).set_duration(duration)
    over_w, over_h = clip.size
    max_x = over_w - WIDTH
    max_y = over_h - HEIGHT

    # pick a pan direction so consecutive clips don't feel identical
    import random
    x0, y0 = random.randint(0, max_x), random.randint(0, max_y)
    x1, y1 = random.randint(0, max_x), random.randint(0, max_y)

    def pos(t):
        progress = t / duration if duration else 0
        x = x0 + (x1 - x0) * progress
        y = y0 + (y1 - y0) * progress
        return (-x, -y)

    panned = clip.set_position(pos)
    return CompositeVideoClip([panned], size=(WIDTH, HEIGHT)).set_duration(duration)


def build_video(rhyme: dict):
    narration = AudioFileClip(str(AUDIO_FILE))
    lines = split_lines(rhyme["lyrics"], NUM_IMAGES)
    per_clip_dur = narration.duration / NUM_IMAGES

    segment_clips = []
    for i, line in enumerate(lines):
        bg_path = ROOT / f"bg_{i}.jpg"
        cap_path = ROOT / f"captioned_{i}.jpg"
        fetch_background(rhyme["image_prompt"], seed=hash((rhyme["title"], i)) % 100000, out_path=bg_path)
        caption_image(bg_path, line, rhyme["title"], show_title=(i == 0), out_path=cap_path)
        clip = ken_burns_clip(cap_path, per_clip_dur)
        if i > 0:
            clip = clip.crossfadein(0.4)
        segment_clips.append(clip)

    video = concatenate_videoclips(segment_clips, method="compose", padding=-0.4)
    video = video.set_duration(narration.duration)

    if BG_MUSIC_FILE.exists():
        music = AudioFileClip(str(BG_MUSIC_FILE)).fx(audio_loop, duration=narration.duration).fx(volumex, 0.12)
        final_audio = CompositeAudioClip([music, narration])
    else:
        final_audio = narration

    video = video.set_audio(final_audio)
    video.write_videofile(str(VIDEO_FILE), fps=24, codec="libx264", audio_codec="aac")


def main():
    rhyme = pick_rhyme()
    print(f"Selected rhyme: {rhyme['title']}")

    asyncio.run(make_audio(rhyme["lyrics"]))
    normalize_audio()
    build_video(rhyme)

    TITLE_FILE.write_text(f"{rhyme['title']} | Nursery Rhymes for Kids 🎵")
    DESC_FILE.write_text(
        f"{rhyme['title']} - a classic nursery rhyme for toddlers and kids.\n\n"
        f"Lyrics: {rhyme['lyrics']}\n\n"
        "#nurseryrhymes #kidssongs #toddlersongs #shorts"
    )
    print("Done. Video ready at", VIDEO_FILE)


if __name__ == "__main__":
    main()
