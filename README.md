# Agente de actividad de escritorio

Agente en Python que ejecuta acciones aleatorias en el equipo a lo largo de la
jornada (arranca a una hora aleatoria entre 8:00 y 9:00, y termina a una hora
aleatoria entre 17:00 y 18:00 — distinta cada día —, de lunes a viernes): redacta en Word,
alimenta una hoja de Excel, agrega diapositivas en PowerPoint, escribe una
bitácora, abre carpetas, navega y mueve el ratón entre acción y acción.

Cada día genera un **plan distinto**: número de acciones, horas, orden y duración
del almuerzo se sortean al arrancar.

## Instalación

Doble clic en **`instalar.bat`** (o desde consola). Crea un entorno virtual
`.venv`, instala las dependencias, muestra qué acciones quedan activas en ese
equipo y ofrece registrar la tarea programada.

Instalación manual, si prefieres controlarlo tú:

```bash
pip install -r requirements.txt
```

Requiere Windows y Python 3.9+ (probado en 3.14). `pywin32` da el control COM de
Office y `pyautogui` el manejo de ratón.

## Uso

```bash
python -m agente --config config.json
```

| Comando | Qué hace |
|---|---|
| `python -m agente --config config.json` | Corre la jornada completa |
| `python -m agente --config config.json --plan` | Muestra el plan del día y sale (sin tocar nada) |
| `python -m agente --config config.json --plan --semilla 7` | Plan reproducible, útil para comparar configuraciones |
| `python -m agente --config config.json --prueba` | Encadena 5 acciones seguidas **ahora mismo**, sin esperar al horario |
| `python -m agente --config config.json --prueba 10` | Lo mismo con el número de acciones que quieras |
| `python -m agente --listar` | Lista las acciones y por qué están activas o no |
| `python -m agente --accion word_redactar_notas -v` | Ejecuta una sola acción, para probar |
| `python -m agente --detener` | Pide al agente en curso que termine |
| `python -m agente --simular-cierre` | Lista las aplicaciones que cerraría el cierre total, sin cerrar nada |
| `python -m agente --cerrar-todo` | Pide cerrar ahora todas las aplicaciones abiertas (con confirmación) |
| `python -m agente --vigilia` | Mantiene la pantalla encendida 24/7 (lo lanza su tarea al iniciar sesión) |
| `python -m agente --detener-vigilia` | Pide a la vigilia 24/7 que termine |
| `python -m agente --crear-config mi.json` | Escribe una configuración con los valores por defecto |

### "Se abre la consola y no hace nada"

Es lo normal, y hay tres motivos posibles:

1. **Está esperando.** El agente arma el plan y espera a la hora de la primera
   acción, que puede estar a 10 minutos. Ahora lo dice en pantalla:
   `Esperando: word_redactar_notas a las 11:28:23 (en 51s)`. Entre acciones hay
   huecos de varios minutos a propósito — así es como se ve el día real.
2. **Lo abriste fuera del horario.** Si son más de las 17:00, todas las tareas
   quedaron en el pasado y el agente lo avisa antes de salir.
3. **Hoy no es día hábil.** Sale de inmediato diciéndolo.

Para verlo trabajar sin esperar, usa **`ejecutar.bat --prueba`**: encadena cinco
acciones seguidas con pausas de segundos. Es la forma rápida de comprobar que
todo funciona en un equipo nuevo.

Y si lo abriste con doble clic, la ventana ya no se cierra sola al terminar: se
queda con un *Presione una tecla* para que alcances a leer.

### Cómo detenerlo

Tres formas, todas limpias (cierra las aplicaciones que abrió y registra el motivo):

1. `python -m agente --detener` desde otra consola.
2. `Ctrl+C` en la consola donde corre.
3. Llevar el ratón a la **esquina superior izquierda** de la pantalla: es el
   *failsafe* de `pyautogui` y aborta la ejecución.

## Configuración (`config.json`)

