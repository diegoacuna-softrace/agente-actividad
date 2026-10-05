"""Carga y validacion de la configuracion del agente."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from datetime import time
from pathlib import Path


def _hora(texto):
    horas, minutos = texto.split(":")
    return time(int(horas), int(minutos))


@dataclass
class Jornada:
    # La hora de inicio se sortea entre inicio_min e inicio_max, y la de fin
    # entre fin_min y fin_max. Cada dia sale una hora distinta dentro de esas
    # ventanas.
    inicio_min: str = "08:00"
    inicio_max: str = "09:00"
    fin_min: str = "17:00"
    fin_max: str = "18:00"
    dias: list = field(default_factory=lambda: [0, 1, 2, 3, 4])  # 0=lunes ... 6=domingo

    @property
    def hora_inicio_min(self):
        return _hora(self.inicio_min)

    @property
    def hora_inicio_max(self):
        return _hora(self.inicio_max)

    @property
    def hora_fin_min(self):
        return _hora(self.fin_min)

    @property
    def hora_fin_max(self):
        return _hora(self.fin_max)


@dataclass
class Almuerzo:
    activo: bool = True
    desde: str = "12:30"
    hasta: str = "13:30"
    duracion_min: int = 45
    duracion_max: int = 75


@dataclass
class Ritmo:
    acciones_min: int = 20
    acciones_max: int = 34
    separacion_minutos: int = 5
    latido_min: int = 7
    latido_max: int = 20


@dataclass
class Comportamiento:
    apps_visibles: bool = True
    respetar_usuario: bool = True
    umbral_usuario_seg: int = 120
    aplazar_min: int = 4
    aplazar_max: int = 12
    max_aplazamientos: int = 3
    cerrar_apps: bool = True
    mantener_despierto: bool = True   # pedir a Windows no apagar pantalla ni suspender
    forzar_energia: bool = True       # ademas, poner el plan de energia en 'nunca' (Modern Standby)
    vigilia_evita_bloqueo: bool = True  # la vigilia pulsa F15 fuera de horario para no bloquearse
    # Que se cierra a la hora de fin de la jornada:
    #   ninguno - nada (Office lo sigue gobernando cerrar_apps)
    #   agente  - solo lo que abrio el agente y no estaba ya abierto
    #   simular - como agente, y ademas registra lo que cerraria "todas"
    #   todas   - como agente, y ademas pide cerrar todas las aplicaciones abiertas
    modo_cierre: str = "agente"
    forzar_cierre: bool = False      # terminar SIN GUARDAR lo que no cierre por las buenas
    espera_usuario_min: int = 30     # espera si alguien usa el equipo antes del cierre total
    cerrar_navegador: bool = False   # modos agente/simular: incluir el navegador que abrio


@dataclass
class Navegador:
    activo: bool = False
    urls: list = field(default_factory=list)


@dataclass
class Config:
    jornada: Jornada = field(default_factory=Jornada)
    almuerzo: Almuerzo = field(default_factory=Almuerzo)
    ritmo: Ritmo = field(default_factory=Ritmo)
    comportamiento: Comportamiento = field(default_factory=Comportamiento)
    navegador: Navegador = field(default_factory=Navegador)
    carpeta_trabajo: str = "~/AgenteActividad"
    carpeta_logs: str = "logs"
    pesos: dict = field(default_factory=dict)   # nombre_accion -> peso (0 la desactiva)
    semilla: object = None

    # ------------------------------------------------------------------ rutas
    @property
    def ruta_trabajo(self):
        return Path(self.carpeta_trabajo).expanduser()

    @property
    def ruta_logs(self):
        ruta = Path(self.carpeta_logs).expanduser()
        return ruta if ruta.is_absolute() else self.ruta_trabajo / ruta

    # ------------------------------------------------------ (des)serializacion
    @classmethod
    def _anidados(cls):
        return {
            "jornada": Jornada,
            "almuerzo": Almuerzo,
            "ritmo": Ritmo,
            "comportamiento": Comportamiento,
            "navegador": Navegador,
        }

    @classmethod
    def desde_dict(cls, datos):
        anidados = cls._anidados()
        propios = set(f.name for f in dataclasses.fields(cls))
        kwargs = {}
        for clave, valor in datos.items():
            if clave.startswith("_"):        # claves tipo "_comentario" se ignoran
                continue
            if clave in anidados:
                kwargs[clave] = _construir(anidados[clave], valor, clave)
            elif clave in propios:
                kwargs[clave] = valor
            else:
                raise ValueError("Clave desconocida en la configuracion: %r" % clave)
        return cls(**kwargs)

    @classmethod
    def cargar(cls, ruta=None):
        if ruta is None:
            return cls()
        ruta = Path(ruta).expanduser()
        if not ruta.exists():
            raise FileNotFoundError("No existe el archivo de configuracion: %s" % ruta)
        # utf-8-sig tolera el BOM que agregan el Bloc de notas y varios editores
        # de Windows al guardar; sin esto el JSON no se puede leer.
        return cls.desde_dict(json.loads(ruta.read_text(encoding="utf-8-sig")))

    def a_dict(self):
        return dataclasses.asdict(self)

    def validar(self):
        j = self.jornada
        if j.hora_inicio_min > j.hora_inicio_max:
            raise ValueError("jornada.inicio_min no puede ser posterior a inicio_max.")
        if j.hora_fin_min > j.hora_fin_max:
            raise ValueError("jornada.fin_min no puede ser posterior a fin_max.")
        if j.hora_inicio_max >= j.hora_fin_min:
            raise ValueError("La jornada debe empezar (inicio_max) antes de terminar (fin_min).")
        if self.ritmo.acciones_min > self.ritmo.acciones_max:
            raise ValueError("ritmo.acciones_min no puede superar a ritmo.acciones_max.")
        if self.ritmo.latido_min > self.ritmo.latido_max:
            raise ValueError("ritmo.latido_min no puede superar a ritmo.latido_max.")
        if self.ritmo.separacion_minutos < 1:
            raise ValueError("ritmo.separacion_minutos debe ser al menos 1.")
        if self.navegador.activo and not self.navegador.urls:
            raise ValueError("navegador.activo exige al menos una URL en navegador.urls.")
        modos = ("ninguno", "agente", "simular", "todas")
        if self.comportamiento.modo_cierre not in modos:
            raise ValueError("comportamiento.modo_cierre debe ser uno de: %s." % ", ".join(modos))
        if self.comportamiento.espera_usuario_min < 0:
            raise ValueError("comportamiento.espera_usuario_min no puede ser negativo.")


def _construir(clase, datos, seccion):
    if not isinstance(datos, dict):
        raise ValueError("La seccion %r debe ser un objeto JSON." % seccion)
    validos = set(f.name for f in dataclasses.fields(clase))
    # Igual que en el nivel superior: cualquier clave que empiece por guion bajo
    # es un comentario del JSON y se ignora.
    utiles = dict((k, v) for k, v in datos.items() if not k.startswith("_"))
    desconocidos = set(utiles) - validos
    if desconocidos:
        raise ValueError(
            "Claves desconocidas en %r: %s" % (seccion, ", ".join(sorted(desconocidos)))
        )
    return clase(**utiles)
