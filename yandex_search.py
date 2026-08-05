import base64
import logging
import re
import xml.etree.ElementTree as ET
import httpx
from typing import List, Tuple
from config import settings

logger = logging.getLogger(__name__)

try:
    from yandex_ai_studio_sdk import AIStudio
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

URL_REGEX = r'https?://[^\s\'"<>]+'

class YandexImageSearchClient:
    """
    Клиент для Yandex Search API (Поиск по изображениям / Поиск по картинке).
    Использует официальный yandex-ai-studio-sdk.
    """
    def __init__(self, api_key: str = None, folder_id: str = None):
        self.api_key = api_key or settings.yandex_api_key
        self.folder_id = folder_id or settings.yandex_folder_id

    async def search_by_image_bytes(self, image_bytes: bytes, max_pages: int = 2) -> Tuple[List[str], str]:
        """
        Ищет страницы в Интернете по бинарным данным картинки.
        Запрашивает max_pages страниц ответа Yandex Search API для глубокого анализа.
        """
        if not self.api_key or not self.folder_id:
            return [], "YANDEX_API_KEY или YANDEX_FOLDER_ID не указаны в настройках."

        if not HAS_SDK:
            return [], "Модуль yandex-ai-studio-sdk не установлен."

        try:
            sdk = AIStudio(
                folder_id=self.folder_id,
                auth=self.api_key,
            )

            search = sdk.search_api.by_image(
                family_mode="FAMILY_MODE_MODERATE",
            )

            all_urls = set()
            for p in range(max_pages):
                try:
                    search_result = search.run(image_bytes, page=p)
                    page_urls = self._extract_urls_from_sdk_result(search_result)
                    all_urls.update(page_urls)
                except Exception as page_err:
                    logger.warning(f"Ошибка при получении страницы {p}: {page_err}")
                    if p == 0:
                        raise page_err

            logger.info(f"Yandex SDK извлек всего {len(all_urls)} уникальных источников")
            return list(all_urls), ""

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Ошибка Yandex Search API: {err_msg}")
            if "PERMISSION_DENIED" in err_msg or "Permission denied" in err_msg:
                return [], " Ошибка Yandex API: PERMISSION_DENIED. В Yandex Cloud не привязан платежный аккаунт или сервисному аккаунту не назначена роль `search-api.user`."
            elif "UNAUTHENTICATED" in err_msg:
                return [], " Ошибка Yandex API: UNAUTHENTICATED. Проверьте правильность YANDEX_API_KEY."
            else:
                return [], f" Ошибка Yandex Search API: {err_msg}"

    async def search_by_image_url(self, image_url: str, max_pages: int = 2) -> Tuple[List[str], str]:
        """
        Ищет страницы в Интернете по ссылке на картинку.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(image_url)
                if resp.status_code != 200:
                    return [], f"Не удалось скачать картинку по ссылке (HTTP статус {resp.status_code})."
                image_bytes = resp.content

            return await self.search_by_image_bytes(image_bytes, max_pages=max_pages)
        except Exception as e:
            logger.error(f"Ошибка при скачивании ссылки: {e}")
            return [], f"Ошибка при загрузке картинки по ссылке: {e}"

    def _extract_urls_from_sdk_result(self, search_result) -> List[str]:
        urls = set()

        try:
            for item in search_result:
                for attr in ("page_url", "url", "link", "site_url"):
                    val = getattr(item, attr, None)
                    if val and isinstance(val, str) and val.startswith("http"):
                        if not val.lower().endswith((".jpg", ".png", ".webp", ".jpeg", ".gif")):
                            urls.add(val)
        except Exception as e:
            logger.warning(f"Предупреждение итерации SDK: {e}")

        if not urls:
            try:
                raw_str = str(search_result)
                found = re.findall(URL_REGEX, raw_str)
                for u in found:
                    if not u.lower().endswith((".jpg", ".png", ".webp", ".jpeg", ".gif")):
                        urls.add(u)
            except Exception:
                pass

        return list(urls)
