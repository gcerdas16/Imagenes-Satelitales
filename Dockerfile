# Usa una imagen oficial de Python como base
FROM python:3.11-slim

# Establece el directorio de trabajo dentro del contenedor
WORKDIR /app

# Actualiza los paquetes e instala ffmpeg y chromium.
# El flag --no-install-recommends reduce el tamaño de la imagen.
# Luego, limpia la caché para mantener la imagen ligera.
RUN apt-get update && apt-get install -y \
    ffmpeg \
    chromium \
    --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copia el archivo de requerimientos primero para aprovechar el caché de Docker
COPY requirements.txt .

# Instala las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia el resto del código de tu aplicación al contenedor
COPY . .

# Comando que se ejecutará cuando el contenedor se inicie
CMD ["python", "bot.py"]