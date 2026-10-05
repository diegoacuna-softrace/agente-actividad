"""Utilidades transversales: logging, deteccion de actividad humana y textos."""

from __future__ import annotations

import ctypes
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

ES_WINDOWS = sys.platform == "win32"


# ---------------------------------------------------------------------- logging
def configurar_logging(carpeta, verboso=False):
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    archivo = carpeta / ("agente-%s.log" % datetime.now().strftime("%Y-%m-%d"))

    logger = logging.getLogger("agente")
    logger.setLevel(logging.DEBUG if verboso else logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    consola = logging.StreamHandler()
    consola.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))
    logger.addHandler(consola)

    disco = logging.FileHandler(archivo, encoding="utf-8")
    disco.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s"))
    logger.addHandler(disco)
    return logger


# -------------------------------------------------- deteccion de usuario humano
class _LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


_ultimo_input_sintetico = 0.0


def marcar_input_sintetico():
    """Registra que el propio agente acaba de mover el raton o pulsar teclas."""
    global _ultimo_input_sintetico
    _ultimo_input_sintetico = time.time()


def segundos_inactividad():
    """Segundos transcurridos desde la ultima entrada de teclado o raton."""
    if not ES_WINDOWS:
        return 1e9
    info = _LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 1e9
    kernel32 = ctypes.windll.kernel32
    kernel32.GetTickCount.restype = ctypes.c_uint32
    ahora = kernel32.GetTickCount()
    # dwTime viene de GetTickCount (32 bits): el modulo evita el desborde a los 49 dias.
    return ((ahora - info.dwTime) % (2 ** 32)) / 1000.0


def usuario_activo(umbral_seg):
    """True si hubo actividad *humana* reciente; descarta la que genera el agente."""
    inactivo = segundos_inactividad()
    if inactivo > umbral_seg:
        return False
    momento_ultimo_input = time.time() - inactivo
    return momento_ultimo_input > _ultimo_input_sintetico + 1.5


# ------------------------------------------------- mantener el equipo despierto
# SetThreadExecutionState le pide a Windows que no apague la pantalla ni suspenda
# el equipo. Es un refuerzo de los movimientos de raton: NO desbloquea una
# pantalla ya bloqueada, eso depende de la configuracion del equipo.
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001
_ES_DISPLAY_REQUIRED = 0x00000002


def mantener_despierto(activar):
    """Activa o desactiva el estado 'no suspender / no apagar pantalla'.

    El estado es por hilo y persiste hasta que se cambia, asi que debe activarse
    y desactivarse desde el mismo hilo que gobierna la jornada (el principal).

    OJO: esto evita que la pantalla se apague y que el equipo se suspenda, pero
    NO evita el bloqueo. El bloqueo lo dispara la inactividad de teclado/raton;
    para eso esta pulsar_tecla_inofensiva().
    """
    if not ES_WINDOWS:
        return False
    if activar:
        estado = _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED | _ES_DISPLAY_REQUIRED
    else:
        estado = _ES_CONTINUOUS
    # Devuelve 0 (NULL) si falla; cualquier otro valor es exito.
    return ctypes.windll.kernel32.SetThreadExecutionState(estado) != 0


_VK_F15 = 0x7E
_KEYEVENTF_KEYUP = 0x0002


def pulsar_tecla_inofensiva():
    """Envia F15 (una tecla que no hace nada en ninguna aplicacion).

    Reinicia el contador de inactividad de Windows, evitando el bloqueo y el
    protector de pantalla sin alterar el trabajo del usuario ni el foco.
    """
    if not ES_WINDOWS:
        return False
    user32 = ctypes.windll.user32
    user32.keybd_event(_VK_F15, 0, 0, 0)                  # tecla abajo
    user32.keybd_event(_VK_F15, 0, _KEYEVENTF_KEYUP, 0)   # tecla arriba
    marcar_input_sintetico()
    return True


