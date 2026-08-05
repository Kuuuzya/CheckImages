import logging
import httpx
from typing import List, Tuple
from config import settings

logger = logging.getLogger(__name__)

class GoogleImageSearchClient:
    """
    Клиент для обратного поиска по изображениям через Google (Google Lens / SerpAPI / Google Cloud Vision).
    """
    def __init__(self, serpapi_key: str = None, google_api_key: str = None):
        self.serpapi_key = serpapi_key or settings.serpapi_key
        self.google_api_key = google_api_key or settings.google_api_key

    async def search_by_image_url(self, image_url: str) -> Tuple[List[str], str]:
        """
        Выполняет обратный поиск по ссылке на картинку через Google Lens / SerpAPI или Google Cloud Vision.
        """
        urls = set()
        err_msg = ""

        # 1. Попытка поиска через SerpAPI (Google Lens API - Exact Matches)
        if self.serpapi_key:
            try:
                serp_urls = await self._search_via_serpapi(image_url)
                urls.update(serp_urls)
            except Exception as e:
                logger.error(f"Ошибка при поиске через SerpAPI Google Lens: {e}")

        # 2. Попытка поиска через Google Cloud Vision API (WEB_DETECTION)
        if not urls and self.google_api_key:
            try:
                vision_urls = await self._search_via_google_vision(image_url)
                urls.update(vision_urls)
            except Exception as e:
                logger.error(f"Ошибка при поиске через Google Cloud Vision: {e}")

        if not self.serpapi_key and not self.google_api_key:
            err_msg = "Google API ключи (SERPAPI_KEY или GOOGLE_API_KEY) не указаны в .env файле."

        return list(urls), err_msg

    async def _search_via_serpapi(self, image_url: str) -> List[str]:
        """
        Обратный поиск через SerpAPI Google Lens Engine.
        Документация: https://serpapi.com/google-lens-api
        """
        params = {
            "engine": "google_lens",
            "url": image_url,
            "api_key": self.serpapi_key,
            "hl": "ru",
            "country": "ru"
        }

        urls = set()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get("https://serpapi.com/search.json", params=params)
            if response.status_code == 200:
                data = response.json()

                # Извлекаем Точные Совпадения (exact_matches)
                exact_matches = data.get("exact_matches", [])
                for match in exact_matches:
                    link = match.get("link") or match.get("source")
                    if link and isinstance(link, str) and link.startswith("http"):
                        urls.add(link)

                # Извлекаем Визуальные Совпадения (visual_matches)
                visual_matches = data.get("visual_matches", [])
                for match in visual_matches:
                    link = match.get("link") or match.get("source")
                    if link and isinstance(link, str) and link.startswith("http"):
                        urls.add(link)
            else:
                logger.warning(f"SerpAPI статус {response.status_code}: {response.text}")

        return list(urls)

    async def _search_via_google_vision(self, image_url: str) -> List[str]:
        """
        Обратный поиск через Google Cloud Vision REST API (WEB_DETECTION).
        """
        endpoint = f"https://vision.googleapis.com/v1/images:annotate?key={self.google_api_key}"
        payload = {
            "requests": [
                {
                    "image": {"source": {"imageUri": image_url}},
                    "features": [{"type": "WEB_DETECTION", "maxResults": 50}]
                }
            ]
        }

        urls = set()
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(endpoint, json=payload)
            if response.status_code == 200:
                data = response.json()
                responses = data.get("responses", [])
                if responses:
                    web_detection = responses[0].get("webDetection", {})
                    
                    # Полные точные совпадения (full_matching_images)
                    for item in web_detection.get("fullMatchingImages", []):
                        url = item.get("url")
                        if url and url.startswith("http"):
                            urls.add(url)
                            
                    # Страницы с совпадающим изображением (pages_with_matching_images)
                    for item in web_detection.get("pagesWithMatchingImages", []):
                        url = item.get("url")
                        if url and url.startswith("http"):
                            urls.add(url)
            else:
                logger.warning(f"Google Vision API статус {response.status_code}: {response.text}")

        return list(urls)
