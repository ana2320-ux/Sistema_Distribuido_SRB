"""
Arma el informe de pruebas y rendimiento (docs/informe/informe-segunda-entrega.docx) con los
datos de docs/informe/datos/ (resumen.csv, saturacion.csv, fallas.csv y los graficos) y los
diagramas de docs/diagramas/png/. Necesita python-docx.

Uso (desde la raiz del proyecto):   python docs/informe/generar_informe.py
Despues, en Word: actualizar las tres tablas de contenido y exportar a PDF. Sin Word (Linux, con
LibreOffice):   /usr/bin/python3 docs/informe/exportar_pdf.py
"""
import csv
from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

AQUI = Path(__file__).resolve().parent
DATOS = AQUI / "datos"
DIAGRAMAS = AQUI.parent / "diagramas" / "png"
SALIDA = AQUI / "informe-segunda-entrega.docx"

TITULO = "Informe de pruebas y rendimiento: Sistema distribuido basado en servicios para la reserva de boletos"
AUTORES = "Ana Murcia Gómez, Martín Sanmiguel Delgado, David Felipe Mannios Romero, Jhon Sebastian Mejia y Alejandro Martínez Mesa"
FUENTE = "Times New Roman"

doc = Document()
contador = {"figura": 0, "tabla": 0}


# ------------------------------------------------------------------ apoyo de formato
def quitar_tema(estilo):
    """Los titulos de la plantilla usan la fuente del tema; se quita para que valga Times New Roman."""
    rfonts = estilo.element.get_or_add_rPr().get_or_add_rFonts()
    for atributo in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        rfonts.attrib.pop(qn(f"w:{atributo}"), None)
    for nombre in ("ascii", "hAnsi", "eastAsia", "cs"):
        rfonts.set(qn(f"w:{nombre}"), FUENTE)


def preparar_estilos():
    seccion = doc.sections[0]
    seccion.page_width, seccion.page_height = Cm(21.59), Cm(27.94)          # carta
    for lado in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(seccion, lado, Cm(2.54))

    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size = FUENTE, Pt(12)
    quitar_tema(normal)
    normal.paragraph_format.space_after = Pt(0)
    normal.paragraph_format.line_spacing = 1.0

    for nombre, alineacion in (("Heading 1", WD_ALIGN_PARAGRAPH.CENTER), ("Heading 2", WD_ALIGN_PARAGRAPH.LEFT)):
        estilo = doc.styles[nombre]
        estilo.font.name, estilo.font.size, estilo.font.bold = FUENTE, Pt(12), True
        estilo.font.italic = False
        estilo.font.color.rgb = RGBColor(0, 0, 0)
        quitar_tema(estilo)
        formato = estilo.paragraph_format
        formato.alignment = alineacion
        formato.space_before, formato.space_after = Pt(12), Pt(4)
        formato.keep_with_next = True

    # numero de pagina arriba a la derecha
    encabezado = seccion.header.paragraphs[0]
    encabezado.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    campo(encabezado, "PAGE", "1")


def campo(parrafo, instruccion, provisional=""):
    """Inserta un campo de Word (PAGE, TOC, TC...). Word lo calcula al actualizar."""
    for tipo in ("begin", None, "separate", "texto", "end"):
        run = parrafo.add_run()
        if tipo is None:
            instr = OxmlElement("w:instrText")
            instr.set(qn("xml:space"), "preserve")
            instr.text = f" {instruccion} "
            run._r.append(instr)
        elif tipo == "texto":
            run.text = provisional
        else:
            marca = OxmlElement("w:fldChar")
            marca.set(qn("w:fldCharType"), tipo)
            run._r.append(marca)


def escribir(parrafo, texto, negrita=False, cursiva=False, tamano=None):
    """Agrega texto al parrafo; lo que va entre `comillas invertidas` sale en letra de codigo."""
    for i, parte in enumerate(texto.split("`")):
        if not parte:
            continue
        run = parrafo.add_run(parte)
        run.bold, run.italic = negrita, cursiva
        if tamano:
            run.font.size = Pt(tamano)
        if i % 2:                                   # dentro de comillas invertidas
            run.font.name = "Consolas"
            run._r.get_or_add_rPr().get_or_add_rFonts().set(qn("w:hAnsi"), "Consolas")
            run.font.size = Pt((tamano or 12) - 1.5)


def parrafo(texto, sangria=True, alineacion=WD_ALIGN_PARAGRAPH.LEFT, despues=6):
    p = doc.add_paragraph()
    p.alignment = alineacion
    p.paragraph_format.space_after = Pt(despues)
    if sangria:
        p.paragraph_format.first_line_indent = Cm(1.27)
    escribir(p, texto)
    return p


