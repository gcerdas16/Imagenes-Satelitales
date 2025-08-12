# Dockerfile - Método Robusto con el Repositorio Oficial de Google

# 1. Usar una imagen base de Python robusta para evitar problemas de espacio
FROM python:3.10

# 2. Establecer el directorio de trabajo
WORKDIR /app

# 3. Instalar dependencias del sistema y configurar el repositorio de Google Chrome
RUN apt-get update && apt-get install -y \
    # Dependencias necesarias para Chrome
    ca-certificates \
    curl \
    gnupg \
    unzip \
    ffmpeg \
    --no-install-recommends \
    # Configurar el repositorio oficial de Google Chrome
    && curl -fsSL https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome-keyring.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome-keyring.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    \
    # Actualizar la lista de paquetes e instalar Chrome y Chromedriver
    && apt-get update \
    && apt-get install -y \
    google-chrome-stable \
    # Limpiar para mantener la imagen pequeña
    && rm -rf /var/lib/apt/lists/*

# 4. Encontrar la versión de Chromedriver que corresponda a Google Chrome Stable
#    Este paso ahora es mucho más simple porque ambos se instalan desde el mismo lugar
#    Normalmente, ya se coloca en una ruta accesible, pero nos aseguramos
RUN LATEST_CHROMEDRIVER_VERSION=$(curl -sS https://googlechromelabs.github.io/chrome-for-testing/LATEST_RELEASE_STABLE) \
    && wget -q https://storage.googleapis.com/chrome-for-testing-public/${LATEST_CHROMEDRIVER_VERSION}/linux64/chromedriver-linux64.zip \
    && unzip chromedriver-linux64.zip \
    && mv -f chromedriver-linux64/chromedriver /usr/bin/chromedriver \
    && rm chromedriver-linux64.zip && rm -rf chromedriver-linux64

# 5. Copiar e instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copiar el resto del código
COPY . .

# 7. Comando para ejecutar la aplicación
CMD ["python", "main.py"]