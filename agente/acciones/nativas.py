"""Acciones que funcionan en cualquier Windows limpio, sin Office instalado.

Sustituyen el trabajo de Word y Excel con herramientas que trae el sistema:
archivos de texto, un CSV que va creciendo, organizacion de carpetas y las
aplicaciones basicas de Windows. Todo dentro de la carpeta de trabajo.
"""

from __future__ import annotations

import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from .. import util
from .base import registrar

CARPETA_NOTAS = "notas"
CARPETA_ARCHIVO = "archivo"

NOTAS = {
    "seguimiento.txt": "SEGUIMIENTO DE ACTIVIDADES",
    "pendientes.txt": "PENDIENTES POR RESOLVER",
    "reunion.txt": "NOTAS DE REUNION",
    "incidencias.txt": "REGISTRO DE INCIDENCIAS",
}

ENCABEZADO_CSV = "Fecha;Sucursal;Bodega;Cantidad;Valor;Estado"

# Umbral de lineas a partir del cual cada archivo se rota hacia archivo\AAAA-MM
LIMITES = {"bitacora.txt": 120, "informe_actividad.csv": 400}
LIMITE_NOTAS = 120

def _lineas(ruta):
    try:
        return ruta.read_text(encoding="utf-8", errors="replace").count("\n")
    except OSError:
        return 0


# ------------------------------------------------------------- notas de texto
@registrar(
    nombre="notas_tematicas",
    descripcion="Redacta en uno de los archivos de notas y lo abre en el Bloc de notas",
    categoria="nativa",
    peso=12,
)
def notas_tematicas(ctx):
    carpeta = ctx.carpeta / CARPETA_NOTAS
    carpeta.mkdir(parents=True, exist_ok=True)

    nombre = ctx.rng.choice(list(NOTAS))
    ruta = carpeta / nombre

    if not ruta.exists():
        cabecera = "%s\n%s\n\n" % (NOTAS[nombre], "=" * len(NOTAS[nombre]))
        ruta.write_text(cabecera, encoding="utf-8")

    bloque = ["[%s]" % datetime.now().strftime("%Y-%m-%d %H:%M")]
    for _ in range(ctx.rng.randint(1, 4)):
        bloque.append("  - " + util.frase(ctx.rng))
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write("\n".join(bloque) + "\n\n")

    if ctx.cfg.comportamiento.apps_visibles:
        # Misma clave que la bitacora: nunca hay mas de un Bloc de notas abierto.
        ctx.lanzar_proceso("bloc_notas", ["notepad.exe", str(ruta)])
        util.pausa(ctx.rng, 6.0, 18.0)

    ctx.logger.info("Notas: %d lineas agregadas en %s.", len(bloque) - 1, nombre)


# ------------------------------------------------------------------- informe
@registrar(
    nombre="csv_informe_actualizar",
    descripcion="Agrega registros al informe CSV que hace las veces de hoja de calculo",
    categoria="nativa",
    peso=12,
)
def csv_informe_actualizar(ctx):
    ruta = ctx.carpeta / "informe_actividad.csv"
    nuevo = not ruta.exists()

    filas = []
    for _ in range(ctx.rng.randint(3, 12)):
        filas.append(";".join(str(valor) for valor in util.fila_tabular(ctx.rng)))

    with open(ruta, "a", encoding="utf-8") as archivo:
        if nuevo:
            archivo.write(ENCABEZADO_CSV + "\n")
        archivo.write("\n".join(filas) + "\n")
        util.pausa(ctx.rng, 1.0, 4.0)

    # El CSV se revisa de vez en cuando, no cada vez que se alimenta.
    if ctx.cfg.comportamiento.apps_visibles and ctx.rng.random() < 0.35:
        ctx.lanzar_proceso("bloc_notas", ["notepad.exe", str(ruta)])
        util.pausa(ctx.rng, 5.0, 15.0)

    ctx.logger.info("Informe: %d filas agregadas (%d en total).",
                    len(filas), _lineas(ruta) - 1)


# --------------------------------------------------------------- organizacion
@registrar(
    nombre="organizar_archivos",
    descripcion="Rota los archivos grandes a archivo\\AAAA-MM y regenera el inventario",
    categoria="nativa",
    peso=7,
    roba_foco=False,
)
def organizar_archivos(ctx):
    destino = ctx.carpeta / CARPETA_ARCHIVO / datetime.now().strftime("%Y-%m")

    candidatos = []
    for nombre, limite in LIMITES.items():
        candidatos.append((ctx.carpeta / nombre, limite))
    carpeta_notas = ctx.carpeta / CARPETA_NOTAS
    if carpeta_notas.is_dir():
        for ruta in carpeta_notas.glob("*.txt"):
            candidatos.append((ruta, LIMITE_NOTAS))

    rotados = 0
    for ruta, limite in candidatos:
        if not ruta.exists() or _lineas(ruta) <= limite:
            continue
        destino.mkdir(parents=True, exist_ok=True)
        marca = datetime.now().strftime("%Y%m%d-%H%M%S")
        shutil.move(str(ruta), str(destino / ("%s_%s%s" % (ruta.stem, marca, ruta.suffix))))
        rotados += 1

    # Inventario de todo lo que el agente ha generado hasta ahora.
    lineas = ["INVENTARIO DE LA CARPETA DE TRABAJO",
              "Generado: %s" % datetime.now().strftime("%Y-%m-%d %H:%M"), ""]
    total = 0
    for ruta in sorted(ctx.carpeta.rglob("*")):
        if ruta.is_file() and ruta.name != "inventario.txt":
            relativa = ruta.relative_to(ctx.carpeta)
            lineas.append("%-52s %8.1f KB   %s" % (
                relativa, ruta.stat().st_size / 1024,
                datetime.fromtimestamp(ruta.stat().st_mtime).strftime("%Y-%m-%d %H:%M")))
            total += 1
    lineas.append("")
    lineas.append("%d archivos" % total)

    carpeta_archivo = ctx.carpeta / CARPETA_ARCHIVO
    carpeta_archivo.mkdir(parents=True, exist_ok=True)
    (carpeta_archivo / "inventario.txt").write_text("\n".join(lineas), encoding="utf-8")

    util.pausa(ctx.rng, 2.0, 6.0)
    ctx.logger.info("Organizacion: %d archivos rotados, inventario con %d entradas.",
                    rotados, total)


# ------------------------------------------------------------------ explorador
@registrar(
    nombre="explorador_revisar_archivo",
    descripcion="Abre el Explorador con un archivo de trabajo seleccionado",
    categoria="nativa",
    peso=6,
)
def explorador_revisar_archivo(ctx):
    archivos = [ruta for ruta in ctx.carpeta.rglob("*")
                if ruta.is_file() and ruta.suffix.lower() != ".log"]
    if not archivos:
        ctx.logger.info("Explorador: aun no hay archivos que revisar.")
        return

    ctx.cerrar_ventanas_explorador()
    elegido = ctx.rng.choice(archivos)
    # explorer exige la ruta pegada al modificador y entre comillas.
    subprocess.Popen('explorer /select,"%s"' % elegido)
    ctx.logger.info("Explorador: %s seleccionado.", elegido.relative_to(ctx.carpeta))
    util.pausa(ctx.rng, 5.0, 15.0)
