"""Enumeracion y cierre de las ventanas de aplicacion del escritorio.

Se usa en el cierre de jornada con modo_cierre = "todas". Primero se pide el
cierre a cada ventana con WM_CLOSE, exactamente lo mismo que pulsar su X. Con
forzar=True, lo que no haya terminado por las buenas pasado un margen (una
aplicacion que pregunta si guardar, una colgada, o una que solo se escondio en
la bandeja del sistema) se termina SIN GUARDAR.
"""

from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from dataclasses import dataclass, field

from . import util

WM_CLOSE = 0x0010
GW_OWNER = 4
GWL_EXSTYLE = -20
WS_EX_TOOLWINDOW = 0x00000080
DWMWA_CLOAKED = 14
PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000
WAIT_TIMEOUT = 0x00000102

# Ventanas del propio shell de Windows. Mandarle WM_CLOSE al escritorio
# (Progman) abre el dialogo de apagado del sistema: jamas deben tocarse.
CLASES_EXCLUIDAS = {
    "progman", "workerw", "shell_traywnd", "shell_secondarytraywnd",
    "consolewindowclass",               # consolas clasicas, incluida la del agente
    "cascadia_hosting_window_class",    # Windows Terminal
}

# Procesos del sistema que exponen ventanas "visibles" sin ser aplicaciones del
# usuario, y hospedadores de consola: la del agente se cierra sola al terminar.
PROCESOS_EXCLUIDOS = {
    "textinputhost.exe", "shellexperiencehost.exe", "startmenuexperiencehost.exe",
    "searchhost.exe", "searchapp.exe", "lockapp.exe", "systemsettingsbroker.exe",
    "windowsterminal.exe", "openconsole.exe", "conhost.exe",
}

# Procesos que jamas se terminan a la fuerza aunque tengan ventanas en la lista.
# explorer.exe es a la vez las carpetas y el escritorio con la barra de tareas:
# matarlo se llevaria el shell entero. ApplicationFrameHost aloja a todas las
# apps modernas a la vez, asi que se termina la app concreta, nunca el marco.
NUNCA_TERMINAR = {
    "explorer.exe", "applicationframehost.exe", "dwm.exe", "csrss.exe",
    "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe", "sihost.exe",
    "ctfmon.exe", "fontdrvhost.exe", "taskhostw.exe", "runtimebroker.exe",
}


@dataclass
class Ventana:
    hwnd: int
    pid: int          # proceso duenio de la ventana
    pid_app: int      # proceso a terminar si hay que forzar (la app real en las modernas)
    proceso: str
    clase: str


@dataclass
class ResultadoCierre:
    solicitadas: int = 0
    abiertas: dict = field(default_factory=dict)   # proceso -> ventanas que siguen visibles
    forzadas: dict = field(default_factory=dict)   # proceso -> procesos terminados sin guardar

    @property
    def cerradas(self):
        return self.solicitadas - sum(self.abiertas.values())


# ------------------------------------------------------------ API de Windows
if util.ES_WINDOWS:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    try:
        _dwmapi = ctypes.WinDLL("dwmapi")
    except OSError:
        _dwmapi = None

    _ENUM_PROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    _user32.EnumWindows.argtypes = [_ENUM_PROC, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.EnumChildWindows.argtypes = [wintypes.HWND, _ENUM_PROC, wintypes.LPARAM]
    _user32.EnumChildWindows.restype = wintypes.BOOL
    _user32.IsWindow.argtypes = [wintypes.HWND]
    _user32.IsWindow.restype = wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindow.argtypes = [wintypes.HWND, wintypes.UINT]
    _user32.GetWindow.restype = wintypes.HWND
    _user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowLongW.restype = ctypes.c_long
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetClassNameW.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT,
                                     wintypes.WPARAM, wintypes.LPARAM]
    _user32.PostMessageW.restype = wintypes.BOOL

    _kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    _kernel32.OpenProcess.restype = wintypes.HANDLE
    _kernel32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                                     wintypes.LPWSTR,
                                                     ctypes.POINTER(wintypes.DWORD)]
    _kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    _kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    _kernel32.TerminateProcess.restype = wintypes.BOOL
    _kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    _kernel32.WaitForSingleObject.restype = wintypes.DWORD
    _kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    _kernel32.CloseHandle.restype = wintypes.BOOL
    _kernel32.GetConsoleWindow.argtypes = []
    _kernel32.GetConsoleWindow.restype = wintypes.HWND

    if _dwmapi is not None:
        _dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                                  ctypes.c_void_p, wintypes.UINT]
        _dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long


def _clase(hwnd):
    buffer = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, buffer, 256)
    return buffer.value


def _pid(hwnd):
    pid = wintypes.DWORD(0)
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _nombre_proceso(pid):
    manejador = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not manejador:
        return ""
    try:
        tamano = wintypes.DWORD(1024)
        buffer = ctypes.create_unicode_buffer(tamano.value)
        if _kernel32.QueryFullProcessImageNameW(manejador, 0, buffer, ctypes.byref(tamano)):
            return os.path.basename(buffer.value).lower()
        return ""
    finally:
        _kernel32.CloseHandle(manejador)


def _oculta_por_dwm(hwnd):
    """Las apps modernas suspendidas dicen ser visibles, pero DWM las oculta."""
    if _dwmapi is None:
        return False
    valor = ctypes.c_int(0)
    resultado = _dwmapi.DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED,
                                              ctypes.byref(valor), ctypes.sizeof(valor))
    return resultado == 0 and valor.value != 0