| Sección | Para qué sirve |
|---|---|
| `jornada` | Ventanas de inicio (`inicio_min`–`inicio_max`) y fin (`fin_min`–`fin_max`) —la hora se sortea dentro de cada una, distinta cada día— y días hábiles (`0`=lunes … `6`=domingo) |
| `almuerzo` | Ventana en la que se sortea la pausa y su duración en minutos |
| `ritmo` | Acciones grandes por día, separación mínima entre ellas y cadencia de los *latidos* |
| `comportamiento` | Visibilidad de las aplicaciones, respeto al usuario, aplazamientos y cierre al final |
| `navegador` | Lista blanca de URLs |
| `pesos` | Peso relativo de cada acción. **`0` la desactiva** sin tocar código |
| `carpeta_trabajo` | Carpeta aislada donde vive todo (`~/AgenteActividad` por defecto) |

Dos opciones que conviene entender:

- **`comportamiento.respetar_usuario`** (recomendado en `true`): antes de ejecutar
  una acción que trae una ventana al frente, el agente consulta a Windows cuándo
  fue la última entrada de teclado o ratón. Si detecta actividad **humana** en los
  últimos `umbral_usuario_seg` segundos, aplaza la acción entre 4 y 12 minutos
  (hasta 3 veces) en lugar de robarte el foco mientras trabajas. La entrada que
  genera el propio agente se descuenta, así que sus movimientos de ratón no
  cuentan como "usuario presente".
- **`comportamiento.apps_visibles`**: en `false`, Word y Excel trabajan ocultos.
  PowerPoint siempre se muestra (su API no admite lo contrario).

### El equipo debe estar desbloqueado

Bloqueado **no** es lo mismo que con la sesión cerrada: la sesión sigue abierta,
los programas corren y la tarea programada se dispara. Pero **con la pantalla
bloqueada Windows manda el ratón y las pulsaciones a la pantalla de bloqueo, no a
tu escritorio**, así que la actividad simulada no llega a las aplicaciones y la
automatización de Office se vuelve poco fiable. Solo siguen funcionando la
escritura de archivos y el cierre final (que usa mensajes de ventana, no el
ratón).

En resumen: para el comportamiento completo, el PC tiene que estar **desbloqueado
y con la sesión iniciada**.

Con `comportamiento.mantener_despierto` en `true` (por defecto), mientras corre
desbloqueado el agente le pide a Windows **no apagar la pantalla ni suspender el
equipo**, y sus movimientos de ratón evitan el bloqueo automático. Lo que sí lo
rompe: bloquearlo a mano (Win+L) o una política de empresa que fuerce el bloqueo.

**Modern Standby: por qué a veces la pantalla se apaga igual.** En los portátiles
modernos Windows usa *Modern Standby* (suspensión S0), y ahí la petición anterior
**no es fiable**: el equipo se apaga o suspende aunque el agente pida lo
contrario. Por eso, con `comportamiento.forzar_energia` en `true` (por defecto),
el agente **cambia el plan de energía** a *nunca apagar pantalla / nunca
suspender* con `powercfg` (no requiere admin), lo aplica al instalar y al arrancar
la vigilía, y lo **vuelve a poner cada 20 minutos** por si una política lo
revierte. Esto es lo único que funciona de verdad en Modern Standby. Al
desinstalar se restauran valores razonables. Para comprobar si un equipo usa
Modern Standby: `powercfg /a` (busca "S0 Low Power Idle"). Si una política de
empresa vuelve a forzar la suspensión pese a esto, solo TI puede cambiarlo.

### Pantalla encendida 24/7 (independiente del horario)

El agente de trabajo solo corre de 9 a 5, así que su "mantener despierto" solo
cubre ese horario. Para que la **pantalla siga encendida las 24 horas** hay una
pieza aparte: la **vigilia**, un proceso ligero que no ejecuta ninguna acción —
solo le pide a Windows no apagar la pantalla ni suspender— y corre todo el día.

`instalar.bat` la registra como la tercera tarea, **"Agente de actividad -
pantalla"**, que arranca **al iniciar sesión** y la deja corriendo en segundo
plano (con `pythonw`, sin ventana de consola). Se arranca también en el momento de
instalar, sin esperar al siguiente inicio de sesión. Así queda el reparto:

