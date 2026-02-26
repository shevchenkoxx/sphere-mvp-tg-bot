"""
Community Bingo — weekly bingo card with member traits.

Generates a 3x3 bingo grid of traits derived from member profiles.
Members claim squares by tagging each other or through inline buttons.
Completing a row triggers a DM CTA.
"""

import asyncio
import io
import logging
import random
from typing import Optional, List, Dict, Any
from uuid import UUID

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Trait templates — filled with real member data when possible
GENERIC_TRAITS = [
    "Works in tech", "Speaks 3+ languages", "Has lived abroad",
    "Started a business", "Can cook a signature dish", "Plays an instrument",
    "Has a side project", "Meditates regularly", "Loves board games",
    "Has run a marathon", "Writes a blog/newsletter", "Works remotely",
    "Has a pet", "Loves hiking", "Reads 20+ books/year",
    "Has given a public talk", "Volunteers regularly", "Knows how to code",
    "Is a morning person", "Has a creative hobby", "Loves podcasts",
    "Has a tattoo", "Has traveled to 10+ countries", "Plays video games",
    "Is into crypto/web3", "Does yoga", "Paints or draws",
]

# Card dimensions
BINGO_WIDTH = 700
BINGO_HEIGHT = 780
CELL_SIZE = 200
GRID_OFFSET_X = 50
GRID_OFFSET_Y = 100

