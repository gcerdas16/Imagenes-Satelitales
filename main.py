# main.py

import os
import time
import base64
import imageio
import telegram
import asyncio
from dotenv import load_dotenv

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# --- 1. CONFIGURACIÓN ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
INITIAL_URL = (
    "https://rammb.cira.colostate.edu/ramsdis/online/rmtc.asp#Central_and_South_America"
)

# --- LISTA DE MAPAS A PROCESAR ---
MAPS_TO_PROCESS = [
    {
        "link_text": "Costa Rica 1 km Visible",
        "output_filename": "costa_rica_visible_1km",
        "caption": "Video del Satélite: Costa Rica 1 km Visible",
    },
    {
        "link_text": "Costa Rica 2 km Visible",
        "output_filename": "costa_rica_visible_2km",
        "caption": "Video del Satélite: Costa Rica 2 km Visible",
    },
    {
        "link_text": "Costa Rica 2 km Short Wave - IR2",
        "output_filename": "costa_rica_ir2_2km",
        "caption": "Video del Satélite: Costa Rica 2 km Short Wave - IR2",
    },
    {
        "link_text": "Costa Rica 2 km Thermal Infrared - IR4",
        "output_filename": "costa_rica_ir4_2km",
        "caption": "Video del Satélite: Costa Rica 2 km Thermal Infrared - IR4",
    },
]


def setup_driver():
    """Configura el driver de Selenium."""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1280x1024")

    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=options)
    print("WebDriver configurado exitosamente.")
    return driver


def download_gif(driver, map_info):
    """Navega el sitio web, realiza los clics y descarga el GIF para un mapa específico."""
    link_text_to_find = map_info["link_text"]
    gif_path = f"{map_info['output_filename']}.gif"

    try:
        driver.get(INITIAL_URL)
        print(f"Navegando a: {INITIAL_URL}")

        print(f"Buscando el enlace para '{link_text_to_find}'...")
        map_link_xpath = f"//h3[text()='{link_text_to_find}']/following-sibling::a[1]"

        # --- AJUSTE CLAVE AQUÍ ---
        # 1. Esperamos solo a que el elemento esté PRESENTE en el código, no necesariamente clickeable.
        map_link_element = WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.XPATH, map_link_xpath))
        )
        # 2. Usamos JavaScript para forzar el clic. Esto evita errores de "elemento no interactuable".
        driver.execute_script("arguments[0].click();", map_link_element)

        print(f"Clic en '{link_text_to_find}' realizado. Ahora en la página del visor.")

        print("Buscando y haciendo clic en 'Download Loop'...")
        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "downloadLoop"))
        ).click()
        print("Clic en 'Download Loop' realizado. Esperando que el GIF aparezca...")

        print(
            "Esperando que la imagen del GIF con datos Base64 se cargue completamente..."
        )
        img_locator = (
            By.XPATH,
            "//div[@id='animatedGifWrapper']/img[starts-with(@src, 'data:image/gif;base64,')]",
        )

        gif_element = WebDriverWait(driver, 90).until(
            EC.presence_of_element_located(img_locator)
        )
        print("¡Imagen GIF con Base64 encontrada y completamente cargada!")

        base64_src = gif_element.get_attribute("src")
        base64_data = base64_src.split(",", 1)[1]

        print(f"Decodificando y guardando en: {gif_path}")
        with open(gif_path, "wb") as f:
            f.write(base64.b64decode(base64_data))

        print(f"GIF guardado exitosamente.")
        return True

    except TimeoutException:
        print(f"\n--- ERROR (TIMEOUT) en el mapa '{link_text_to_find}' ---")
        print("No se encontró un elemento a tiempo.")
        driver.save_screenshot(f"error_{map_info['output_filename']}.png")
        return False
    except Exception as e:
        print(f"\n--- ERROR INESPERADO en el mapa '{link_text_to_find}' ---")
        print(f"Error: {e.__class__.__name__} - {e}")
        driver.save_screenshot(f"error_{map_info['output_filename']}.png")
        return False


def convert_gif_to_mp4(map_info):
    """Convierte el archivo GIF descargado a un video MP4."""
    gif_path = f"{map_info['output_filename']}.gif"
    video_path = f"{map_info['output_filename']}.mp4"

    try:
        print(f"Iniciando conversión de {gif_path} a {video_path}...")
        with imageio.get_reader(gif_path) as reader:
            with imageio.get_writer(
                video_path, format="FFMPEG", mode="I", fps=10, codec="libx264"
            ) as writer:
                for frame in reader:
                    writer.append_data(frame)
        print("Conversión a MP4 completada.")
        return True
    except Exception as e:
        print(f"Error convirtiendo GIF a MP4: {e}")
        return False


async def send_video_telegram(map_info):
    """Envía el video MP4 a través del bot de Telegram."""
    video_path = f"{map_info['output_filename']}.mp4"
    caption = map_info["caption"]

    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Error: Las variables de entorno de Telegram no están configuradas.")
        return
    try:
        print(f"Preparando para enviar '{caption}' por Telegram...")
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        async with bot:
            await bot.send_video(
                chat_id=TELEGRAM_CHAT_ID,
                video=open(video_path, "rb"),
                caption=caption,
                connect_timeout=30,
                read_timeout=30,
            )
        print("Video enviado a Telegram exitosamente.")
    except Exception as e:
        print(f"Error al enviar el video por Telegram: {e}")


def cleanup_files(map_info):
    """Elimina los archivos temporales para un mapa específico."""
    print(f"Limpiando archivos para '{map_info['output_filename']}'...")
    gif_path = f"{map_info['output_filename']}.gif"
    video_path = f"{map_info['output_filename']}.mp4"
    error_screenshot = f"error_{map_info['output_filename']}.png"

    for file_path in [gif_path, video_path, error_screenshot]:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Archivo eliminado: {file_path}")
            except OSError as e:
                print(f"Error eliminando archivo {file_path}: {e}")


async def main():
    for map_data in MAPS_TO_PROCESS:
        print(f"\n{'=' * 50}")
        print(f"PROCESANDO MAPA: {map_data['caption']}")
        print(f"{'=' * 50}")

        driver = None
        try:
            driver = setup_driver()
            if driver:
                if download_gif(driver, map_data):
                    if convert_gif_to_mp4(map_data):
                        await send_video_telegram(map_data)
        finally:
            if driver:
                driver.quit()
                print("WebDriver cerrado.")
            cleanup_files(map_data)
            print(f"\n--- Fin del procesamiento para: {map_data['caption']} ---")


if __name__ == "__main__":
    asyncio.run(main())
    print("\nPROCESO COMPLETO DE TODOS LOS MAPAS HA FINALIZADO.")
