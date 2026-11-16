# Imagen única del SRB: la misma para todas las capas; cada Deployment elige el comando.
FROM python:3.12-slim
RUN pip install --no-cache-dir pyzmq python-dotenv locust
WORKDIR /app
COPY . .
ENV PYTHONUNBUFFERED=1
