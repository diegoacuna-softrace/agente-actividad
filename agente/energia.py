"""Forzar el plan de energia para que la pantalla no se apague ni el equipo se
suspenda.

En equipos con Modern Standby (S0 Low Power Idle) —la mayoria de los portatiles
modernos— la peticion SetThreadExecutionState no basta: Windows suspende igual.
Cambiar los tiempos del plan activo a 0 ("nunca") con powercfg si funciona, y no
requiere privilegios de administrador. Solo lo revierte una politica de empresa.
"""

from __future__ import annotations

import subprocess

from . import util

# Poner en "nunca" (0) todo lo que apaga pantalla o suspende, con y sin corriente.
_A_NUNCA = [
    "monitor-timeout-ac", "monitor-timeout-dc",
    "standby-timeout-ac", "standby-timeout-dc",
    "hibernate-timeout-ac", "hibernate-timeout-dc",
]

# Valores razonables para restaurar al desinstalar (minutos).
_DEFECTO = {
    "monitor-timeout-ac": "10", "monitor-timeout-dc": "5",
    "standby-timeout-ac": "30", "standby-timeout-dc": "15",
    "hibernate-timeout-ac": "0", "hibernate-timeout-dc": "0",
}

_CREAR_SIN_VENTANA = 0x08000000  # CREATE_NO_WINDOW: powercfg no parpadea una consola


def _powercfg(ajuste, valor):
    try:
        resultado = subprocess.run(
            ["powercfg", "/change", ajuste, str(valor)],
            capture_output=True, text=True, timeout=20,
            creationflags=_CREAR_SIN_VENTANA if util.ES_WINDOWS else 0,
        )
        return resultado.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def aplicar(logger=None):
    """Deja el plan activo en 'nunca apagar pantalla / nunca suspender'."""
    if not util.ES_WINDOWS:
        return False
    fallos = [a for a in _A_NUNCA if not _powercfg(a, "0")]
    if logger:
        if not fallos:
            logger.info("Energia: plan activo en 'nunca apagar pantalla ni suspender'.")
        else:
            logger.warning("Energia: no se pudieron ajustar %d valores (posible politica de "
                           "empresa): %s", len(fallos), ", ".join(fallos))
    return not fallos


def restaurar(logger=None):
    """Devuelve el plan a valores razonables (al desinstalar)."""
    if not util.ES_WINDOWS:
        return False
    ok = True
    for ajuste, valor in _DEFECTO.items():
        if not _powercfg(ajuste, valor):
            ok = False
    if logger:
        logger.info("Energia: plan restaurado a valores por defecto." if ok
                    else "Energia: no se pudieron restaurar todos los valores.")
    return ok
