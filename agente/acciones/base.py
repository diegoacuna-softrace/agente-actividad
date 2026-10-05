"""Registro de acciones y contexto de ejecucion compartido."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass, field
from pathlib import Path

from .. import util

# Registro global: nombre -> Accion. Se llena con el decorador @registrar.
ACCIONES = {}


@dataclass
class Accion:
    nombre: str
    descripcion: str
    categoria: str                 # office | nativa | sistema | navegador
    funcion: object
    peso: int = 10
    roba_foco: bool = True         # si trae una ventana al frente
    es_latido: bool = False        # micro-accion de relleno entre acciones grandes
    disponible: object = None      # callable(cfg) -> bool

    def esta_disponible(self, cfg):
        if self.disponible is None:
            return True
        try:
            return bool(self.disponible(cfg))
        except Exception:
            return False


def registrar(nombre, descripcion, categoria, peso=10, roba_foco=True,
              es_latido=False, disponible=None):
    def decorador(funcion):
        ACCIONES[nombre] = Accion(
            nombre=nombre,
            descripcion=descripcion,
            categoria=categoria,
            funcion=funcion,
            peso=peso,
            roba_foco=roba_foco,
            es_latido=es_latido,
            disponible=disponible,
        )
        return funcion
    return decorador


# ------------------------------------------------------------- disponibilidad
def hay_modulo(nombre):
    try:
        return importlib.util.find_spec(nombre) is not None
    except (ImportError, ValueError):
        return False


def progid_registrado(prog_id):
    """True si el ProgID COM existe en el registro (sin lanzar la aplicacion)."""
    if not util.ES_WINDOWS:
        return False
    try:
        import winreg
        winreg.CloseKey(winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, prog_id))
        return True
    except OSError:
        return False


def hay_com():
    return util.ES_WINDOWS and hay_modulo("win32com")


# ------------------------------------------------------------------- contexto
# PowerPoint no admite Application.Visible = False: siempre se muestra.
_SIEMPRE_VISIBLE = {"PowerPoint.Application"}
# Aplicaciones COM que el agente abre pero nunca cierra. Vacio: el agente solo
# abre Word, Excel y PowerPoint, y esas si se cierran al terminar.
_NO_CERRAR = set()


@dataclass
class Contexto:
    cfg: object
    logger: object
    rng: object
    carpeta: Path
    datos: dict = field(default_factory=dict)   # estado libre entre acciones de una jornada
    _apps: dict = field(default_factory=dict)
    _procesos: dict = field(default_factory=dict)
    _com_iniciado: bool = False

    # -------------------------------------------------------------- Office COM
    def app_office(self, prog_id):
        """Devuelve la aplicacion COM, reutilizando la instancia previa si sigue viva."""
        app = self._apps.get(prog_id)
        if app is not None:
            try:
                app.Name              # sonda barata: falla si el usuario la cerro
                return app
            except Exception:
                self.logger.debug("La instancia de %s ya no responde; se recrea.", prog_id)
                self._apps.pop(prog_id, None)

        import pythoncom
        import win32com.client

        if not self._com_iniciado:
            pythoncom.CoInitialize()
            self._com_iniciado = True

        if prog_id in _NO_CERRAR:
            # Dispatch se engancha a la instancia ya abierta en vez de duplicarla.
            app = win32com.client.Dispatch(prog_id)
        else:
            # DispatchEx crea una instancia propia y no toca los documentos del usuario.
            app = win32com.client.DispatchEx(prog_id)

        if prog_id not in _NO_CERRAR:
            visible = True if prog_id in _SIEMPRE_VISIBLE else self.cfg.comportamiento.apps_visibles
            try:
                app.Visible = visible
            except Exception:
                pass
        self._apps[prog_id] = app
        return app

    # ------------------------------------------------------------ Explorador
    def cerrar_ventanas_explorador(self):
        """Cierra las ventanas del Explorador abiertas sobre la carpeta de trabajo.

        Evita acumular una ventana por cada vez que el agente abre la carpeta.
        Solo toca las que apuntan dentro del area de trabajo: las ventanas del
        usuario sobre cualquier otra ruta se dejan intactas.
        """
        try:
            import win32com.client
            ventanas = win32com.client.Dispatch("Shell.Application").Windows()
        except Exception:
            return 0

        from urllib.parse import unquote
        base = str(self.carpeta.resolve()).lower()
        candidatas = []
        for indice in range(ventanas.Count):
            try:
                ventana = ventanas.Item(indice)
                url = str(ventana.LocationURL or "")
                if not url.lower().startswith("file:"):
                    continue
                ruta = unquote(url)[len("file:///"):].replace("/", "\\").lower()
                if ruta.startswith(base):
                    candidatas.append(ventana)
            except Exception:
                continue

        cerradas = 0
        for ventana in candidatas:          # se cierran fuera del recorrido
            try:
                ventana.Quit()
                cerradas += 1
            except Exception:
                continue
        return cerradas

    # ------------------------------------------------------------- procesos
    def procesos_en_ejecucion(self):
        """Conjunto de ejecutables activos ahora mismo, en minusculas."""
        import subprocess
        try:
            resultado = subprocess.run(["tasklist", "/nh", "/fo", "csv"],
                                       capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return set()
        nombres = set()
        for linea in resultado.stdout.splitlines():
            if linea.startswith('"'):
                nombres.add(linea.split('","')[0].strip('"').lower())
        return nombres

    def proceso_activo(self, nombres):
        activos = self.procesos_en_ejecucion()
        return any(nombre.lower() in activos for nombre in nombres)

    def marcar_para_cierre(self, nombres):
        """Apunta ejecutables que el agente abrio, para cerrarlos al terminar.

        Solo debe usarse con aplicaciones que no estaban corriendo antes: lo que
        ya estaba abierto es del usuario y no se toca.
        """
        self.datos.setdefault("procesos_a_cerrar", set()).update(nombres)

    def _cerrar_marcados(self):
        import subprocess
        marcados = self.datos.get("procesos_a_cerrar", set())
        if not marcados:
            return 0
        activos = self.procesos_en_ejecucion()
        cerrados = 0
        for nombre in sorted(marcados):
            if nombre.lower() not in activos:
                continue
            try:
                # Sin /f a proposito: es una peticion de cierre, no una muerte.
                # Si la aplicacion tiene trabajo sin guardar preguntara y se
                # quedara abierta, que es lo correcto.
                resultado = subprocess.run(["taskkill", "/im", nombre],
                                           capture_output=True, text=True, timeout=20)
                if resultado.returncode == 0:
                    cerrados += 1
            except (OSError, subprocess.SubprocessError):
                continue
        marcados.clear()
        return cerrados

    # ---------------------------------------------------------- subprocesos
    def lanzar_proceso(self, clave, argumentos):
        """Lanza un proceso auxiliar cerrando antes el anterior con la misma clave."""
        import subprocess
        self.terminar_proceso(clave)
        proceso = subprocess.Popen(argumentos)
        self._procesos[clave] = proceso
        return proceso

    def terminar_proceso(self, clave):
        proceso = self._procesos.pop(clave, None)
        if proceso is None or proceso.poll() is not None:
            return
        try:
            proceso.terminate()
        except Exception:
            self.logger.debug("No se pudo cerrar el proceso %r.", clave)

    # ------------------------------------------------------------- limpieza
    def cerrar_todo(self):
        for clave in list(self._procesos):
            self.terminar_proceso(clave)

        if self.cfg.comportamiento.cerrar_apps:
            for prog_id, app in list(self._apps.items()):
                if prog_id in _NO_CERRAR:
                    continue
                try:
                    app.DisplayAlerts = False
                except Exception:
                    pass
                try:
                    app.Quit()
                    self.logger.debug("Cerrada la aplicacion %s.", prog_id)
                except Exception:
                    self.logger.debug("No se pudo cerrar %s.", prog_id)
        self._apps.clear()

        # Lo que quedo abierto por el camino y no se cierra solo. Nunca toca lo
        # que ya estaba abierto antes de arrancar el agente. El cierre de TODAS
        # las aplicaciones no vive aqui: lo decide el runner, porque solo
        # procede cuando la jornada termina por su hora.
        if self.cfg.comportamiento.modo_cierre != "ninguno":
            ventanas = self.cerrar_ventanas_explorador()
            procesos = self._cerrar_marcados()
            if ventanas or procesos:
                self.logger.info(
                    "Cierre de jornada: %d ventanas del Explorador y %d aplicaciones cerradas.",
                    ventanas, procesos)

        if self._com_iniciado:
            try:
                import pythoncom
                pythoncom.CoUninitialize()
            except Exception:
                pass
            self._com_iniciado = False
