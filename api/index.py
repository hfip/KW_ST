# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from .akwam_api import AkwamM3u8API
from bs4 import BeautifulSoup
import requests
import json
import re

app = FastAPI(title="Stremio Akwam Addon")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

akwam = AkwamM3u8API()

MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "3.6.0",
    "name": "أكوام الذكي - Akwam Proxy Pass",
    "description": "قنص تلقائي لـ 18 سيرفر بث عبر كشط المعرف بالبروكسي وبدون كتالوجات",
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"]
}

def clean_title(title: str) -> str:
    """تنظيف الاسم من الرموز والكلمات الزائدة لتسهيل البحث في أكوام"""
    title = title.lower()
    title = re.sub(r'[:\-–,.]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def get_media_title_from_imdb_via_proxy(imdb_id: str) -> str:
    """كشط صفحة IMDb بالكامل عبر وسيط corsproxy لتخطي حظر Render"""
    try:
        target_url = f"https://www.imdb.com/title/{imdb_id}/"
        proxy_url = f"https://corsproxy.io/?{target_url}"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9"
        }
        print(f"[🔍 Diagnostic] جاري كشط صفحة IMDb عبر البروكسي للمعّرف: {imdb_id}...")
        response = requests.get(proxy_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('title')
            if title_tag:
                raw_title = title_tag.text
                # تنظيف عنوان الصفحة لاستخراج اسم الفيلم أو المسلسل الإنجليزي النظيف
                clean_name = re.sub(r'\s*\(\d{4}\)\s*.*$', '', raw_title)
                clean_name = clean_name.replace(" - IMDb", "").strip()
                print(f"[✓ Diagnostic] نجح الكشط بالبروكسي! الاسم هو: '{clean_name}'")
                return clean_name
    except Exception as e:
        print(f"[🚨 Diagnostic Error] فشل الكشط بالبروكسي: {e}")
    return ""

@app.get("/manifest.json")
async def get_manifest():
    manifest_json = json.dumps(MANIFEST, ensure_ascii=False, indent=4)
    return Response(content=manifest_json, media_type="application/json; charset=utf-8")

@app.get("/stream/{stream_type}/{stream_id}.json")
async def get_streams(stream_type: str, stream_id: str):
    try:
        full_id = stream_id.replace(".json", "")
        parts = full_id.split(":")
        imdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else "1"
        episode = parts[2] if len(parts) > 2 else "1"

        print(f"\n================ [ بداية فحص طلب البث ] ================")
        print(f"[ℹ️] النوع: {stream_type} | المعرف: {imdb_id} | الموسم: {season} | الحلقة: {episode}")

        # 1. جلب الاسم مباشرة عبر كشط IMDb بالبروكسي
        original_title = get_media_title_from_imdb_via_proxy(imdb_id)
        if not original_title:
            print("[-] فشل استخراج الاسم بالبروكسي. توقف الفحص.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        # 2. تنظيف كلمة البحث
        search_query = clean_title(original_title)
        print(f"[🔍] الكلمة المفتاحية للبحث: '{search_query}'")

        # 3. البحث في أكوام
        search_results = akwam.search(search_query, media_type=stream_type)
        if not search_results:
            words = search_query.split()
            if len(words) > 2:
                fallback_query = " ".join(words[:2])
                print(f"[⚠️] تجربة البحث المرن بـ: '{fallback_query}'")
                search_results = akwam.search(fallback_query, media_type=stream_type)

        if not search_results:
            print("[-] لم نجد أي نتائج في موقع أكوام للبحث الصامت.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        target_page_url = search_results[0]['url']
        print(f"[🎯] رابط صفحة أكوام المكتشفة: {target_page_url}")

        if stream_type == "series":
            episodes = akwam.get_episodes(target_page_url)
            target_page_url = None
            target_episode_name = f"الحلقة {episode}"
            for ep in episodes:
                if target_episode_name in ep['name'] or f" {episode} " in ep['name']:
                    target_page_url = ep['url']
                    break
            if not target_page_url and episodes:
                target_page_url = episodes[0]['url']

        # 4. كشط روابط الـ 18 سيرفر
        streams = []
        if target_page_url:
            raw_streams = akwam.extract_stream_links(target_page_url)
            for stream in raw_streams:
                streams.append({
                    "name": stream["title"],
                    "title": f"{stream['title']}\n🌐 المستضيف: أكوام المطور",
                    "url": stream["url"]
                })

        print(f"================ [ نهاية فحص طلب البث ] ================\n")
        streams_json = json.dumps({"streams": streams}, ensure_ascii=False, indent=4)
        return Response(content=streams_json, media_type="application/json; charset=utf-8")

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
