import asyncio
import os
import random
from playwright.async_api import async_playwright
from supabase import create_client
from datetime import datetime, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BASE = "/data/instagram_sessions"
os.makedirs(BASE, exist_ok=True)


async def dar_like(page):
    await page.wait_for_timeout(3000)
    for s in ['svg[aria-label="Ya no me gusta"]', 'svg[aria-label="Unlike"]']:
        if await page.locator(s).count() > 0:
            return True, "ya_tenia_like"
    for s in ['svg[aria-label="Me gusta"]', 'svg[aria-label="Like"]']:
        loc = page.locator(s).first
        try:
            if await loc.count() == 0:
                continue
            await loc.scroll_into_view_if_needed(timeout=5000)
            await loc.click(force=True, timeout=5000)
            return True, None
        except Exception:
            continue
    return False, "boton_no_encontrado"


async def ejecutar(cuenta, video):
    carpeta = os.path.join(BASE, cuenta["usuario"])
    os.makedirs(carpeta, exist_ok=True)
    proxy = {"server": cuenta["proxy"]} if cuenta.get("proxy") else None
    exito, err = False, None

    async with async_playwright() as p:
        ctx = None
        try:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=carpeta,
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled",
                ],
                proxy=proxy,
                viewport={"width": 1280, "height": 800},
            )
            page = await ctx.new_page()
            await page.add_init_script(
                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"
            )
            print(f"🤖 @{cuenta['usuario']} → {video['url']}")
            await page.goto(video["url"], wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(random.randint(15, 25))
            exito, err = await dar_like(page)
            print(f"{'❤️' if exito else '❌'} @{cuenta['usuario']} ({err or 'ok'})")
        except Exception as e:
            err = str(e)
            print(f"❌ @{cuenta['usuario']}: {e}")
        finally:
            if ctx:
                await ctx.close()

    try:
        supabase.table("log_likes").insert({
            "cuenta_id": cuenta["id"],
            "video_id": video["id"],
            "exito": exito,
            "error": err,
        }).execute()
        supabase.table("cuentas").update({
            "estado": "durmiendo"
        }).eq("id", cuenta["id"]).execute()
    except Exception as e:
        print(f"⚠️ Supabase: {e}")
    return exito


async def main():
    while True:
        try:
            cuentas = (
                supabase.table("cuentas").select("*").eq("estado", "activa").execute().data
            )
            videos = (
                supabase.table("videos").select("*").eq("activo", True).execute().data
            )

            if not cuentas or not videos:
                print("⚠️ Sin cuentas activas o videos. Reintentando en 10 min...")
                await asyncio.sleep(600)
                continue

            print(f"\n📦 {len(cuentas)} cuentas × {len(videos)} videos")

            for i, c in enumerate(cuentas, 1):
                print(f"\n=== {i}/{len(cuentas)}: @{c['usuario']} ===")
                for v in videos:
                    await ejecutar(c, v)
                    await asyncio.sleep(5)
                if i < len(cuentas):
                    m = random.randint(40, 50)
                    print(f"⏳ {m} min entre cuentas...")
                    await asyncio.sleep(m * 60)

            print("\n🏁 Ciclo completo. Reiniciando en 30 min...")
            await asyncio.sleep(30 * 60)

        except Exception as e:
            print(f"💥 Error general: {e}")
            await asyncio.sleep(300)


asyncio.run(main())
