#!/usr/bin/env python3
"""
Test script for audio transcription extraction.
Runs the AUDIO_EXTRACTION_PROMPT against a transcription and shows results.

Usage:
    python scripts/test_extraction.py --text "Hi, I'm John, a product manager at Google..."
    python scripts/test_extraction.py --file transcription.txt
    python scripts/test_extraction.py --file transcription.txt --event "Tech Startup Meetup"
"""

import argparse
import asyncio
import json
import re
import sys
import os

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from openai import AsyncOpenAI
from config.settings import settings
from core.prompts.audio_onboarding import AUDIO_EXTRACTION_PROMPT


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Test audio transcription extraction prompt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/test_extraction.py --text "Hi, I'm Sarah, a UX designer looking for startup founders"
    python scripts/test_extraction.py --file my_transcription.txt --event "AI Summit 2024"
    python scripts/test_extraction.py --text "..." --language ru
        """
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--text", "-t",
        type=str,
        help="Transcription text to process"
    )
    input_group.add_argument(
        "--file", "-f",
        type=str,
        help="Path to file containing transcription text"
    )

    parser.add_argument(
        "--event", "-e",
        type=str,
        default="Networking Event",
        help="Event context/name (default: 'Networking Event')"
    )

    parser.add_argument(
        "--language", "-l",
        type=str,
        default="en",
        help="User's UI language preference (default: 'en')"
    )

    parser.add_argument(
        "--model", "-m",
        type=str,
        default="gpt-4o-mini",
        help="OpenAI model to use (default: 'gpt-4o-mini')"
    )

    parser.add_argument(
        "--raw", "-r",
        action="store_true",
        help="Show raw response without formatting"
    )

    return parser.parse_args()


def extract_json_from_response(response: str) -> dict:
    """Extract JSON object from the response text."""
    # Look for JSON section marked with ## JSON: header
    json_match = re.search(r'##\s*JSON:?\s*\n*```json\s*(.*?)```', response, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding JSON without markdown code block
    json_match = re.search(r'##\s*JSON:?\s*\n*(\{.*\})', response, re.DOTALL | re.IGNORECASE)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try finding any JSON object in the response
    json_match = re.search(r'```json\s*(.*?)```', response, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Last resort: find first { to last }
    start = response.find('{')
    end = response.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(response[start:end+1])
        except json.JSONDecodeError:
            pass

    return None


def extract_chain_of_thought(response: str) -> str:
    """Extract chain-of-thought steps from response (before JSON)."""
    # Find where JSON section starts
    json_markers = ['## JSON:', '## STEP 4 - JSON OUTPUT', '```json']

    cot_end = len(response)
    for marker in json_markers:
        idx = response.lower().find(marker.lower())
        if idx != -1 and idx < cot_end:
            cot_end = idx

    return response[:cot_end].strip()


def format_json_output(data: dict) -> str:
    """Format extracted JSON for display."""
    if not data:
        return "  (No JSON extracted)"

    # Key fields to highlight
    key_fields = [
        'display_name', 'language', 'about', 'looking_for', 'can_help_with',
        'interests', 'goals', 'profession', 'company', 'industry',
        'experience_level', 'skills', 'expertise_areas', 'personality_traits',
        'communication_style', 'location', 'raw_highlights', 'unique_value',
        'confidence_score', 'extraction_notes'
    ]

    output_lines = []
    for field in key_fields:
        if field in data and data[field]:
            value = data[field]
            if isinstance(value, list):
                value = ', '.join(str(v) for v in value) if value else '(empty)'
            elif isinstance(value, float):
                value = f"{value:.2f}"
            output_lines.append(f"  {field}: {value}")

    # Add any extra fields not in key_fields
    for field, value in data.items():
        if field not in key_fields and value:
            if isinstance(value, list):
                value = ', '.join(str(v) for v in value)
            output_lines.append(f"  {field}: {value}")

    return '\n'.join(output_lines)


async def run_extraction(
    transcription: str,
    event_name: str,
    language: str,
    model: str
) -> str:
    """Run the extraction prompt and return the response."""

    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not set in environment or .env file")

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Format the prompt with variables
    prompt = AUDIO_EXTRACTION_PROMPT.format(
        transcription=transcription,
        event_name=event_name,
        language=language
    )

    print(f"Sending request to {model}...")
    print("-" * 60)

    response = await client.chat.completions.create(
        model=model,
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.choices[0].message.content


async def main():
    args = parse_args()

    # Get transcription text
    if args.text:
        transcription = args.text
    else:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                transcription = f.read().strip()
        except FileNotFoundError:
            print(f"Error: File not found: {args.file}")
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)

    if not transcription:
        print("Error: Empty transcription text")
        sys.exit(1)

    print("=" * 60)
    print("TRANSCRIPTION EXTRACTION TEST")
    print("=" * 60)
    print(f"\nInput transcription ({len(transcription)} chars):")
    print("-" * 40)
    # Show truncated transcription if too long
    if len(transcription) > 500:
        print(transcription[:500] + "...")
    else:
        print(transcription)
    print("-" * 40)
    print(f"\nEvent context: {args.event}")
    print(f"Language: {args.language}")
    print(f"Model: {args.model}")
    print()

    try:
        response = await run_extraction(
            transcription=transcription,
            event_name=args.event,
            language=args.language,
            model=args.model
        )

        if args.raw:
            print("\n" + "=" * 60)
            print("RAW RESPONSE")
            print("=" * 60)
            print(response)
        else:
            # Extract and display chain-of-thought
            cot = extract_chain_of_thought(response)
            if cot:
                print("\n" + "=" * 60)
                print("CHAIN OF THOUGHT")
                print("=" * 60)
                print(cot)

            # Extract and display JSON
            json_data = extract_json_from_response(response)

            print("\n" + "=" * 60)
            print("EXTRACTED JSON")
            print("=" * 60)

            if json_data:
                print("\nFormatted fields:")
                print(format_json_output(json_data))

                print("\n" + "-" * 40)
                print("Raw JSON:")
                print(json.dumps(json_data, indent=2, ensure_ascii=False))
            else:
                print("\nWarning: Could not parse JSON from response")
                print("\nFull response:")
                print(response)

        print("\n" + "=" * 60)
        print("DONE")
        print("=" * 60)

    except ValueError as e:
        print(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
