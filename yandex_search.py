import base64
import logging
import xml.etree.ElementTree as ET
import httpx
from typing import List, Optional
from config import settings

logger = logging.getLogger(__name__)

# Импортируем официальный Yandex AI Studio SDK
try:
    from yandex_ai_studio_sdk import AIStudio
    HAS_SDK = True
except ImportError:
    HAS_SDK = False

class YandexImageSearchClient:
    """
    Клиент для Yandex Search API (Поиск по изображениям / Поиск по картинке).
    Использует официальный yandex-ai-studio-sdk с фоллбеком на REST/XML API.
    """
    def __init__(self, api_key: str = None, folder_id: str = None):
        self.api_key = api_key or settings.yandex_api_key
        self.folder_id = folder_id or settings.yandex_folder_id
        
        self.cloud_endpoint = "https://yandex.cloud/search/v2/image"
        self.xml_endpoint = "https://yandex.ru/search/xml"

    async def search_by_image_bytes(self, image_bytes: bytes) -> List[str]:
        """
        Ищет страницы в Интернете по бинарным данным картинки (байт-массиву).
        """
        if not self.api_key or not self.folder_id:
            logger.warning("YANDEX_API_KEY или YANDEX_FOLDER_ID не настроены!")
            return []

        urls = set()

        if HAS_SDK:
            try:
                sdk_urls = await self._search_bytes_via_sdk(image_bytes)
                urls.update(sdk_urls)
            except Exception as e:
                logger.error(f"Ошибка при поиске по байтам картинки через SDK: {e}")

        return list(urls)

    async def search_by_image_url(self, image_url: str) -> List[str]:
        """
        Ищет страницы в Интернете по ссылке на картинку.
        """
        if not self.api_key or not self.folder_id:
            logger.warning("YANDEX_API_KEY или YANDEX_FOLDER_ID не настроены!")
            return []

        urls = set()

        # Попытка 1: Использование официального Yandex AI Studio SDK
        if HAS_SDK:
            try:
                sdk_urls = await self._search_via_sdk(image_url)
                urls.update(sdk_urls)
            except Exception as e:
                logger.error(f" Ошибка при запросе через Yandex AI Studio SDK: {e}")

        # Попытка 2: Запрос через REST API Yandex Cloud
        if not urls:
            try:
                cloud_urls = await self._search_cloud_api(image_url)
                urls.update(cloud_urls)
            except Exception as e:
                logger.error(f" Ошибка при запросе к Yandex Cloud Search API: {e}")

        # Попытка 3: Запрос через Yandex XML Search API
        if not urls:
            try:
                xml_urls = await self._search_xml_api(image_url)
                urls.update(xml_urls)
            except Exception as e:
                logger.error(f" Ошибка при запросе к Yandex XML API: {e}")

        return list(urls)

    async def _search_bytes_via_sdk(self, image_bytes: bytes) -> List[str]:
        """
        Отправляет бинарные данные картинки в base64 через yandex-ai-studio-sdk
        """
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        sdk = AIStudio(
            folder_id=self.folder_id,
            auth=self.api_key,
        )

        search = sdk.search_api.by_image(
            family_mode="FAMILY_MODE_MODERATE",
        )

        search_result = search.run(image_base64, page=0)

        if hasattr(search_result, "model_dump"):
            result_data = search_result.model_dump()
        elif hasattr(search_result, "to_dict"):
            result_data = search_result.to_dict()
        elif isinstance(search_result, dict):
            result_data = search_result
        else:
            result_data = str(search_result)

        return self._extract_urls_from_dict_or_obj(result_data)

    async def _search_via_sdk(self, image_url: str) -> List[str]:
        """
        Запрос к Яндекс Поиску по картинке через yandex-ai-studio-sdk по URL ссылки
        """
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(image_url)
            if resp.status_code != 200:
                logger.warning(f"Не удалось скачать картинку {image_url}: статус {resp.status_code}")
                return []
            image_bytes = resp.content

        return await self._search_bytes_via_sdk(image_bytes)

    async def _search_cloud_api(self, image_url: str) -> List[str]:
        """
        Прямой REST запрос к Yandex Cloud Search API.
        """
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "x-folder-id": self.folder_id,
            "Content-Type": "application/json"
        }

        payload = {
            "folderId": self.folder_id,
            "imageUrl": image_url,
            "searchType": "SIMILAR_IMAGES",
            "page": 0,
            "pageSize": 50
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(self.cloud_endpoint, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return self._extract_urls_from_dict_or_obj(data)
            else:
                logger.warning(f"Yandex Cloud API статус {response.status_code}: {response.text}")
                return []

    async def _search_xml_api(self, image_url: str) -> List[str]:
        """
        Запрос к Yandex XML API.
        """
        params = {
            "folderid": self.folder_id,
            "apikey": self.api_key,
            "type": "image",
            "image_url": image_url,
            "cbir_page": "similar_data"
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(self.xml_endpoint, params=params)
            if response.status_code == 200:
                return self._parse_xml_response(response.text)
            else:
                return []

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

    def _parse_xml_response(self, xml_text: str) -> List[str]:
        urls = set()
        try:
            root = ET.fromstring(xml_text)
            for elem in root.iter():
                if elem.tag.endswith("url") or elem.tag.endswith("link"):
                    if elem.text and elem.text.startswith("http"):
                        urls.add(elem.text.strip())
        except ET.ParseError as e:
            logger.error(f"Ошибка парсинга XML: {e}")
            
        return list(urls)