def vineta(texto):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    escribir(p, texto)
    return p


def titulo1(texto):
    return doc.add_heading(texto, level=1)


def titulo2(texto):
    return doc.add_heading(texto, level=2)


def centrado_negrita(texto, antes=0, despues=12):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(antes), Pt(despues)
    escribir(p, texto, negrita=True)
    return p


def rotulo(clase, titulo):
    """'Figura 3' en negrita y el titulo en cursiva debajo (APA), con la entrada para su lista."""
    contador[clase] += 1
    numero = contador[clase]
    nombre = f"{clase.capitalize()} {numero}"
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.keep_with_next = True
    escribir(p, nombre, negrita=True)
    campo(p, f'TC "{nombre}. {titulo}" \\f {"F" if clase == "figura" else "T"} \\l 1')
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    escribir(p, titulo, cursiva=True)
    return numero


def nota(texto):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(10)
    escribir(p, "Nota. ", cursiva=True, tamano=10)
    escribir(p, texto, tamano=10)


def figura(titulo, ruta, ancho_cm=16.0, texto_nota=None):
    numero = rotulo("figura", titulo)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(4 if texto_nota else 10)
    p.add_run().add_picture(str(ruta), width=Cm(ancho_cm))
    if texto_nota:
        nota(texto_nota)
    return numero


def borde(celda, **lados):
    """borde(celda, top=8, bottom=4): lineas horizontales de la celda, en octavos de punto."""
    bordes = celda._tc.get_or_add_tcPr().find(qn("w:tcBorders"))
    if bordes is None:
        bordes = OxmlElement("w:tcBorders")
        celda._tc.get_or_add_tcPr().append(bordes)
    for lado, grosor in lados.items():
        linea = OxmlElement(f"w:{lado}")
        linea.set(qn("w:val"), "single")
        linea.set(qn("w:sz"), str(grosor))
        linea.set(qn("w:color"), "000000")
        bordes.append(linea)


def tabla(titulo, encabezados, filas, anchos_cm, texto_nota=None, tamano=10, centrar_desde=None):
    """Tabla con formato APA: linea arriba, linea bajo el encabezado y linea al final."""
    numero = rotulo("tabla", titulo)
    t = doc.add_table(rows=1 + len(filas), cols=len(encabezados))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for i, fila in enumerate([encabezados] + filas):
        for j, valor in enumerate(fila):
            celda = t.cell(i, j)
            celda.width = Cm(anchos_cm[j])
            p = celda.paragraphs[0]
            p.paragraph_format.space_before = p.paragraph_format.space_after = Pt(2)
            if centrar_desde is not None and j >= centrar_desde:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            escribir(p, str(valor), negrita=(i == 0), tamano=tamano)
            if i == 0:
                borde(celda, top=8, bottom=4)
            if i == len(filas):
                borde(celda, bottom=8)
    # la fila de encabezado se repite si la tabla pasa de pagina
    marca = OxmlElement("w:tblHeader")
    t.rows[0]._tr.get_or_add_trPr().append(marca)
    if texto_nota:
        nota(texto_nota)
    else:
        doc.add_paragraph().paragraph_format.space_after = Pt(4)
    return numero


def salto_de_pagina():
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def num(valor, decimales=2):
    """1234.5 -> '1 234,50' (formato en espanol)."""
    if valor in ("", None):
        return "–"
    texto = f"{float(valor):,.{decimales}f}"
    return texto.replace(",", " ").replace(".", ",")


def leer(nombre):
    with open(DATOS / nombre, newline="", encoding="utf-8") as archivo:
        return list(csv.DictReader(archivo))


def mejora(base, nuevo, menor_es_mejor=True):
    """Porcentaje de mejora de 'nuevo' frente a 'base' (positivo = mejor)."""
    base, nuevo = float(base), float(nuevo)
    cambio = (base - nuevo) / base * 100 if menor_es_mejor else (nuevo - base) / base * 100
    return f"{'+' if cambio >= 0 else '−'}{num(abs(cambio), 1)} %"


# ------------------------------------------------------------------ datos
resumen = {(f["arquitectura"], int(f["clientes"]), f["operacion"]): f for f in leer("resumen.csv")}
saturacion = {(f["arquitectura"], f["operacion"]): f for f in leer("saturacion.csv")}
fallas = {f["evento"]: f for f in leer("fallas.csv")}
fallas_k8s = leer("fallas_k8s.csv")
OPERACIONES = [("CONSULTA", "Consulta"), ("RESERVA", "Reserva"), ("MODIFICACION", "Modificación")]
ESCENARIOS = [3, 5, 8]

