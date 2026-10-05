"""Construccion del plan aleatorio del dia."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from . import util

DIAS_ES = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]


def _hora(texto):
    horas, minutos = texto.split(":")
    return time(int(horas), int(minutos))


@dataclass
class Tarea:
    momento: datetime
    accion: str
    tipo: str = "accion"        # accion | latido
    aplazamientos: int = 0


@dataclass
class Plan:
    fecha: object
    inicio: datetime
    fin: datetime
    almuerzo: object            # (inicio, fin) o None
    tareas: list

    def __len__(self):
        return len(self.tareas)


def _combinar(fecha, hora):
    return datetime.combine(fecha, hora)


def _ventana_almuerzo(fecha, cfg, inicio, fin, rng):
    if not cfg.almuerzo.activo:
        return None
    desde = _combinar(fecha, _hora(cfg.almuerzo.desde))
    hasta = _combinar(fecha, _hora(cfg.almuerzo.hasta))
    if hasta < desde:
        desde, hasta = hasta, desde
    margen = int((hasta - desde).total_seconds() // 60)
    arranque = desde + timedelta(minutes=rng.randint(0, max(0, margen)))
    duracion = rng.randint(cfg.almuerzo.duracion_min, cfg.almuerzo.duracion_max)
    cierre = arranque + timedelta(minutes=duracion)
    if arranque <= inicio or arranque >= fin:
        return None
    return (arranque, min(cierre, fin))


def _intervalos_libres(inicio, fin, almuerzo):
    if almuerzo is None:
        return [(inicio, fin)]
    tramos = [(inicio, almuerzo[0]), (almuerzo[1], fin)]
    return [t for t in tramos if (t[1] - t[0]).total_seconds() > 60]


def _puntos(intervalo, cantidad, separacion_min, rng):
    """Instantes aleatorios dentro del intervalo, con separacion minima garantizada."""
    if cantidad <= 0:
        return []
    inicio, fin = intervalo
    largo = (fin - inicio).total_seconds()
    separacion = separacion_min * 60
    disponible = largo - (cantidad - 1) * separacion
    if disponible <= 0:
        cantidad = max(1, int(largo // separacion))
        disponible = largo - (cantidad - 1) * separacion
        if disponible <= 0:
            return [inicio]
    desplazamientos = sorted(rng.uniform(0, disponible) for _ in range(cantidad))
    return [inicio + timedelta(seconds=d + i * separacion)
            for i, d in enumerate(desplazamientos)]


def _capacidad(intervalo, separacion_min):
    largo = (intervalo[1] - intervalo[0]).total_seconds() / 60.0
    return max(0, int(largo // separacion_min))


def elegir_ponderado(nombres, pesos, rng, anterior):
    """Eleccion ponderada evitando repetir la accion inmediatamente anterior."""
    for _ in range(6):
        elegida = rng.choices(nombres, weights=pesos, k=1)[0]
        if elegida != anterior or len(nombres) == 1:
            return elegida
    return elegida


def _hora_aleatoria(fecha, hora_desde, hora_hasta, rng):
    """Instante aleatorio del dia entre dos horas (incluye ambos extremos)."""
    desde = _combinar(fecha, hora_desde)
    hasta = _combinar(fecha, hora_hasta)
    segundos = int((hasta - desde).total_seconds())
    return desde + timedelta(seconds=rng.randint(0, max(0, segundos)))


def generar_plan(fecha, cfg, catalogo, rng):
    # Inicio y fin se sortean dentro de sus ventanas: distintos cada dia.
    inicio = _hora_aleatoria(fecha, cfg.jornada.hora_inicio_min,
                             cfg.jornada.hora_inicio_max, rng)
    fin = _hora_aleatoria(fecha, cfg.jornada.hora_fin_min,
                          cfg.jornada.hora_fin_max, rng)
    almuerzo = _ventana_almuerzo(fecha, cfg, inicio, fin, rng)
    intervalos = _intervalos_libres(inicio, fin, almuerzo)

    principales = [(n, p) for n, (a, p) in catalogo.items() if not a.es_latido]
    latidos = [(n, p) for n, (a, p) in catalogo.items() if a.es_latido]

    tareas = []

    # --- acciones principales, repartidas proporcionalmente al tramo -------
    if principales and intervalos:
        objetivo = rng.randint(cfg.ritmo.acciones_min, cfg.ritmo.acciones_max)
        total_seg = sum((f - i).total_seconds() for i, f in intervalos)
        nombres = [n for n, _ in principales]
        pesos = [p for _, p in principales]
        anterior = None
        for intervalo in intervalos:
            porcion = (intervalo[1] - intervalo[0]).total_seconds() / total_seg
            cantidad = min(int(round(objetivo * porcion)),
                           _capacidad(intervalo, cfg.ritmo.separacion_minutos))
            for momento in _puntos(intervalo, cantidad, cfg.ritmo.separacion_minutos, rng):
                anterior = elegir_ponderado(nombres, pesos, rng, anterior)
                tareas.append(Tarea(momento=momento, accion=anterior, tipo="accion"))

    # --- latidos: micro actividad de relleno --------------------------------
    if latidos:
        nombres = [n for n, _ in latidos]
        pesos = [p for _, p in latidos]
        cursor = inicio + timedelta(minutes=rng.randint(1, cfg.ritmo.latido_min))
        anterior = None
        while cursor < fin:
            en_almuerzo = almuerzo is not None and almuerzo[0] <= cursor < almuerzo[1]
            if not en_almuerzo:
                anterior = elegir_ponderado(nombres, pesos, rng, anterior)
                tareas.append(Tarea(momento=cursor, accion=anterior, tipo="latido"))
            cursor += timedelta(minutes=rng.randint(cfg.ritmo.latido_min, cfg.ritmo.latido_max))

    tareas.sort(key=lambda t: t.momento)
    return Plan(fecha=fecha, inicio=inicio, fin=fin, almuerzo=almuerzo, tareas=tareas)


def resumen(plan, detallado=True):
    lineas = []
    lineas.append("Jornada : %s %s  de %s a %s" % (
        plan.fecha.strftime("%Y-%m-%d"),
        "(%s)" % DIAS_ES[plan.fecha.weekday()],
        plan.inicio.strftime("%H:%M"),
        plan.fin.strftime("%H:%M"),
    ))
    if plan.almuerzo:
        duracion = (plan.almuerzo[1] - plan.almuerzo[0]).total_seconds()
        lineas.append("Almuerzo: %s a %s (%s)" % (
            plan.almuerzo[0].strftime("%H:%M"),
            plan.almuerzo[1].strftime("%H:%M"),
            util.formatear_duracion(duracion),
        ))
    principales = [t for t in plan.tareas if t.tipo == "accion"]
    lineas.append("Tareas  : %d acciones + %d latidos" % (
        len(principales), len(plan.tareas) - len(principales)))

    conteo = {}
    for tarea in principales:
        conteo[tarea.accion] = conteo.get(tarea.accion, 0) + 1
    if conteo:
        lineas.append("Reparto : " + ", ".join(
            "%s x%d" % (nombre, veces)
            for nombre, veces in sorted(conteo.items(), key=lambda x: -x[1])
        ))

    if detallado:
        lineas.append("")
        for tarea in plan.tareas:
            marca = "." if tarea.tipo == "latido" else "*"
            lineas.append("  %s %s  %s" % (marca, tarea.momento.strftime("%H:%M:%S"), tarea.accion))
    return "\n".join(lineas)
