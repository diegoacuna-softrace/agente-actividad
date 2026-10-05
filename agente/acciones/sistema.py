"""Acciones de sistema: raton, ventanas, bloc de notas, explorador y navegador.

El agente solo escribe texto en documentos que el mismo abrio a traves de COM.
Nunca envia pulsaciones de teclado "a ciegas" a la ventana que este al frente,
porque no puede saber que aplicacion la tiene y podria alterar trabajo real.
"""

from __future__ import annotations

import os
import webbrowser
from datetime import datetime

from .. import util
from .base import hay_modulo, registrar

MARGEN = 0.08          # fraccion de pantalla que se evita en los bordes

# Lista cerrada de navegadores que el cierre de jornada puede tocar.
NAVEGADORES = ("msedge.exe", "chrome.exe", "firefox.exe", "brave.exe", "opera.exe")


def _pyautogui():
    import pyautogui
    pyautogui.FAILSAFE = True      # llevar el raton a la esquina superior izquierda aborta
    pyautogui.PAUSE = 0.05
    return pyautogui


def _hay_raton(cfg):
    return util.ES_WINDOWS and hay_modulo("pyautogui")


def _punto_seguro(gui, rng):
    ancho, alto = gui.size()
    return (
        rng.randint(int(ancho * MARGEN), int(ancho * (1 - MARGEN))),
        rng.randint(int(alto * MARGEN), int(alto * (1 - MARGEN))),
    )


# ------------------------------------------------------------------- latidos
@registrar(
    nombre="raton_movimiento",
    descripcion="Mueve el raton describiendo un recorrido corto y suave",
    categoria="sistema",
    peso=10,
    roba_foco=False,
    es_latido=True,
    disponible=_hay_raton,
)
def raton_movimiento(ctx):
    gui = _pyautogui()
    saltos = ctx.rng.randint(2, 5)
    for _ in range(saltos):
        destino = _punto_seguro(gui, ctx.rng)
        gui.moveTo(destino[0], destino[1],
                   duration=ctx.rng.uniform(0.3, 1.2),
                   tween=gui.easeInOutQuad)
        util.pausa(ctx.rng, 0.2, 1.1)
    util.marcar_input_sintetico()
    ctx.logger.debug("Sistema: %d movimientos de raton.", saltos)


@registrar(
    nombre="rueda_scroll",
    descripcion="Desplaza la rueda del raton hacia abajo y regresa",
    categoria="sistema",
    peso=8,
    roba_foco=False,
    es_latido=True,
    disponible=_hay_raton,
)
def rueda_scroll(ctx):
    gui = _pyautogui()
    bajada = ctx.rng.randint(2, 7)
    gui.scroll(-bajada * 100)
    util.pausa(ctx.rng, 0.8, 2.5)
    gui.scroll(ctx.rng.randint(1, bajada) * 100)
    util.marcar_input_sintetico()
    ctx.logger.debug("Sistema: desplazamiento de rueda.")


@registrar(
    nombre="cambiar_ventana",
    descripcion="Alterna entre las dos ultimas ventanas con Alt+Tab",
    categoria="sistema",
    peso=6,
    roba_foco=True,
    es_latido=True,
    disponible=_hay_raton,
)
def cambiar_ventana(ctx):
    gui = _pyautogui()
    gui.hotkey("alt", "tab")
    util.marcar_input_sintetico()
    util.pausa(ctx.rng, 1.0, 4.0)
    ctx.logger.debug("Sistema: cambio de ventana.")


# ------------------------------------------------------------------ acciones
@registrar(
    nombre="bitacora_bloc_notas",
    descripcion="Anota una linea en la bitacora de texto y la abre en el Bloc de notas",
    categoria="sistema",
    peso=9,
)
def bitacora_bloc_notas(ctx):
    ruta = ctx.carpeta / "bitacora.txt"
    linea = "%s  %s\n" % (datetime.now().strftime("%Y-%m-%d %H:%M"), util.frase(ctx.rng))
    with open(ruta, "a", encoding="utf-8") as archivo:
        archivo.write(linea)

    if ctx.cfg.comportamiento.apps_visibles:
        # Cierra la instancia anterior del Bloc de notas abierta por el agente
        # para no acumular ventanas a lo largo del dia.
        ctx.lanzar_proceso("bloc_notas", ["notepad.exe", str(ruta)])
        util.pausa(ctx.rng, 5.0, 15.0)

    ctx.logger.info("Sistema: linea agregada a %s.", ruta.name)


