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

MANIFEST = {
    "id": "community.abdullah.akwam.addon",
    "version": "3.2.0",
    "name": "أكوام الفاحص - Akwam Diagnostic",
    "description": "نسخة اختبارية لطباعة سجلات البحث وتحديد الخلل في السيرفرات",
    "resources": ["stream"],
    "types": ["movie", "series"],
    "idPrefixes": ["tt"]
}

def clean_title(title: str) -> str:
    """تنظيف الاسم من الرموز والكلمات الزائدة لتسهيل البحث في أكوام"""
    title = title.lower()
    # إزالة الرموز الشهيرة التي تعيق البحث في أكوام
    title = re.sub(r'[:\-–,.]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    return title

def get_media_title_from_imdb(imdb_id: str, media_type: str) -> str:
    """جلب اسم المادة صامتاً وسريعاً عبر Cinemeta مع طباعة التشخيص"""
    try:
        cinemeta_type = "movie" if media_type == "movie" else "series"
        url = f"https://v3-cinemeta.strem.io/meta/{cinemeta_type}/{imdb_id}.json"
        print(f"[🔍 Diagnostic] جاري طلب اسم الـ IMDB: {imdb_id} من Cinemeta...")
        
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            title = data.get("meta", {}).get("name", "")
            print(f"[🔍 Diagnostic] الاسم العائد من Cinemeta هو: '{title}'")
            return title
    except Exception as e:
        print(f"[🚨 Diagnostic Error] فشل الاتصال بـ Cinemeta: {e}")
    return ""

@app.get("/manifest.json")
async def get_manifest():
    manifest_json = json.dumps(MANIFEST, ensure_ascii=False, indent=4)
    return Response(content=manifest_json, media_type="application/json; charset=utf-8")

@app.get("/stream/{stream_type}/{stream_id}.json")
async def get_streams(stream_type: str, stream_id: str):
    """ممر البث الفاحص: يطبع خطوات البحث والنتائج بالتفصيل في الـ Logs"""
    try:
        full_id = stream_id.replace(".json", "")
        parts = full_id.split(":")
        imdb_id = parts[0]
        season = parts[1] if len(parts) > 1 else "1"
        episode = parts[2] if len(parts) > 2 else "1"

        print(f"\n================ [ بداية فحص طلب البث ] ================")
        print(f"[ℹ️] النوع: {stream_type} | المعرف: {imdb_id} | الموسم: {season} | الحلقة: {episode}")

        # 1. جلب اسم المادة
        original_title = get_media_title_from_imdb(imdb_id, stream_type)
        if not original_title:
            print("[-] فشل جلب الاسم من Cinemeta. توقف الفحص.")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        # 2. تنظيف وتهيئة الكلمة البحثية
        search_query = clean_title(original_title)
        print(f"[🔍] الكلمة المفتاحية للبحث بعد التنظيف: '{search_query}'")

        # 3. محاولة البحث في أكوام
        print(f"[🛰️] جاري إرسال طلب البحث الصامت إلى أكوام...")
        search_results = akwam.search(search_query, media_type=stream_type)
        
        # تكتيك البحث المرن (Fuzzy Search): إذا لم تظهر نتائج بالاسم الكامل، نبحث بأول كلمتين فقط
        if not search_results:
            words = search_query.split()
            if len(words) > 2:
                fallback_query = " ".join(words[:2])
                print(f"[⚠️] لم تظهر نتائج بالاسم الكامل. نجرب بحث مرن بـ: '{fallback_query}'")
                search_results = akwam.search(fallback_query, media_type=stream_type)

        # طباعة قائمة النتائج العائدة من أكوام بالكامل لتشخيصها
        print(f"[📊] نتائج البحث المكتشفة في موقع أكوام (العدد: {len(search_results)}):")
        for idx, res in enumerate(search_results, 1):
            print(f"    {idx}. الاسم في أكوام: '{res['name']}' | الرابط: {res['url']}")

        if not search_results:
            print("[-] لم يعثر البروكسي على أي نتائج مطابقة في موقع أكوام.")
            print(f"================ [ نهاية فحص طلب البث ] ================\n")
            return Response(content=json.dumps({"streams": []}), media_type="application/json")

        # اختيار أول نتيجة مطابقة
        target_page_url = search_results[0]['url']
        print(f"[🎯] الرابط المستهدف المختار للمادة: {target_page_url}")

        # معالجة جلب الحلقات للمسلسلات وطباعتها
        if stream_type == "series":
            print(f"[🎬] جاري جلب قائمة الحلقات من صفحة المسلسل...")
            episodes = akwam.get_episodes(target_page_url)
            print(f"[📊] تم العثور على {len(episodes)} حلقة في السورس.")
            
            target_page_url = None
            target_episode_name = f"الحلقة {episode}"
            for ep in episodes:
                print(f"    - حلقة مكتشفة: '{ep['name']}' -> {ep['url']}")
                if target_episode_name in ep['name'] or f" {episode} " in ep['name']:
                    target_page_url = ep['url']
                    print(f"[✓] تم مطابقة الحلقة المطلوبة بنجاح: '{ep['name']}'")
                    break
            
            if not target_page_url and episodes:
                target_page_url = episodes[0]['url']
                print(f"[⚠️] لم نجد تطابق دقيق لرقم الحلقة. تم اختيار أول حلقة تلقائياً كاحتياط: {target_page_url}")

        # 4. كشط السيرفرات النهائية
        streams = []
        if target_page_url:
            print(f"[⚡] جاري استخراج أزرار السيرفرات (data-link) من الصفحة المستهدفة...")
            raw_streams = akwam.extract_stream_links(target_page_url)
            print(f"[✓] تم استخراج {len(raw_streams)} سيرفر تشغيل بنجاح.")
            
            for stream in raw_streams:
                print(f"    - سيرفر جاهز للتشغيل: {stream['title']} -> {stream['url']}")
                streams.append({
                    "name": stream["title"],
                    "title": f"{stream['title']}\n🌐 المستضيف: أكوام الفاحص",
                    "url": stream["url"]
                })
        else:
            print("[-] لم نتمكن من تحديد رابط صفحة العرض النهائية للكشط.")

        print(f"================ [ نهاية فحص طلب البث ] ================\n")
        streams_json = json.dumps({"streams": streams}, ensure_ascii=False, indent=4)
        return Response(content=streams_json, media_type="application/json; charset=utf-8")

    except Exception as e:
        print(f"[🚨 خطأ فادح أثناء الفحص السريري]: {e}")
        raise HTTPException(status_code=500, detail=str(e))
