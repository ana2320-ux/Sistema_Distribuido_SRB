#!/usr/bin/env bash
# QUÉ HACE: todo el experimento de la Tabla 1 con un solo comando, sobre Kubernetes.
#   1. Despliega el SRB en el clúster (bash scripts/k8s.sh desplegar).
#   2. Mide la arquitectura BASE: 1 RMC que consulta en el servicio principal (sin réplica de lectura).
#   3. Mide la arquitectura ESCALABLE: 3 RMC que consultan en la réplica de lectura.
#      En cada una corre los escenarios 1, 2 y 3 (3, 5 y 8 clientes), varias corridas, y reinicia
#      la base de datos antes de cada escenario.
#   4. Analiza los resultados: tabla en resultados/resumen.csv y gráficos en resultados/graficos/.
# DÓNDE: en la máquina 2 (servidor de k3s), desde la carpeta del proyecto, con el clúster ya
#   instalado (bash scripts/k8s.sh servidor y agente). Tarda cerca de 50 minutos con los valores por defecto.
# USO: bash scripts/k8s-medir.sh
#   Opcionales: DURACION=150 (segundos por corrida), POR_MINUTO=20, CORRIDAS=3
# En la arquitectura base el gestor de respaldo y la réplica de lectura siguen encendidos, pero no
# atienden peticiones: el respaldo solo espera y el RMC base no consulta en la réplica.
set -euo pipefail
cd "$(dirname "$0")/.."
DURACION="${DURACION:-150}"
POR_MINUTO="${POR_MINUTO:-20}"
CORRIDAS="${CORRIDAS:-3}"
k() { sudo k3s kubectl -n srb "$@"; }

rmc() {  # rmc <réplicas> <comando en JSON>: cambia el Deployment del RMC y espera a que quede listo
    k patch deploy rmc --type=json -p "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/command\",\"value\":$2}]"
    k scale deploy rmc --replicas="$1"
    k rollout status deploy rmc --timeout=300s
}

medir() {  # medir <etiqueta>
    for escenario in 1 2 3; do
        k exec deploy/persistencia -c principal -- python -m capa_persistencia.cargar_datos > /dev/null
        for corrida in $(seq 1 "$CORRIDAS"); do
            echo "[$(date +%H:%M:%S)] $1: escenario $escenario, corrida $corrida"
            k exec deploy/clientes -- python -m capa_cliente.escenarios --escenario "$escenario" --etiqueta "$1" \
                --corrida "$corrida" --duracion "$DURACION" --por-minuto "$POR_MINUTO" > /dev/null
        done
    done
}

bash scripts/k8s.sh desplegar
rmc 1 '["python","-m","capa_negocios.main","rmc"]'
medir base
rmc 3 '["python","-m","capa_negocios.main","rmc","--con-replica"]'
medir escalable
k exec deploy/persistencia -c principal -- python -m capa_persistencia.cargar_datos > /dev/null
uv run python -m herramientas.analizar_metricas
