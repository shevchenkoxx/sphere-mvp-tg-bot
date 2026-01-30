#!/usr/bin/env python3
"""
Prompt Test Runner - Test AI prompts and save results.
"""

import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from openai import AsyncOpenAI
from config.settings import settings
from core.prompts.audio_onboarding import AUDIO_EXTRACTION_PROMPT
from core.prompts.templates import (
    ONBOARDING_SYSTEM_PROMPT,
    PROFILE_EXTRACTION_PROMPT,
    MATCH_ANALYSIS_PROMPT,
)

# Test directory paths
TESTS_DIR = Path(__file__).parent
TEST_CASES_DIR = TESTS_DIR / "test_cases"
RESULTS_DIR = TESTS_DIR / "results"


class PromptTester:
    """Test prompts and save results"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"

    async def test_audio_extraction(
        self,
        transcription: str,
        event_name: str = "Test Event",
        language: str = "ru"
    ) -> Dict[str, Any]:
        """Test audio extraction prompt"""

        prompt = AUDIO_EXTRACTION_PROMPT.format(
            transcription=transcription,
            event_name=event_name,
            language=language
        )

        start_time = time.time()

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.1
        )

        elapsed = time.time() - start_time
        raw_response = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        # Parse JSON
        try:
            import re
            text = re.sub(r'```json\s*', '', raw_response)
            text = re.sub(r'```\s*', '', text)
            output = json.loads(text.strip())
        except:
            output = {"error": "Failed to parse JSON", "raw": raw_response}

        return {
            "prompt_type": "audio_extraction",
            "input": {
                "transcription": transcription,
                "event_name": event_name,
                "language": language
            },
            "output": output,
            "raw_response": raw_response,
            "metadata": {
                "model": self.model,
                "tokens": tokens,
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now().isoformat()
            }
        }

    async def test_profile_extraction(
        self,
        conversation_history: str
    ) -> Dict[str, Any]:
        """Test profile extraction from conversation"""

        prompt = PROFILE_EXTRACTION_PROMPT.format(
            conversation_history=conversation_history
        )

        start_time = time.time()

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.1
        )

        elapsed = time.time() - start_time
        raw_response = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        try:
            import re
            text = re.sub(r'```json\s*', '', raw_response)
            text = re.sub(r'```\s*', '', text)
            output = json.loads(text.strip())
        except:
            output = {"error": "Failed to parse JSON", "raw": raw_response}

        return {
            "prompt_type": "profile_extraction",
            "input": {"conversation_history": conversation_history},
            "output": output,
            "raw_response": raw_response,
            "metadata": {
                "model": self.model,
                "tokens": tokens,
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now().isoformat()
            }
        }

    async def test_onboarding_conversation(
        self,
        user_message: str,
        event_name: str = "Test Event",
        history: list = None
    ) -> Dict[str, Any]:
        """Test conversational onboarding response"""

        system_prompt = ONBOARDING_SYSTEM_PROMPT.format(event_name=event_name)

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user_message})

        start_time = time.time()

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=500,
            temperature=0.7
        )

        elapsed = time.time() - start_time
        raw_response = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        return {
            "prompt_type": "onboarding_conversation",
            "input": {
                "user_message": user_message,
                "event_name": event_name,
                "history_length": len(history) if history else 0
            },
            "output": {
                "response": raw_response,
                "is_complete": "PROFILE_COMPLETE" in raw_response
            },
            "raw_response": raw_response,
            "metadata": {
                "model": self.model,
                "tokens": tokens,
                "elapsed_seconds": round(elapsed, 2),
                "timestamp": datetime.now().isoformat()
            }
        }


def save_result(result: Dict[str, Any], name: str = None):
    """Save test result to file"""
    # Create results directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result_dir = RESULTS_DIR / timestamp

    if name:
        result_dir = result_dir / name

    result_dir.mkdir(parents=True, exist_ok=True)

    # Save files
    with open(result_dir / "result.json", "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    with open(result_dir / "output.json", "w", encoding="utf-8") as f:
        json.dump(result.get("output", {}), f, ensure_ascii=False, indent=2)

    with open(result_dir / "raw_response.txt", "w", encoding="utf-8") as f:
        f.write(result.get("raw_response", ""))

    print(f"✓ Results saved to: {result_dir}")
    return result_dir


async def run_sample_tests():
    """Run sample tests with predefined inputs"""
    tester = PromptTester()

    print("\n=== Audio Extraction Test (Russian) ===\n")

    sample_ru = """
    Привет! Меня зовут Александр, я продакт-менеджер в финтех стартапе.
    Занимаюсь разработкой мобильных приложений уже 5 лет. Увлекаюсь
    технологиями, особенно AI и блокчейном. На этом ивенте хочу
    познакомиться с разработчиками и возможно найти кофаундера для
    своего side-проекта. Могу помочь с продуктовой стратегией,
    монетизацией и выходом на рынок. Мой линкедин - linkedin.com/in/alex
    """

    result = await tester.test_audio_extraction(sample_ru, "Tech Meetup Moscow")
    save_result(result, "audio_extraction_ru")
    print(f"Extracted: {json.dumps(result['output'], ensure_ascii=False, indent=2)}")

    print("\n=== Audio Extraction Test (English) ===\n")

    sample_en = """
    Hey! I'm Sarah, a UX designer working at a health tech startup.
    I've been in design for about 7 years now, mainly focused on
    mobile apps and user research. I'm really passionate about
    accessible design and making technology work for everyone.
    I'm here looking to connect with founders and product people,
    maybe find some interesting projects to collaborate on.
    I can help with design systems, user research, and prototyping.
    """

    result = await tester.test_audio_extraction(sample_en, "Design Week SF", "en")
    save_result(result, "audio_extraction_en")
    print(f"Extracted: {json.dumps(result['output'], ensure_ascii=False, indent=2)}")

    print("\n=== Conversation Test ===\n")

    result = await tester.test_onboarding_conversation(
        "Привет! Я Дима, занимаюсь маркетингом в IT",
        "Startup Grind"
    )
    save_result(result, "conversation_test")
    print(f"Response: {result['output']['response'][:200]}...")

    print("\n✅ All tests completed!")


async def test_from_file(file_path: str):
    """Run test from a file"""
    tester = PromptTester()
    path = Path(file_path)

    if not path.exists():
        print(f"Error: File not found: {file_path}")
        return

    content = path.read_text(encoding="utf-8")
    name = path.stem

    if path.suffix == ".json":
        data = json.loads(content)
        if "messages" in data:
            # Conversation test
            result = await tester.test_profile_extraction(
                json.dumps(data["messages"], ensure_ascii=False)
            )
        else:
            print("Unknown JSON format")
            return
    else:
        # Assume audio transcription
        result = await tester.test_audio_extraction(content)

    save_result(result, name)
    print(f"\nOutput: {json.dumps(result['output'], ensure_ascii=False, indent=2)}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Test AI prompts")
    parser.add_argument("--input", "-i", help="Input file to test")
    parser.add_argument("--prompt", "-p", help="Prompt type to test")
    parser.add_argument("--samples", "-s", action="store_true", help="Run sample tests")

    args = parser.parse_args()

    # Ensure directories exist
    TEST_CASES_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if args.input:
        asyncio.run(test_from_file(args.input))
    else:
        asyncio.run(run_sample_tests())


if __name__ == "__main__":
    main()
