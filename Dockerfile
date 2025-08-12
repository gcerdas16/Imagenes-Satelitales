# Dockerfile - Versión Plan B con imagen no-slim

# 1. Usar una imagen base de Python más robusta
FROM python:3.10

# 2. Establecer el directorio de trabajo dentro del contenedor
WORKDIR /app

# 3. Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    ffmpeg \
    jq \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 4. Descargar e instalar Chrome y Chromedriver
RUN LATEST_VERSIONS_URL="https://googlechromelabs.github.io/chrome-for-testing/last-known-good-versions-with-downloads.json" \
    && BROWSER_DOWNLOAD_URL=$(wget -qO- ${LATEST_VERSIONS_URL} | jq -r '.channels.Stable.downloads.chrome[?(@.platform=="linux64")].url') \
    && DRIVER_DOWNLOAD_URL=$(wget -qO- ${LATEST_VERSIONS_URL} | jq -r '.channels.Stable.downloads.chromedriver[?(@.platform=="linux64")].url') \
    \
    && echo "Descargando Chrome..." \
    && wget -q --show-progress -O chrome-linux64.zip "${BROWSER_DOWNLOAD_URL}" \
    && unzip -q chrome-linux64.zip \
    && mv chrome-linux64/* /usr/bin/ \
    && rm chrome-linux64.zip && rm -rf chrome-linux64 \
    \
    && echo "Descargando Chromedriver..." \
    && wget -q --show-progress -O chromedriver-linux64.zip "${DRIVER_DOWNLOAD_URL}" \
    && unzip -q chromedriver-linux64.zip \
    && mv chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && rm chromedriver-linux64.zip && rm -rf chromedriver-linux64

# 5. Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el resto del código
COPY . .

# 7. Comando para ejecutar la aplicación
CMD ["python", "main.py"]