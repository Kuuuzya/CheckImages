import base64
import logging
import xml.etree.ElementTree as ET
import httpx
from typing import List, Tuple
from config import settings

logger = logging.getLogger(__name__)

# Импортируем официальный Yandex AI Studio SDK
try:
    from yandex_ai_studio_sdk import AIStudio
    from yandex_ai_studio_sdk._exceptions import AioRpcError
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

class YandexImageSearchClient:
    """
    Клиент для Yandex Search API (Поиск по изображениям / Поиск по картинке).
    Использует официальный yandex-ai-studio-sdk.
    """
    def __init__(self, api_key: str = None, folder_id: str = None):
        self.api_key = api_key or settings.yandex_api_key
        self.folder_id = folder_id or settings.yandex_folder_id

    async def search_by_image_bytes(self, image_bytes: bytes) -> Tuple[List[str], str]:
        """
        Ищет страницы в Интернете по бинарным данным картинки.
        Возвращает кортеж: (список_найденных_URL, сообщение_об_ошибке_если_есть)
        """
        if not self.api_key or not self.folder_id:
            return [], "YANDEX_API_KEY или YANDEX_FOLDER_ID не указаны в настройках."

        if not HAS_SDK:
            return [], "Модуль yandex-ai-studio-sdk не установлен."

        try:
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")
            sdk = AIStudio(
                folder_id=self.folder_id,
                auth=self.api_key,
            )

            search = sdk.search_api.by_image(
                family_mode="FAMILY_MODE_MODERATE",
            )

            # В yandex-ai-studio-sdk run принимаются сырые байты изображения
            search_result = search.run(image_bytes, page=0)

            if hasattr(search_result, "model_dump"):
                result_data = search_result.model_dump()
            elif hasattr(search_result, "to_dict"):
                result_data = search_result.to_dict()
            elif isinstance(search_result, dict):
                result_data = search_result
            else:
                result_data = str(search_result)

            urls = self._extract_urls_from_dict_or_obj(result_data)
            return urls, ""

        except Exception as e:
            err_msg = str(e)
            logger.error(f"Ошибка Yandex Search API: {err_msg}")
            if "PERMISSION_DENIED" in err_msg or "Permission denied" in err_msg:
                return [], " Ошибка Yandex API: PERMISSION_DENIED. В Yandex Cloud не привязан платежный аккаунт или сервисному аккаунту не назначена роль `search-api.user`."
            elif "UNAUTHENTICATED" in err_msg:
                return [], " Ошибка Yandex API: UNAUTHENTICATED. Проверьте правильность YANDEX_API_KEY."
            else:
                return [], f" Ошибка Yandex Search API: {err_msg}"

    async def search_by_image_url(self, image_url: str) -> Tuple[List[str], str]:
        """
        Ищет страницы в Интернете по ссылке на картинку.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                resp = await client.get(image_url)
                if resp.status_code != 200:
                    return [], f"Не удалось скачать картинку по ссылке (HTTP статус {resp.status_code})."
                image_bytes = resp.content

            return await self.search_by_image_bytes(image_bytes)
        except Exception as e:
            logger.error(f"Ошибка при скачивании ссылки: {e}")
            return [], f"Ошибка при загрузке картинки по ссылке: {e}"

    def _extract_urls_from_dict_or_obj(self, data) -> List[str]:
        urls = set()

        def _recursive_search(node):
            if isinstance(node, dict):
                for k, v in node.items():
                    if k in ("url", "link", "pageUrl", "page_url", "site_url") and isinstance(v, str) and v.startswith("http"):
                        urls.add(v)
                    else:
                        _recursive_search(v)
            elif isinstance(node, list):
                for item in node:
                    _recursive_search(item)
            elif isinstance(node, str) and node.startswith("http") and not node.endswith((".jpg", ".png", ".webp", ".jpeg")):
                urls.add(node)

        _recursive_search(data)
        return list(urls)
