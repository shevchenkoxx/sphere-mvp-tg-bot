"""
Personality Card Generator — creates shareable profile card images.

After DM onboarding, generates an AI personality summary and renders
a branded card image with: type label, traits, interests, vibe, QR code.
Users share in groups to drive onboarding.
"""

import asyncio
import io
import logging
from typing import Optional, List

from PIL import Image, ImageDraw, ImageFont
import qrcode

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Lazy singleton OpenAI client — avoids creating a new client on every call
_openai_client: Optional[AsyncOpenAI] = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        from config.settings import settings
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=20.0)
    return _openai_client

# Card dimensions (Telegram-friendly aspect ratio)
CARD_WIDTH = 800
CARD_HEIGHT = 1000

# Colors — Sphere brand palette
BG_COLOR = (18, 18, 30)         # Dark navy
ACCENT_COLOR = (99, 102, 241)   # Indigo / purple
ACCENT_LIGHT = (139, 92, 246)   # Lighter purple
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY = (180, 180, 200)
TEXT_MUTED = (120, 120, 150)
CARD_BG = (28, 28, 48)          # Slightly lighter card area
TAG_BG = (50, 50, 80)           # Tag background


def _load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load a font with fallback to default."""
    paths = [
        "/System/Library/Fonts/Avenir Next.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ]
    if bold:
        paths = [
            "/System/Library/Fonts/Avenir Next.ttc",
            "/System/Library/Fonts/Helvetica.ttc",
        ] + paths

    for path in paths:
        try:
            return ImageFont.truetype(path, size, index=1 if bold else 0)
        except (OSError, IndexError):
            try:
                return ImageFont.truetype(path, size)
            except OSError:
                continue

    return ImageFont.load_default()


async def generate_personality_summary(user) -> dict:
    """Generate a personality type + traits via LLM."""
    client = _get_openai_client()

    profile_text = f"""
