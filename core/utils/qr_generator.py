"""
QR code generator for event deep links.
Generates branded QR PNGs with event label.
"""

import os
import qrcode
from PIL import Image, ImageDraw, ImageFont


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_event_qr(event_code: str, bot_username: str, label: str = None) -> str:
    """Generate a QR code PNG for an event deep link.

    Returns the file path of the generated QR image.
    """
    deep_link = f"https://t.me/{bot_username}?start=event_{event_code}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=12,
        border=2,
    )
    qr.add_data(deep_link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Add label below QR
    label_text = label or f"{event_code} — Scan to Join"
    width, height = img.size
    new_height = height + 60
    final = Image.new("RGB", (width, new_height), "white")
    final.paste(img, (0, 0))

    draw = ImageDraw.Draw(final)
    font = None
    for font_path in [
        "/System/Library/Fonts/Helvetica.ttc",           # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Debian/Ubuntu
        "/usr/share/fonts/TTF/DejaVuSans.ttf",           # Arch
    ]:
        try:
            font = ImageFont.truetype(font_path, 24)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label_text, font=font)
    text_w = bbox[2] - bbox[0]
    draw.text(((width - text_w) / 2, height + 15), label_text, fill="black", font=font)

    out_path = os.path.join(PROJECT_ROOT, f"{event_code}_QR.png")
    final.save(out_path)
    return out_path