@registrar(
    nombre="notepad_escribir",
    descripcion="Abre el Bloc de notas y escribe tecleando en vivo, letra a letra",
    categoria="sistema",
    peso=14,
    roba_foco=True,
    disponible=_hay_raton,
)
def notepad_escribir(ctx):
    """Escribe en el Bloc de notas simulando pulsaciones reales, una a una.

    A diferencia de las otras notas (que vuelcan el texto al archivo y luego lo
    abren ya escrito), aqui el texto APARECE tecleandose en vivo en la ventana.
    Como roba el foco, el planificador la aplaza si detecta a un humano usando el
    equipo, para no escribir encima de su trabajo.
    """
    gui = _pyautogui()
    ruta = ctx.carpeta / "bitacora_en_vivo.txt"
    if not ruta.exists():
        ruta.write_text("BITACORA (escrita en vivo)\n==========================\n\n",
                        encoding="utf-8")
    # Misma clave 'bloc_notas' que las demas: nunca hay mas de un Bloc del agente.
    ctx.lanzar_proceso("bloc_notas", ["notepad.exe", str(ruta)])
    util.pausa(ctx.rng, 2.0, 3.5)          # esperar a que abra y quede al frente
    gui.hotkey("ctrl", "end")              # ir al final del texto existente
    util.pausa(ctx.rng, 0.3, 0.8)

    total = util.teclear_unicode("\n[%s]\n" % datetime.now().strftime("%Y-%m-%d %H:%M"),
                                 ctx.rng)
    lineas = ctx.rng.randint(2, 4)
    for _ in range(lineas):
        total += util.teclear_unicode("  - " + util.frase(ctx.rng) + "\n",
                                      ctx.rng, 0.04, 0.13)
        util.pausa(ctx.rng, 0.5, 1.6)      # pausa de "pensar" entre renglones
    gui.hotkey("ctrl", "s")                # guardar
    util.pausa(ctx.rng, 0.4, 1.0)
    ctx.logger.info("Notepad: %d caracteres tecleados en vivo (%d lineas).", total, lineas)


@registrar(
    nombre="paint_dibujar",
    descripcion="Abre Paint y dibuja varios trazos moviendo el raton",
    categoria="sistema",
    peso=10,
    roba_foco=True,
    disponible=_hay_raton,
)
def paint_dibujar(ctx):
    """Abre Paint y dibuja trazos a mano alzada arrastrando el raton.

    No solo lo abre: mantiene el boton pulsado y recorre varios puntos, dejando
    lineas en el lienzo. Paint se cierra al terminar la jornada (si no estaba ya
    abierto por el usuario).
    """
    import subprocess

    gui = _pyautogui()
    ya_estaba = ctx.proceso_activo(["mspaint.exe"])
    try:
        subprocess.Popen(["mspaint.exe"])
    except OSError as error:
        ctx.logger.warning("Paint: no se pudo abrir (%s).", error)
        return
    if not ya_estaba:
        ctx.marcar_para_cierre(["mspaint.exe"])
    util.pausa(ctx.rng, 2.5, 4.5)          # esperar a que Paint abra y quede al frente

    ancho, alto = gui.size()
    # Zona central segura: lejos de las barras de Paint y de los bordes. Nunca
    # cerca de la esquina (0,0), que dispararia el FAILSAFE de pyautogui.
    x0, x1 = int(ancho * 0.28), int(ancho * 0.72)
    y0, y1 = int(alto * 0.38), int(alto * 0.82)

    trazos = ctx.rng.randint(3, 6)
    try:
        for _ in range(trazos):
            gui.moveTo(ctx.rng.randint(x0, x1), ctx.rng.randint(y0, y1),
                       duration=ctx.rng.uniform(0.2, 0.5))
            gui.mouseDown()
            try:
                for _ in range(ctx.rng.randint(3, 7)):
                    gui.moveTo(ctx.rng.randint(x0, x1), ctx.rng.randint(y0, y1),
                               duration=ctx.rng.uniform(0.3, 0.9), tween=gui.easeInOutQuad)
            finally:
                gui.mouseUp()              # el boton nunca queda hundido
            util.pausa(ctx.rng, 0.3, 1.0)
    finally:
        util.marcar_input_sintetico()
    ctx.logger.info("Paint: %d trazos dibujados.", trazos)


