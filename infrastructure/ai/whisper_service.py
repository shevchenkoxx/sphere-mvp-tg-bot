"""
OpenAI Whisper service for voice transcription.
"""

import os
import tempfile
import aiohttp
import aiofiles
from openai import OpenAI
from core.interfaces.ai import IVoiceService
from config.settings import settings


class WhisperVoiceService(IVoiceService):
    """OpenAI Whisper-based voice transcription service"""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)

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

    async def transcribe(self, audio_file_path: str, language: str = "ru") -> str:
        """Transcribe audio file to text"""
        try:
            with open(audio_file_path, "rb") as audio_file:
                transcript = self.client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=language
                )
            return transcript.text
        except Exception as e:
            print(f"Transcription error: {e}")
            return None
        finally:
            # Clean up temp file
            if os.path.exists(audio_file_path):
                try:
                    os.remove(audio_file_path)
                except OSError:
                    pass

    async def download_and_transcribe(self, file_url: str, language: str = "ru") -> str:
        """Download audio from URL and transcribe"""
        file_path = await self.download_file(file_url)
        if file_path:
            return await self.transcribe(file_path, language)
        return None
