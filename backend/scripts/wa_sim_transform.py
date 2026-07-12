"""WhatsApp-mangle transforms (spec §16.1) — the full set: images, video,
text. Used both standalone (CLI, for manually mangling a demo file) and by
scripts/evaluate.py (spec §16.2) to measure how much soft-match survives.
"""
import argparse
import io
import subprocess
import tempfile
from pathlib import Path

from PIL import Image


# --- image transforms ---

def jpeg_requality(data: bytes, quality: int) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=quality)
        return buf.getvalue()


def resize_factor(data: bytes, factor: float) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        new_size = (max(1, int(im.width * factor)), max(1, int(im.height * factor)))
        buf = io.BytesIO()
        im.resize(new_size, Image.LANCZOS).save(buf, format="JPEG", quality=85)
        return buf.getvalue()


def metadata_strip(data: bytes) -> bytes:
    """Image.save without an exif= kwarg drops metadata by construction."""
    with Image.open(io.BytesIO(data)) as im:
        buf = io.BytesIO()
        im.convert("RGB").save(buf, format="JPEG", quality=90)
        return buf.getvalue()


def screenshot_sim(data: bytes) -> bytes:
    """5% crop + PNG round-trip -> JPEG q80, approximating a phone
    screenshot of a forwarded image (spec §16.1)."""
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        w, h = im.size
        dx, dy = int(w * 0.025), int(h * 0.025)
        im = im.crop((dx, dy, w - dx, h - dy))
        png_buf = io.BytesIO()
        im.save(png_buf, format="PNG")
        with Image.open(io.BytesIO(png_buf.getvalue())) as im2:
            buf = io.BytesIO()
            im2.convert("RGB").save(buf, format="JPEG", quality=80)
            return buf.getvalue()


IMAGE_PRESETS = {
    "jpeg_q85": lambda d: jpeg_requality(d, 85),
    "jpeg_q70": lambda d: jpeg_requality(d, 70),
    "jpeg_q50": lambda d: jpeg_requality(d, 50),
    "resize_0.75": lambda d: resize_factor(d, 0.75),
    "resize_0.5": lambda d: resize_factor(d, 0.5),
    "metadata_strip": metadata_strip,
    "screenshot_sim": screenshot_sim,
}

# Epic 5's original single preset — kept for backward compatibility with
# scripts/smoke_epic5.py; equivalent to resize 0.75 + JPEG q70.
WHATSAPP_JPEG_QUALITY = 70
WHATSAPP_RESIZE_FACTOR = 0.75


def mangle_image(data: bytes) -> bytes:
    with Image.open(io.BytesIO(data)) as im:
        im = im.convert("RGB")
        new_size = (
            max(1, int(im.width * WHATSAPP_RESIZE_FACTOR)),
            max(1, int(im.height * WHATSAPP_RESIZE_FACTOR)),
        )
        im = im.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=WHATSAPP_JPEG_QUALITY)
        return buf.getvalue()


# --- video transforms ---

_VIDEO_FFMPEG_ARGS = {
    "crf26": ["-vf", "scale=848:-2", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
              "-c:a", "aac", "-b:a", "64k", "-map_metadata", "-1"],
    "crf30": ["-vf", "scale=848:-2", "-c:v", "libx264", "-crf", "30", "-preset", "veryfast",
              "-c:a", "aac", "-b:a", "64k", "-map_metadata", "-1"],
}


def video_transform(data: bytes, preset: str) -> bytes:
    with tempfile.TemporaryDirectory(prefix="trustrail-wa-") as tmp:
        in_path = Path(tmp) / "in.mp4"
        out_path = Path(tmp) / "out.mp4"
        in_path.write_bytes(data)
        cmd = [
            "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
            "-i", str(in_path), *_VIDEO_FFMPEG_ARGS[preset], str(out_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg transform failed: {proc.stderr.decode(errors='replace')[:500]}")
        return out_path.read_bytes()


VIDEO_PRESETS = {name: (lambda d, n=name: video_transform(d, n)) for name in _VIDEO_FFMPEG_ARGS}


# --- text transforms ---

_EMOJI = ["😊", "🚀", "💰", "📈"]
_ZERO_WIDTH = "​‌‍﻿"


def text_whitespace_emoji_inject(text: str) -> str:
    words = text.split(" ")
    out: list[str] = []
    for i, w in enumerate(words):
        out.append(w)
        if i % 3 == 2:
            out.append(_EMOJI[i % len(_EMOJI)])
    return ("  ".join(out)) + _ZERO_WIDTH[0]


def text_zero_width_strip_test(text: str) -> str:
    """Interleaves zero-width characters — SimHash must be stable after
    normalize_text() strips them (spec §16.1)."""
    out: list[str] = []
    for i, ch in enumerate(text):
        out.append(ch)
        if i % 4 == 3:
            out.append(_ZERO_WIDTH[i % len(_ZERO_WIDTH)])
    return "".join(out)


TEXT_PRESETS = {
    "whitespace_emoji": text_whitespace_emoji_inject,
    "zero_width_strip": text_zero_width_strip_test,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate WhatsApp media mangling.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--preset", default="whatsapp",
                         choices=["whatsapp", *IMAGE_PRESETS, *VIDEO_PRESETS])
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()

    data = args.input.read_bytes()
    if args.preset == "whatsapp":
        out = mangle_image(data)
    elif args.preset in IMAGE_PRESETS:
        out = IMAGE_PRESETS[args.preset](data)
    else:
        out = VIDEO_PRESETS[args.preset](data)
    out_path = args.output or args.input.with_stem(f"{args.input.stem}_{args.preset}")
    out_path.write_bytes(out)
    print(f"wrote {out_path} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
