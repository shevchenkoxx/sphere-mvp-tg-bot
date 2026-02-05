"""
Event Parser Service - Extract event info from URLs using LLM.
Supports: Luma, Eventbrite, custom websites.
"""

import json
import re
import logging
import httpx
from typing import Optional, Dict, Any
from openai import AsyncOpenAI
from config.settings import settings

logger = logging.getLogger(__name__)


EVENT_EXTRACTION_PROMPT = """Extract structured event information from this webpage content.

WEBPAGE CONTENT:
{content}

Extract ALL available information and return valid JSON:
{{
  "full_description": "Complete event description in original language",
  "schedule": [
    {{"time": "HH:MM", "title": "Session title", "speaker": "Speaker name or null", "description": "Brief description or null"}}
  ],
  "speakers": [
    {{"name": "Full name", "bio": "Short bio", "social": "@handle or URL or null", "topics": ["topic1", "topic2"]}}
  ],
  "topics": ["Main topic 1", "Topic 2"],
  "organizer": {{
    "name": "Organizer name",
    "social": "@handle or null",
    "website": "URL or null",
    "telegram": "@channel or null"
  }},
  "venue_details": "Specific venue info like floor, room, etc. or null",
  "event_date": "YYYY-MM-DD or null",
  "event_time": "HH:MM or null",
  "ticket_info": "Free / Paid / Price or null"
}}

RULES:
1. Extract ONLY what's explicitly stated, don't invent data
2. Keep original language for descriptions
3. If info not found, use null
4. Schedule should be chronological
5. Return valid JSON only, no markdown
"""


class EventParserService:
    """Service to extract event info from URLs using LLM"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"

    async def fetch_url_content(self, url: str) -> Optional[str]:
        """Fetch webpage content and convert to text"""
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                headers = {
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
                }
                response = await client.get(url, headers=headers)
                response.raise_for_status()

                html = response.text

                # Simple HTML to text conversion
                # Remove script and style tags
                html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
                html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)

                # Remove HTML tags but keep content
                text = re.sub(r'<[^>]+>', ' ', html)

                # Clean up whitespace
                text = re.sub(r'\s+', ' ', text)
                text = text.strip()

                # Truncate if too long (GPT context limit)
                if len(text) > 15000:
                    text = text[:15000] + "..."

                return text

        except Exception as e:
            logger.error(f"Failed to fetch URL {url}: {e}")
            return None

    async def parse_event_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract event info from URL using LLM.
        Returns structured event_info dict or None on failure.
        """
        # Fetch content
        content = await self.fetch_url_content(url)
        if not content:
            return None

        # Extract with LLM
        try:
            prompt = EVENT_EXTRACTION_PROMPT.format(content=content)

            response = await self.client.chat.completions.create(
                model=self.model,
                max_tokens=2000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)

            # Parse JSON
            event_info = json.loads(text)

            # Add metadata
            event_info["source_url"] = url
            event_info["imported_at"] = __import__('datetime').datetime.utcnow().isoformat() + "Z"

            logger.info(f"Successfully parsed event from {url}")
            return event_info

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON: {e}")
            return None
        except Exception as e:
            logger.error(f"Event parsing failed: {e}")
            return None

    def format_event_card(self, event_info: Dict[str, Any], event_name: str, lang: str = "en") -> str:
        """Format event_info as a nice Telegram message"""
        lines = [f"<b>📅 {event_name}</b>\n"]

        # Description
        desc = event_info.get("full_description")
        if desc:
            # Truncate long descriptions
            if len(desc) > 300:
                desc = desc[:300] + "..."
            lines.append(f"{desc}\n")

        # Date & Time
        date = event_info.get("event_date")
        time = event_info.get("event_time")
        if date or time:
            dt_line = "🗓 "
            if date:
                dt_line += date
            if time:
                dt_line += f" at {time}"
            lines.append(dt_line)

        # Topics
        topics = event_info.get("topics", [])
        if topics:
            topic_tags = " ".join([f"#{t.replace(' ', '_')}" for t in topics[:5]])
            lines.append(f"\n{topic_tags}")

        # Schedule preview
        schedule = event_info.get("schedule", [])
        if schedule:
            lines.append("\n<b>📋 Schedule:</b>")
            for item in schedule[:5]:  # Show first 5
                time_str = item.get("time", "")
                title = item.get("title", "")
                speaker = item.get("speaker")
                line = f"• {time_str} {title}"
                if speaker:
                    line += f" — {speaker}"
                lines.append(line)
            if len(schedule) > 5:
                lines.append(f"... and {len(schedule) - 5} more sessions")

        # Speakers preview
        speakers = event_info.get("speakers", [])
        if speakers:
            lines.append("\n<b>🎤 Speakers:</b>")
            for s in speakers[:4]:
                name = s.get("name", "")
                bio = s.get("bio", "")
                if bio and len(bio) > 50:
                    bio = bio[:50] + "..."
                lines.append(f"• <b>{name}</b> — {bio}" if bio else f"• <b>{name}</b>")
            if len(speakers) > 4:
                lines.append(f"... and {len(speakers) - 4} more")

        # Organizer
        org = event_info.get("organizer", {})
        if org.get("name"):
            org_line = f"\n👤 Organized by: {org['name']}"
            if org.get("telegram"):
                org_line += f" {org['telegram']}"
            lines.append(org_line)

        # Venue
        venue = event_info.get("venue_details")
        if venue:
            lines.append(f"📍 {venue}")

        # Source
        source = event_info.get("source_url")
        if source:
            lines.append(f"\n🔗 <a href='{source}'>Event page</a>")

        return "\n".join(lines)
