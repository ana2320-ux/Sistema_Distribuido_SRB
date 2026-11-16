#!/usr/bin/env bash
# Construye la imagen srb:2 y la guarda en srb.tar, en la carpeta del proyecto (compartida por NFS).
# Se ejecuta en una máquina con docker; luego se importa en cada nodo.
set -e
cd "$(dirname "$0")/.."
docker build -t srb:2 .
docker save srb:2 -o srb.tar
echo "Imagen guardada en srb.tar. En cada nodo (máquinas 1, 2 y 3):"
echo "  sudo k3s ctr images import srb.tar"
