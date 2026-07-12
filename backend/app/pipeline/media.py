"""ffmpeg keyframe extraction (spec §8.2). Fixed argument list, no shell."""
import subprocess
import tempfile
from pathlib import Path

import imagehash
from PIL import Image

FRAME_FPS = 1
FRAME_CAP = 24
FRAME_SCALE = 512  # longest side


def extract_frame_phashes(video_path: Path) -> list[str]:
    """1 fps frames (max 24), longest side 512 → ordered phash64 hex list.

    Raises RuntimeError with ffmpeg stderr on failure — callers decide how
    loud to be.
    """
    with tempfile.TemporaryDirectory(prefix="trustrail-frames-") as tmp:
        pattern = str(Path(tmp) / "frame-%03d.png")
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-i", str(video_path),
            "-vf", f"fps={FRAME_FPS},scale='if(gt(iw,ih),{FRAME_SCALE},-2)':'if(gt(iw,ih),-2,{FRAME_SCALE})'",
            "-frames:v", str(FRAME_CAP),
            pattern,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg frame extraction failed: {proc.stderr.strip()[:500]}")
        hashes: list[str] = []
        for frame in sorted(Path(tmp).glob("frame-*.png")):
            with Image.open(frame) as im:
                hashes.append(str(imagehash.phash(im.convert("RGB"))))
        return hashes
