"""Ejecucion del plan diario."""

from __future__ import annotations

import heapq
import random
import time
import traceback
from datetime import date, datetime, timedelta

from . import energia, escritorio, planificador, util
from .acciones import Contexto, catalogo, descartadas

ARCHIVO_PARADA = "DETENER.txt"
ARCHIVO_PARADA_VIGILIA = "DETENER-PANTALLA.txt"
# Marca que deja el agente de trabajo mientras su jornada esta en curso, para que
# la vigilia sepa que NO debe pulsar F15 en ese rato (lo hace ya el propio agente
# moviendo el raton). Contiene el inicio y fin sorteados de hoy.
ARCHIVO_TRABAJO_ACTIVO = ".trabajo_activo.json"
VIGILIA_LATIDO_SEG = 45         # cada cuanto la vigilia re-afirma el estado, pulsa y revisa la parada
VIGILIA_AVISO_MIN = 60          # cada cuantos minutos deja constancia en el log de que sigue viva
VIGILIA_ENERGIA_MIN = 20        # cada cuanto la vigilia vuelve a forzar el plan de energia
MINUTOS_RESPALDO = 10           # el cierre de respaldo corre este tiempo despues del fin
VENTANA_RESPALDO_HORAS = 3      # fuera de [fin, fin + esto] el respaldo no cierra nada
MAX_ERRORES_SEGUIDOS = 6
TOLERANCIA_ATRASO_SEG = 90      # una tarea mas vieja que esto se descarta


def _detalle(grupos):
    return ", ".join("%s x%d" % par for par in grupos.items())