| Tarea | Cuándo | Qué hace |
|---|---|---|
| Agente de actividad | 08:00 diario | Arranca y espera la hora sorteada (8–9); trabaja hasta la hora sorteada (17–18) |
| Agente de actividad - cierre | 18:10 diario | Cierra todo (respaldo) |
| Agente de actividad - pantalla | al iniciar sesión | Mantiene la pantalla encendida 24/7 |

Detalles de la vigilia:

- **Mantiene la pantalla encendida y evita el bloqueo.** Con
  `SetThreadExecutionState` impide que se apague la pantalla o se suspenda; y como
  eso **no** basta para evitar el bloqueo (que lo dispara la inactividad de
  teclado/ratón, no la energía), **fuera del horario laboral pulsa F15** —una tecla
  que no hace nada— cada 45 segundos para reiniciar el contador de inactividad.
  Dentro del horario no pulsa: ahí ya mueve el ratón el agente de trabajo, y si la
  vigilía tecleara a la vez, el agente creería que hay un humano y aplazaría todo.
  Se puede apagar el F15 con `comportamiento.vigilia_evita_bloqueo` en `false`.
- **Una sola instancia**: usa un mutex con nombre; si ya hay una corriendo, la
  segunda no hace nada.
- **Cómo pararla**: `ejecutar.bat --detener-vigilia` (se detiene en menos de un
  minuto), o cerrando sesión / apagando el equipo. `desinstalar.bat` la para y
  quita su tarea.
- **No desbloquea** una pantalla ya bloqueada: mantener la pantalla encendida y
  desbloquearla son cosas distintas. El F15 evita que **llegue** a bloquearse, pero
  si ya estaba bloqueada (por ejemplo, porque se bloqueó antes de instalar el
  agente, o alguien pulsó Win+L), no puede abrirla. Por eso conviene, además,
  desactivar el bloqueo automático en Windows (ver abajo), como doble seguridad.

### Si aun así se bloquea: desactivar el bloqueo en Windows

El F15 de la vigilía evita el bloqueo por inactividad en casi todos los equipos.
Si algún PC tiene una política más estricta, desactiva el bloqueo también en
Windows (hay que hacerlo en cada equipo):

1. **Configuración → Cuentas → Opciones de inicio de sesión** → "Si has estado
   ausente, ¿cuándo debe Windows volver a solicitar el inicio de sesión?" →
   **Nunca**.
2. **Protector de pantalla** (busca "protector de pantalla" en el menú Inicio) →
   ponlo en **Ninguno**, o desmarca *"Mostrar la pantalla de inicio de sesión al
   reanudar"*.

Si el bloqueo lo impone una **política de la empresa** (dominio corporativo), es
posible que estas opciones estén bloqueadas y haya que pedírselo a sistemas: el
dato que necesitan es "Interactive logon: Machine inactivity limit".

Nota práctica: esto deja el monitor encendido toda la noche. Si prefieres que la
pantalla se apague fuera del horario pero el equipo no se bloquee, quita esta
tarea (`--detener-vigilia` + borrar la tarea) y apóyate solo en la configuración
de Windows.

El agente **no puede desbloquear** una pantalla ya bloqueada — haría falta la
contraseña, y no automatiza credenciales. Eso se resuelve dejándolo desbloqueado
o desactivando el bloqueo automático en Windows (Cuentas → Opciones de inicio de
sesión → "requerir inicio de sesión" en Nunca; y Energía sin apagado de pantalla
ni suspensión).

### Cierre de jornada

A la hora de fin (sorteada entre 17:00 y 18:00) el agente cierra lo que indique
`comportamiento.modo_cierre`. Espera a esa hora aunque la última tarea haya
terminado unos minutos antes.

| Modo | Qué cierra |
|---|---|
| `ninguno` | Nada (Word, Excel y PowerPoint los sigue gobernando `cerrar_apps`) |
| `agente` | Solo lo que abrió el agente y no estaba ya abierto |
| `simular` | Lo mismo que `agente`, y además **anota en el log** lo que cerraría `todas`, sin cerrarlo |
| `todas` | Lo mismo que `agente`, y además **cierra todas las aplicaciones abiertas**, también las tuyas |

El `config.json` que se entrega viene en **`todas` con `forzar_cierre: true`**:
al acabar la jornada se cierra todo y **no se guarda nada**. Si quieres ganar
confianza el primer día en un equipo nuevo, ponlo en `simular` y revisa el log.

