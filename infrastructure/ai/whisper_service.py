"""
OpenAI Whisper service for voice transcription.
"""

import os
import tempfile
import asyncio
import aiohttp
import aiofiles
import logging
from openai import OpenAI
from core.interfaces.ai import IVoiceService
from config.settings import settings

logger = logging.getLogger(__name__)


class WhisperVoiceService(IVoiceService):
    """OpenAI Whisper-based voice transcription service"""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key, timeout=60.0)

    async def download_file(self, file_url: str) -> str:
        """Download file from URL to temp location"""
        async with aiohttp.ClientSession() as session:
            async with session.get(file_url) as response:
                if response.status == 200:
                    # Create temp file
                    fd, path = tempfile.mkstemp(suffix='.ogg')
                    async with aiofiles.open(path, 'wb') as f:
                        await f.write(await response.read())
                    os.close(fd)
                    return path
        return None

    async def transcribe(self, audio_file_path: str, language: str = None, prompt: str = None) -> str:
        """Transcribe audio file to text. Language=None for auto-detection."""
        try:
            # Run sync OpenAI call in executor to not block event loop
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._transcribe_sync,
                audio_file_path,
                language,
                prompt
            )
        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None
        finally:
            # Clean up temp file
            if os.path.exists(audio_file_path):
                try:
                    os.remove(audio_file_path)
                except OSError:
                    pass

    def _transcribe_sync(self, audio_file_path: str, language: str = None, prompt: str = None) -> str:
        """Synchronous transcription - runs in executor"""
        with open(audio_file_path, "rb") as audio_file:
            params = {
                "model": "whisper-1",
                "file": audio_file,
            }
            if language:
                params["language"] = language
            if prompt:
                params["prompt"] = prompt

            transcript = self.client.audio.transcriptions.create(**params)
            return transcript.text

    async def download_and_transcribe(self, file_url: str, language: str = None, prompt: str = None) -> str:
        """Download audio from URL and transcribe. Language=None for auto-detect."""
        file_path = await self.download_file(file_url)
        if file_path:
            return await self.transcribe(file_path, language, prompt)
        return None