@registrar(
    nombre="calculadora_operar",
    descripcion="Abre la Calculadora y realiza varias operaciones tecleando en vivo",
    categoria="sistema",
    peso=8,
    roba_foco=True,
    disponible=lambda cfg: util.ES_WINDOWS,
)
def calculadora_operar(ctx):
    """Abre la Calculadora y teclea operaciones que se ven resolverse en vivo.

    Pulsa teclas reales (digitos y operadores del teclado numerico), asi que el
    resultado aparece en pantalla como si alguien estuviera calculando. La cierra
    al terminar la jornada, salvo que ya estuviera abierta por el usuario.
    """
    import subprocess

    ya_estaba = ctx.proceso_activo(["CalculatorApp.exe", "Calculator.exe"])
    try:
        subprocess.Popen(["calc.exe"])
    except OSError as error:
        ctx.logger.warning("Calculadora: no se pudo abrir (%s).", error)
        return
    if not ya_estaba:
        ctx.marcar_para_cierre(["CalculatorApp.exe"])
    util.pausa(ctx.rng, 2.5, 4.0)          # la Calculadora tarda un momento en abrir

    operaciones = ctx.rng.randint(2, 4)
    for _ in range(operaciones):
        a = ctx.rng.randint(11, 989)
        b = ctx.rng.randint(2, 89)
        op = ctx.rng.choice(["+", "-", "*", "/"])
        util.teclear_vks("%d%s%d=" % (a, op, b), ctx.rng)
        util.pausa(ctx.rng, 1.2, 3.0)      # dejar ver el resultado
        util.pulsar_vk(util.VK_ESCAPE)     # limpiar antes de la siguiente
        util.pausa(ctx.rng, 0.4, 1.0)
    ctx.logger.info("Calculadora: %d operaciones realizadas.", operaciones)


@registrar(
    nombre="abrir_carpeta_trabajo",
    descripcion="Abre la carpeta de trabajo en el Explorador de archivos",
    categoria="sistema",
    peso=5,
)
def abrir_carpeta_trabajo(ctx):
    # Cierra la ventana que dejo la vez anterior para no llenar el escritorio.
    cerradas = ctx.cerrar_ventanas_explorador()
    os.startfile(str(ctx.carpeta))
    ctx.logger.info("Sistema: carpeta de trabajo abierta en el Explorador (%d previas cerradas).",
                    cerradas)
    util.pausa(ctx.rng, 4.0, 12.0)


@registrar(
    nombre="navegador_consulta",
    descripcion="Abre en el navegador una direccion de la lista autorizada",
    categoria="navegador",
    peso=7,
    disponible=lambda cfg: cfg.navegador.activo and bool(cfg.navegador.urls),
)
def navegador_consulta(ctx):
    url = ctx.rng.choice(ctx.cfg.navegador.urls)
    if not url.lower().startswith(("http://", "https://")):
        ctx.logger.warning("Navegador: se omite %r (solo se permiten http/https).", url)
        return

    # Solo se apunta para cerrar el navegador que arranca por esta accion.
    # Si ya habia uno abierto es del usuario, con sus pestanas, y no se toca.
    vigilar = ctx.cfg.comportamiento.cerrar_navegador
    antes = set(n for n in NAVEGADORES if ctx.proceso_activo([n])) if vigilar else set()

    webbrowser.open(url, new=2)
    ctx.logger.info("Navegador: abierta %s.", url)
    util.pausa(ctx.rng, 4.0, 9.0)          # esperar a que cargue la pagina

    # Recorrer la pagina como si se leyera: baja a saltos con pausas y a veces
    # regresa un poco. Solo si hay pyautogui; el navegador acaba de quedar al
    # frente, asi que el desplazamiento va a su ventana.
    if hay_modulo("pyautogui"):
        import pyautogui
        pyautogui.FAILSAFE = True
        vueltas = ctx.rng.randint(3, 6)
        for _ in range(vueltas):
            pyautogui.scroll(-ctx.rng.randint(3, 8) * 100)
            util.pausa(ctx.rng, 1.5, 4.5)  # "leer" antes del siguiente desplazamiento
        if ctx.rng.random() < 0.5:
            pyautogui.scroll(ctx.rng.randint(2, 5) * 100)   # volver a subir un poco
        util.marcar_input_sintetico()
        ctx.logger.info("Navegador: %d desplazamientos de lectura.", vueltas)
    util.pausa(ctx.rng, 3.0, 12.0)

    if vigilar:
        nuevos = set(n for n in NAVEGADORES if ctx.proceso_activo([n])) - antes
        if nuevos:
            ctx.marcar_para_cierre(nuevos)
            ctx.logger.debug("Navegador: %s se cerrara al terminar.", ", ".join(sorted(nuevos)))
