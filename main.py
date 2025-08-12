# main.py

import os
import time
import base64
import imageio
import telegram
from dotenv import load_dotenv

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --- 1. CONFIGURACIÓN ---
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
INITIAL_URL = (
    "https://rammb.cira.colostate.edu/ramsdis/online/rmtc.asp#Central_and_South_America"
)
GIF_PATH = "downloaded_loop.gif"
VIDEO_PATH = "final_video.mp4"


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


def download_gif(driver):
    """Navega el sitio web, realiza los clics y descarga el GIF."""
    try:
        # --- PASO 1: Ir a la página inicial ---
        driver.get(INITIAL_URL)
        print(f"Navegando a: {INITIAL_URL}")

        # --- PASO 2: Clic en 'HTML5 Loop' ---
        print("Buscando y haciendo clic en 'HTML5 Loop'...")
        WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "HTML5 Loop"))
        ).click()
        print("Clic en 'HTML5 Loop' realizado. Ahora en la página del visor.")

        # --- PASO 3: Clic en 'Download Loop' ---
        print("Buscando y haciendo clic en 'Download Loop'...")
        WebDriverWait(driver, 30).until(
            EC.element_to_be_clickable((By.ID, "downloadLoop"))
        ).click()
        print(
            "Clic en 'Download Loop' realizado. Esperando que el GIF aparezca en la página actual..."
        )

        # --- PASO 4: ESPERAR POR LA IMAGEN CON LOS DATOS BASE64 ---
        # Este es el ajuste final y definitivo. Esperamos por la imagen que
        # ya tenga en su 'src' el texto 'data:image/gif;base64,'.
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

        # --- PASO 5: Extraer y guardar ---
        # Ahora esta parte es 100% segura
        base64_src = gif_element.get_attribute("src")
        base64_data = base64_src.split(",", 1)[1]

        print("Decodificando y guardando el archivo GIF...")
        with open(GIF_PATH, "wb") as f:
            f.write(base64.b64decode(base64_data))

        print(f"GIF guardado exitosamente en: {GIF_PATH}")
        return True

    except TimeoutException:
        print("\n--- ERROR: TIEMPO DE ESPERA AGOTADO ---")
        print("El script no encontró un elemento en el tiempo asignado (Timeout).")
        print(f"URL al momento del error: {driver.current_url}")
        print(f"Título de la página: '{driver.title}'")
        print("Guardando captura de pantalla como 'error_screenshot.png'")
        driver.save_screenshot("error_screenshot.png")
        return False
    except Exception as e:
        print(f"\n--- ERROR INESPERADO DURANTE EL SCRAPING ---")
        print(f"Error: {e.__class__.__name__} - {e}")
        print("Guardando captura de pantalla como 'error_screenshot.png'")
        driver.save_screenshot("error_screenshot.png")
        return False
    finally:
        if driver:
            driver.quit()
            print("WebDriver cerrado.")


def convert_gif_to_mp4():
    """Convierte el archivo GIF descargado a un video MP4."""
    try:
        print(f"Iniciando conversión de {GIF_PATH} a {VIDEO_PATH}...")
        with imageio.get_reader(GIF_PATH) as reader:
            with imageio.get_writer(
                VIDEO_PATH, format="FFMPEG", mode="I", fps=10, codec="libx264"
            ) as writer:
                for frame in reader:
                    writer.append_data(frame)
        print("Conversión a MP4 completada.")
        return True
    except Exception as e:
        print(f"Error convirtiendo GIF a MP4: {e}")
        return False


async def send_video_telegram():
    """Envía el video MP4 a través del bot de Telegram."""
    if not all([TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID]):
        print("Error: Las variables de entorno de Telegram no están configuradas.")
        return
    try:
        print("Preparando para enviar video por Telegram...")
        bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
        async with bot:
            await bot.send_video(
                chat_id=TELEGRAM_CHAT_ID,
                video=open(VIDEO_PATH, "rb"),
                caption="Aquí está el video más reciente del satélite GOES-East.",
                connect_timeout=30,
                read_timeout=30,
            )
        print("Video enviado a Telegram exitosamente.")
    except Exception as e:
        print(f"Error al enviar el video por Telegram: {e}")


def cleanup_files():
    """Elimina los archivos temporales."""
    print("Limpiando archivos locales...")
    for file_path in [GIF_PATH, VIDEO_PATH, "error_screenshot.png"]:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Archivo eliminado: {file_path}")
            except OSError as e:
                print(f"Error eliminando archivo {file_path}: {e}")


# --- FUNCIÓN PRINCIPAL ---
if __name__ == "__main__":
    import asyncio

    cleanup_files()

    driver_instance = setup_driver()
    if driver_instance:
        if download_gif(driver_instance):
            if convert_gif_to_mp4():
                asyncio.run(send_video_telegram())

    cleanup_files()
    print("Proceso finalizado.")