**Cómo cierra el modo `todas`**, en dos pasos:

1. A cada ventana de aplicación le manda `WM_CLOSE`, lo mismo que pulsar su X, y
   le da 15 segundos. Lo que cierra por las buenas sale limpio.
2. Con `forzar_cierre: true`, tras otros 10 segundos **termina sin guardar** todo
   proceso que siga vivo: la aplicación que preguntó si guardar, la que está
   colgada y la que solo se escondió en la bandeja del sistema (Teams, por
   ejemplo). Con `forzar_cierre: false` esas se quedan abiertas.

Nunca toca el escritorio ni la barra de tareas — un `WM_CLOSE` al escritorio
abriría el diálogo de apagar Windows —, ni las consolas, ni los procesos del
sistema. Y **`explorer.exe` jamás se termina a la fuerza**, aunque tenga carpetas
abiertas: es a la vez esas carpetas y el escritorio con la barra de tareas. Puede
resistirse al forzado una aplicación ejecutada como administrador; el log la
señala. En el log solo figura el nombre del programa, nunca el título de la
ventana.

Efectos secundarios de terminar sin guardar: el navegador puede ofrecer restaurar
las pestañas al abrirlo al día siguiente, y el Bloc de notas de Windows 11
recupera por su cuenta las pestañas sin guardar si tiene activada la opción de
continuar la sesión anterior.

**Si hay alguien usando el equipo** a la hora de fin, espera a que quede libre dos
minutos, como máximo `espera_usuario_min` (5 en el `config.json` entregado). Con
`forzar_cierre`, pasado ese tiempo **cierra igual**; sin él, renuncia antes que
interrumpir. `--prueba` y `--accion` nunca hacen el cierre total.

**Red de seguridad: la segunda tarea programada.** El cierre del agente solo
ocurre si el agente está corriendo a esa hora. Para los días en que no — el PC se
encendió después de la hora de arranque, alguien cerró la consola, se paró a mano
o se cortó por errores —, `instalar.bat` registra una segunda tarea, **"Agente de
actividad - cierre"**, que hace el cierre total por su cuenta **10 minutos
después del fin máximo** (18:10). Solo actúa en días hábiles y entre `fin_max` y
tres horas después; fuera de eso no cierra nada. Si cambias las ventanas de
horario en `config.json`, vuelve a ejecutar `instalar.bat` para moverlas.

**Para ver qué cerraría ahora mismo**, sin cerrar nada:

```bash
ejecutar.bat --simular-cierre
```

Y `ejecutar.bat --cerrar-todo` hace el cierre en el acto, con el forzado que
indique la configuración, después de mostrar la lista y pedir que escribas `SI`.

**Lo que abrió el agente** se cierra con su propia regla, en los modos `agente`,
`simular` y `todas`: solo si no estaba ya abierto antes de que lo lanzara, y con
`taskkill` sin `/f`. El navegador queda fuera de esa regla salvo que pongas
`cerrar_navegador` en `true`; en modo `todas` da igual, porque ahí se cierra como
cualquier otra aplicación.

## Acciones disponibles

