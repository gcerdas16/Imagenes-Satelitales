import os
import shutil
import base64
import asyncio
import subprocess
import requests
from pyppeteer import launch
from pyppeteer.errors import TimeoutError

# --- CONFIGURACIÓN PRINCIPAL ---
START_URL = (
    "https://rammb.cira.colostate.edu/ramsdis/online/rmtc.asp#Central_and_South_America"
)
OUTPUT_DIR = "gif_animado_final"
MAPS_TO_PROCESS = [
    {
        "id": "rmtc/rmtccosvis1",
        "caption": "🛰️ Animación Satelital (Canal Visible) - Costa Rica",
    },
    {
        "id": "rmtc/rmtccosir2",
        "caption": "🛰️ Animación Satelital (Canal Infrarrojo) - Costa Rica",
    },
    {
        "id": "rmtc/rmtccosir22",
        "caption": "🛰️ Animación Satelital (Infrarrojo de Onda Corta) - Costa Rica",
    },
    {
        "id": "rmtc/rmtccosir42",
        "caption": "🛰️ Animación Satelital (Vapor de Agua) - Costa Rica",
    },
]

# --- CREDENCIALES DE TELEGRAM ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# --- FUNCIONES AUXILIARES (SIN CAMBIOS) ---
def convert_gif_to_mp4(gif_path, mp4_path):
    print(f"🎬 Convirtiendo {os.path.basename(gif_path)} a MP4...")
    try:
        command = [
            "ffmpeg",
            "-i",
            gif_path,
            "-movflags",
            "faststart",
            "-pix_fmt",
            "yuv420p",
            "-vf",
            "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-y",
            mp4_path,
        ]
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("✅ Conversión a MP4 exitosa.")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"❌ Error durante la conversión con FFmpeg: {e}")
        return False


def send_video_to_telegram(video_path, caption):
    print(f"🚀 Enviando video a Telegram con el caption: '{caption}'")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    try:
        with open(video_path, "rb") as video_file:
            files = {"video": (os.path.basename(video_path), video_file)}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            response = requests.post(url, files=files, data=data, timeout=120)
            response.raise_for_status()
            if response.json().get("ok"):
                print("✅ ¡Video enviado a Telegram con éxito!")
            else:
                print(f"❌ Error en la respuesta de Telegram: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar la petición a Telegram: {e}")


async def generate_all_videos():
    """Función principal que orquesta todo el proceso."""
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    print("🖥️  Iniciando navegador Chromium...")
    browser = await launch(
        headless=True,
        executablePath="/usr/bin/chromium",
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )
    page = await browser.newPage()

    # --- MEJORA 1: CAMUFLAJE (USER-AGENT DE UN NAVEGADOR REAL) ---
    await page.setUserAgent(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    )
    await page.setViewport({"width": 1920, "height": 1080})

    print(f"➡️  Navegando a {START_URL}")
    await page.goto(START_URL, {"waitUntil": "networkidle0", "timeout": 60000})

    main_image_selector = 'img[name="imag"]'

    # --- MEJORA 2: BLOQUE DE DIAGNÓSTICO (CAJA NEGRA) ---
    try:
        print("⏳ Esperando a que cargue la imagen principal inicial...")
        await page.waitForSelector(main_image_selector, {"timeout": 60000})
        print("✅ Imagen principal encontrada.")
    except TimeoutError:
        print("❌ ERROR DE TIMEOUT: No se pudo encontrar la imagen principal.")
        print("--- INICIANDO DEBUG ---")
        html_content = await page.content()
        print("CONTENIDO HTML DE LA PÁGINA FALLIDA:")
        print(html_content)
        print("--- FIN DE DEBUG ---")
        print("El bot no puede continuar y se cerrará.")
        await browser.close()
        return  # Salir de la función si falla

    last_image_src = await page.evaluate(
        f'document.querySelector("{main_image_selector}").src'
    )

    for map_info in MAPS_TO_PROCESS:
        map_id = map_info["id"]
        map_caption = map_info["caption"]
        print(f"\n--- 🗺️  Procesando mapa: {map_id} ---")

        try:
            print(f"🖱️  Haciendo clic en el enlace del mapa '{map_id}'")
            map_link_selector = f"a[href*='{map_id}']"
            await page.waitForSelector(map_link_selector)
            await page.click(map_link_selector)

            print("⏳ Esperando a que el nuevo mapa cargue...")
            wait_function = f"""(selector, last_src) => {{
                const current_src = document.querySelector(selector).src;
                return current_src !== last_src;
            }}"""
            await page.waitForFunction(
                wait_function, {"timeout": 60000}, main_image_selector, last_image_src
            )
            print("✅ El nuevo mapa ha cargado.")
            last_image_src = await page.evaluate(
                f'document.querySelector("{main_image_selector}").src'
            )

            print("⏳ Esperando el botón 'Download Loop'...")
            download_button_selector = 'input[value="Download Loop"]'
            await page.waitForSelector(download_button_selector)
            await page.click(download_button_selector)
            print("🖱️  Clic en 'Download Loop'. Generando animación...")

            gif_image_selector = 'img[src^="data:image/gif;base64,"]'
            print("⏳ Esperando que el GIF sea generado por el servidor...")
            await page.waitForSelector(gif_image_selector, {"timeout": 120000})

            gif_base64_data = await page.evaluate(
                f'() => document.querySelector("{gif_image_selector}").src'
            )
            print("📥 GIF generado y encontrado en la página.")

            header, encoded = gif_base64_data.split(",", 1)
            gif_data = base64.b64decode(encoded)
            gif_filename = f"{map_id.replace('/', '_')}.gif"
            gif_path = os.path.join(OUTPUT_DIR, gif_filename)
            with open(gif_path, "wb") as f:
                f.write(gif_data)
            print(f"💾 GIF guardado como: {gif_path}")

            mp4_path = gif_path.replace(".gif", ".mp4")
            if convert_gif_to_mp4(gif_path, mp4_path):
                send_video_to_telegram(mp4_path, map_caption)

        except Exception as e:
            print(f"❌ Ocurrió un error procesando el mapa '{map_id}': {e}")
            print("Continuando con el siguiente mapa...")
            await page.goto(START_URL, {"waitUntil": "networkidle0", "timeout": 60000})
            last_image_src = await page.evaluate(
                f'document.querySelector("{main_image_selector}").src'
            )
            continue

    print("\n--- ✅ Proceso completado para todos los mapas ---")
    await browser.close()
    print("🖥️  Navegador cerrado.")


if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "🚨 ERROR CRÍTICO: Las variables de entorno TELEGRAM_TOKEN y TELEGRAM_CHAT_ID deben estar definidas."
        )
    else:
        asyncio.get_event_loop().run_until_complete(generate_all_videos())
