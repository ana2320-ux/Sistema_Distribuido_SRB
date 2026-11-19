#!/usr/bin/env bash
# QUÉ HACE: las corridas de rendimiento de la Tabla 1 para UNA arquitectura, con el sistema
#   levantado como procesos (sin Kubernetes). Lanza los escenarios 1, 2 y 3 (3, 5 y 8 clientes),
#   tres corridas de cada uno, y antes de cada escenario se detiene para que la base de datos se
#   reinicie a mano en la máquina 3. Para hacer todo solo y sobre Kubernetes: scripts/k8s-medir.sh
# DÓNDE: en la máquina 1 (clientes), con las máquinas 2 y 3 ya levantadas en la arquitectura que
#   se va a medir (README, sección 5.1).
# USO, desde la carpeta del proyecto:
#   bash scripts/medir.sh base          # con la arquitectura base levantada
#   bash scripts/medir.sh escalable     # con la arquitectura escalable levantada
#   Opcionales: DURACION=150 (segundos por corrida), POR_MINUTO=20, CORRIDAS=3, PYTHON="uv run python"

set -u
cd "$(dirname "$0")/.."
ETIQUETA="${1:?uso: bash scripts/medir.sh <base|escalable>}"
PYTHON="${PYTHON:-python3}"
DURACION="${DURACION:-150}"
POR_MINUTO="${POR_MINUTO:-20}"
CORRIDAS="${CORRIDAS:-3}"

for escenario in 1 2 3; do
    echo
    echo "Escenario $escenario ($ETIQUETA). Antes de seguir, la base de datos se reinicia en la maquina 3:"
    echo "    python -m capa_persistencia.cargar_datos"
    read -r -p "Enter para continuar... "
    for corrida in $(seq 1 "$CORRIDAS"); do
        $PYTHON -m capa_cliente.escenarios --escenario "$escenario" --etiqueta "$ETIQUETA" \
            --corrida "$corrida" --duracion "$DURACION" --por-minuto "$POR_MINUTO"
    done
done
echo
echo "Corridas de '$ETIQUETA' terminadas. Con el CSV del GT (maquina 2) en resultados/gt_metricas.csv:"
echo "    $PYTHON -m herramientas.analizar_metricas"
