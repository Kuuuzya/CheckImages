import re
from urllib.parse import urlparse
from typing import Optional, Dict, Set

# Официальный список ТОЛЬКО коммерческих фотобанков, стоков и микростоков
PHOTOBANK_DOMAINS: Dict[str, str] = {
    # Крупнейшие международные фотобанки
    "shutterstock.com": "Shutterstock",
    "gettyimages.com": "Getty Images",
    "gettyimages.ru": "Getty Images Russia",
    "gettyimages.co.uk": "Getty Images UK",
    "gettyimages.de": "Getty Images DE",
    "stock.adobe.com": "Adobe Stock",
    "istockphoto.com": "iStock by Getty Images",
    "depositphotos.com": "Depositphotos",
    "dreamstime.com": "Dreamstime",
    "alamy.com": "Alamy",
    "123rf.com": "123RF",
    "freepik.com": "Freepik",
    "unsplash.com": "Unsplash",
    "pexels.com": "Pexels",
    "pixabay.com": "Pixabay",
    "vectorstock.com": "VectorStock",
    "bigstockphoto.com": "Bigstock",
    "bigstock.com": "Bigstock",
    "canstockphoto.com": "CanStockPhoto",
    "photodune.net": "PhotoDune / Envato Market",
    "elements.envato.com": "Envato Elements",
    "envato.com": "Envato",
    "eyeem.com": "EyeEm",
    "pond5.com": "Pond5",
    "masterfile.com": "Masterfile",
    "superstock.com": "SuperStock",
    "cliparto.com": "Cliparto",
    "panthermedia.net": "PantherMedia",
    "westend61.de": "Westend61",
    "agefotostock.com": "age fotostock",
    "mostphotos.com": "Mostphotos",
    "creativemarket.com": "Creative Market",
    "vecteezy.com": "Vecteezy",
    "rawpixel.com": "Rawpixel",
    "burst.shopify.com": "Shopify Burst",
    "picjumbo.com": "Picjumbo",
    "kaboompics.com": "Kaboompics",
    "splitshire.com": "SplitShire",
    "stocksnap.io": "StockSnap.io",
    "gratisography.com": "Gratisography",
    "shotstash.com": "Shotstash",
    "skitterphoto.com": "Skitterphoto",
    "picography.co": "Picography",
    "foodiesfeed.com": "Foodiesfeed",
    "fineartamerica.com": "Fine Art America",
    "photoxpress.com": "PhotoXpress",
    "stockunlimited.com": "StockUnlimited",
    "storyblocks.com": "Storyblocks",
    "motionelements.com": "MotionElements",
    "cutcaster.com": "Cutcaster",
    "zoonar.com": "Zoonar",
    "pixtastock.com": "Pixta",
    "ingimage.com": "Ingimage",
    "graphicriver.net": "GraphicRiver",

    # Российские и СНГ коммерческие фотобанки и фотоагентства
    "lori.ru": "Фотобанк Лори (Lori.ru)",
    "photogenica.ru": "Фотодженика (Photogenica)",
    "rosfoto.ru": "Росфото (Rosfoto)",
    "pressphoto.ru": "PressPhoto",
    "fotolia.com": "Fotolia",
    "sputnikimages.com": "Sputnik Images",
    "visualrian.ru": "РИА Новости Медиабанк (Visual RIAN)",
    "tassphoto.com": "Фотохроника ТАСС (TASS Photo)",
    "foto-bank.ru": "Фотобанк.ру",
    "geo-photo.ru": "Geo-Photo",
    "eastnews.ru": "East News",
    "globallookpress.com": "Global Look Press",
}

# Ключевые слова доменов фотобанков
PHOTOBANK_KEYWORDS = [
    r'shutterstock', r'gettyimages', r'istock', r'depositphotos',
    r'dreamstime', r'alamy', r'123rf', r'freepik', r'adobe\.stock',
    r'photodune', r'vectorstock', r'bigstock', r'lori\.ru', r'photogenica',
    r'pressphoto', r'envato', r'vecteezy', r'tassphoto', r'visualrian',
    r'sputnikimages', r'globallookpress', r'masterfile', r'superstock'
]

def extract_domain(url: str) -> str:
    """
    Извлекает чистое доменное имя из URL.
    """
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc.lower()
        if ":" in netloc:
            netloc = netloc.split(":")[0]
        
        if netloc.startswith("www."):
            netloc = netloc[4:]
            
        return netloc
    except Exception:
        return ""

def check_photobank_domain(url: str) -> Optional[str]:
    """
    Проверяет, принадлежит ли URL строго известному коммерческому фотобанку.
    """
    domain = extract_domain(url)
    if not domain:
        return None

    # Точное совпадение с доменной базой фотобанков
    for pb_domain, pb_name in PHOTOBANK_DOMAINS.items():
        if domain == pb_domain or domain.endswith("." + pb_domain):
            return pb_name
            
    # Проверка по ключам только стоковых паттернов
    for pattern in PHOTOBANK_KEYWORDS:
        if re.search(pattern, url, re.IGNORECASE):
            return f"Стоковый ресурс ({domain})"

    return None

def find_photobanks_in_urls(urls: list[str]) -> dict[str, str]:
    """
    Принимает список URL-адресов.
    Возвращает словарь {url: photobank_name} ТОЛЬКО для реальных фотобанков.
    """
    found = {}
    for url in urls:
        name = check_photobank_domain(url)
        if name:
            found[url] = name
    return found