# ------------------------------------------------------ tecleo Unicode en vivo
# Escribe texto caracter a caracter con SendInput y KEYEVENTF_UNICODE, para que
# se vea aparecer "en vivo" en la ventana enfocada. Al enviar codigos Unicode (y
# no codigos de tecla), es INDEPENDIENTE de la distribucion del teclado: escribe
# lo mismo en un teclado en espanol (es-LA) que en uno en ingles, a diferencia de
# pyautogui.typewrite, que asume distribucion de EE.UU.
if ES_WINDOWS:
    from ctypes import wintypes

    _ULONG_PTR = ctypes.c_size_t

    class _KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", _ULONG_PTR)]

    class _MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]

    class _HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("ki", _KEYBDINPUT), ("mi", _MOUSEINPUT), ("hi", _HARDWAREINPUT)]

    class _INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    _INPUT_KEYBOARD = 1
    _KEYEVENTF_UNICODE = 0x0004
    _VK_RETURN = 0x0D

    def _evento_unicode(ch, keyup):
        flags = _KEYEVENTF_UNICODE | (_KEYEVENTF_KEYUP if keyup else 0)
        ki = _KEYBDINPUT(0, ord(ch), flags, 0, 0)
        return _INPUT(_INPUT_KEYBOARD, _INPUTUNION(ki=ki))

    def _evento_vk(vk, keyup):
        flags = _KEYEVENTF_KEYUP if keyup else 0
        ki = _KEYBDINPUT(vk, 0, flags, 0, 0)
        return _INPUT(_INPUT_KEYBOARD, _INPUTUNION(ki=ki))

    def _enviar_eventos(*eventos):
        cantidad = len(eventos)
        arreglo = (_INPUT * cantidad)(*eventos)
        return ctypes.windll.user32.SendInput(cantidad, arreglo, ctypes.sizeof(_INPUT))


def teclear_unicode(texto, rng=None, lento_min=0.03, lento_max=0.10):
    """Teclea 'texto' caracter a caracter en la ventana enfocada, en vivo.

    Cada caracter se envia como pulsacion Unicode con una pequena pausa, de modo
    que se ve escribir letra a letra (no es un pegado). Los saltos de linea van
    como Enter. Devuelve cuantos caracteres se escribieron.

    OJO: escribe en la ventana que tenga el foco. Solo debe usarse tras abrir y
    enfocar una ventana propia del agente (p. ej. el Bloc de notas que abrio el).
    """
    if not ES_WINDOWS:
        return 0
    escritos = 0
    for ch in texto:
        if ch == "\r":
            continue
        if ch == "\n":
            _enviar_eventos(_evento_vk(_VK_RETURN, False), _evento_vk(_VK_RETURN, True))
        else:
            _enviar_eventos(_evento_unicode(ch, False), _evento_unicode(ch, True))
        escritos += 1
        if rng is not None:
            time.sleep(rng.uniform(lento_min, lento_max))
        else:
            time.sleep((lento_min + lento_max) / 2)
    marcar_input_sintetico()
    return escritos


# ---------------------------------------------------- pulsaciones por codigo VK
# Para la calculadora: digitos de la fila superior (0x30-0x39, iguales en todas
# las distribuciones) y operadores del teclado numerico (teclas dedicadas, que
# no dependen de Bloq Num ni del idioma). '=' se envia como Enter.
VK_ESCAPE = 0x1B
VK_CALC = {str(d): 0x30 + d for d in range(10)}
VK_CALC.update({"+": 0x6B, "-": 0x6D, "*": 0x6A, "/": 0x6F, "=": 0x0D})


def pulsar_vk(vk):
    """Envia una sola tecla (abajo y arriba) por su codigo virtual."""
    if not ES_WINDOWS:
        return False
    _enviar_eventos(_evento_vk(vk, False), _evento_vk(vk, True))
    marcar_input_sintetico()
    return True


def teclear_vks(secuencia, rng=None, lento_min=0.10, lento_max=0.30):
    """Teclea una expresion (p. ej. '128+47=') pulsando teclas reales, una a una.

    Solo interpreta digitos y los operadores + - * / = (ver VK_CALC); cualquier
    otro caracter se ignora. Sirve para operar la Calculadora de forma visible e
    independiente del idioma del teclado. Devuelve cuantas teclas se enviaron.
    """
    if not ES_WINDOWS:
        return 0
    enviadas = 0
    for ch in secuencia:
        vk = VK_CALC.get(ch)
        if vk is None:
            continue
        _enviar_eventos(_evento_vk(vk, False), _evento_vk(vk, True))
        enviadas += 1
        if rng is not None:
            time.sleep(rng.uniform(lento_min, lento_max))
        else:
            time.sleep((lento_min + lento_max) / 2)
    marcar_input_sintetico()
    return enviadas


# ------------------------------------------------------------- pausas y textos
def pausa(rng, minimo, maximo):
    time.sleep(rng.uniform(minimo, maximo))