from textos import TEXTOS as T        # los parrafos que dependen de los resultados (docs/informe/textos.py)

preparar_estilos()

# ------------------------------------------------------------------ portada
for _ in range(5):
    doc.add_paragraph()
centrado_negrita(TITULO, despues=24)
for linea in (AUTORES,
              "Pontificia Universidad Javeriana, Facultad de Ingeniería, Departamento de Ingeniería de Sistemas",
              "Introducción a Sistemas Distribuidos",
              "22 de noviembre de 2026"):
    p = parrafo(linea, sangria=False, alineacion=WD_ALIGN_PARAGRAPH.CENTER, despues=14)
salto_de_pagina()

# ------------------------------------------------------------------ tablas de contenido
centrado_negrita("Tabla de contenido")
campo(doc.add_paragraph(), 'TOC \\o "1-2" \\h \\z \\u', "(se genera al actualizar los campos en Word)")
centrado_negrita("Tabla de figuras", antes=18)
campo(doc.add_paragraph(), "TOC \\f F \\h \\z", "(se genera al actualizar los campos en Word)")
centrado_negrita("Lista de tablas", antes=18)
campo(doc.add_paragraph(), "TOC \\f T \\h \\z", "(se genera al actualizar los campos en Word)")
salto_de_pagina()

# ------------------------------------------------------------------ cuerpo
centrado_negrita(TITULO)

titulo1("1. Introducción")
for texto in T["introduccion"]:
    parrafo(texto)

titulo1("2. Entorno de pruebas")
titulo2("2.1 Hardware")
parrafo(T["hardware"])
tabla("Máquinas del despliegue y capa que corre en cada una",
      ["Máquina", "Dirección IP", "Capa", "Procesos", "Procesador y memoria"],
      [["1", "10.43.99.236", "Consumidores", "Clientes, casos de prueba y carga con Locust",
        "Intel Xeon Gold 6348 a 2,60 GHz (4 núcleos), 12 GB de RAM"],
       ["2 (NBIG333)", "10.43.100.36", "Servicios de negocio",
        "Gestor de Transacciones activo y de respaldo, réplicas del RMC y Servicio de Cancelaciones",
        "Intel Xeon Gold 6348 a 2,60 GHz (4 núcleos), 12 GB de RAM"],
       ["3 (NBIG305)", "10.43.99.246", "Almacenamiento",
        "Servicio de Persistencia principal, réplica de lectura y base de datos SQLite",
        "Intel Xeon Gold 6348 a 2,60 GHz (4 núcleos), 12 GB de RAM"]],
      [2.2, 2.5, 3.0, 5.0, 3.7])
parrafo(T["equipo_medicion"])

titulo2("2.2 Software")
tabla("Software utilizado",
      ["Elemento", "Versión", "Uso"],
      [["Ubuntu", "22.04.5 LTS", "Sistema operativo de las tres máquinas"],
       ["Python", "3.12 o superior: 3.15.2 en las máquinas (con `uv`) y 3.12.16 en los contenedores",
        "Lenguaje de todos los procesos"],
       ["ZeroMQ (`pyzmq`)", "pyzmq 27.2.0 (27.3.0 en los contenedores), libzmq 4.3.5",
        "Comunicación entre procesos: REQ/REP, ROUTER/DEALER y PUSH/PULL"],
       ["SQLite", "3.53.1 (3.46.1 en los contenedores), en modo WAL", "Base de datos del Servicio de Persistencia"],
       ["`python-dotenv`", "1.2", "Lectura de la configuración (`.env`)"],
       ["`uv`", "–", "Instalación de dependencias y ejecución"],
       ["Locust", "2.47.0", "Generación de la carga de los clientes"],
       ["Kubernetes (k3s)", "v1.37.2+k3s1, imagen `python:3.12-slim`",
        "Despliegue de los servicios en contenedores, una capa por nodo"],
       ["`pytest`", "9.2.0", "Pruebas unitarias, de integración y de tolerancia a fallas"],
       ["`matplotlib`", "3.11.2", "Gráficos de las métricas"]],
      [3.6, 5.2, 7.6])

titulo2("2.3 Herramientas de medición")
for texto in T["herramientas"]:
    parrafo(texto)

