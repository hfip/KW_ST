# -*- coding: utf-8 -*-
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.middleware.cors import CORSMiddleware
from .akwam_api import AkwamM3u8API
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

TMDB_KEY = "8265bd1679663a7ea12ac168da84d2e8"

MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "3.3.0",
    "name": "أكوام الذكي - Akwam TMDB",
    "description": "قنص تلقائي لـ 18 سيرفر بث مباشر بالاعتماد على TMDB وبدون كتالوجات",
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

def get_media_title_from_tmdb(imdb_id: str, media_type: str) -> str:
    """تكتيك FaselHD: جلب الاسم الإنجليزي الصافي والبديل العربي من TMDB لضمان التطابق"""
    try:
        # البحث عن المادة باستخدام معرف IMDB في TMDB
        url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_KEY}&external_source=imdb_id"
        print(f"[🔍 Diagnostic] جاري طلب اسم الـ IMDB: {imdb_id} من TMDB...")
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("movie_results", []) if media_type == "movie" else data.get("tv_results", [])
            
            if results:
                title_en = results[0].get("title") or results[0].get("name") or ""
                print(f"[✓ Diagnostic] الاسم الإنجليزي العائد من TMDB هو: '{title_en}'")
                return title_en
    except Exception as e:
        print(f"[🚨 Diagnostic Error] فشل الاتصال بـ TMDB: {e}")
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

        # 1. جلب اسم المادة من TMDB عوضاً عن Cinemeta المتعطلة
        original_title = get_media_title_from_tmdb(imdb_id, stream_type)
        if not original_title:
            print("[-] فشل جلب الاسم من TMDB. توقف الفحص.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        # 2. تنظيف وتهيئة الكلمة البحثية
        search_query = clean_title(original_title)
        print(f"[🔍] الكلمة المفتاحية للبحث بعد التنظيف: '{search_query}'")

        # 3. البحث الصامت عبر البروكسي في أكوام
        print(f"[🛰️] جاري إرسال طلب البحث الصامت إلى أكوام...")
        search_results = akwam.search(search_query, media_type=stream_type)
        
        # البحث المرن في حال عدم العثور على نتائج بالاسم الكامل
        if not search_results:
            words = search_query.split()
            if len(words) > 2:
                fallback_query = " ".join(words[:2])
                print(f"[⚠️] لم تظهر نتائج بالاسم الكامل. نجرب بحث مرن بـ: '{fallback_query}'")
                search_results = akwam.search(fallback_query, media_type=stream_type)

        if not search_results:
            print("[-] لم يعثر البروكسي على أي نتائج مطابقة في موقع أكوام.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        # اختيار النتيجة الأولى
        target_page_url = search_results[0]['url']
        print(f"[🎯] الرابط المستهدف المختار للمادة: {target_page_url}")

        # معالجة جلب الحلقات للمسلسلات وطباعتها
        if stream_type == "series":
            print(f"[🎬] جاري جلب قائمة الحلقات من صفحة المسلسل...")
            episodes = akwam.get_episodes(target_page_url)
            
            target_page_url = None
            target_episode_name = f"الحلقة {episode}"
            for ep in episodes:
                if target_episode_name in ep['name'] or f" {episode} " in ep['name']:
                    target_page_url = ep['url']
                    print(f"[✓] تم مطابقة الحلقة المطلوبة بنجاح: '{ep['name']}'")
                    break
            
            if not target_page_url and episodes:
                target_page_url = episodes[0]['url']
                print(f"[⚠️] تم اختيار أول حلقة تلقائياً كاحتياط: {target_page_url}")

        # 4. كشط السيرفرات النهائية
        streams = []
        if target_page_url:
            print(f"[⚡] جاري استخراج أزرار السيرفرات (data-link) من الصفحة المستهدفة...")
            raw_streams = akwam.extract_stream_links(target_page_url)
            print(f"[✓] تم استخراج {len(raw_streams)} سيرفر تشغيل بنجاح.")
            
            for stream in raw_streams:
                streams.append({
                    "name": stream["title"],
                    "title": f"{stream['title']}\n🌐 المستضيف: أكوام المطور",
                    "url": stream["url"]
                })
        else:
            print("[-] لم نتمكن من تحديد رابط صفحة العرض النهائية للكشط.")

        print(f"================ [ نهاية فحص طلب البث ] ================\n")
        streams_json = json.dumps({"streams": streams}, ensure_ascii=False, indent=4)
        return Response(content=streams_json, media_type="application/json; charset=utf-8")

    except Exception as e:
        print(f"[🚨 خطأ فادح أثناء الفحص]: {e}")
        raise HTTPException(status_code=500, detail=str(e))
