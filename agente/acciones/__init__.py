"""Catalogo de acciones disponibles para el agente."""

from __future__ import annotations

from .base import ACCIONES, Accion, Contexto, registrar  # noqa: F401

# Los modulos se importan por su efecto colateral: registran sus acciones.
from . import nativas, office, sistema  # noqa: E402,F401


def catalogo(cfg):
    """Acciones aplicables a esta configuracion, con el peso ya resuelto.

    Un peso de 0 en cfg.pesos desactiva la accion sin tener que tocar el codigo.
    """
    resultado = {}
    for nombre, accion in ACCIONES.items():
        if not accion.esta_disponible(cfg):
            continue
        peso = cfg.pesos.get(nombre, accion.peso)
        if peso <= 0:
            continue
        resultado[nombre] = (accion, peso)
    return resultado


def descartadas(cfg):
    """Acciones que no se usaran, con el motivo. Sirve para diagnosticar."""
    motivos = {}
    for nombre, accion in ACCIONES.items():
        if not accion.esta_disponible(cfg):
            motivos[nombre] = "no disponible en este equipo o desactivada en la configuracion"
        elif cfg.pesos.get(nombre, accion.peso) <= 0:
            motivos[nombre] = "peso 0 en la configuracion"
    return motivos
