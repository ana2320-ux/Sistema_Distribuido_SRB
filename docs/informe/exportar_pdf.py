"""
Exporta docs/informe/informe-segunda-entrega.docx a PDF con LibreOffice, sin Word: abre el documento,
actualiza la tabla de contenido, la tabla de figuras y la lista de tablas, y guarda el PDF.
LibreOffice no separa las entradas TC \\f F (figuras) y \\f T (tablas) de Word, así que esas dos
listas se rehacen como índices de usuario.

Uso (desde la raiz del proyecto, despues de generar_informe.py; usa el Python del sistema, que trae uno):
    /usr/bin/python3 docs/informe/exportar_pdf.py
"""
import subprocess
import time
from pathlib import Path

import uno
from com.sun.star.beans import PropertyValue

AQUI = Path(__file__).resolve().parent
DOCX = AQUI / "informe-segunda-entrega.docx"
PDF = AQUI / "informe-segunda-entrega.pdf"


def prop(nombre, valor):
    p = PropertyValue()
    p.Name, p.Value = nombre, valor
    return p


def buscar(doc, texto):
    busqueda = doc.createSearchDescriptor()
    busqueda.SearchString = texto
    busqueda.SearchCaseSensitive = True
    return doc.findFirst(busqueda)


def rehacer_listas(doc):
    """Cambia las dos listas de Word (TC \\f F y \\f T) por índices de usuario de LibreOffice."""
    texto = doc.getText()
    indices = doc.getDocumentIndexes()
    lista_figuras, lista_tablas = indices.getByIndex(1), indices.getByIndex(2)
    lista_figuras.update()
    for marca in lista_figuras.DocumentIndexMarks:      # todas las entradas TC del documento
        entrada = marca.AlternativeText or marca.getAnchor().getString()
        nueva = doc.createInstance("com.sun.star.text.UserIndexMark")
        nueva.UserIndexName = "Figuras" if entrada.startswith("Figura") else "Tablas"
        nueva.AlternativeText = entrada
        ancla = marca.getAnchor()
        ancla.getText().insertTextContent(ancla.getStart(), nueva, False)
        ancla.getText().removeTextContent(marca)

    for vieja, nombre, encabezado in ((lista_figuras, "Figuras", "Tabla de figuras"),
                                      (lista_tablas, "Tablas", "Lista de tablas")):
        texto.removeTextContent(vieja)
        cursor = texto.createTextCursorByRange(buscar(doc, encabezado).getEnd())
        cursor.ParaKeepTogether = True                  # en LibreOffice: «mantener con el siguiente»
        nuevo = doc.createInstance("com.sun.star.text.UserIndex")
        nuevo.UserIndexName = nombre
        nuevo.CreateFromMarks = True
        nuevo.Title = ""
        niveles = nuevo.LevelFormat                     # entrada, puntos y número de página
        formato = ((prop("TokenType", "TokenEntryText"),),
                   (prop("TokenType", "TokenTabStop"), prop("TabStopRightAligned", True),
                    prop("TabStopFillCharacter", ".")),
                   (prop("TokenType", "TokenPageNumber"),))
        uno.invoke(niveles, "replaceByIndex", (1, uno.Any("[][]com.sun.star.beans.PropertyValue", formato)))
        nuevo.LevelFormat = niveles
        texto.insertTextContent(cursor, nuevo, False)
        nuevo.update()
        parrafos = nuevo.getAnchor().createEnumeration()
        while parrafos.hasMoreElements():               # sin sangría, como la tabla de contenido
            p = parrafos.nextElement()
            p.ParaLeftMargin = 0
            p.ParaFirstLineIndent = 0


soffice = subprocess.Popen(["soffice", "--headless", "--invisible", "--norestore",
                            "-env:UserInstallation=file:///tmp/srb-libreoffice",
                            "--accept=socket,host=127.0.0.1,port=2002;urp;"])
try:
    for _ in range(60):                                 # espera a que LibreOffice acepte conexiones
        try:
            local = uno.getComponentContext()
            resolver = local.ServiceManager.createInstanceWithContext("com.sun.star.bridge.UnoUrlResolver", local)
            ctx = resolver.resolve("uno:socket,host=127.0.0.1,port=2002;urp;StarOffice.ComponentContext")
            break
        except Exception:
            time.sleep(1)
    escritorio = ctx.ServiceManager.createInstanceWithContext("com.sun.star.frame.Desktop", ctx)
    doc = escritorio.loadComponentFromURL(uno.systemPathToFileUrl(str(DOCX)), "_blank", 0, (prop("Hidden", True),))
    rehacer_listas(doc)
    doc.refresh()
    indices = doc.getDocumentIndexes()
    for i in range(indices.getCount()):                 # números de página ya con las listas puestas
        indices.getByIndex(i).update()
    doc.storeToURL(uno.systemPathToFileUrl(str(PDF)), (prop("FilterName", "writer_pdf_Export"),))
    doc.close(True)
    print(f"PDF guardado en {PDF}")
finally:
    try:
        escritorio.terminate()
    except Exception:
        pass
    try:
        soffice.wait(timeout=30)
    except subprocess.TimeoutExpired:
        soffice.kill()