_APERTURAS = [
    "Se reviso", "Se valido", "Se actualizo", "Se consolido", "Se depuro",
    "Se verifico", "Se ajusto", "Se documento", "Se reproceso", "Se concilio",
    "Se cargo", "Se cerro", "Se recalculo", "Se confirmo", "Se reviso a detalle",
    "Se dejo listo", "Se reviso con el area", "Se normalizo", "Se cruzo",
    "Se depuro y valido", "Se contrasto", "Se reviso preliminarmente",
]
_OBJETOS = [
    "el consolidado de existencias", "el reporte de movimientos del dia",
    "la conciliacion de saldos", "el listado de pendientes por confirmar",
    "la trazabilidad de los traslados", "el cierre parcial del periodo",
    "el seguimiento a las solicitudes abiertas", "el tablero de indicadores",
    "la matriz de responsables por regional", "el cargue de la ultima remesa",
    "el inventario ciclico de la bodega", "el detalle de faltantes y sobrantes",
    "la validacion de seriales", "el reporte de rotacion de material",
    "el archivo de cargue masivo", "la conciliacion contra el sistema",
    "el balance de la ubicacion de conciliacion", "el reporte de consumos",
    "la revision de las transferencias internas", "el listado de bajas documentadas",
    "el cruce de saldos por sucursal", "el seguimiento a los traslados inter-sucursal",
    "el reporte de material en terreno", "la ficha tecnica de los equipos",
    "el borrador del informe mensual", "el resumen de novedades por regional",
    "el control de recepciones", "la depuracion de ubicaciones duplicadas",
]
_COMPLEMENTOS = [
    "sin novedades relevantes", "con dos diferencias menores por confirmar",
    "y queda pendiente la respuesta del area responsable",
    "quedando el resultado a la espera de aprobacion",
    "y se dejo la evidencia en la carpeta compartida",
    "con corte al cierre de la jornada anterior",
    "para revisarlo en el comite de la proxima semana",
    "y se notifico al responsable del proceso",
    "sin diferencias frente al periodo anterior",
    "con una observacion menor por documentar",
    "y se actualizo el estado en el tablero",
    "a la espera de la validacion final",
    "con los ajustes ya aplicados",
    "y se escalo el caso al area correspondiente",
    "quedando conforme lo revisado",
    "con un pendiente por cerrar manana",
    "y se solicito soporte al equipo tecnico",
    "sin impacto en los saldos",
    "y se programo una segunda revision",
    "con el detalle registrado en la bitacora",
]
_AREAS = [
    "logistica", "operaciones", "el area de inventarios", "la regional Centro",
    "la regional Antioquia", "la regional Costa", "la regional Valle", "compras",
    "el almacen", "distribucion", "control interno", "planeacion", "el CEDI",
    "la coordinacion nacional", "el equipo de conciliacion", "soporte tecnico",
]
_ROLES = [
    "el coordinador regional", "el responsable de bodega", "el analista de inventarios",
    "la jefatura de logistica", "el supervisor de operaciones", "el auditor interno",
    "el lider del proceso", "el responsable de la sucursal", "la coordinacion regional",
    "el encargado del CEDI",
]
_ACCIONES_INF = [
    "revisar", "conciliar", "validar", "actualizar", "depurar", "confirmar",
    "cerrar", "reprocesar", "documentar", "cargar", "verificar", "ajustar",
    "cruzar", "normalizar",
]
_ESTADOS_ADJ = [
    "conciliado", "pendiente de aprobacion", "en revision", "cerrado",
    "a la espera de respuesta", "documentado", "escalado al area responsable",
    "listo para aprobacion", "sin diferencias",
]
_TEMAS = [
    "Seguimiento operativo", "Revision de saldos", "Conciliacion pendiente",
    "Avance del plan de trabajo", "Notas de la reunion", "Control de novedades",
    "Resumen de la jornada", "Puntos por confirmar", "Preparacion del cierre",
    "Inventario ciclico", "Cruce de existencias", "Novedades por regional",
    "Traslados inter-sucursal", "Faltantes y sobrantes", "Cargue masivo",
    "Validacion de seriales", "Indicadores de rotacion", "Bajas documentadas",
    "Recepciones del dia", "Seguimiento a pendientes",
]
_PERIODOS = [
    "semana en curso", "corte del dia", "periodo actual", "seguimiento diario",
    "revision quincenal", "cierre mensual", "corte semanal", "avance del mes",
    "seguimiento de la regional", "consolidado del periodo",
]
_SUCURSALES = [
    "Bogota", "Medellin", "Barranquilla", "Cali", "Bucaramanga", "Pereira",
    "Cartagena", "Cucuta", "Manizales", "Ibague", "Villavicencio", "Santa Marta",
    "Neiva", "Monteria", "Pasto", "Armenia",
]
_ESTADOS = [
    "Conciliado", "En revision", "Pendiente", "Cerrado", "Aprobado",
    "Por confirmar", "Escalado", "Ajustado",
]
_TIPOS_BODEGA = ["A", "Q", "U", "K"]