class Agente:
    def __init__(self, cfg, logger, rng=None):
        cfg.validar()
        self.cfg = cfg
        self.logger = logger
        self.rng = rng or random.Random(cfg.semilla)
        self.carpeta = cfg.ruta_trabajo
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.ctx = Contexto(cfg=cfg, logger=logger, rng=self.rng, carpeta=self.carpeta)
        self.catalogo = catalogo(cfg)

    # ------------------------------------------------------------ parada
    @property
    def ruta_parada(self):
        return self.carpeta / ARCHIVO_PARADA

    def _debe_detenerse(self):
        return self.ruta_parada.exists()

    def _limpiar_parada(self):
        if self.ruta_parada.exists():
            self.ruta_parada.unlink()
            self.logger.info("Se elimino el archivo de parada de una ejecucion anterior.")

    @property
    def ruta_parada_vigilia(self):
        return self.carpeta / ARCHIVO_PARADA_VIGILIA

    # ------------------------------------------------------- vigilia 24/7
    def vigilia(self):
        """Mantiene la pantalla encendida y el equipo despierto de forma continua.

        Es un proceso aparte del agente que trabaja de 9 a 5: no ejecuta ninguna
        accion, solo le pide a Windows que no apague la pantalla ni suspenda. Corre
        todo el dia (arranca al iniciar sesion) hasta que se cierra la sesion, se
        apaga el equipo, o aparece el archivo DETENER-PANTALLA.txt.

        No desbloquea una pantalla ya bloqueada: eso depende de la configuracion.
        """
        if not util.ES_WINDOWS:
            self.logger.warning("La vigilia solo tiene efecto en Windows.")
            return

        guarda = _instancia_unica("AgenteActividadVigilia")
        if guarda is None:
            self.logger.info("Ya hay una vigilia en marcha: esta instancia no hace nada.")
            return

        if self.ruta_parada_vigilia.exists():
            self.ruta_parada_vigilia.unlink()

        evita_bloqueo = self.cfg.comportamiento.vigilia_evita_bloqueo
        forzar_energia = self.cfg.comportamiento.forzar_energia
        util.mantener_despierto(True)
        if forzar_energia:
            energia.aplicar(self.logger)
        self.logger.info("Vigilia iniciada: la pantalla se mantendra encendida las 24 horas.")
        if evita_bloqueo:
            self.logger.info("Fuera del horario laboral evitara ademas el bloqueo (tecla F15).")
        siguiente_aviso = datetime.now() + timedelta(minutes=VIGILIA_AVISO_MIN)
        # El plan de energia se re-afirma cada tanto: una politica de empresa que
        # refresca cada ~90 min podria revertirlo, y asi se vuelve a poner.
        siguiente_energia = datetime.now() + timedelta(minutes=VIGILIA_ENERGIA_MIN)
        try:
            while not self.ruta_parada_vigilia.exists():
                # Re-afirmar es barato y cubre el caso de que algo reinicie el estado.
                util.mantener_despierto(True)
                if forzar_energia and datetime.now() >= siguiente_energia:
                    energia.aplicar()
                    siguiente_energia = datetime.now() + timedelta(minutes=VIGILIA_ENERGIA_MIN)
                # El F15 solo cuando el agente de trabajo NO esta en su jornada:
                # durante la jornada ya mueve el raton el, y si la vigilia pulsara
                # a la vez, el agente creeria que hay un humano y aplazaria todo.
                # Como la jornada empieza y termina a una hora aleatoria cada dia,
                # la vigilia no la deduce del reloj: la lee del marcador que deja
                # el propio agente mientras trabaja.
                if evita_bloqueo and not self._trabajo_activo():
                    util.pulsar_tecla_inofensiva()
                if datetime.now() >= siguiente_aviso:
                    self.logger.info("Vigilia activa: la pantalla sigue encendida.")
                    siguiente_aviso = datetime.now() + timedelta(minutes=VIGILIA_AVISO_MIN)
                time.sleep(VIGILIA_LATIDO_SEG)
            self.logger.info("Vigilia detenida por %s.", ARCHIVO_PARADA_VIGILIA)
        except KeyboardInterrupt:
            self.logger.info("Vigilia detenida manualmente.")
        finally:
            util.mantener_despierto(False)

    # --------------------------------------------------- marca de trabajo activo
    @property
    def ruta_trabajo_activo(self):
        return self.carpeta / ARCHIVO_TRABAJO_ACTIVO

    def _marcar_trabajo(self, inicio, fin):
        import json
        try:
            self.ruta_trabajo_activo.write_text(
                json.dumps({"inicio": inicio.isoformat(), "fin": fin.isoformat()}),
                encoding="utf-8")
        except OSError:
            self.logger.debug("No se pudo escribir la marca de trabajo activo.")

    def _desmarcar_trabajo(self):
        try:
            if self.ruta_trabajo_activo.exists():
                self.ruta_trabajo_activo.unlink()
        except OSError:
            self.logger.debug("No se pudo borrar la marca de trabajo activo.")

    def _trabajo_activo(self):
        """True si el agente de trabajo esta en su jornada de hoy ahora mismo."""
        import json
        try:
            datos = json.loads(self.ruta_trabajo_activo.read_text(encoding="utf-8"))
            inicio = datetime.fromisoformat(datos["inicio"])
            fin = datetime.fromisoformat(datos["fin"])
        except (OSError, ValueError, KeyError):
            return False
        return inicio <= datetime.now() <= fin

    def detener_vigilia(self):
        self.carpeta.mkdir(parents=True, exist_ok=True)
        self.ruta_parada_vigilia.write_text(
            "Solicitud de parada de la vigilia: %s\n" % datetime.now().isoformat(),
            encoding="utf-8")
        return self.ruta_parada_vigilia

    # ------------------------------------------------------------- espera
    def _esperar_hasta(self, momento):
        """Espera hasta el instante indicado. Devuelve False si se pidio detener."""
        while True:
            restante = (momento - datetime.now()).total_seconds()
            if restante <= 0:
                return True
            if self._debe_detenerse():
                return False
            time.sleep(min(2.0, restante))

    # ------------------------------------------------------------ ejecucion
    def ejecutar_accion(self, nombre):
        entrada = self.catalogo.get(nombre)
        if entrada is None:
            raise KeyError("La accion %r no esta disponible con esta configuracion." % nombre)
        accion, _ = entrada
        inicio = time.time()
        accion.funcion(self.ctx)
        self.logger.debug("Accion %s completada en %s.",
                          nombre, util.formatear_duracion(time.time() - inicio))

    def planificar(self, fecha=None):
        fecha = fecha or date.today()
        return planificador.generar_plan(fecha, self.cfg, self.catalogo, self.rng)

    def ejecutar_prueba(self, cantidad=5):
        """Encadena varias acciones seguidas, ignorando el horario de la jornada.

        Sirve para comprobar de un vistazo que todo funciona en un equipo nuevo,
        sin tener que esperar a que llegue la hora de la primera tarea.
        """
        candidatas = [(nombre, peso) for nombre, (accion, peso) in self.catalogo.items()
                      if not accion.es_latido]
        if not candidatas:
            self.logger.warning("No hay ninguna accion disponible en este equipo.")
            return 0

        self._reportar_catalogo()
        self.logger.info("Modo prueba: %d acciones seguidas, sin esperar al horario.", cantidad)

        nombres = [nombre for nombre, _ in candidatas]
        pesos = [peso for _, peso in candidatas]
        anterior = None
        hechas = 0
        try:
            for indice in range(1, cantidad + 1):
                anterior = planificador.elegir_ponderado(nombres, pesos, self.rng, anterior)
                self.logger.info("[%d/%d] %s", indice, cantidad, anterior)
                try:
                    self.ejecutar_accion(anterior)
                    hechas += 1
                except Exception as error:
                    self.logger.warning("Fallo la accion %s: %s", anterior, error)
                    self.logger.debug("Detalle:\n%s", traceback.format_exc())
                util.pausa(self.rng, 2.0, 5.0)
        except KeyboardInterrupt:
            self.logger.info("Prueba interrumpida.")
        finally:
            self.ctx.cerrar_todo()

        self.logger.info("Prueba terminada: %d de %d acciones completadas.", hechas, cantidad)
        return hechas

    def ejecutar(self, fecha=None, forzar=False):
        fecha = fecha or date.today()

        if not forzar and fecha.weekday() not in self.cfg.jornada.dias:
            self.logger.info("%s no es dia habil segun la configuracion. Nada que hacer.",
                             fecha.strftime("%Y-%m-%d"))
            return 0

        # Instancia unica: la jornada puede lanzarse por dos vias (la tarea diaria
        # y la de inicio de sesion). Si ya hay una en marcha, esta no hace nada.
        guarda = _instancia_unica("AgenteActividadTrabajo")
        if guarda is None:
            self.logger.info("Ya hay una jornada en marcha: esta instancia no hace nada.")
            return 0

        self._limpiar_parada()
        self._reportar_catalogo()

        plan = self.planificar(fecha)
        self.logger.info("Plan del dia:\n%s", planificador.resumen(plan, detallado=False))
        if not plan.tareas:
            self.logger.warning("El plan quedo vacio: revisa los pesos y la disponibilidad.")
            return 0

        ahora = datetime.now()
        if ahora >= plan.fin:
            self.logger.warning("La jornada de hoy ya termino a las %s: no queda nada por hacer.",
                                plan.fin.strftime("%H:%M"))
            self.logger.warning("Para ver el agente trabajando ahora mismo, usa: "
                                "ejecutar.bat --prueba")
            return 0
        if ahora < plan.inicio:
            self.logger.info("La jornada empieza a las %s: faltan %s de espera.",
                             plan.inicio.strftime("%H:%M"),
                             util.formatear_duracion((plan.inicio - ahora).total_seconds()))

        cola = []
        for indice, tarea in enumerate(plan.tareas):
            heapq.heappush(cola, (tarea.momento, indice, tarea))
        secuencia = len(plan.tareas)

        ejecutadas = omitidas = aplazadas = 0
        errores_seguidos = 0
        motivo_final = "plan completado"

        if self.cfg.comportamiento.mantener_despierto and util.mantener_despierto(True):
            self.logger.info("Se pidio a Windows no apagar la pantalla ni suspender el equipo "
                             "durante la jornada.")

        # Marca la ventana [inicio, fin] de hoy para que la vigilia no pulse F15
        # mientras el agente trabaja (ya mueve el raton el mismo).
        self._marcar_trabajo(plan.inicio, plan.fin)

        try:
            while cola:
                momento, _, tarea = heapq.heappop(cola)

                if datetime.now() > momento + timedelta(seconds=TOLERANCIA_ATRASO_SEG):
                    omitidas += 1
                    self.logger.debug("Omitida %s (programada %s, ya paso).",
                                      tarea.accion, momento.strftime("%H:%M:%S"))
                    continue

                espera = (momento - datetime.now()).total_seconds()
                if espera > 5:
                    # Los latidos son constantes: anunciarlos todos llenaria el log.
                    anunciar = self.logger.debug if tarea.tipo == "latido" else self.logger.info
                    anunciar("Esperando: %s a las %s (en %s).", tarea.accion,
                             momento.strftime("%H:%M:%S"), util.formatear_duracion(espera))

                if not self._esperar_hasta(momento):
                    motivo_final = "archivo %s detectado" % ARCHIVO_PARADA
                    break

                accion = self.catalogo[tarea.accion][0]
                if self._debe_ceder(accion, tarea):
                    nuevo = self._reprogramar(tarea, plan.fin)
                    if nuevo is None:
                        omitidas += 1
                    else:
                        aplazadas += 1
                        secuencia += 1
                        heapq.heappush(cola, (nuevo, secuencia, tarea))
                    continue

                try:
                    self.ejecutar_accion(tarea.accion)
                    ejecutadas += 1
                    errores_seguidos = 0
                except KeyboardInterrupt:
                    raise
                except Exception as error:
                    if type(error).__name__ == "FailSafeException":
                        motivo_final = "parada de emergencia del raton (esquina de pantalla)"
                        break
                    errores_seguidos += 1
                    self.logger.warning("Fallo la accion %s: %s", tarea.accion, error)
                    self.logger.debug("Detalle:\n%s", traceback.format_exc())
                    if errores_seguidos >= MAX_ERRORES_SEGUIDOS:
                        motivo_final = "demasiados errores consecutivos"
                        break

            # El plan suele agotarse unos minutos antes de la hora de salida,
            # porque la ultima tarea cae antes del fin. El cierre se hace a la
            # hora real de fin de jornada, no al terminar la ultima tarea.
            if motivo_final == "plan completado" and datetime.now() < plan.fin:
                self.logger.info("Ultima tarea hecha. Cierre de jornada a las %s (en %s).",
                                 plan.fin.strftime("%H:%M"),
                                 util.formatear_duracion((plan.fin - datetime.now()).total_seconds()))
                if not self._esperar_hasta(plan.fin):
                    motivo_final = "archivo %s detectado" % ARCHIVO_PARADA
        except KeyboardInterrupt:
            motivo_final = "interrupcion manual (Ctrl+C)"
        finally:
            self.ctx.cerrar_todo()
            # El estado "no suspender" se levanta al final: el cierre total, que
            # viene despues, ya no lo necesita y no debe dejarlo pegado.
            if self.cfg.comportamiento.mantener_despierto:
                util.mantener_despierto(False)
            # Se retira la marca: desde ya, la vigilia vuelve a encargarse del F15
            # (pantalla encendida y sin bloqueo el resto del dia y la noche).
            self._desmarcar_trabajo()

        self.logger.info(
            "Fin de la jornada (%s): %d ejecutadas, %d aplazadas, %d omitidas.",
            motivo_final, ejecutadas, aplazadas, omitidas)

        # El cierre total solo procede si la jornada termino por su hora. Una
        # parada, un Ctrl+C o una racha de errores significan que alguien
        # intervino, y en ese caso no se toca nada del usuario.
        if motivo_final == "plan completado":
            self._cierre_total()
        return ejecutadas

    # --------------------------------------------------------- ceder al humano
    def _debe_ceder(self, accion, tarea):
        comportamiento = self.cfg.comportamiento
        if not (comportamiento.respetar_usuario and accion.roba_foco):
            return False
        if not util.usuario_activo(comportamiento.umbral_usuario_seg):
            return False
        self.logger.info("El usuario esta trabajando: se aplaza %s.", tarea.accion)
        return True

    def _reprogramar(self, tarea, fin_jornada):
        comportamiento = self.cfg.comportamiento
        if tarea.aplazamientos >= comportamiento.max_aplazamientos:
            self.logger.info("Se descarta %s tras %d aplazamientos.",
                             tarea.accion, tarea.aplazamientos)
            return None
        minutos = self.rng.randint(comportamiento.aplazar_min, comportamiento.aplazar_max)
        nuevo = datetime.now() + timedelta(minutes=minutos)
        if nuevo >= fin_jornada:
            self.logger.info("Se descarta %s: el aplazamiento cae fuera de la jornada.",
                             tarea.accion)
            return None
        tarea.aplazamientos += 1
        tarea.momento = nuevo
        return nuevo

    # ----------------------------------------------------------- cierre total
    def cierre_programado(self):
        """Red de seguridad: el cierre total lanzado por su propia tarea programada.

        Cubre los dias en que el agente no llego a hacer su cierre: equipo
        encendido tarde, consola cerrada a mano, parada manual o errores.
        """
        hoy = date.today()
        if hoy.weekday() not in self.cfg.jornada.dias:
            self.logger.info("Cierre de respaldo: hoy no es dia habil, no se cierra nada.")
            return
        # La jornada puede terminar en cualquier momento hasta fin_max; el respaldo
        # cuenta desde ahi para no cerrar antes de que el agente haya podido acabar.
        fin = datetime.combine(hoy, self.cfg.jornada.hora_fin_max)
        tope = fin + timedelta(hours=VENTANA_RESPALDO_HORAS)
        ahora = datetime.now()
        if not fin <= ahora <= tope:
            self.logger.warning("Cierre de respaldo fuera de su ventana (%s a %s): "
                                "no se cierra nada.", fin.strftime("%H:%M"), tope.strftime("%H:%M"))
            return
        self.logger.info("Cierre de respaldo de las %s.", ahora.strftime("%H:%M"))
        self._cierre_total()

    def _cierre_total(self):
        comportamiento = self.cfg.comportamiento
        modo = comportamiento.modo_cierre
        if modo not in ("simular", "todas") or not util.ES_WINDOWS:
            return
        try:
            if modo == "simular":
                grupos = escritorio.agrupar(escritorio.ventanas_de_aplicacion())
                self.logger.info("Cierre total SIMULADO%s: se pediria cerrar %d ventanas (%s).",
                                 " con forzado" if comportamiento.forzar_cierre else "",
                                 sum(grupos.values()), _detalle(grupos) or "ninguna")
                return

            if not self._esperar_usuario_libre():
                return
            resultado = escritorio.cerrar_aplicaciones(forzar=comportamiento.forzar_cierre)
            self.logger.info("Cierre total: %d de %d ventanas cerradas.",
                             resultado.cerradas, resultado.solicitadas)
            # Solo nombres de proceso: los titulos pueden llevar datos privados.
            if resultado.forzadas:
                self.logger.info("Terminadas sin guardar: %s", _detalle(resultado.forzadas))
            if resultado.abiertas:
                if comportamiento.forzar_cierre:
                    self.logger.warning("No se pudieron cerrar (p. ej. corren como "
                                        "administrador): %s", _detalle(resultado.abiertas))
                else:
                    self.logger.info("Siguen abiertas, seguramente pidiendo guardar cambios: %s",
                                     _detalle(resultado.abiertas))
        except KeyboardInterrupt:
            self.logger.info("Cierre total cancelado.")

    def _esperar_usuario_libre(self):
        """Espera a que nadie use el equipo antes del cierre total.

        Sin forzar_cierre devuelve False si hay que renunciar: se pidio detener o
        alguien siguio trabajando toda la espera. Con forzar_cierre el cierre es
        obligatorio: la espera solo da un margen y despues se cierra igual.
        """
        comportamiento = self.cfg.comportamiento
        if not comportamiento.respetar_usuario:
            return True
        forzar = comportamiento.forzar_cierre
        maximo_min = comportamiento.espera_usuario_min
        limite = datetime.now() + timedelta(minutes=maximo_min)
        avisado = False
        while util.usuario_activo(comportamiento.umbral_usuario_seg):
            if not forzar and self._debe_detenerse():
                return False
            if datetime.now() >= limite:
                if forzar:
                    self.logger.info("El equipo siguio en uso %d minutos: el cierre se hace "
                                     "igualmente (forzar_cierre).", maximo_min)
                    return True
                self.logger.info("Alguien siguio usando el equipo %d minutos: se omite el "
                                 "cierre total para no interrumpirle.", maximo_min)
                return False
            if not avisado:
                self.logger.info("Hay alguien usando el equipo: el cierre total espera a que "
                                 "quede libre (maximo %d minutos).", maximo_min)
                avisado = True
            time.sleep(15)
        return True

    # ------------------------------------------------------------- diagnostico
    def _reportar_catalogo(self):
        self.logger.info("Acciones activas (%d): %s",
                         len(self.catalogo), ", ".join(sorted(self.catalogo)))
        fuera = descartadas(self.cfg)
        if fuera:
            self.logger.debug("Acciones descartadas: %s", "; ".join(
                "%s (%s)" % (nombre, motivo) for nombre, motivo in sorted(fuera.items())))


def _instancia_unica(nombre):
    """Devuelve un manejador de mutex si es la primera instancia, o None si ya hay otra.

    El manejador debe seguir vivo mientras corra el proceso: al devolverlo, quien
    llama lo guarda y Windows lo libera solo al terminar el proceso.
    """
    if not util.ES_WINDOWS:
        return object()
    import ctypes
    ERROR_ALREADY_EXISTS = 183
    kernel32 = ctypes.windll.kernel32
    manejador = kernel32.CreateMutexW(None, False, nombre)   # sesion actual, sin prefijo Global
    if not manejador or kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        return None
    return manejador