Name: {user.display_name or user.first_name or 'Unknown'}
Bio: {user.bio or 'N/A'}
Interests: {', '.join(user.interests or [])}
Goals: {', '.join(user.goals or [])}
Looking for: {user.looking_for or 'N/A'}
Can help with: {user.can_help_with or 'N/A'}
Profession: {getattr(user, 'profession', None) or 'N/A'}
""".strip()

    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You create fun, flattering personality types for a social matching app. "
                    "Given a user profile, output JSON with these exact keys:\n"
                    '{"type": "The [Creative Type Name]", "tagline": "[one catchy sentence]", '
                    '"traits": ["trait1", "trait2", "trait3"], "vibe": "[one word vibe]"}\n'
                    "Be creative and positive. Types should feel like premium MBTI alternatives. "
                    "Examples: 'The Curious Architect', 'The Vibe Alchemist', 'The Bridge Builder'."
                )},
                {"role": "user", "content": profile_text},
            ],
            max_tokens=150,
            temperature=0.9,
        )
        import json
        text = response.choices[0].message.content or "{}"
        # Clean up markdown wrapping if present
        if "```json" in text:
            text = text.split("```json")[-1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())
    except Exception as e:
        logger.error(f"[CARD] Failed to generate personality summary: {e}")
        return {
            "type": "The Explorer",
            "tagline": "Always discovering new connections.",
            "traits": ["Curious", "Open-minded", "Authentic"],
            "vibe": "Adventurous",
        }


def render_personality_card(
    name: str,
    personality: dict,
    interests: Optional[List[str]] = None,
    qr_url: Optional[str] = None,
) -> bytes:
    """Render a personality card as PNG bytes."""
    img = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), BG_COLOR)
    draw = ImageDraw.Draw(img)

    # Fonts
    font_title = _load_font(42, bold=True)
    font_type = _load_font(32, bold=True)
    font_tagline = _load_font(20)
    font_body = _load_font(22)
    font_label = _load_font(16)
    font_small = _load_font(14)

    y = 40

    # --- Header: SPHERE logo text ---
    draw.text((40, y), "SPHERE", fill=ACCENT_COLOR, font=font_label)
    y += 30

    # --- Decorative line ---
    draw.rectangle([(40, y), (CARD_WIDTH - 40, y + 2)], fill=ACCENT_COLOR)
    y += 25

    # --- Name ---
    draw.text((40, y), name, fill=TEXT_WHITE, font=font_title)
    y += 55

    # --- Personality type ---
    ptype = personality.get("type", "The Explorer")
    draw.text((40, y), ptype, fill=ACCENT_LIGHT, font=font_type)
    y += 45

    # --- Tagline ---
    tagline = personality.get("tagline", "")
    if tagline:
        # Word wrap tagline
        _draw_wrapped_text(draw, 40, y, tagline, font_tagline, TEXT_GRAY, CARD_WIDTH - 80)
        y += 35

    y += 15

    # --- Vibe badge ---
    vibe = personality.get("vibe", "")
    if vibe:
        draw.text((40, y), "VIBE", fill=TEXT_MUTED, font=font_label)
        y += 22
        # Draw vibe pill
        vibe_text = vibe.upper()
        bbox = draw.textbbox((0, 0), vibe_text, font=font_body)
        pill_w = bbox[2] - bbox[0] + 30
        pill_h = bbox[3] - bbox[1] + 16
        _draw_rounded_rect(draw, 40, y, 40 + pill_w, y + pill_h, 12, ACCENT_COLOR)
        draw.text((55, y + 5), vibe_text, fill=TEXT_WHITE, font=font_body)
        y += pill_h + 20

    y += 10

    # --- Traits ---
    traits = personality.get("traits", [])
    if traits:
        draw.text((40, y), "TRAITS", fill=TEXT_MUTED, font=font_label)
        y += 25
        for trait in traits[:4]:
            draw.text((50, y), f"  {trait}", fill=TEXT_WHITE, font=font_body)
            y += 32
        y += 10

    # --- Interests tags ---
    if interests:
        draw.text((40, y), "INTERESTS", fill=TEXT_MUTED, font=font_label)
        y += 25
        x = 40
        for tag in interests[:6]:
            tag_text = f"#{tag}"
            bbox = draw.textbbox((0, 0), tag_text, font=font_small)
            tw = bbox[2] - bbox[0] + 20
            th = bbox[3] - bbox[1] + 12
            if x + tw > CARD_WIDTH - 40:
                x = 40
                y += th + 8
            _draw_rounded_rect(draw, x, y, x + tw, y + th, 8, TAG_BG)
            draw.text((x + 10, y + 4), tag_text, fill=TEXT_GRAY, font=font_small)
            x += tw + 8
        y += 40

    # --- QR code (bottom right) ---
    if qr_url:
        qr = qrcode.QRCode(version=1, box_size=4, border=1)
        qr.add_data(qr_url)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="white", back_color=BG_COLOR)
        qr_img = qr_img.convert("RGB").resize((120, 120))
        img.paste(qr_img, (CARD_WIDTH - 160, CARD_HEIGHT - 160))
        draw.text((CARD_WIDTH - 160, CARD_HEIGHT - 32), "Scan to match", fill=TEXT_MUTED, font=font_small)

    # --- Footer ---
    draw.rectangle([(40, CARD_HEIGHT - 45), (CARD_WIDTH - 40, CARD_HEIGHT - 43)], fill=TAG_BG)
    draw.text((40, CARD_HEIGHT - 35), "sphere.social", fill=TEXT_MUTED, font=font_small)

    # Export as PNG bytes
    buffer = io.BytesIO()
    img.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


def _draw_rounded_rect(draw: ImageDraw.ImageDraw, x1, y1, x2, y2, radius, fill):
    """Draw a rounded rectangle."""
    draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=radius, fill=fill)


async def render_personality_card_async(
    name: str,
    personality: dict,
    interests: Optional[List[str]] = None,
    qr_url: Optional[str] = None,
) -> bytes:
    """Async wrapper for render_personality_card — runs Pillow rendering in a thread pool."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, render_personality_card, name, personality, interests, qr_url
    )


def _draw_wrapped_text(draw: ImageDraw.ImageDraw, x, y, text: str, font, fill, max_width):
    """Draw text with word wrapping."""
    words = text.split()
    lines = []
    current_line = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]

    if current_line:
        lines.append(" ".join(current_line))

    for line in lines[:3]:  # Max 3 lines
        draw.text((x, y), line, fill=fill, font=font)
        y += 25
