"""
OMR: multiple-mark anomalies in grading, cleaning of the model's answer list, and
image preparation (EXIF rotation, greyscale, contrast, size cap).
"""
import io
import sys
from pathlib import Path

from PIL import Image

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_grade_flags_multiple_marks_separately_from_blanks():
    from services.omr_processor import grade_omr_answers
    r = grade_omr_answers([0, -1, -2, 1], answer_key=[0, 1, 2, 0], marks_per_question=1, negative_marking=0.5)
    assert r["correct_count"] == 1 and r["incorrect_count"] == 1 and r["blank_count"] == 1
    assert r["multiple_count"] == 1 and r["multiple_marked"] == [2]
    assert r["score"] == 0.5  # one correct, one wrong at -0.5; multiple marks earn nothing but are not penalised
    assert r["needs_review"] is True


def test_grade_clean_sheet_needs_no_review():
    from services.omr_processor import grade_omr_answers
    r = grade_omr_answers([0, 1], answer_key=[0, 1], marks_per_question=2)
    assert r["needs_review"] is False and r["multiple_count"] == 0 and r["score"] == 4


def test_grade_mostly_blank_sheet_needs_review():
    from services.omr_processor import grade_omr_answers
    r = grade_omr_answers([-1, -1, -1, 0], answer_key=[0, 0, 0, 0], marks_per_question=1)
    assert r["needs_review"] is True and r["blank_count"] == 3


def test_clean_detected_answers_accepts_minus_two_and_fixes_junk():
    from services.omr_processor import clean_detected_answers
    assert clean_detected_answers([0, -2, "x", 9, True, -1], num_questions=7, options_per_question=4) == [0, -2, -1, -1, -1, -1, -1]


def _jpeg_with_orientation(width, height, orientation):
    img = Image.new("RGB", (width, height), "white")
    exif = img.getexif()
    exif[0x0112] = orientation
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    buf.seek(0)
    return Image.open(buf)


def test_prepare_sheet_image_applies_exif_rotation_greyscale_and_size_cap():
    from services.omr_processor import prepare_sheet_image, MAX_SHEET_SIDE
    out = prepare_sheet_image(_jpeg_with_orientation(100, 50, 6))  # 6 = rotate 90 degrees
    assert out.size == (50, 100)
    assert out.mode == "L"
    big = prepare_sheet_image(Image.new("RGB", (4000, 2000), "white"))
    assert max(big.size) == MAX_SHEET_SIDE


def test_prepare_sheet_image_improves_contrast():
    from services.omr_processor import prepare_sheet_image
    img = Image.new("L", (10, 10), 100)
    img.putpixel((0, 0), 120)
    out = prepare_sheet_image(img)
    lo, hi = out.getextrema()
    assert lo == 0 and hi == 255
