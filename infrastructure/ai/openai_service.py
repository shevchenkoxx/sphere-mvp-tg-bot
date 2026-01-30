"""
OpenAI GPT service implementation.
Handles user analysis and match compatibility using GPT-4.
"""

import json
import re
from typing import Dict, Any
from openai import OpenAI
from core.domain.models import MatchResult, MatchType
from core.interfaces.ai import IAIService
from config.settings import settings


class OpenAIService(IAIService):
    """OpenAI GPT-based AI service for user analysis and matching"""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o-mini"  # Fast and cheap, good for MVP

    async def generate_user_summary(self, user_data: Dict[str, Any]) -> str:
        """Generate AI summary of user profile"""

        prompt = f"""Проанализируй профиль пользователя и создай краткое, но информативное описание для системы матчинга.

Данные пользователя:
- Имя: {user_data.get('display_name', 'Не указано')}
- Родной город: {user_data.get('city_born', 'Не указано')}
- Текущий город: {user_data.get('city_current', 'Не указано')}
- Интересы: {', '.join(user_data.get('interests', []))}
- Цели: {', '.join(user_data.get('goals', []))}
- О себе: {user_data.get('bio', 'Не указано')}

Создай summary в 2-3 предложениях, выделяя:
1. Ключевые характеристики личности (на основе интересов)
2. Что человек ищет (на основе целей)
3. Потенциальные точки соприкосновения с другими

Пиши от третьего лица, тепло но информативно. Без эмодзи."""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content

    async def analyze_match(
        self,
        user_a: Dict[str, Any],
        user_b: Dict[str, Any],
        event_context: str = None
    ) -> MatchResult:
        """Analyze compatibility between two users"""

        prompt = f"""Проанализируй совместимость двух людей для потенциального знакомства.

=== ЧЕЛОВЕК А ===
Имя: {user_a.get('display_name', user_a.get('first_name', 'Аноним'))}
Город: {user_a.get('city_current', 'Не указан')}
Интересы: {', '.join(user_a.get('interests', []))}
Цели: {', '.join(user_a.get('goals', []))}
О себе: {user_a.get('bio', 'Не указано')}
AI-профиль: {user_a.get('ai_summary', 'Нет данных')}

=== ЧЕЛОВЕК Б ===
Имя: {user_b.get('display_name', user_b.get('first_name', 'Аноним'))}
Город: {user_b.get('city_current', 'Не указан')}
Интересы: {', '.join(user_b.get('interests', []))}
Цели: {', '.join(user_b.get('goals', []))}
О себе: {user_b.get('bio', 'Не указано')}
AI-профиль: {user_b.get('ai_summary', 'Нет данных')}

{f'Контекст: оба находятся на ивенте "{event_context}"' if event_context else ''}

Определи:
1. compatibility_score (0.0-1.0) — насколько они могут быть интересны друг другу
2. match_type — один из: "friendship" (дружба), "professional" (деловое), "romantic" (романтика), "creative" (творческое партнёрство)
3. explanation — почему они могут быть интересны друг другу (2-3 предложения, тепло и по-человечески, БЕЗ упоминания имён)
4. icebreaker — один хороший вопрос для начала разговора

ВАЖНО: Отвечай ТОЛЬКО валидным JSON без markdown-форматирования:
{{"compatibility_score": 0.75, "match_type": "friendship", "explanation": "...", "icebreaker": "..."}}"""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=800,
            messages=[{"role": "user", "content": prompt}]
        )

        # Parse JSON from response
        text = response.choices[0].message.content

        # Remove possible markdown blocks
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        text = text.strip()

        try:
            data = json.loads(text)
            return MatchResult(
                compatibility_score=data["compatibility_score"],
                match_type=MatchType(data["match_type"]),
                explanation=data["explanation"],
                icebreaker=data["icebreaker"]
            )
        except (json.JSONDecodeError, KeyError, ValueError):
            # Fallback on parse error
            return MatchResult(
                compatibility_score=0.5,
                match_type=MatchType.FRIENDSHIP,
                explanation="У вас есть общие интересы, которые могут стать основой для интересного общения.",
                icebreaker="Что привело тебя на это мероприятие?"
            )

    async def generate_icebreaker(
        self,
        user_a: Dict[str, Any],
        user_b: Dict[str, Any],
        match_type: str
    ) -> str:
        """Generate conversation starter"""

        prompt = f"""Сгенерируй один интересный вопрос для начала разговора между двумя людьми.

Человек А интересуется: {', '.join(user_a.get('interests', []))}
Человек Б интересуется: {', '.join(user_b.get('interests', []))}
Тип знакомства: {match_type}

Вопрос должен быть:
- Открытым (не да/нет)
- Связанным с общими интересами
- Легким и дружелюбным
- Без клише типа "расскажи о себе"

Отвечай ТОЛЬКО вопросом, без преамбулы."""

        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )

        return response.choices[0].message.content.strip()
