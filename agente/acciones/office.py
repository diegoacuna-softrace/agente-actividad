"""Acciones sobre Word, Excel y PowerPoint mediante automatizacion COM.

Todo ocurre dentro de la carpeta de trabajo del agente: nunca se abren ni se
modifican documentos propios del usuario.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from .. import util
from .base import hay_com, progid_registrado, registrar

WD_COLLAPSE_END = 0
XL_UP = -4162
XL_FORMATO_XLSX = 51
PP_LAYOUT_TEXT = 2

ENCABEZADOS_EXCEL = ["Fecha", "Sucursal", "Bodega", "Cantidad", "Valor", "Estado"]


def _disponible(prog_id):
    return lambda cfg: hay_com() and progid_registrado(prog_id)


def _documento_abierto(coleccion, ruta):
    """Busca en una coleccion COM (Documents/Workbooks/Presentations) el archivo dado."""
    objetivo = str(Path(ruta).resolve()).lower()
    for indice in range(1, coleccion.Count + 1):
        try:
            item = coleccion.Item(indice)
            if str(Path(item.FullName).resolve()).lower() == objetivo:
                return item
        except Exception:
            continue
    return None


def _guardar(objeto, ruta, es_nuevo, formato=None):
    if not es_nuevo:
        objeto.Save()
        return
    ruta = str(ruta)
    try:
        if formato is None:
            objeto.SaveAs2(ruta)
        else:
            objeto.SaveAs(ruta, formato)
    except AttributeError:
        objeto.SaveAs(ruta)


# ---------------------------------------------------------------------- Word
def _abrir_word(ctx, ruta):
    word = ctx.app_office("Word.Application")
    abierto = _documento_abierto(word.Documents, ruta)
    if abierto is not None:
        return word, abierto, False
    if Path(ruta).exists():
        return word, word.Documents.Open(str(ruta)), False
    return word, word.Documents.Add(), True


@registrar(
    nombre="word_redactar_notas",
    descripcion="Abre Word y agrega un bloque de notas al documento de trabajo",
    categoria="office",
    peso=12,
    disponible=_disponible("Word.Application"),
)
def word_redactar_notas(ctx):
    ruta = ctx.carpeta / "notas_operativas.docx"
    word, doc, es_nuevo = _abrir_word(ctx, ruta)

    encabezado = "%s  |  %s" % (datetime.now().strftime("%Y-%m-%d %H:%M"), util.asunto(ctx.rng))
    rango = doc.Content
    rango.Collapse(WD_COLLAPSE_END)
    rango.InsertAfter(encabezado + "\r")
    rango.Bold = True

    util.pausa(ctx.rng, 1.5, 4.0)

    cuerpo = doc.Content
    cuerpo.Collapse(WD_COLLAPSE_END)
    cuerpo.InsertAfter(util.parrafo(ctx.rng, 2, 5) + "\r\r")
    cuerpo.Bold = False

    _guardar(doc, ruta, es_nuevo)
    ctx.logger.info("Word: notas agregadas en %s (%d parrafos).", ruta.name, doc.Paragraphs.Count)

    util.pausa(ctx.rng, 3.0, 10.0)
    if ctx.cfg.comportamiento.cerrar_apps:
        doc.Close(0)


@registrar(
    nombre="word_revisar_documento",
    descripcion="Abre el documento de notas y lo recorre sin modificarlo",
    categoria="office",
    peso=6,
    disponible=_disponible("Word.Application"),
)
def word_revisar_documento(ctx):
    ruta = ctx.carpeta / "notas_operativas.docx"
    if not ruta.exists():
        ctx.logger.info("Word: aun no existe %s; se redactan notas en su lugar.", ruta.name)
        return word_redactar_notas(ctx)

    word, doc, _ = _abrir_word(ctx, ruta)
    for _ in range(ctx.rng.randint(2, 6)):
        try:
            word.ActiveWindow.SmallScroll(Down=ctx.rng.randint(3, 12))
        except Exception:
            break
        util.pausa(ctx.rng, 1.0, 3.5)
    ctx.logger.info("Word: revision de %s sin cambios.", ruta.name)
    if ctx.cfg.comportamiento.cerrar_apps:
        doc.Close(0)


# --------------------------------------------------------------------- Excel
def _abrir_excel(ctx, ruta):
    xl = ctx.app_office("Excel.Application")
    try:
        xl.DisplayAlerts = False
    except Exception:
        pass
    abierto = _documento_abierto(xl.Workbooks, ruta)
    if abierto is not None:
        return xl, abierto, False
    if Path(ruta).exists():
        return xl, xl.Workbooks.Open(str(ruta)), False
    return xl, xl.Workbooks.Add(), True


@registrar(
    nombre="excel_actualizar_hoja",
    descripcion="Agrega registros y recalcula formulas en la hoja de seguimiento",
    categoria="office",
    peso=14,
    disponible=_disponible("Excel.Application"),
)
def excel_actualizar_hoja(ctx):
    ruta = ctx.carpeta / "seguimiento_operativo.xlsx"
    xl, libro, es_nuevo = _abrir_excel(ctx, ruta)
    hoja = libro.Worksheets(1)

    if not hoja.Cells(1, 1).Value:
        for columna, titulo in enumerate(ENCABEZADOS_EXCEL, start=1):
            hoja.Cells(1, columna).Value = titulo
        hoja.Range("A1:F1").Font.Bold = True

    fila = int(hoja.Cells(hoja.Rows.Count, 1).End(XL_UP).Row) + 1
    nuevas = ctx.rng.randint(3, 12)
    for _ in range(nuevas):
        for columna, valor in enumerate(util.fila_tabular(ctx.rng), start=1):
            hoja.Cells(fila, columna).Value = valor
        fila += 1
        util.pausa(ctx.rng, 0.2, 0.9)

    ultima = fila - 1
    hoja.Cells(1, 8).Value = "Total cantidad"
    hoja.Cells(2, 8).Formula = "=SUM(D2:D%d)" % ultima
    hoja.Cells(1, 9).Value = "Valor promedio"
    hoja.Cells(2, 9).Formula = "=IFERROR(AVERAGE(E2:E%d),0)" % ultima

    try:
        hoja.Columns("A:I").AutoFit()
        xl.Calculate()
    except Exception:
        pass

    _guardar(libro, ruta, es_nuevo, XL_FORMATO_XLSX)
    ctx.logger.info("Excel: %d filas nuevas en %s (total %d).", nuevas, ruta.name, ultima - 1)

    util.pausa(ctx.rng, 2.0, 8.0)
    if ctx.cfg.comportamiento.cerrar_apps:
        libro.Close(SaveChanges=False)


@registrar(
    nombre="excel_revisar_tablero",
    descripcion="Abre la hoja de seguimiento, la recorre y recalcula sin escribir",
    categoria="office",
    peso=7,
    disponible=_disponible("Excel.Application"),
)
def excel_revisar_tablero(ctx):
    ruta = ctx.carpeta / "seguimiento_operativo.xlsx"
    if not ruta.exists():
        ctx.logger.info("Excel: aun no existe %s; se actualiza en su lugar.", ruta.name)
        return excel_actualizar_hoja(ctx)

    xl, libro, _ = _abrir_excel(ctx, ruta)
    hoja = libro.Worksheets(1)
    ultima = int(hoja.Cells(hoja.Rows.Count, 1).End(XL_UP).Row)

    for _ in range(ctx.rng.randint(2, 5)):
        destino = ctx.rng.randint(1, max(1, ultima))
        try:
            hoja.Cells(destino, ctx.rng.randint(1, 6)).Select()
            xl.ActiveWindow.SmallScroll(Down=ctx.rng.randint(4, 15))
        except Exception:
            break
        util.pausa(ctx.rng, 1.0, 3.0)

    ctx.logger.info("Excel: revision de %s (%d filas) sin cambios.", ruta.name, ultima - 1)
    if ctx.cfg.comportamiento.cerrar_apps:
        libro.Close(SaveChanges=False)


# ---------------------------------------------------------------- PowerPoint
@registrar(
    nombre="powerpoint_avance_presentacion",
    descripcion="Agrega una diapositiva de avance a la presentacion de trabajo",
    categoria="office",
    peso=6,
    disponible=_disponible("PowerPoint.Application"),
)
def powerpoint_avance_presentacion(ctx):
    ruta = ctx.carpeta / "avance_semanal.pptx"
    ppt = ctx.app_office("PowerPoint.Application")

    abierta = _documento_abierto(ppt.Presentations, ruta)
    if abierta is not None:
        presentacion, es_nueva = abierta, False
    elif ruta.exists():
        presentacion, es_nueva = ppt.Presentations.Open(str(ruta)), False
    else:
        presentacion, es_nueva = ppt.Presentations.Add(), True

    indice = presentacion.Slides.Count + 1
    diapositiva = presentacion.Slides.Add(indice, PP_LAYOUT_TEXT)
    diapositiva.Shapes(1).TextFrame.TextRange.Text = util.asunto(ctx.rng)
    diapositiva.Shapes(2).TextFrame.TextRange.Text = "\r".join(
        util.vinetas(ctx.rng, ctx.rng.randint(2, 4))
    )

    util.pausa(ctx.rng, 2.0, 6.0)
    _guardar(presentacion, ruta, es_nueva)
    ctx.logger.info("PowerPoint: diapositiva %d agregada en %s.", indice, ruta.name)

    if ctx.cfg.comportamiento.cerrar_apps:
        presentacion.Close()