| Acción | Categoría | Qué hace |
|---|---|---|
| `word_redactar_notas` | office | Agrega fecha, título en negrita y párrafos a `notas_operativas.docx` |
| `word_revisar_documento` | office | Abre el documento y lo recorre, sin modificarlo |
| `excel_actualizar_hoja` | office | Añade filas y fórmulas `SUM`/`AVERAGE` en `seguimiento_operativo.xlsx` |
| `excel_revisar_tablero` | office | Recorre y recalcula la hoja sin escribir |
| `powerpoint_avance_presentacion` | office | Agrega una diapositiva a `avance_semanal.pptx` |
| `notas_tematicas` | nativa | Redacta en uno de los cuatro archivos de `notas\` y lo abre en el Bloc de notas |
| `csv_informe_actualizar` | nativa | Alimenta `informe_actividad.csv`, el sustituto de la hoja de Excel |
| `organizar_archivos` | nativa | Rota los archivos que crecen a `archivo\AAAA-MM` y regenera el inventario |
| `explorador_revisar_archivo` | nativa | Abre el Explorador con un archivo de trabajo seleccionado |
| `abrir_aplicacion_windows` | nativa | Abre Calculadora o Paint, una vez por jornada cada una, y las cierra al final |
| `bitacora_bloc_notas` | sistema | Anota una línea en `bitacora.txt` y la abre en el Bloc de notas |
| `abrir_carpeta_trabajo` | sistema | Abre la carpeta de trabajo en el Explorador |
| `navegador_consulta` | navegador | Abre una URL de la lista blanca |
| `raton_movimiento` | latido | Recorrido corto y suave del ratón |
| `rueda_scroll` | latido | Desplaza la rueda y regresa |
| `cambiar_ventana` | latido | Alt+Tab |

Los *latidos* son micro-acciones que rellenan los huecos cada 7–20 minutos; las
demás son las acciones "grandes" del plan.

### En un equipo sin Office

Las cinco acciones de Office se desactivan solas si no encuentran Word, Excel o
PowerPoint. Para esos equipos están las acciones de categoría **nativa**, que solo
usan lo que trae cualquier Windows: archivos de texto, un CSV que crece,
organización de carpetas, el Explorador, Calculadora, Paint y Edge.

Sin Office el día queda con 7 u 8 acciones distintas, no muy lejos de las 10 que
salen con Office instalado. No hay que configurar nada: el agente detecta qué hay
y arma el plan con lo que encuentre. Si luego instalas Office, las acciones se
activan solas y puedes bajarle el peso a las nativas en `pesos`.

Dos matices de esas acciones:

- `organizar_archivos` **rota** los archivos cuando pasan de cierto tamaño
  (120 líneas las notas y la bitácora, 400 el CSV): los mueve a
  `archivo\AAAA-MM\` con la fecha en el nombre y deja el original limpio. Solo
  toca archivos que creó el propio agente.
- `abrir_aplicacion_windows` abre Calculadora y Paint **una vez por jornada cada
  una**, y las cierra en el cierre de jornada. Son aplicaciones empaquetadas de
  Windows: el ejecutable que se lanza termina de inmediato y la ventana queda en
  manos del sistema, así que se cierran por nombre de proceso
  (`calc.exe` arranca en realidad `CalculatorApp.exe`). Ponle peso `0` si
  prefieres no verlas.

## Llevarlo a otro equipo

Genera el paquete desde este PC:

```bash
powershell -ExecutionPolicy Bypass -File empaquetar.ps1
```

Queda en `dist\agente-actividad.zip` (sin `.venv`, sin logs, sin caché). En el
otro equipo: descomprimir y ejecutar **`instalar.bat`**. Eso es todo.

### Si el equipo destino no tiene internet

```bash
powershell -ExecutionPolicy Bypass -File empaquetar.ps1 -SinInternet
```

Añade al zip una carpeta `vendor\` con las dependencias ya descargadas
(≈8 MB); `instalar.bat` las detecta y las instala con `--no-index`, sin salir a
PyPI. **Ese paquete queda atado a la versión de Python de este equipo (3.14, 64
bits)**, porque `pywin32` se compila por versión de intérprete. Si allá hay otra
versión de Python, borra `vendor\` y usa el modo con internet.

### Si el equipo destino no tiene Python

Opción A: instalar Python 3.9+ desde python.org marcando *Add python.exe to PATH*.

Opción B: generar un ejecutable único desde este PC, que no requiere Python allá:

```bash
pip install pyinstaller && pyinstaller --onefile --name agente --add-data "config.json;." agente/__main__.py
```

Ten en cuenta que algunos antivirus corporativos marcan los `.exe` de PyInstaller
como sospechosos; si el equipo destino tiene EDR, la opción A da menos problemas.

### Qué revisar en el equipo destino

| Diferencia | Qué pasa |
|---|---|
| Sin Word / Excel / PowerPoint | Esas acciones se desactivan solas; el resto sigue |
| Otra resolución de pantalla | El ratón se mueve en porcentajes, no en píxeles fijos |
| Otro usuario de Windows | `carpeta_trabajo` usa `~`, así que apunta a su propio perfil |
| Antivirus / EDR corporativo | `pyautogui` mueve el ratón; algunos EDR lo registran |

`instalar.bat` termina mostrando la lista de acciones activas: ahí ves de una vez
qué quedó habilitado en ese equipo.

## Programar el arranque automático

`instalar.bat` registra tres tareas: la de **inicio** al principio de la ventana
de arranque (08:00; el agente espera dentro hasta la hora que sortea), la de
**cierre de respaldo** 10 minutos después del fin máximo (18:10), y la de
**pantalla 24/7** al iniciar sesión. A mano, las dos de horario serían:

```bash
schtasks /create /tn "Agente de actividad" /tr "\"C:\ruta\agente-actividad\ejecutar.bat\" /tarea" /sc daily /st 08:00 /it /f
```

```bash
schtasks /create /tn "Agente de actividad - cierre" /tr "\"C:\ruta\agente-actividad\ejecutar.bat\" /cierre" /sc daily /st 18:10 /it /f
```

Si ya las habías registrado con una versión anterior, vuelve a ejecutar
`instalar.bat` y responde `S`: las reemplaza por las nuevas.

Tres detalles a propósito:

- **`/tarea`** le indica al lanzador que lo abrió el Programador de tareas, para
  que no deje la consola esperando un *Presione una tecla* toda la noche. Con
  doble clic esa pausa sí aparece, para que alcances a leer.
- **`/sc daily`** en vez de días de la semana: los nombres de día en `schtasks`
  cambian con el idioma de Windows y romperían la portabilidad. El propio agente
  sale de inmediato si hoy no está en `jornada.dias`.
- **`/it`** hace que corra solo con el usuario conectado. Es obligatorio: la
  automatización de Office necesita un escritorio interactivo, así que **no**
  marques "Ejecutar tanto si el usuario inició sesión como si no".

Para quitarlas, `desinstalar.bat` o:

```bash
schtasks /delete /tn "Agente de actividad" /f
```

```bash
schtasks /delete /tn "Agente de actividad - cierre" /f
```

Si arranca a mitad del día, las tareas cuya hora ya pasó se descartan y sigue con
las siguientes.

## Límites deliberados

El agente está construido para no poder hacer daño:

- **No toca el correo.** No abre Outlook ni ningún cliente de correo, no lee la
  bandeja ni crea borradores: se quitó todo lo relacionado con el correo.
- **No escribe a ciegas.** Solo teclea dentro de documentos que él mismo abrió por
  COM. Nunca manda pulsaciones a la ventana que esté al frente, porque no puede
  saber qué aplicación es. De `pyautogui` usa únicamente ratón, rueda y Alt+Tab.
- **No toca tus archivos.** Trabaja exclusivamente dentro de `carpeta_trabajo`, y
  crea sus documentos con `DispatchEx`, en instancias de Office separadas de las
  que tengas abiertas.
- **Solo fuerza cuando se lo pides.** Sin `forzar_cierre`, el cierre total pide
  cerrar como la X de cada ventana y lo que tenga cambios sin guardar se queda
  abierto. Con `forzar_cierre` activo — como en el `config.json` entregado —, lo
  que no cierre por las buenas se termina **sin guardar**.
- **No borra nada.** Los archivos que genera quedan ahí para que los revises o
  elimines tú.
- **Cede el paso.** Si estás usando el equipo, aplaza en vez de interrumpirte.

## Archivos que genera

En `~/AgenteActividad` (`C:\Users\<usuario>\AgenteActividad`):

```
notas_operativas.docx        documento de Word que va creciendo
seguimiento_operativo.xlsx   hoja con filas y fórmulas
avance_semanal.pptx          presentación con una diapositiva por acción
informe_actividad.csv        informe tabular (sustituto de Excel)
bitacora.txt                 registro de texto plano
notas\*.txt                  cuatro archivos temáticos de notas
archivo\AAAA-MM\             archivos rotados, con la fecha en el nombre
archivo\inventario.txt       listado de todo lo generado, con tamaños
DETENER.txt                  archivo de parada (lo crea --detener)
logs\agente-AAAA-MM-DD.log   registro de todo lo ejecutado
```

Se puede borrar la carpeta entera cuando quieras: el agente la vuelve a crear.
