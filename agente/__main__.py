"""Interfaz de linea de comandos del agente de actividad."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from . import planificador, util
from .acciones import ACCIONES, catalogo, descartadas
from .config import Config
from .runner import ARCHIVO_PARADA, MINUTOS_RESPALDO, Agente


def _argumentos():
    parser = argparse.ArgumentParser(
        prog="agente",
        description="Agente que realiza acciones aleatorias de escritorio durante la jornada.",
    )
    parser.add_argument("-c", "--config", help="ruta al archivo JSON de configuracion")
    parser.add_argument("--plan", action="store_true",
                        help="muestra el plan del dia y termina, sin ejecutar nada")
    parser.add_argument("--fecha", help="fecha a planificar en formato AAAA-MM-DD (con --plan)")
    parser.add_argument("--prueba", nargs="?", type=int, const=5, metavar="N",
                        help="encadena N acciones seguidas (5 por defecto) sin esperar "
                             "al horario, para comprobar que todo funciona")
    parser.add_argument("--accion", help="ejecuta una sola accion por su nombre y termina")
    parser.add_argument("--listar", action="store_true",
                        help="lista las acciones registradas y su disponibilidad")
    parser.add_argument("--detener", action="store_true",
                        help="crea el archivo de parada para que el agente en curso termine")
    parser.add_argument("--forzar", action="store_true",
                        help="ejecuta aunque hoy no sea un dia habil de la configuracion")
    parser.add_argument("--simular-cierre", action="store_true",
                        help="lista las aplicaciones que cerraria el cierre total, sin cerrar nada")
    parser.add_argument("--cerrar-todo", action="store_true",
                        help="pide cerrar ahora todas las aplicaciones abiertas (con confirmacion)")
    parser.add_argument("--vigilia", action="store_true",
                        help="mantiene la pantalla encendida 24/7 sin ejecutar acciones; "
                             "lo lanza su propia tarea al iniciar sesion")
    parser.add_argument("--detener-vigilia", action="store_true",
                        help="pide a la vigilia 24/7 que termine")
    parser.add_argument("--cierre-programado", action="store_true",
                        help="cierre total de respaldo; lo lanza su propia tarea programada")
    parser.add_argument("--hora-respaldo", action="store_true",
                        help="imprime la hora HH:MM del cierre de respaldo (la usa el instalador)")
    parser.add_argument("--hora-inicio", action="store_true",
                        help="imprime la hora HH:MM en que debe arrancar la tarea (la usa el instalador)")
    parser.add_argument("--en-ventana", action="store_true",
                        help="sale con codigo 0 si ahora es dia y hora de trabajo; 1 si no (la usa el instalador)")
    parser.add_argument("--forzar-energia", action="store_true",
                        help="pone el plan de energia en 'nunca apagar pantalla ni suspender'")
    parser.add_argument("--restaurar-energia", action="store_true",
                        help="devuelve el plan de energia a valores por defecto")
    parser.add_argument("--semilla", type=int,
                        help="semilla aleatoria para reproducir un plan")
    parser.add_argument("--crear-config", metavar="RUTA",
                        help="escribe un archivo de configuracion con los valores por defecto")
    parser.add_argument("-v", "--verbose", action="store_true", help="registro detallado")
    parser.add_argument("--version", action="store_true", help="muestra la version del agente y termina")
    return parser.parse_args()


def _cargar(args):
    cfg = Config.cargar(args.config)
    if args.semilla is not None:
        cfg.semilla = args.semilla
    cfg.validar()
    return cfg


def _listar(cfg):
    activas = catalogo(cfg)
    fuera = descartadas(cfg)
    print("Acciones registradas (%d):\n" % len(ACCIONES))
    for nombre in sorted(ACCIONES):
        accion = ACCIONES[nombre]
        if nombre in activas:
            estado = "activa (peso %d)" % activas[nombre][1]
        else:
            estado = "inactiva: %s" % fuera.get(nombre, "sin motivo")
        tipo = "latido" if accion.es_latido else "accion"
        print("  %-28s %-9s %-9s %s" % (nombre, accion.categoria, tipo, estado))
        print("  %-28s %s" % ("", accion.descripcion))
    return 0


def _cierre_manual(cfg, confirmar):
    from . import escritorio

    forzar = cfg.comportamiento.forzar_cierre
    grupos = escritorio.agrupar(escritorio.ventanas_de_aplicacion())
    if not grupos:
        print("No hay aplicaciones abiertas que cerrar.")
        return 0

    print("Aplicaciones que recibirian la peticion de cierre (%d ventanas):\n"
          % sum(grupos.values()))
    for proceso, cantidad in grupos.items():
        print("  %-36s %d ventana%s" % (proceso, cantidad, "" if cantidad == 1 else "s"))
    print("\nNunca se tocan el escritorio, la barra de tareas, las consolas ni los")
    print("procesos del sistema.")
    if forzar:
        print("forzar_cierre esta activo: lo que no cierre por las buenas (pide guardar,")
        print("esta colgado o se esconde en la bandeja) se terminara SIN GUARDAR.")
    else:
        print("El cierre no fuerza: lo que tenga cambios sin guardar preguntara y se")
        print("quedara abierto.")

    if not confirmar:
        return 0
    try:
        respuesta = input("\nEscribe SI para cerrar ahora: ").strip().upper()
    except EOFError:
        respuesta = ""
    if respuesta != "SI":
        print("Cancelado: no se cerro nada.")
        return 0

    resultado = escritorio.cerrar_aplicaciones(forzar=forzar)
    print("\n%d de %d ventanas cerradas." % (resultado.cerradas, resultado.solicitadas))
    if resultado.forzadas:
        print("Terminadas sin guardar:")
        for proceso, cantidad in resultado.forzadas.items():
            print("  %-36s %d" % (proceso, cantidad))
    if resultado.abiertas:
        print("Siguen abiertas%s:" % ("" if forzar else " (seguramente piden guardar cambios)"))
        for proceso, cantidad in resultado.abiertas.items():
            print("  %-36s %d" % (proceso, cantidad))
    return 0


def main():
    args = _argumentos()

    if args.version:
        from . import __version__
        print("Agente de actividad, version %s" % __version__)
        return 0

    if args.crear_config:
        ruta = Path(args.crear_config).expanduser()
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(json.dumps(Config().a_dict(), indent=2, ensure_ascii=False),
                        encoding="utf-8")
        print("Configuracion por defecto escrita en %s" % ruta)
        return 0

    try:
        cfg = _cargar(args)
    except (ValueError, FileNotFoundError) as error:
        print("Error de configuracion: %s" % error, file=sys.stderr)
        return 2

    if args.listar:
        return _listar(cfg)

    if args.detener:
        cfg.ruta_trabajo.mkdir(parents=True, exist_ok=True)
        ruta = cfg.ruta_trabajo / ARCHIVO_PARADA
        ruta.write_text("Solicitud de parada: %s\n" % datetime.now().isoformat(),
                        encoding="utf-8")
        print("Archivo de parada creado en %s" % ruta)
        print("El agente terminara en cuanto revise el archivo (maximo 2 segundos).")
        return 0

    if args.hora_inicio:
        # La tarea arranca al principio de la ventana; el agente espera hasta la
        # hora aleatoria que sortee dentro de ella.
        print(cfg.jornada.hora_inicio_min.strftime("%H:%M"))
        return 0

    if args.forzar_energia or args.restaurar_energia:
        from . import energia
        if args.restaurar_energia:
            ok = energia.restaurar()
            print("Plan de energia restaurado a valores por defecto." if ok
                  else "No se pudieron restaurar todos los valores de energia.")
        else:
            ok = energia.aplicar()
            print("Plan de energia en 'nunca apagar pantalla ni suspender'." if ok
                  else "Aviso: no se pudo forzar todo el plan de energia (posible politica de empresa).")
        return 0 if ok else 1

    if args.en_ventana:
        hoy = date.today()
        ahora = datetime.now()
        j = cfg.jornada
        dentro = (hoy.weekday() in j.dias
                  and datetime.combine(hoy, j.hora_inicio_min) <= ahora
                  <= datetime.combine(hoy, j.hora_fin_max))
        return 0 if dentro else 1

    if args.hora_respaldo:
        fin = datetime.combine(date.today(), cfg.jornada.hora_fin_max)
        print((fin + timedelta(minutes=MINUTOS_RESPALDO)).strftime("%H:%M"))
        return 0

    if args.simular_cierre or args.cerrar_todo:
        return _cierre_manual(cfg, confirmar=args.cerrar_todo)

    if not util.ES_WINDOWS:
        print("Aviso: este agente automatiza Windows; fuera de Windows casi nada funcionara.",
              file=sys.stderr)

    logger = util.configurar_logging(cfg.ruta_logs, verboso=args.verbose)
    agente = Agente(cfg, logger)

    if args.detener_vigilia:
        ruta = agente.detener_vigilia()
        print("Se pidio a la vigilia que termine (%s)." % ruta)
        print("Se detendra en cuanto revise el archivo (maximo 1 minuto).")
        return 0

    if args.vigilia:
        agente.vigilia()
        return 0

    if args.cierre_programado:
        agente.cierre_programado()
        return 0

    if args.plan:
        fecha = date.today()
        if args.fecha:
            fecha = datetime.strptime(args.fecha, "%Y-%m-%d").date()
        print(planificador.resumen(agente.planificar(fecha), detallado=True))
        return 0

    if args.prueba:
        agente.ejecutar_prueba(args.prueba)
        return 0

    if args.accion:
        try:
            agente.ejecutar_accion(args.accion)
        except KeyError as error:
            print(error, file=sys.stderr)
            return 2
        finally:
            agente.ctx.cerrar_todo()
        return 0

    agente.ejecutar(forzar=args.forzar)
    return 0


if __name__ == "__main__":
    sys.exit(main())