def _cap(texto):
    return texto[:1].upper() + texto[1:] if texto else texto


def _a(frase):
    """Contraccion 'a' + articulo: 'a el X' -> 'al X'."""
    return "al " + frase[3:] if frase.startswith("el ") else "a " + frase


def _de(frase):
    """Contraccion 'de' + articulo: 'de el X' -> 'del X'."""
    return "del " + frase[3:] if frase.startswith("el ") else "de " + frase


def frase(rng):
    """Genera una frase de oficina verosimil eligiendo entre varias estructuras."""
    obj = rng.choice(_OBJETOS)
    comp = rng.choice(_COMPLEMENTOS)
    plantilla = rng.randint(1, 9)
    if plantilla == 1:
        return "%s %s %s." % (rng.choice(_APERTURAS), obj, comp)
    if plantilla == 2:
        return "Pendiente: %s; %s." % (obj, comp)
    if plantilla == 3:
        return "%s solicito %s %s." % (_cap(rng.choice(_ROLES)),
                                       rng.choice(_ACCIONES_INF), obj)
    if plantilla == 4:
        return "Se coordino con %s para %s %s." % (rng.choice(_AREAS),
                                                   rng.choice(_ACCIONES_INF), obj)
    if plantilla == 5:
        return "%s quedo %s tras la revision %s." % (_cap(obj),
                                                     rng.choice(_ESTADOS_ADJ),
                                                     _de(rng.choice(_AREAS)))
    if plantilla == 6:
        return "%s %s (%d registros) %s." % (rng.choice(_APERTURAS), obj,
                                             rng.randint(3, 480), comp)
    if plantilla == 7:
        return "Segun %s, %s %s." % (rng.choice(_AREAS), obj, comp)
    if plantilla == 8:
        return "Queda para %s: %s %s." % (rng.choice(_PERIODOS),
                                          rng.choice(_ACCIONES_INF), obj)
    return "%s %s y se informo %s." % (rng.choice(_APERTURAS), obj,
                                       _a(rng.choice(_ROLES)))


def parrafo(rng, minimo=2, maximo=5):
    return " ".join(frase(rng) for _ in range(rng.randint(minimo, maximo)))


def asunto(rng):
    tema = rng.choice(_TEMAS)
    forma = rng.randint(1, 5)
    if forma == 1:
        return "%s - %s" % (tema, rng.choice(_PERIODOS))
    if forma == 2:
        return "%s: %s" % (tema, _cap(rng.choice(_AREAS)))
    if forma == 3:
        return "%s (%s)" % (tema, rng.choice(_PERIODOS))
    if forma == 4:
        return "RE: %s" % tema
    return "%s - %s" % (tema, rng.choice(_SUCURSALES))


def vinetas(rng, cantidad=3):
    return [frase(rng) for _ in range(cantidad)]


def fila_tabular(rng):
    """Fila ficticia para la hoja de calculo de trabajo."""
    return [
        datetime.now().strftime("%Y-%m-%d"),
        rng.choice(_SUCURSALES),
        "%s%d-%03d" % (rng.choice(_TIPOS_BODEGA), rng.randint(1, 6), rng.randint(1, 90)),
        rng.randint(1, 500),
        round(rng.uniform(1000, 250000), 2),
        rng.choice(_ESTADOS),
    ]


def formatear_duracion(segundos):
    segundos = int(max(0, segundos))
    horas, resto = divmod(segundos, 3600)
    minutos, seg = divmod(resto, 60)
    if horas:
        return "%dh %02dm" % (horas, minutos)
    if minutos:
        return "%dm %02ds" % (minutos, seg)
    return "%ds" % seg
