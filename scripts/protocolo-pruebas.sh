#!/usr/bin/env bash
# Protocolo de pruebas automaticas del SRB.
# Ejecuta, en orden, las pruebas de pytest de la carpeta pruebas/ y muestra un resumen
# PASA / FALLA por tipo de prueba:
#   1. Unitarias                    2. Integracion y funcionales
#   3. Concurrencia y consistencia  4. Seguridad basica
#   5. Tolerancia a fallas
# Las pruebas arrancan sus propios procesos en este computador (127.0.0.1), en otros
# puertos y con una base de datos aparte (datos/pruebas.db): no tocan un sistema en marcha.
# Las pruebas de rendimiento, escalabilidad y despliegue se hacen en las tres maquinas
# (seccion "Medicion del rendimiento" del README).
#
# Uso, desde la carpeta del proyecto:   bash scripts/protocolo-pruebas.sh
# Con uv:                               PYTHON="uv run python" bash scripts/protocolo-pruebas.sh

set -u
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python3}"

VERDE=$'\e[32m'; ROJO=$'\e[31m'; AZUL=$'\e[1;34m'; NORMAL=$'\e[0m'
RESUMEN=()
FALLAS=0

probar() {  # probar "titulo" argumentos de pytest...
    local titulo="$1"; shift
    echo; echo "${AZUL}=== $titulo ===${NORMAL}"
    if $PYTHON -m pytest -q "$@"; then
        RESUMEN+=("${VERDE}PASA${NORMAL}  $titulo")
    else
        RESUMEN+=("${ROJO}FALLA${NORMAL} $titulo"); FALLAS=$((FALLAS + 1))
    fi
}

probar "1. Unitarias: mensajes, base de datos y logica de los servicios" \
    pruebas/test_mensajes.py pruebas/test_bd.py pruebas/test_servicios.py
probar "2. Integracion y funcionales: consulta, reserva, modificacion y cancelacion con notificacion" \
    pruebas/test_sistema.py -k "caso_basico or consulta or reserva or cancelacion"
probar "3. Concurrencia y consistencia: varios clientes por los ultimos asientos" \
    pruebas/test_sistema.py -k "compiten"
probar "4. Seguridad basica: mensajes mal formados y datos invalidos" \
    pruebas/test_sistema.py -k "mal_formados"
probar "5. Tolerancia a fallas: caida del GT, de un RMC, de Cancelaciones y de la replica" \
    pruebas/test_fallas.py

echo; echo "${AZUL}=== Resumen del protocolo ===${NORMAL}"
for linea in "${RESUMEN[@]}"; do echo "$linea"; done
exit "$FALLAS"
