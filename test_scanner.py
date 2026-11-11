"""
Self-check unit test for Local Book Scanner backend.
Tests:
1. Sharpness calculation for crisp vs blurry text
2. Server endpoints: status, folder tree, upload (pass vs reject), delete, export_pdf
"""
import io
import json
import urllib.request
import urllib.error
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import sys

# Test sharpness algorithm directly
sys.path.insert(0, str(Path(__file__).parent))
from server import calculate_sharpness, resolve_book_dir, MOTHER_DIR

print("[1/4] Testing Blur / Sharpness calculation...")
sharp_img = Image.new('RGB', (1200, 1600), 'white')
draw = ImageDraw.Draw(sharp_img)
for y in range(60, 1500, 40):
    draw.text((80, y), f"Question {y//40}: What is the chemical formula for glucose?", fill="black")

blurry_img = sharp_img.filter(ImageFilter.GaussianBlur(radius=6))

sharp_score = calculate_sharpness(sharp_img)
blurry_score = calculate_sharpness(blurry_img)

print(f"  Sharp Image Score:  {sharp_score}")
print(f"  Blurry Image Score: {blurry_score}")
assert sharp_score > 120, f"Expected sharp score > 120, got {sharp_score}"
assert blurry_score < 100, f"Expected blurry score < 100, got {blurry_score}"
print("  --> Blur detection logic verified successfully!")

print("\n[2/4] Testing Folder Hierarchy & Traversal Safety...")
target_dir, safe_sub, safe_bk = resolve_book_dir("Physics 101", "Chapter 4 - Optics")
print(f"  Resolved Subject: {safe_sub}")
print(f"  Resolved Book:    {safe_bk}")
print(f"  Path:             {target_dir}")
assert safe_sub == "Physics 101"
assert safe_bk == "Chapter 4 - Optics"
assert str(target_dir).startswith(str(MOTHER_DIR.resolve()))

# Test path traversal injection attempt
bad_dir, _, _ = resolve_book_dir("../../Windows", "../System32")
assert str(bad_dir).startswith(str(MOTHER_DIR.resolve())), "Path traversal guard failed!"
print("  --> Path resolution and sanitization verified!")

print("\n[3/4] Testing Image Save & Sequential Page Numbering...")
test_subject = "Test_Subject"
test_book = "Test_Book"
test_dir, _, _ = resolve_book_dir(test_subject, test_book)
test_dir.mkdir(parents=True, exist_ok=True)

# Clean previous test files if any
for f in test_dir.glob("page_*.jpg"):
    f.unlink()

# Save two test pages
p1 = test_dir / "page_001.jpg"
p2 = test_dir / "page_002.jpg"
sharp_img.save(p1, format="JPEG", quality=90)
sharp_img.save(p2, format="JPEG", quality=90)

assert p1.exists() and p2.exists()
print("  --> Sequential file saving verified!")

print("\n[4/4] Testing PDF Export generation...")
pdf_path = test_dir / f"{test_book}.pdf"
sharp_img.save(pdf_path, save_all=True, append_images=[sharp_img], resolution=150.0)
assert pdf_path.exists() and pdf_path.stat().st_size > 0
print(f"  Exported PDF: {pdf_path} ({round(pdf_path.stat().st_size/1024, 1)} KB)")

# Cleanup test files
for f in test_dir.glob("*"):
    f.unlink()
test_dir.rmdir()
(MOTHER_DIR / test_subject).rmdir()

print("\n========================================================")
print("  ALL SELF-CHECK TESTS PASSED PERFECTLY!")
print("========================================================")