titulo1("3. Arquitectura final")
parrafo(T["arquitectura"])
titulo2("3.1 Despliegue")
parrafo(T["despliegue"])
figura("Diagrama de despliegue de la arquitectura final", DIAGRAMAS / "01-despliegue.png", 16.5)
figura("Diagrama de despliegue en el clúster de Kubernetes", DIAGRAMAS / "08-despliegue-kubernetes.png", 16.5)
titulo2("3.2 Componentes para la escalabilidad y la tolerancia a fallas")
parrafo(T["componentes"])
figura("Diagrama de componentes de la arquitectura final", DIAGRAMAS / "02-componentes.png", 16.5)
tabla("Componentes de la arquitectura final y su justificación",
      ["Componente", "Atributo", "Cómo funciona y por qué"],
      T["tabla_componentes"], [4.0, 2.6, 9.8])
for texto in T["kubernetes"]:
    parrafo(texto)
titulo2("3.3 Patrones de resiliencia")
for texto in T["patrones"]:
    parrafo(texto)
tabla("Patrones de sistemas distribuidos resilientes usados en el SRB",
      ["Patrón", "Cómo se aplica", "Qué resuelve"], T["tabla_patrones"], [4.6, 7.4, 4.4],
      tamano=9, texto_nota=T["nota_patrones"])
titulo2("3.4 Clases y modelo de datos")
parrafo(T["clases"])
figura("Diagrama de clases del sistema", DIAGRAMAS / "03-clases.png", 16.5)
figura("Modelo de datos de la base SQLite", DIAGRAMAS / "04-entidad-relacion.png", 15.0)
titulo2("3.5 Secuencia de las operaciones")
parrafo(T["secuencia"])
figura("Diagrama de secuencia de las operaciones síncronas", DIAGRAMAS / "05-secuencia-sincrona.png", 15.0)
figura("Diagrama de secuencia de la cancelación asíncrona con notificación",
       DIAGRAMAS / "06-secuencia-cancelacion.png", 15.5)
figura("Diagrama de secuencia de la recuperación ante la caída de un RMC y del Gestor de Transacciones",
       DIAGRAMAS / "07-secuencia-fallas.png", 15.5)
titulo2("3.6 Mensajes")
parrafo(T["mensajes"])
tabla("Mensajes del sistema", ["Tipo", "Quién lo envía", "Datos", "Respuesta"], T["tabla_mensajes"],
      [3.6, 3.0, 5.6, 4.2], tamano=9)
titulo2("3.7 Modelos de fallos y de seguridad en la implementación")
for texto in T["fallos_seguridad"]:
    parrafo(texto)

titulo1("4. Protocolo de pruebas")
for texto in T["protocolo"]:
    parrafo(texto)
tabla("Protocolo de pruebas ejecutado y su resultado",
      ["Tipo", "Caso", "Criterio de aceptación", "Resultado obtenido", "Estado"],
      T["tabla_protocolo"], [2.1, 3.5, 3.8, 5.0, 2.0], tamano=9,
      texto_nota=T["nota_protocolo"])
titulo2("4.1 Tolerancia a fallas bajo carga")
for texto in T["fallas"]:
    parrafo(texto)
tabla("Recuperación medida al matar procesos durante una carga",
      ["Falla provocada", "Peticiones enviadas", "Con error", "Mayor tiempo de respuesta", "Base de datos al final"],
      [[f["descripcion"], f["peticiones"], f["errores"], f"{num(f['max_ms'], 0)} ms", f["consistencia"]]
       for f in fallas.values()],
      [5.4, 2.3, 1.8, 3.0, 3.9], texto_nota=T["nota_fallas"])

titulo1("5. Resultados de rendimiento")
titulo2("5.1 Diseño de los experimentos")
for texto in T["experimentos"]:
    parrafo(texto)

titulo2("5.2 Tiempo de respuesta")
filas = []
for clientes in ESCENARIOS:
    for clave, nombre in OPERACIONES:
        base, esc = resumen.get(("base", clientes, clave)), resumen.get(("escalable", clientes, clave))
        if base and esc:
            filas.append([clientes, nombre, num(base["promedio_ms"]), num(base["desviacion_ms"]), num(base["p95_ms"]),
                          num(esc["promedio_ms"]), num(esc["desviacion_ms"]), num(esc["p95_ms"]),
                          mejora(base["promedio_ms"], esc["promedio_ms"])])
tabla("Tiempo de respuesta por escenario, operación y arquitectura, en milisegundos",
      ["Clientes", "Operación", "Base: promedio", "Base: desv. estándar", "Base: percentil 95",
       "Escalable: promedio", "Escalable: desv. estándar", "Escalable: percentil 95", "Cambio del promedio"],
      filas, [1.5, 2.3, 1.7, 1.8, 1.8, 1.9, 1.9, 1.9, 1.8], tamano=9, centrar_desde=2,
      texto_nota=T["nota_tiempos"])
