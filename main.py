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
# Cargar variables de entorno desde un archivo .env (para desarrollo local)
# En Railway, estas variables se configuran en el panel del proyecto.
load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# URLs y rutas de archivos
INITIAL_URL = (
    "https://rammb.cira.colostate.edu/ramsdis/online/rmtc.asp#Central_and_South_America"
)
GIF_PATH = "downloaded_loop.gif"
VIDEO_PATH = "final_video.mp4"


def setup_driver():
    """Configura el driver de Selenium para ejecutarse en modo headless en un contenedor."""
    options = webdriver.ChromeOptions()
    # Opciones clave para correr en Railway/Docker
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("window-size=1280x800")

    # Railway/Docker usualmente provee chromedriver en /usr/bin/chromedriver
    # Si no, se necesita especificar la ruta con ChromeService
    service = ChromeService()
    driver = webdriver.Chrome(service=service, options=options)
    print("WebDriver configurado exitosamente.")
    return driver


def download_gif(driver):
    """Navega el sitio web, realiza los clics y descarga el GIF."""
    try:
        driver.get(INITIAL_URL)
        print(f"Navegando a: {INITIAL_URL}")

        # Guardar la ventana principal
        original_window = driver.current_window_handle

        # --- Clic en "HTML5 Loop" ---
        print("Buscando el enlace 'HTML5 Loop'...")
        html5_loop_link = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.PARTIAL_LINK_TEXT, "HTML5 Loop"))
        )
        html5_loop_link.click()
        print("Clic en 'HTML5 Loop' realizado.")

        # Esperar a que la nueva pestaña se abra y cambiar a ella
        WebDriverWait(driver, 10).until(EC.number_of_windows_to_be(2))
        for window_handle in driver.window_handles:
            if window_handle != original_window:
                driver.switch_to.window(window_handle)
                break

        print(f"Cambiado a la nueva pestaña: {driver.title}")

        # --- Clic en "Download Loop" ---
        print("Buscando el botón de descarga...")
        download_button = WebDriverWait(driver, 20).until(
            EC.element_to_be_clickable((By.ID, "downloadLoop"))
        )
        download_button.click()
        print("Clic en el botón de descarga realizado.")

        # Esperar 15 segundos para que la nueva ventana con el GIF se genere y abra
        print("Esperando 15 segundos para la generación del GIF...")
        time.sleep(15)

        # Esperar a que la tercera ventana (la del GIF) se abra y cambiar a ella
        WebDriverWait(driver, 20).until(EC.number_of_windows_to_be(3))
        gif_window_handle = [
            wh
            for wh in driver.window_handles
            if wh not in [original_window, driver.current_window_handle]
        ][0]
        driver.switch_to.window(gif_window_handle)
        print(f"Cambiado a la ventana del GIF: {driver.title}")

        # --- Descargar el GIF desde la etiqueta <img> con datos Base64 ---
        print("Localizando la imagen GIF (Base64)...")
        gif_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (By.XPATH, "//div[@id='animatedGifWrapper']/img")
            )
        )

        base64_src = gif_element.get_attribute("src")
        # El string es "data:image/gif;base64,R0lGODlhgALgAQA..."
        # Necesitamos remover el prefijo para obtener solo los datos base64
        base64_data = base64_src.split(",", 1)[1]

        print("Decodificando y guardando el archivo GIF...")
        with open(GIF_PATH, "wb") as f:
            f.write(base64.b64decode(base64_data))

        print(f"GIF guardado exitosamente en: {GIF_PATH}")
        return True

    except (TimeoutException, NoSuchElementException) as e:
        print(f"Error durante el scraping: {e}")
        # Tomar una captura de pantalla para depuración
        driver.save_screenshot("error_screenshot.png")
        return False
    finally:
        driver.quit()
        print("WebDriver cerrado.")


def convert_gif_to_mp4():
    """Convierte el archivo GIF descargado a un video MP4."""
    try:
        print(f"Iniciando conversión de {GIF_PATH} a {VIDEO_PATH}...")
        with imageio.get_reader(GIF_PATH) as reader:
            # Usar FFMPEG que es bueno para compatibilidad
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
                caption="Aquí está el video más reciente del satélite GOES-East - GeoColor.",
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
            os.remove(file_path)
            print(f"Archivo eliminado: {file_path}")


# --- FUNCIÓN PRINCIPAL ---
if __name__ == "__main__":
    import asyncio

    cleanup_files()  # Limpiar archivos de una ejecución anterior

    driver = setup_driver()
    if download_gif(driver):
        if convert_gif_to_mp4():
            asyncio.run(send_video_telegram())

    cleanup_files()  # Limpiar al final
    print("Proceso finalizado.")
