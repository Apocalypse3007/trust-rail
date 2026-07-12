"""WhatsApp-mangle transforms (spec §16.1).

Minimal image preset only, built now to self-verify Epic 5's gate
end-to-end (publish -> mangle -> verify still matches). The full harness
— video crf variants, text whitespace/emoji injection, screenshot-sim —
is Epic 10 scope (`scripts/evaluate.py` + `docs/METRICS.md`).
"""
import argparse
import io
from pathlib import Path

from PIL import Image

WHATSAPP_JPEG_QUALITY = 70
WHATSAPP_RESIZE_FACTOR = 0.75


def mangle_image(data: bytes) -> bytes:
    """JPEG re-encode at reduced quality + resize; Image.save without an
    exif= kwarg drops metadata by construction — the cheapest real
    approximation of WhatsApp's media re-compression."""
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simulate WhatsApp media mangling (image preset only for now)."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--preset", default="whatsapp", choices=["whatsapp"])
    parser.add_argument("-o", "--output", type=Path, default=None)
    args = parser.parse_args()

    data = args.input.read_bytes()
    out = mangle_image(data)
    out_path = args.output or args.input.with_stem(args.input.stem + "_whatsapp")
    out_path.write_bytes(out)
    print(f"wrote {out_path} ({len(out)} bytes)")


if __name__ == "__main__":
    main()
