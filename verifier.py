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
    с использованием локальной базы доменов и API ChatGPT (OpenAI Vision).
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
        Возвращает словарь {url: название_фотобанка} ТОЛЬКО для точных совпадений фотобанков.
        """
        if not urls:
            return {}

        # 1. Быстрая проверка по локальной базе доменов фотобанков
        detected_photobanks = find_photobanks_in_urls(urls)
        logger.info(f"Локально найдено кандидатов фотобанков: {len(detected_photobanks)}")

        # 2. Проверка нераспознанных URL через текстовый ChatGPT API
        unrecognized_urls = [u for u in urls if u not in detected_photobanks]
        if unrecognized_urls and self.openai_client:
            gpt_text_results = await self._verify_urls_with_chatgpt(unrecognized_urls[:20])
            detected_photobanks.update(gpt_text_results)

        if not detected_photobanks:
            return {}

        # 3. Дополнительная проверка на ТОЧНОЕ СОВПАДЕНИЕ через ChatGPT Vision API (если есть оригинал)
        if self.openai_client and (original_image_bytes or original_image_url):
            exact_photobanks = await self._filter_exact_matches_with_vision(
                detected_photobanks, original_image_bytes, original_image_url
            )
            return exact_photobanks

        return detected_photobanks

    async def _filter_exact_matches_with_vision(
        self,
        candidates: Dict[str, str],
        image_bytes: Optional[bytes],
        image_url: Optional[str]
    ) -> Dict[str, str]:
        """
        Фильтрует найденные ссылки фотобанков через Vision API,
        отсеивая просто «похожие» картинки и оставляя ТОЛЬКО точные копии (дубликаты).
        """
        exact_results = {}
        
        # Подготавливаем оригинальное изображение для OpenAI Vision
        image_content = None
        if image_url:
            image_content = {"type": "image_url", "image_url": {"url": image_url}}
        elif image_bytes:
            b64_img = base64.b64encode(image_bytes).decode("utf-8")
            image_content = {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}

        if not image_content:
            return candidates

        for pb_url, pb_name in candidates.items():
            prompt = (
                f"Сравни оригинальное изображение с тем, что находится по ссылке фотобанка {pb_name} ({pb_url}).\n"
                "Требуется определить: является ли данное изображение на фотобанке ТОЧНО ТАКИМ ЖЕ ФОТО (точным дубликатом оригинала), "
                "или это просто похожий объект/похожая композиция стока?\n"
                "Ответь строго в формате JSON:\n"
                "{\"is_exact_match\": true} или {\"is_exact_match\": false}"
            )

            try:
                response = await self.openai_client.chat.completions.create(
                    model=settings.openai_model,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                image_content
                            ]
                        }
                    ],
                    temperature=0.0,
                    response_format={"type": "json_object"}
                )

                content = response.choices[0].message.content
                if content:
                    parsed = json.loads(content)
                    if parsed.get("is_exact_match") is True:
                        exact_results[pb_url] = pb_name
                    else:
                        logger.info(f"ChatGPT Vision отсеял ссылку {pb_url} (не точное совпадение)")
                else:
                    # По умолчанию оставляем, если не удалось спарсить
                    exact_results[pb_url] = pb_name

            except Exception as e:
                logger.error(f"Ошибка при проверке Vision exact match для {pb_url}: {e}")
                exact_results[pb_url] = pb_name

        return exact_results

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
            "Если URL не является фотобанком, НЕ включай его в JSON."
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