# Colors
BG = (18, 18, 30)
CELL_BG = (35, 35, 60)
CELL_FILLED = (99, 102, 241)
BORDER = (60, 60, 90)
TEXT_WHITE = (255, 255, 255)
TEXT_GRAY = (180, 180, 200)
ACCENT = (139, 92, 246)


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    paths = [
        "/System/Library/Fonts/Avenir Next.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in paths:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


class BingoService:
    """Manages community bingo games."""

    def __init__(self, game_repo, community_repo, user_repo):
        self.game_repo = game_repo
        self.community_repo = community_repo
        self.user_repo = user_repo

    async def create_bingo(self, community_id: UUID) -> Optional[Dict[str, Any]]:
        """Create a new bingo card for a community."""
        # Get member profiles to generate relevant traits
        members = await self.community_repo.get_members(community_id)
        onboarded = [m for m in members if m.is_onboarded]

        if len(onboarded) < 3:
            return None

        # Generate traits — mix of profile-based and generic
        traits = await self._generate_traits(onboarded)
        if len(traits) < 9:
            return None

        # Pick 9 traits for the 3x3 grid
        selected = random.sample(traits, 9)

        game_data = {
            "grid": selected,  # 9 traits, row-major order
            "claimed": {},      # trait_index -> [{"user_id": ..., "claimer_name": ...}]
            "completed_rows": [],
        }

        session = await self.game_repo.create_session(
            community_id=community_id,
            game_type="bingo",
            game_data=game_data,
        )

        # Render card image (sync Pillow code — run in executor to avoid blocking event loop)
        loop = asyncio.get_running_loop()
        card_bytes = await loop.run_in_executor(None, self._render_bingo_card, selected, {})

        return {
            "session": session,
            "game_data": game_data,
            "card_image": card_bytes,
        }

    async def _generate_traits(self, members: list) -> List[str]:
        """Generate bingo traits from member profiles + generic pool."""
        traits = set()

        # Batch fetch all member profiles in a single query
        member_ids = [member.user_id for member in members]
        users = await self.user_repo.get_users_by_ids(member_ids)

        for user in users:
            # Extract traits from profile
            if user.interests:
                for interest in user.interests[:2]:
                    traits.add(f"Is into {interest}")

            profession = getattr(user, 'profession', None)
            if profession:
                traits.add(f"Works in {profession.lower()}")

            skills = getattr(user, 'skills', None)
            if skills:
                for skill in skills[:1]:
                    traits.add(f"Knows {skill}")

            if user.goals:
                for goal in user.goals[:1]:
                    traits.add(f"Looking for {goal}")

        # Fill with generic traits to ensure we have enough
        generic_pool = [t for t in GENERIC_TRAITS if t not in traits]
        random.shuffle(generic_pool)
        traits.update(generic_pool[:max(0, 12 - len(traits))])

        return list(traits)

    def _render_bingo_card(self, grid: List[str], claimed: Dict[str, list]) -> bytes:
        """Render a bingo card image as PNG bytes."""
        img = Image.new("RGB", (BINGO_WIDTH, BINGO_HEIGHT), BG)
        draw = ImageDraw.Draw(img)

        font_title = _load_font(32)
        font_cell = _load_font(16)
        font_small = _load_font(12)

        # Title
        draw.text((BINGO_WIDTH // 2 - 100, 25), "COMMUNITY BINGO", fill=ACCENT, font=font_title)
        draw.text((BINGO_WIDTH // 2 - 130, 65), "Find someone who matches each square!", fill=TEXT_GRAY, font=font_small)

        # Draw 3x3 grid
        for row in range(3):
            for col in range(3):
                idx = row * 3 + col
                x = GRID_OFFSET_X + col * (CELL_SIZE + 10)
                y = GRID_OFFSET_Y + row * (CELL_SIZE + 10)

                # Check if cell is claimed
                is_claimed = str(idx) in claimed and len(claimed[str(idx)]) > 0
                cell_color = CELL_FILLED if is_claimed else CELL_BG

                # Draw cell
                draw.rounded_rectangle(
                    [(x, y), (x + CELL_SIZE, y + CELL_SIZE)],
                    radius=12,
                    fill=cell_color,
                    outline=BORDER,
                    width=2,
                )

                # Draw trait text (word-wrapped)
                trait = grid[idx] if idx < len(grid) else "???"
                self._draw_cell_text(draw, x + 15, y + 15, trait, font_cell, CELL_SIZE - 30)

                # Draw checkmark if claimed
                if is_claimed:
                    draw.text((x + CELL_SIZE - 30, y + CELL_SIZE - 30), "✓", fill=TEXT_WHITE, font=font_title)

        # Footer
        draw.text((50, BINGO_HEIGHT - 40), "Tap a square to claim it!", fill=TEXT_GRAY, font=font_small)

        buffer = io.BytesIO()
        img.save(buffer, format="PNG", optimize=True)
        buffer.seek(0)
        return buffer.getvalue()

    def _draw_cell_text(self, draw: ImageDraw.ImageDraw, x: int, y: int,
                        text: str, font, max_width: int):
        """Draw word-wrapped text in a cell."""
        words = text.split()
        lines = []
        current = []

        for word in words:
            test = " ".join(current + [word])
            bbox = draw.textbbox((0, 0), test, font=font)
            if bbox[2] - bbox[0] <= max_width:
                current.append(word)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))

        for i, line in enumerate(lines[:4]):
            draw.text((x, y + i * 22), line, fill=TEXT_WHITE, font=font)

    async def claim_square(self, session_id: UUID, square_index: int,
                            claimer_user_id: UUID, claimer_name: str) -> Dict[str, Any]:
        """Claim a bingo square. Returns updated game data + whether a row was completed."""
        session = await self.game_repo.get_session(session_id)
        if not session or session.status != "active":
            return {"error": "Game not active"}

        game_data = session.game_data or {}
        claimed = game_data.get("claimed", {})
        key = str(square_index)

        # Check if already claimed by this user
        existing = claimed.get(key, [])
        if any(c["user_id"] == str(claimer_user_id) for c in existing):
            return {"error": "Already claimed"}

        # Add claim
        existing.append({"user_id": str(claimer_user_id), "claimer_name": claimer_name})
        claimed[key] = existing
        game_data["claimed"] = claimed

        # Check for completed rows
        new_completions = self._check_completions(claimed, game_data.get("completed_rows", []))
        game_data["completed_rows"] = game_data.get("completed_rows", []) + new_completions

        # Save
        await self.game_repo.update_session(session_id, game_data=game_data)

        return {
            "claimed": True,
            "new_completions": new_completions,
            "game_data": game_data,
        }

    def _check_completions(self, claimed: dict, already_completed: list) -> List[str]:
        """Check if any new rows/cols/diags are complete."""
        completions = []

        # Row check
        for row in range(3):
            indices = [str(row * 3 + col) for col in range(3)]
            name = f"row_{row}"
            if name not in already_completed and all(
                indices[i] in claimed and len(claimed[indices[i]]) > 0 for i in range(3)
            ):
                completions.append(name)

        # Column check
        for col in range(3):
            indices = [str(row * 3 + col) for row in range(3)]
            name = f"col_{col}"
            if name not in already_completed and all(
                indices[i] in claimed and len(claimed[indices[i]]) > 0 for i in range(3)
            ):
                completions.append(name)

        # Diagonal check
        diag1 = ["0", "4", "8"]
        if "diag_1" not in already_completed and all(
            d in claimed and len(claimed[d]) > 0 for d in diag1
        ):
            completions.append("diag_1")

        diag2 = ["2", "4", "6"]
        if "diag_2" not in already_completed and all(
            d in claimed and len(claimed[d]) > 0 for d in diag2
        ):
            completions.append("diag_2")

        return completions
