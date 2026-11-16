"""La carga de un cliente con Locust (capa_cliente/locustfile.py) contra el sistema completo."""
import csv
import subprocess
import sys

from config import configuracion as config


def test_un_cliente_de_locust_envia_al_ritmo_y_recibe_las_notificaciones(sistema, tmp_path):
    salida = tmp_path / "cliente_5.csv"
    resultado = subprocess.run(
        [sys.executable, "-m", "locust", "-f", "capa_cliente/locustfile.py", "--headless", "-u", "1", "-r", "1",
         "-t", "6s", "--only-summary", "--id-cliente", "5", "--por-minuto", "120", "--consultas", "20",
         "--cancelaciones", "50", "--semilla", "1", "--salida", str(salida)],
        cwd=config.RAIZ, capture_output=True, text=True, timeout=30)

    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    with open(salida, newline="", encoding="utf-8") as archivo:
        filas = list(csv.DictReader(archivo))
    assert 8 <= len(filas) <= 14                                        # 120 por minuto durante 6 s: unas 12
    assert all(f["estado"] != "ERROR" for f in filas)
    cancelaciones = sum(f["tipo"] == "CANCELACION" for f in filas)
    assert cancelaciones > 0
    assert resultado.stdout.count("NOTIFICACION") == cancelaciones      # llegaron todas las notificaciones