figura("Tiempo promedio de respuesta de la consulta según el número de clientes",
       DATOS / "graficos" / "tiempo_promedio_consulta.png", 12.5)
figura("Tiempo promedio de respuesta de la reserva según el número de clientes",
       DATOS / "graficos" / "tiempo_promedio_reserva.png", 12.5)
figura("Percentil 95 del tiempo de respuesta de la consulta según el número de clientes",
       DATOS / "graficos" / "percentil_95_consulta.png", 12.5)
figura("Percentil 95 del tiempo de respuesta de la reserva según el número de clientes",
       DATOS / "graficos" / "percentil_95_reserva.png", 12.5)

titulo2("5.3 Transacciones por minuto y tasa de error")
filas = []
for clientes in ESCENARIOS:
    for clave, nombre in OPERACIONES:
        base, esc = resumen.get(("base", clientes, clave)), resumen.get(("escalable", clientes, clave))
        if base and esc:
            filas.append([clientes, nombre, base["peticiones"], num(base["tpm"], 1), num(base["tasa_error_pct"]),
                          esc["peticiones"], num(esc["tpm"], 1), num(esc["tasa_error_pct"])])
tabla("Transacciones por minuto medidas en el Gestor de Transacciones y tasa de error",
      ["Clientes", "Operación", "Base: peticiones", "Base: TPM", "Base: error (%)",
       "Escalable: peticiones", "Escalable: TPM", "Escalable: error (%)"],
      filas, [1.6, 2.6, 2.0, 1.9, 1.9, 2.2, 2.1, 2.1], tamano=9, centrar_desde=2,
      texto_nota=T["nota_tpm"])
figura("Transacciones de consulta por minuto según el número de clientes",
       DATOS / "graficos" / "tpm_consulta.png", 12.5)
figura("Transacciones de reserva por minuto según el número de clientes",
       DATOS / "graficos" / "tpm_reserva.png", 12.5)

titulo2("5.4 Prueba de saturación")
for texto in T["saturacion"]:
    parrafo(texto)
filas = []
for clave, nombre in OPERACIONES:
    base, esc = saturacion[("base", clave)], saturacion[("escalable", clave)]
    filas.append([nombre, num(base["promedio_ms"]), num(base["p95_ms"]), num(base["tpm"], 0),
                  num(esc["promedio_ms"]), num(esc["p95_ms"]), num(esc["tpm"], 0),
                  mejora(base["tpm"], esc["tpm"], menor_es_mejor=False)])
tabla("Prueba de saturación: 8 clientes enviando sin pausa durante 60 segundos",
      ["Operación", "Base: promedio (ms)", "Base: percentil 95 (ms)", "Base: TPM",
       "Escalable: promedio (ms)", "Escalable: percentil 95 (ms)", "Escalable: TPM", "Cambio de las TPM"],
      filas, [2.4, 1.9, 2.0, 1.9, 2.1, 2.1, 2.1, 1.9], tamano=9, centrar_desde=1,
      texto_nota=T["nota_saturacion"])

titulo1("6. Análisis de los resultados")
for texto in T["analisis"]:
    parrafo(texto)

titulo1("7. Conclusiones")
for texto in T["conclusiones"]:
    parrafo(texto)

titulo1("8. Tolerancia a fallas en Kubernetes")
for texto in T["kubernetes_maquinas"][:2]:
    parrafo(texto)
tabla("Recuperación medida en el clúster de Kubernetes al provocar fallas durante una carga",
      ["Falla provocada", "Peticiones enviadas", "Con error", "Mayor tiempo de respuesta", "Base de datos al final"],
      [[f["descripcion"], f["peticiones"], f["errores"], f"{num(f['max_ms'], 0)} ms", f["consistencia"]]
       for f in fallas_k8s],
      [5.4, 2.3, 1.8, 3.0, 3.9], texto_nota=T["nota_fallas_k8s"])
for texto in T["kubernetes_maquinas"][2:]:
    parrafo(texto)

titulo1("Referencias")
for texto in T["referencias"]:
    p = doc.add_paragraph()
    p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Cm(1.27), Cm(-1.27)
    p.paragraph_format.space_after = Pt(6)
    partes = texto.split("*")                       # *texto* = cursiva
    for i, parte in enumerate(partes):
        escribir(p, parte, cursiva=bool(i % 2))

doc.save(SALIDA)
print(f"Informe guardado en {SALIDA}: {contador['figura']} figuras, {contador['tabla']} tablas")
