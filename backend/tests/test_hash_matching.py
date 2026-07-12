"""Perceptual + SimHash matching survives WhatsApp-style mangling."""
import io
import random

from PIL import Image, ImageDraw

from app.pipeline import hashing

random.seed(42)


def _demo_image(seed: int) -> Image.Image:
    """Structured image (not noise) so phash behaves like real creatives."""
    rng = random.Random(seed)
    im = Image.new("RGB", (640, 480), (rng.randrange(256),) * 3)
    draw = ImageDraw.Draw(im)
    for _ in range(12):
        x0, y0 = rng.randrange(560), rng.randrange(400)
        draw.rectangle(
            [x0, y0, x0 + rng.randrange(30, 200), y0 + rng.randrange(30, 200)],
            fill=(rng.randrange(256), rng.randrange(256), rng.randrange(256)),
        )
    return im


def _bytes(im: Image.Image, fmt: str = "PNG", **kw) -> bytes:
    buf = io.BytesIO()
    im.save(buf, fmt, **kw)
    return buf.getvalue()


class TestPhash:
    def test_reencode_and_resize_stay_within_match_band(self) -> None:
        im = _demo_image(1)
        original = hashing.phash64_hex(_bytes(im))
        jpeg_q50 = hashing.phash64_hex(_bytes(im, "JPEG", quality=50))
        half = hashing.phash64_hex(_bytes(im.resize((320, 240))))
        assert hashing.hamming_hex(original, jpeg_q50) <= 10
        assert hashing.hamming_hex(original, half) <= 10

    def test_different_images_far_apart(self) -> None:
        a = hashing.phash64_hex(_bytes(_demo_image(1)))
        b = hashing.phash64_hex(_bytes(_demo_image(99)))
        assert hashing.hamming_hex(a, b) > 16

    def test_heavy_edit_lands_in_near_band_or_beyond_match(self) -> None:
        im = _demo_image(1)
        draw = ImageDraw.Draw(im)
        draw.rectangle([0, 0, 640, 160], fill=(255, 0, 0))  # big banner slapped on
        edited = hashing.phash64_hex(_bytes(im))
        original = hashing.phash64_hex(_bytes(_demo_image(1)))
        assert hashing.hamming_hex(original, edited) > 0


class TestSimHash:
    BODY = (
        "Kumaon Metals Limited announces its Q1 FY27 results. Revenue grew 14% "
        "year on year to ₹842 crore with EBITDA margins improving to 19.3%. The "
        "board declared an interim dividend of ₹4 per share payable in August."
    )

    def test_whitespace_emoji_zero_width_stable(self) -> None:
        a = hashing.simhash64_hex(self.BODY)
        mangled = "  " + self.BODY.replace(" ", "  ").replace("results.", "results. 📈") + " ​"
        b = hashing.simhash64_hex(mangled)
        assert hashing.hamming_hex(a, b) <= 6

    def test_different_text_far(self) -> None:
        other = (
            "Weather update: monsoon rains expected across coastal Karnataka this "
            "week with fishing advisories issued for three districts by the IMD."
        )
        assert hashing.hamming_hex(
            hashing.simhash64_hex(self.BODY), hashing.simhash64_hex(other)
        ) > 6

    def test_edited_figure_still_similar_text(self) -> None:
        # one changed number ≠ new document; simhash should stay close, which
        # is exactly why VERIFY requires the sha256/envelope for filings
        tampered = self.BODY.replace("14%", "41%")
        assert hashing.hamming_hex(
            hashing.simhash64_hex(self.BODY), hashing.simhash64_hex(tampered)
        ) <= 6

    def test_empty_and_short(self) -> None:
        assert hashing.simhash64_hex("") == f"{0:016x}"
        assert len(hashing.simhash64_hex("hello")) == 16


class TestVideoRatio:
    def test_ratio_counts_query_frames_matching_any_registered(self) -> None:
        reg = ["00ff00ff00ff00ff", "ff00ff00ff00ff00", "0f0f0f0f0f0f0f0f"]
        query = ["00ff00ff00ff00fe", "ff00ff00ff00ff00", "ffffffffffffffff", "0f0f0f0f0f0f0f0e"]
        # three of four query frames within dist 10 of some registered frame
        assert hashing.video_match_ratio(query, reg, 10) == 0.75

    def test_empty_inputs(self) -> None:
        assert hashing.video_match_ratio([], ["aa"], 10) == 0.0
        assert hashing.video_match_ratio(["aa"], [], 10) == 0.0


def test_normalize_text() -> None:
    assert hashing.normalize_text("  HELLO​   World\n\tfoo ") == "hello world foo"
