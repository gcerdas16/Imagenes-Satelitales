import os
import shutil
import asyncio
import subprocess
from urllib.parse import urljoin
from pyppeteer import launch
import requests  # Importamos requests para las descargas

# --- CONFIGURACIÓN PRINCIPAL ---
BASE_URL = "https://rammb.cira.colostate.edu"
OUTPUT_DIR = "final_videos"
# Lista corregida y funcional
MAPS_TO_PROCESS = [
    {
        "id": "rmtc/rmtccosvis1",
        "caption": "🛰️ Animación Satelital (Canal Visible) - Costa Rica",
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


# --- FUNCIONES AUXILIARES ---
def create_video_from_images(image_folder, mp4_path):
    """Usa FFmpeg para crear un video a partir de una secuencia de imágenes."""
    print("🎬 Creando video MP4 desde las imágenes...")
    input_file_path = os.path.join(image_folder, "input.txt")
    image_files = sorted(
        [img for img in os.listdir(image_folder) if img.endswith((".gif", ".jpg"))]
    )

    with open(input_file_path, "w") as f:
        for image_file in image_files:
            f.write(f"file '{image_file}'\n")
            f.write("duration 0.2\n")  # Duración de 0.2 segundos por frame

    command = [
        "ffmpeg",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        input_file_path,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-vf",
        "scale=trunc(iw/2)*2:trunc(ih/2)*2",
        "-y",
        mp4_path,
    ]
    try:
        subprocess.run(
            command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"❌ Error creando video con FFmpeg: {e}")
        return False


def send_video_to_telegram(video_path, caption):
    """Envía un video a Telegram."""
    print(f"🚀 Enviando video a Telegram: '{caption}'")
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    try:
        with open(video_path, "rb") as video_file:
            files = {"video": (os.path.basename(video_path), video_file)}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            requests.post(url, files=files, data=data, timeout=120).raise_for_status()
            print("✅ ¡Video enviado con éxito!")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar a Telegram: {e}")


async def generate_all_videos():
    """Función principal con la estrategia de extracción de datos."""
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    browser = await launch(
        headless=True,
        executablePath="/usr/bin/chromium",
        args=["--no-sandbox", "--disable-setuid-sandbox"],
    )

    for map_info in MAPS_TO_PROCESS:
        map_id = map_info["id"]
        map_caption = map_info["caption"]
        page = None
        print(f"\n--- 🗺️  Procesando mapa: {map_id} ---")

        try:
            page = await browser.newPage()
            await page.setViewport({"width": 1920, "height": 1080})

            # 1. NAVEGAR A LA PÁGINA DE ANIMACIÓN
            loop_page_url = f"{BASE_URL}/ramsdis/online/loop.asp?data_folder={map_id}"
            print(f"➡️  Navegando a: {loop_page_url}")
            await page.goto(
                loop_page_url, {"waitUntil": "networkidle0", "timeout": 60000}
            )

            # 2. EXTRAER LA LISTA DE IMÁGENES DEL JAVASCRIPT (LA CLAVE)
            print("🔎 Extrayendo lista de imágenes desde el JavaScript de la página...")
            # Esperamos a que la variable G_vDynamicImageList exista en la página
            await page.waitForFunction(
                '() => typeof G_vDynamicImageList !== "undefined" && G_vDynamicImageList.length > 0',
                {"timeout": 30000},
            )

            # Una vez que existe, la extraemos
            relative_urls = await page.evaluate(
                "() => G_vDynamicImageList.map(img => img.src)"
            )

            if not relative_urls:
                raise Exception("La lista de imágenes está vacía o no se pudo extraer.")

            print(f"✅ Se extrajeron {len(relative_urls)} URLs de imágenes.")
            # Ya no necesitamos la página, la cerramos para liberar memoria
            await page.close()
            page = None

            # 3. DESCARGAR LAS IMÁGENES CON REQUESTS (MÁS RÁPIDO)
            temp_image_folder = os.path.join(OUTPUT_DIR, map_id.replace("/", "_"))
            os.makedirs(temp_image_folder)
            print(f"📥 Descargando imágenes...")
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
            }

            for i, rel_url in enumerate(relative_urls):
                # La URL en la variable a veces no tiene el dominio, lo añadimos
                full_img_url = urljoin(BASE_URL, rel_url)
                img_response = requests.get(full_img_url, headers=headers, timeout=20)
                file_ext = os.path.splitext(rel_url)[1] or ".gif"
                with open(
                    os.path.join(temp_image_folder, f"{i:03d}{file_ext}"), "wb"
                ) as f:
                    f.write(img_response.content)

            # 4. CREAR VIDEO Y ENVIAR
            mp4_path = os.path.join(OUTPUT_DIR, f"{map_id.replace('/', '_')}.mp4")
            if create_video_from_images(temp_image_folder, mp4_path):
                send_video_to_telegram(mp4_path, map_caption)

            shutil.rmtree(temp_image_folder)

        except Exception as e:
            print(f"❌ Ocurrió un error procesando el mapa '{map_id}': {e}")
            if page:
                await page.close()  # Asegurarse de cerrar la página en caso de error
            continue

    print("\n--- ✅ Proceso completado para todos los mapas ---")
    await browser.close()
    print("🖥️  Navegador cerrado.")


if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("🚨 ERROR CRÍTICO: Variables de entorno de Telegram no definidas.")
    else:
        # En Python 3.7+ se puede usar asyncio.run() que es más simple
        asyncio.run(generate_all_videos())
