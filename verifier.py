import base64
import json
import logging
from typing import Dict, List, Optional
from openai import AsyncOpenAI
from config import settings
from photobanks import find_photobanks_in_urls, check_photobank_domain

logger = logging.getLogger(__name__)

class ImageVerifier:
    """
    Класс для проверки списка URL-адресов на наличие фотобанков
    с использованием локальной базы доменов и API ChatGPT (OpenAI).
    """
    def __init__(self):
        self.openai_client = None
        if settings.openai_api_key:
            try:
                self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
            except Exception as e:
                logger.error(f" Ошибка инициализации OpenAI клиента: {e}")

    async def verify_urls(
        self,
        urls: List[str],
        original_image_bytes: Optional[bytes] = None,
        original_image_url: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Проверяет список URL-адресов.
        Возвращает словарь {url: название_фотобанка} для всех обнаруженных фотобанков.
        """
        if not urls:
            return {}

        # 1. Точная и быстрая проверка по нашей базе доменов фотобанков
        detected_photobanks = find_photobanks_in_urls(urls)
        logger.info(f"Локально найдено фотобанков в результатах Яндекса: {len(detected_photobanks)}")

        # 2. Проверка остального списка URL через ChatGPT API для выявления скрытых стоков
        unrecognized_urls = [u for u in urls if u not in detected_photobanks]
        if unrecognized_urls and self.openai_client:
            gpt_text_results = await self._verify_urls_with_chatgpt(unrecognized_urls[:30])
            detected_photobanks.update(gpt_text_results)

        return detected_photobanks

    async def _verify_urls_with_chatgpt(self, urls: List[str]) -> Dict[str, str]:
        """
        Проверяет ссылки на принадлежность к фотобанкам/стокам через текстовый ChatGPT API.
        """
        if not self.openai_client or not urls:
            return {}

        system_prompt = (
            "Ты — эксперт по коммерческим фотобанкам и стоковой фотографии. "
            "Тебе дан список URL-адресов. Определи, является ли хотя бы один из них фотобанком, "
            "микростоком, коммерческим фотоархивом, галереей продажи лицензий на фото или стоковым сайтом.\n"
            "Верни ответ STRICTLY в формате JSON словаря, где ключ — URL из списка, а значение — название фотобанка/стока.\n"
            "Если URL не является фотобанком, НЕ включай его в JSON.\n"
            "Пример ответа: {\"https://example-stock.com/photo/123\": \"Example Stock\"}"
        )

        user_prompt = f"Проверь следующие ссылки на наличие фотобанков:\n" + "\n".join(urls)

        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,
                response_format={"type": "json_object"}
            )

            content = response.choices[0].message.content
            if not content:
                return {}

            parsed = json.loads(content)
            result = {}
            if isinstance(parsed, dict):
                for url, name in parsed.items():
                    if url in urls and name:
                        result[url] = str(name)
            return result

        except Exception as e:
            logger.error(f" Ошибка при запросе к OpenAI ChatGPT API: {e}")
            return {}
