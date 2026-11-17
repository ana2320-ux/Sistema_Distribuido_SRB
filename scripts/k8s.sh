#!/usr/bin/env bash
# Despliegue del SRB en Kubernetes (k3s), desde la carpeta del proyecto (compartida por NFS).
# Usa las IP del .env: HOST_CAPA_SERVICIOS es el servidor de k3s (máquina 2).
#
#   Máquina 2:        bash scripts/k8s.sh servidor     instala k3s y deja el token en k8s/.token
#   Máquinas 1 y 3:   bash scripts/k8s.sh agente       se unen al clúster con ese token
#   Máquina 2:        bash scripts/k8s.sh desplegar    etiqueta los nodos, instala las librerías,
#                                                      aplica k8s/ y carga la base de datos
#   Máquina 2:        bash scripts/k8s.sh borrar       quita el SRB del clúster (k3s queda instalado)
#
# No hace falta construir una imagen: los contenedores usan python:3.12-slim con esta carpeta
# montada en /app y las librerías en k8s/libs.
set -euo pipefail
cd "$(dirname "$0")/.."
eval "$(grep -E '^HOST_CAPA_[A-Z]+=' .env)"
kubectl() { sudo k3s kubectl "$@"; }

case "${1:-}" in
servidor)
    curl -sfL https://get.k3s.io | sh -
    sudo cat /var/lib/rancher/k3s/server/node-token > k8s/.token
    echo "Servidor listo. Ahora, en las máquinas 1 y 3: bash scripts/k8s.sh agente"
    ;;
agente)
    curl -sfL https://get.k3s.io | K3S_URL="https://$HOST_CAPA_SERVICIOS:6443" K3S_TOKEN="$(cat k8s/.token)" sh -
    ;;
desplegar)
    # Una capa por nodo: se etiqueta cada nodo según su IP en el .env
    kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name} {.status.addresses[?(@.type=="InternalIP")].address}{"\n"}{end}' |
    while read -r nodo ip; do
        case "$ip" in
            "$HOST_CAPA_CONSUMIDORES") capa=consumidores ;;
            "$HOST_CAPA_SERVICIOS")    capa=negocio ;;
            "$HOST_CAPA_PERSISTENCIA") capa=almacenamiento ;;
            *) echo "Nodo $nodo ($ip) no está en el .env; se deja sin capa"; continue ;;
        esac
        kubectl label node "$nodo" capa=$capa --overwrite < /dev/null
    done
    # Librerías de Python 3.12 para los contenedores (una sola vez; quedan en la carpeta NFS)
    [ -d k8s/libs ] || uv pip install --quiet --python-version 3.12 --python-platform x86_64-manylinux_2_28 \
                          --target k8s/libs pyzmq python-dotenv locust
    mkdir -p resultados && chmod 777 resultados    # en NFS, root de los contenedores escribe como nobody
    kubectl apply -f k8s/
    kubectl -n srb wait --for=condition=available deployment --all --timeout=300s
    kubectl -n srb exec deploy/persistencia -c principal -- python -m capa_persistencia.cargar_datos
    kubectl -n srb get pods -o wide
    ;;
borrar)
    kubectl delete namespace srb
    ;;
*)
    sed -n '2,12p' "$0"
    exit 1
    ;;
esac
