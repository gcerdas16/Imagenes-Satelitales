import os
import shutil
import base64
import asyncio
import subprocess
import requests
from pyppeteer import launch

# --- CONFIGURACIÓN PRINCIPAL ---

# URL de inicio para la navegación
START_URL = (
    "https://rammb.cira.colostate.edu/ramsdis/online/rmtc.asp#Central_and_South_America"
)

# Directorio para guardar los archivos generados
OUTPUT_DIR = "gif_animado_final"

# Lista de mapas a procesar
MAPS_TO_PROCESS = [
    {
        "id": "rmtc/rmtccosvis1",
        "caption": "🛰️ Animación Satelital (Canal Visible) - Costa Rica",
    },
    {
        "id": "rmtc/rmtccosir2",  # Corregido de rmtccosvis2 a rmtccosir2 para Infrarrojo
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

# --- CREDENCIALES DE TELEGRAM (LEÍDAS DESDE EL ENTORNO) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def convert_gif_to_mp4(gif_path, mp4_path):
    """
    Convierte un archivo GIF a MP4 usando FFmpeg.
    """
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
            "-y",  # Sobrescribir el archivo de salida si existe
            mp4_path,
        ]
        # Usamos DEVNULL para ocultar la salida detallada de ffmpeg
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        print("✅ Conversión a MP4 exitosa.")
        return True
    except FileNotFoundError:
        print(
            "❌ Error: FFmpeg no está instalado o no se encuentra en el PATH del sistema."
        )
        return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Error durante la conversión con FFmpeg: {e}")
        return False


def send_video_to_telegram(video_path, caption):
    """
    Envía un video a un chat de Telegram.
    """
    print(f"🚀 Enviando video a Telegram con el caption: '{caption}'")
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print(
            "❌ Error: Las variables TELEGRAM_TOKEN y TELEGRAM_CHAT_ID no están configuradas."
        )
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    try:
        with open(video_path, "rb") as video_file:
            files = {"video": (os.path.basename(video_path), video_file)}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}

            response = requests.post(url, files=files, data=data, timeout=60)
            response.raise_for_status()  # Lanza un error para respuestas 4xx/5xx

            if response.json().get("ok"):
                print("✅ ¡Video enviado a Telegram con éxito!")
            else:
                print(f"❌ Error en la respuesta de Telegram: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar la petición a Telegram: {e}")
    except Exception as e:
        print(f"❌ Ocurrió un error inesperado al enviar el video: {e}")


async def generate_all_videos():
    """
    Función principal que orquesta todo el proceso.
    """
    # 1. Preparación Inicial: Limpiar carpeta de salida
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    # Verificar que FFmpeg exista antes de iniciar el navegador
    if not shutil.which("ffmpeg"):
        print(
            "🚨 ALERTA: El comando 'ffmpeg' no fue encontrado. La conversión de video fallará."
        )
        print(
            "Asegúrate de que FFmpeg esté instalado en tu entorno de Railway (revisa nixpacks.toml)."
        )
        # El script puede continuar para descargar los GIFs, pero la conversión y envío fallarán.

    # Iniciar el navegador Pyppeteer
    print("🖥️  Iniciando navegador Chromium...")
    # Opciones para Railway: headless y no-sandbox son cruciales
    browser = await launch(
        headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
    )
    page = await browser.newPage()

    # 2. Bucle para procesar cada mapa
    for map_info in MAPS_TO_PROCESS:
        map_id = map_info["id"]
        map_caption = map_info["caption"]
        print(f"\n--- 🗺️  Procesando mapa: {map_id} ---")

        try:
            # Navegación a la página principal
            print(f"➡️  Navegando a {START_URL}")
            await page.goto(START_URL, {"waitUntil": "networkidle0"})

            # Selección del mapa
            print(f"🖱️  Haciendo clic en el enlace del mapa '{map_id}'")
            map_link_selector = f"a[href*='{map_id}']"
            await page.waitForSelector(map_link_selector)
            await page.click(map_link_selector)

            # Espera y descarga del GIF
            print("⏳ Esperando el botón 'Download Loop'...")
            download_button_selector = 'input[value="Download Loop"]'
            await page.waitForSelector(download_button_selector)
            await page.click(download_button_selector)
            print("🖱️  Clic en 'Download Loop'. Generando animación...")

            # Espera activa hasta que el GIF (como Data URL) se cargue en la página
            gif_image_selector = 'img[src^="data:image/gif;base64,"]'
            print("⏳ Esperando que el GIF sea generado por el servidor...")
            await page.waitForSelector(
                gif_image_selector, {"timeout": 120000}
            )  # Timeout de 2 minutos

            # Extraer el código Base64 del GIF
            gif_base64_data = await page.evaluate(
                f'() => document.querySelector("{gif_image_selector}").src'
            )
            print("📥 GIF generado y encontrado en la página.")

            # Decodificar y guardar el archivo .gif
            header, encoded = gif_base64_data.split(",", 1)
            gif_data = base64.b64decode(encoded)
            gif_filename = f"{map_id.replace('/', '_')}.gif"
            gif_path = os.path.join(OUTPUT_DIR, gif_filename)
            with open(gif_path, "wb") as f:
                f.write(gif_data)
            print(f"💾 GIF guardado como: {gif_path}")

            # Conversión a MP4
            mp4_path = gif_path.replace(".gif", ".mp4")
            if convert_gif_to_mp4(gif_path, mp4_path):
                # Envío a Telegram
                send_video_to_telegram(mp4_path, map_caption)

        except Exception as e:
            print(f"❌ Ocurrió un error procesando el mapa '{map_id}': {e}")
            print("Continuando con el siguiente mapa...")
            continue  # Pasa al siguiente mapa en la lista

    # 3. Finalización
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
