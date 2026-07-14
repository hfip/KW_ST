# -*- coding: utf-8 -*-
import re
import requests
from bs4 import BeautifulSoup

PROXY_BASE_URL = "https://mbox-proxy.h-fip.workers.dev/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "ar,en-US;q=0.7,en;q=0.3",
    "Connection": "keep-alive"
}

class AkwamM3u8API:
    def __init__(self, base_url="https://akwams.org"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search(self, query, media_type='movie'):
        """البحث عن الأفلام أو المسلسلات باستخدام النطاق المحدث"""
        try:
            query_clean = query.replace(' ', '+')
            # استخدام البروكسي لتمرير طلب البحث لتفادي حظر السيرفر السحابي
            target_url = f"{self.base_url}/search?q={query_clean}&section={media_type}"
            final_url = f"{PROXY_BASE_URL}{target_url.replace('https://', '')}"
            
            response = self.session.get(final_url, timeout=15)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            # قنص روابط وصور المواد بناءً على الهيكلية الجديدة
            widget_body = soup.find('div', class_='widget-body')
            results = []
            if widget_body:
                for item in widget_body.find_all('div', class_='entry-box'):
                    title_elem = item.find('h3')
                    link_elem = item.find('a', href=True)
                    img_elem = item.find('img')
                    
                    if title_elem and link_elem:
                        name = title_elem.text.strip()
                        url = link_elem['href']
                        poster = img_elem.get('data-src') or img_elem.get('src') if img_elem else ""
                        results.append({'name': name, 'url': url, 'poster': poster})
            return results
        except Exception:
            return []

    def get_episodes(self, series_url):
        """جلب الحلقات للمسلسلات من الواجهة الجديدة"""
        try:
            final_url = f"{PROXY_BASE_URL}{series_url.replace('https://', '')}"
            response = self.session.get(final_url, timeout=15)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            episodes = []
            # البحث عن روابط الحلقات داخل قسم الحلقات المحدث
            for link in soup.find_all('a', href=True):
                href = link['href']
                if '/مشاهدة-مسلسل-' in href or ' الحلقة-' in link.text:
                    name = link.text.strip()
                    if {'name': name, 'url': href} not in episodes:
                        episodes.append({'name': name, 'url': href})
            return episodes[::-1] # ترتيب تصاعدي للحلقات
        except Exception:
            return []

    def extract_stream_links(self, page_url):
        """التكتيك الجديد: قنص روابط data-link من أزرار السيرفرات المدمجة"""
        try:
            final_url = f"{PROXY_BASE_URL}{page_url.replace('https://', '')}"
            self.session.headers.update({"Referer": page_url})
            
            response = self.session.get(final_url, timeout=20)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            # قنص الأزرار التي تحمل كلاس السيرفرات المحدث
            server_buttons = soup.find_all('button', class_=lambda x: x and 'server-btn' in x)
            
            streams = []
            for idx, btn in enumerate(server_buttons, 1):
                embed_url = btn.get('data-link')
                if embed_url:
                    server_title = btn.text.strip().replace('▶', '').strip()
                    domain_match = re.search(r'https?://([^/]+)', embed_url)
                    provider_name = domain_match.group(1) if domain_match else "CDN"
                    
                    streams.append({
                        "title": f"Akwam - {server_title} ({provider_name})",
                        "url": embed_url
                    })
            return streams
        except Exception:
            return []
