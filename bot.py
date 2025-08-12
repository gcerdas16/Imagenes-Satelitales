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
    "https://rammb.cira.colostate.edu/ramsdis/online/rmtc.asp"  # URL base sin ancla
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
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def send_video_to_telegram(video_path, caption):
    print(f"🚀 Enviando video a Telegram: '{caption}'")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    try:
        with open(video_path, "rb") as video_file:
            files = {"video": (os.path.basename(video_path), video_file)}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            requests.post(url, files=files, data=data, timeout=120).raise_for_status()
            print("✅ ¡Video enviado con éxito!")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar la petición a Telegram: {e}")


async def generate_all_videos():
    """Función principal con la nueva estrategia."""
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
    await page.setViewport({"width": 1920, "height": 1080})

    # --- NUEVA ESTRATEGIA ---
    print(
        f"➡️  Navegando a la página principal para obtener los enlaces directos: {START_URL}"
    )
    await page.goto(START_URL, {"waitUntil": "networkidle0", "timeout": 60000})

    for map_info in MAPS_TO_PROCESS:
        map_id = map_info["id"]
        map_caption = map_info["caption"]
        print(f"\n--- 🗺️  Procesando mapa: {map_id} ---")

        try:
            # 1. Encontrar el enlace directo a la página de animación ("HTML5 Loop")
            print("🔎 Buscando el enlace directo a la animación...")
            # Usamos XPath para encontrar el 'a' que contiene el 'map_id' en su href Y cuyo texto es "HTML5 Loop"
            # Esta es una forma muy robusta de seleccionar el elemento correcto
            xpath_selector = f'//a[contains(@href, "{map_id}") and normalize-space(text())="HTML5 Loop"]'
            link_element_list = await page.xpath(xpath_selector)

            if not link_element_list:
                print(
                    f"❌ No se pudo encontrar el enlace 'HTML5 Loop' para el mapa {map_id}. Saltando..."
                )
                continue

            link_element = link_element_list[0]
            loop_page_url = await page.evaluate(
                "(element) => element.href", link_element
            )
            print(f"✅ Enlace encontrado: {loop_page_url}")

            # 2. Navegar directamente a la página de animación
            print(f"➡️  Navegando a la página de animación...")
            await page.goto(
                loop_page_url, {"waitUntil": "networkidle0", "timeout": 60000}
            )

            # 3. Ejecutar la lógica de descarga en esta página
            print("⏳ Esperando el botón 'Download Loop'...")
            download_button_selector = 'input[value="Download Loop"]'
            await page.waitForSelector(download_button_selector, {"timeout": 60000})
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
            # Volver a la página principal para reiniciar el estado para el siguiente mapa del bucle
            await page.goto(START_URL, {"waitUntil": "networkidle0"})
            continue

    print("\n--- ✅ Proceso completado para todos los mapas ---")
    await browser.close()
    print("🖥️  Navegador cerrado.")


if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("🚨 ERROR CRÍTICO: Variables de entorno de Telegram no definidas.")
    else:
        asyncio.get_event_loop().run_until_complete(generate_all_videos())
