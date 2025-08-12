import os
import shutil
import subprocess
import requests
import re
from urllib.parse import urljoin

# --- CONFIGURACIÓN PRINCIPAL ---
BASE_URL = "https://rammb.cira.colostate.edu/ramsdis/online/"
OUTPUT_DIR = "final_videos"
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

# --- FUNCIONES ---


def send_video_to_telegram(video_path, caption):
    """Envía un video a un chat de Telegram."""
    print(f"🚀 Enviando video a Telegram: '{caption}'")
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Error: Variables de Telegram no configuradas.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
    try:
        with open(video_path, "rb") as video_file:
            files = {"video": (os.path.basename(video_path), video_file)}
            data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
            response = requests.post(url, files=files, data=data, timeout=120)
            response.raise_for_status()
            if response.json().get("ok"):
                print("✅ ¡Video enviado con éxito!")
            else:
                print(f"❌ Error en la respuesta de Telegram: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Error al enviar la petición a Telegram: {e}")


def create_video_from_images(image_folder, mp4_path):
    """Usa FFmpeg para crear un video a partir de una secuencia de imágenes."""
    print("🎬 Creando video MP4 desde las imágenes descargadas...")
    input_file_path = os.path.join(image_folder, "input.txt")

    # Crear el archivo input.txt para ffmpeg
    with open(input_file_path, "w") as f:
        # Obtener la lista de archivos de imagen y ordenarlos
        image_files = sorted(
            [img for img in os.listdir(image_folder) if img.endswith((".gif", ".jpg"))]
        )
        for image_file in image_files:
            f.write(f"file '{image_file}'\n")
            f.write("duration 0.2\n")  # Duración de cada frame

    # Comando FFmpeg para unir las imágenes
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
        print("✅ Video creado con éxito.")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"❌ Error durante la creación del video con FFmpeg: {e}")
        return False


def main():
    """Función principal del bot."""
    if os.path.exists(OUTPUT_DIR):
        shutil.rmtree(OUTPUT_DIR)
    os.makedirs(OUTPUT_DIR)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
    }

    for map_info in MAPS_TO_PROCESS:
        map_id = map_info["id"]
        map_caption = map_info["caption"]
        print(f"\n--- 🗺️  Procesando mapa: {map_id} ---")

        try:
            # 1. Construir la URL de la página de animación
            loop_page_url = urljoin(BASE_URL, f"loop.asp?data_folder={map_id}")
            print(f"➡️  Descargando HTML desde: {loop_page_url}")

            # 2. Descargar el HTML y extraer la lista de imágenes
            response = requests.get(loop_page_url, headers=headers, timeout=30)
            response.raise_for_status()

            image_urls = re.findall(
                r"G_vDynamicImageList\[\d+\]\.src = '(.*?)';", response.text
            )
            if not image_urls:
                print(
                    f"❌ No se encontró la lista de imágenes para el mapa {map_id}. Saltando..."
                )
                continue

            print(f"✅ Se encontraron {len(image_urls)} imágenes en la secuencia.")

            # 3. Descargar cada imagen de la secuencia
            temp_image_folder = os.path.join(OUTPUT_DIR, map_id.replace("/", "_"))
            os.makedirs(temp_image_folder)
            print(f"📥 Descargando imágenes en '{temp_image_folder}'...")

            for i, img_url in enumerate(image_urls):
                full_img_url = urljoin(BASE_URL, img_url.lstrip("/"))
                img_response = requests.get(full_img_url, headers=headers, timeout=20)
                file_ext = os.path.splitext(img_url)[1]
                with open(
                    os.path.join(temp_image_folder, f"{i:03d}{file_ext}"), "wb"
                ) as f:
                    f.write(img_response.content)

            # 4. Crear el video MP4 a partir de las imágenes descargadas
            mp4_path = os.path.join(OUTPUT_DIR, f"{map_id.replace('/', '_')}.mp4")
            if create_video_from_images(temp_image_folder, mp4_path):
                # 5. Enviar el video a Telegram
                send_video_to_telegram(mp4_path, map_caption)

            # 6. Limpiar la carpeta de imágenes temporales
            shutil.rmtree(temp_image_folder)

        except requests.exceptions.RequestException as e:
            print(f"❌ Error de red procesando el mapa '{map_id}': {e}")
            continue
        except Exception as e:
            print(f"❌ Ocurrió un error inesperado procesando el mapa '{map_id}': {e}")
            continue

    print("\n--- ✅ Proceso completado para todos los mapas ---")


if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("🚨 ERROR CRÍTICO: Variables de entorno de Telegram no definidas.")
    else:
        main()