def _app_moderna(hwnd, pid_marco):
    """ApplicationFrameHost aloja las apps modernas: (pid, nombre) de la app real."""
    encontrados = []

    def visitar(hijo, _):
        pid = _pid(hijo)
        if pid and pid != pid_marco:
            encontrados.append(pid)
            return False
        return True

    _user32.EnumChildWindows(hwnd, _ENUM_PROC(visitar), 0)
    if not encontrados:
        return 0, ""
    return encontrados[0], _nombre_proceso(encontrados[0])


# ------------------------------------------------------------------ consulta
def ventanas_de_aplicacion():
    """Ventanas principales de aplicacion que veria el usuario en la barra de tareas."""
    if not util.ES_WINDOWS:
        return []

    propio = os.getpid()
    consola = _kernel32.GetConsoleWindow()
    resultado = []

    def visitar(hwnd, _):
        try:
            if not hwnd or hwnd == consola:
                return True
            if not _user32.IsWindowVisible(hwnd) or _user32.GetWindowTextLengthW(hwnd) == 0:
                return True
            if _user32.GetWindow(hwnd, GW_OWNER):
                return True     # dialogos y ventanas secundarias: caen con su duena
            if _user32.GetWindowLongW(hwnd, GWL_EXSTYLE) & WS_EX_TOOLWINDOW:
                return True
            if _oculta_por_dwm(hwnd):
                return True
            clase = _clase(hwnd)
            if clase.lower() in CLASES_EXCLUIDAS:
                return True
            pid = _pid(hwnd)
            if pid == propio:
                return True
            proceso = _nombre_proceso(pid)
            pid_app = pid
            if proceso == "applicationframehost.exe":
                pid_real, nombre_real = _app_moderna(hwnd, pid)
                pid_app = pid_real              # 0 si no hay app identificable
                proceso = nombre_real or proceso
            if proceso in PROCESOS_EXCLUIDOS:
                return True
            resultado.append(Ventana(hwnd=hwnd, pid=pid, pid_app=pid_app,
                                     proceso=proceso or "desconocido", clase=clase))
        except Exception:
            pass                # una ventana rara no debe cortar la enumeracion
        return True

    _user32.EnumWindows(_ENUM_PROC(visitar), 0)
    return resultado


def agrupar(ventanas):
    """proceso -> numero de ventanas, ordenado por nombre."""
    conteo = {}
    for ventana in ventanas:
        conteo[ventana.proceso] = conteo.get(ventana.proceso, 0) + 1
    return dict(sorted(conteo.items()))


# -------------------------------------------------------------------- cierre
def _visibles(ventanas):
    return [v for v in ventanas if _user32.IsWindow(v.hwnd) and _user32.IsWindowVisible(v.hwnd)]


def _esperar_ventanas(ventanas, espera_seg):
    pendientes = list(ventanas)
    limite = time.time() + espera_seg
    while pendientes and time.time() < limite:
        time.sleep(1.0)
        pendientes = _visibles(pendientes)
    return pendientes


def _esperar_procesos(manejadores, espera_seg):
    """PIDs cuyos procesos siguen vivos al acabar el margen."""
    limite = time.time() + espera_seg
    while True:
        vivos = [pid for pid, (manejador, _) in manejadores.items()
                 if _kernel32.WaitForSingleObject(manejador, 0) == WAIT_TIMEOUT]
        if not vivos or time.time() >= limite:
            return vivos
        time.sleep(1.0)


def cerrar_aplicaciones(espera_seg=15, forzar=False, gracia_proceso_seg=10, filtro=None):
    """Pide el cierre de todas las ventanas de aplicacion y, si se indica, fuerza.

    espera_seg: margen para que las ventanas cierren por las buenas.
    forzar: terminar SIN GUARDAR los procesos que sigan vivos despues.
    gracia_proceso_seg: margen extra para que los procesos que ya cerraron su
        ventana terminen de salir solos antes de forzar a nadie.
    filtro: funcion opcional Ventana -> bool. Solo para pruebas, para verificar el
        cierre sin llevarse por delante el resto del escritorio.
    """
    if not util.ES_WINDOWS:
        return ResultadoCierre()

    ventanas = ventanas_de_aplicacion()
    if filtro is not None:
        ventanas = [v for v in ventanas if filtro(v)]

    # Con forzar, los procesos se abren ANTES de pedir el cierre: tener el
    # manejador impide que Windows reutilice su PID si terminan por su cuenta,
    # asi que nunca se puede terminar por error un proceso distinto.
    manejadores = {}
    if forzar:
        for ventana in ventanas:
            if (not ventana.pid_app or ventana.pid_app in manejadores
                    or ventana.proceso in NUNCA_TERMINAR):
                continue
            manejador = _kernel32.OpenProcess(PROCESS_TERMINATE | SYNCHRONIZE, False,
                                              ventana.pid_app)
            if manejador:           # sin permiso (p. ej. app de administrador): no se fuerza
                manejadores[ventana.pid_app] = (manejador, ventana.proceso)

    forzadas = {}
    try:
        for ventana in ventanas:
            _user32.PostMessageW(ventana.hwnd, WM_CLOSE, 0, 0)

        pendientes = _esperar_ventanas(ventanas, espera_seg)

        if forzar:
            for pid in _esperar_procesos(manejadores, gracia_proceso_seg):
                manejador, proceso = manejadores[pid]
                if _kernel32.TerminateProcess(manejador, 1):
                    _kernel32.WaitForSingleObject(manejador, 5000)
                    forzadas[proceso] = forzadas.get(proceso, 0) + 1
            pendientes = _visibles(pendientes)
    finally:
        for manejador, _ in manejadores.values():
            _kernel32.CloseHandle(manejador)

    return ResultadoCierre(solicitadas=len(ventanas), abiertas=agrupar(pendientes),
                           forzadas=dict(sorted(forzadas.items())))
