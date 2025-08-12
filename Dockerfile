# Dockerfile

# 1. Usar una imagen base de Python oficial
FROM python:3.10-slim

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Actualizar el sistema e instalar dependencias del sistema:
#    - wget y unzip para descargar e instalar chromedriver
#    - ffmpeg para la conversión de video
#    - chromium para tener el navegador
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    ffmpeg \
    chromium \
    # Instalar chromedriver que coincida con la versión de chromium
    && CHROMIUM_VERSION=$(apt-cache show chromium | grep Version | cut -d ' ' -f 2 | cut -d '-' -f 1) \
    && CHROME_DRIVER_VERSION=$(wget -q -O - "https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_${CHROMIUM_VERSION}" | head -n 1) \
    && echo "Instalando chromedriver versión ${CHROME_DRIVER_VERSION} para Chromium ${CHROMIUM_VERSION}" \
    && wget -q "https://storage.googleapis.com/chrome-for-testing-public/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip" \
    && unzip chromedriver-linux64.zip \
    && mv chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && chmod +x /usr/bin/chromedriver \
    # Limpiar para reducir el tamaño de la imagen
    && rm chromedriver-linux64.zip \
    && rm -rf /var/lib/apt/lists/*

# 4. Copiar el archivo de requerimientos e instalar las dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copiar el resto del código de la aplicación al contenedor
COPY . .

# 6. Comando para ejecutar la aplicación cuando el contenedor se inicie
CMD ["python", "main.py"]