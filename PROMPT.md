# Prompt para generar el agente de actividad

Copia todo lo que sigue a partir de la línea de guiones y pégalo como primer
mensaje en una sesión nueva de Claude Code (o cualquier asistente con acceso al
sistema de archivos y a una terminal de Windows).

---

Construye un agente en Python que ejecute acciones aleatorias de escritorio a lo
largo de una jornada laboral en Windows, usando las herramientas de Office y las
aplicaciones del sistema (sin correo). Responde siempre en español y escribe el
código y los comentarios también en español, sin acentos en los identificadores.

## Comportamiento esperado

Cada día debe sortear un plan distinto: número de acciones, horas, orden y
duración del almuerzo. Entre acciones grandes hay huecos de varios minutos, y en
esos huecos se intercalan micro-acciones ("latidos") de ratón cada 7-20 minutos.
La jornada es de lunes a viernes. La hora de inicio se sortea cada día dentro de
una ventana (por defecto 08:00–09:00) y la de fin dentro de otra (17:00–18:00),
de modo que empieza y termina a una hora distinta cada día. La tarea programada
arranca al principio de la ventana de inicio y el agente espera hasta la hora que
sorteó; el cierre total ocurre a la hora de fin sorteada.

## Arquitectura exigida

Paquete `agente/` ejecutable con `python -m agente`, dividido así:

- `config.py` — dataclasses anidadas (`Jornada`, `Almuerzo`, `Ritmo`,
  `Comportamiento`, `Navegador`) cargadas desde un JSON. Rechaza claves
  desconocidas con un mensaje claro e ignora las que empiecen por `_`, para poder
  dejar comentarios dentro del JSON.
- `util.py` — logging a consola y a archivo diario, detección de actividad
  humana, pausas aleatorias y generadores de texto de oficina verosímil.
- `planificador.py` — construye el plan del día y sabe describirlo.
- `runner.py` — ejecuta el plan.
- `acciones/` — un módulo por familia (`office.py`, `sistema.py`, `nativas.py`)
  más `base.py` con el registro.
- `__main__.py` — la interfaz de línea de comandos.

Las acciones se registran con un decorador `@registrar(nombre, descripcion,
categoria, peso, roba_foco, es_latido, disponible)`. El parámetro `disponible` es
un callable que recibe la configuración y decide si esa acción existe en este
equipo. El plan se arma solo con las acciones disponibles, y un peso `0` en la
configuración desactiva cualquiera sin tocar código.

## Planificador

- Sortea la ventana de almuerzo dentro de un rango configurable.
- Reparte N acciones (N aleatorio entre un mínimo y un máximo) proporcionalmente
  a la duración de los tramos libres, garantizando una separación mínima entre
  ellas. Para eso, muestrea `k` puntos uniformes en `[0, L-(k-1)*s]`, los ordena y
  suma `i*s`: así la separación queda garantizada por construcción.
- Elige la acción con `random.choices` ponderado, evitando repetir la anterior.
- Los latidos se generan aparte, recorriendo el día y saltándose el almuerzo.

## Catálogo de acciones

**Office (por COM, con pywin32):** redactar en un `.docx` que crece; recorrerlo
sin modificarlo; agregar filas y fórmulas `SUM`/`AVERAGE` a un `.xlsx`; recorrer
y recalcular esa hoja sin escribir; agregar diapositivas a un `.pptx`.

**Nada de correo:** el agente no abre Outlook ni ningún cliente de correo, no lee
la bandeja ni crea borradores. No incluyas acciones de correo.

**Nativas (funcionan en un Windows limpio, sin Office):** alimentar un CSV que
hace de hoja de cálculo; escribir en varios archivos temáticos de notas y abrirlos
en el Bloc de notas; rotar los archivos que superan cierto tamaño a
`archivo\AAAA-MM\` y regenerar un inventario; abrir el Explorador con un archivo
seleccionado; abrir Calculadora o Paint.

**Sistema y latidos:** abrir la carpeta de trabajo; abrir una URL de una lista
blanca; mover el ratón con recorridos suaves; girar la rueda; Alt+Tab.

## Reglas de seguridad innegociables

Estas condicionan el diseño, no son un añadido:

1. **Nada de correo.** El agente no toca Outlook ni ningún cliente de correo, ni
   por COM ni por `mailto:`. No debe existir código de correo en el proyecto.
2. **Nunca teclear a ciegas.** Solo escribir dentro de documentos que el propio
   agente abrió por COM. Prohibido mandar pulsaciones a la ventana que esté al
   frente. De `pyautogui` usar únicamente ratón, rueda y Alt+Tab.
3. **Trabajar en una carpeta aislada** (`~/AgenteActividad` por defecto), nunca
   sobre documentos del usuario.
4. **Ceder el paso al humano.** Antes de cualquier acción que traiga una ventana
   al frente, consultar `GetLastInputInfo`; si hubo actividad humana reciente,
   aplazar la acción unos minutos (con un máximo de aplazamientos) en vez de
   robar el foco.
5. **No borrar nada** y no registrar contenido privado en el log: en el cierre
   total, solo nombres de proceso, jamás títulos de ventana.
6. Tres formas de parar: un archivo `DETENER.txt`, `Ctrl+C`, y el failsafe de
   `pyautogui` al llevar el ratón a la esquina superior izquierda.

## Interfaz de línea de comandos

`--config`, `--plan` (muestra el plan y sale), `--prueba [N]` (encadena N
acciones seguidas ignorando el horario), `--accion NOMBRE`, `--listar` (todas las
acciones con su estado y el motivo si están inactivas), `--detener`, `--forzar`,
`--semilla`, `--crear-config`, `--simular-cierre` (lista lo que cerraría el cierre
total, sin cerrar nada), `--cerrar-todo` (lo ejecuta en el acto, tras pedir
confirmación escrita), `--cierre-programado` (el cierre de respaldo que lanza su
propia tarea programada, protegido por día y hora), `--hora-respaldo` (la usa el
instalador) y `-v`.

## Empaquetado y despliegue

- `instalar.bat`: detecta Python, crea un `.venv`, instala dependencias, muestra
  qué acciones quedaron activas y ofrece registrar la tarea programada.
- `desinstalar.bat`, `ejecutar.bat` (que use el `.venv` si existe).
- `empaquetar.ps1`: genera `dist\agente-actividad.zip` sin `.venv`, sin logs ni
  `__pycache__`. Con `-SinInternet` incluye además las dependencias descargadas
  en `vendor\` para instalar en un equipo sin acceso a PyPI.

## Trampas conocidas: resuélvelas desde el principio

Estas ya costaron depuración, no las repitas:

- **PowerPoint no admite `Application.Visible = False`**: lanza error. Word y
  Excel sí. Trata PowerPoint como excepción.
- **Para Word, Excel y PowerPoint usa `DispatchEx`** (no `Dispatch`), que crea
  instancias propias y no toca los documentos que el usuario ya tenga abiertos.
- **Cachea las aplicaciones COM entre acciones**, pero sondea que sigan vivas
  (por ejemplo leyendo `app.Name`) y vuelve a crearlas si el usuario las cerró.
- **`GetLastInputInfo` devuelve `dwTime` de `GetTickCount`, de 32 bits**: calcula
  la diferencia módulo `2**32` o el cálculo se rompe a los 49 días de encendido.
- **El propio agente genera entrada de ratón**, que también reinicia ese
  contador. Guarda la marca de tiempo de tu última entrada sintética y
  descuéntala, o el agente se confundirá a sí mismo con el usuario.
- **Las ventanas del Explorador se acumulan**: cada apertura crea una nueva. Antes
  de abrir otra, ciérralas con `Shell.Application.Windows()` filtrando por
  `LocationURL`, y cierra solo las que apuntan dentro de la carpeta de trabajo.
- **`calc.exe` y `mspaint.exe` son lanzadores**: el proceso termina de inmediato y
  la ventana queda en manos del sistema, así que guardar el subproceso no sirve
  para cerrarlas. Ciérralas por nombre de proceso real, que no coincide con el
  lanzador (`calc.exe` arranca `CalculatorApp.exe`; `mspaint.exe` sí se llama
  igual). Ábrelas como máximo una vez por jornada.
- **El cierre de jornada tiene cuatro modos** (`ninguno`, `agente`, `simular`,
  `todas`) y ocurre a la **hora de fin**, no al terminar la última tarea: el plan
  suele agotarse unos minutos antes, así que hay que esperar a esa hora.
- **Lo que abrió el agente** solo se cierra si no estaba ya abierto antes de
  lanzarlo: comprueba el proceso y apúntalo solo si no existía. Usa `taskkill`
  **sin** `/f`, para que una aplicación con trabajo sin guardar pregunte y se
  quede abierta. El navegador queda fuera de esa regla salvo que se active, y
  sobre una lista cerrada de ejecutables.
- **El modo `todas` pide primero con `WM_CLOSE`** sobre las ventanas principales
  (visibles, con título, sin propietaria, sin `WS_EX_TOOLWINDOW`). Trampas de esa
  enumeración: **excluye por clase `Progman`, `WorkerW` y `Shell_TrayWnd`**,
  porque un `WM_CLOSE` al escritorio abre el diálogo de apagar Windows; descarta
  las ventanas **ocultas por DWM** (`DWMWA_CLOAKED`), porque las apps modernas
  suspendidas dicen ser visibles; resuelve el proceso real de las que aloja
  `ApplicationFrameHost.exe` buscando una ventana hija de otro PID; y excluye las
  consolas (`ConsoleWindowClass`, Windows Terminal), o el agente se cierra a sí
  mismo a mitad del cierre. En el log, solo nombres de proceso: los títulos de
  ventana llevan nombres de documentos u otra información privada.
- **Con `forzar_cierre`, lo que siga vivo tras el margen se termina sin guardar**:
  la app que preguntó si guardar, la colgada y la que se escondió en la bandeja.
  Esta última deja de tener ventana visible pero su proceso sigue, así que hay
  que medir procesos, no ventanas. Abre el manejador de cada proceso **antes** de
  mandar `WM_CLOSE`: mientras exista, Windows no reutiliza el PID, y nunca se
  termina por error otro proceso que heredó el número. Jamás termines
  `explorer.exe` (también es el escritorio y la barra de tareas) ni
  `ApplicationFrameHost.exe` (aloja a todas las apps modernas: termina la app real).
- **El cierre del agente solo procede si la jornada terminó por su hora**; nunca
  tras `--prueba` o `--accion`. Si a esa hora hay alguien usando el equipo, espera
  un máximo configurable; con `forzar_cierre` cierra igual al acabar la espera, y
  sin él renuncia.
- **Si el cierre es obligatorio, no puede depender de que el agente esté vivo a esa
  hora**: el equipo pudo encenderse después de la tarea de la mañana, o alguien
  cerró la consola. Registra una segunda tarea programada que haga el cierre por su
  cuenta unos minutos después del fin, protegida para actuar solo en días hábiles y
  dentro de una ventana horaria tras el fin. El instalador saca esa hora de la
  configuración; en el `for /f` usa una ruta **relativa** al Python del `.venv`,
  porque un comando que empieza con una ruta entre comillas choca con la forma en
  que `cmd` quita las comillas.
- **Ofrece el modo `simular`** (anota en el log lo que cerraría) y un
  `--simular-cierre` de solo lectura: sin eso no hay forma segura de probar el
  cierre total en el equipo de desarrollo, donde se llevaría por delante el propio
  asistente.
- **La tarea programada debe llamar al lanzador con un argumento propio**
  (`/tarea`) para saltarse la pausa final del doble clic. `%cmdcmdline%` contiene
  el nombre del `.bat` tanto con doble clic como desde el Programador de tareas,
  así que no sirve para distinguirlos, y la consola se quedaría toda la noche con
  "Presione una tecla".
- **Lee el JSON de configuración con `utf-8-sig`**: el Bloc de notas y varios
  editores de Windows le meten BOM al guardar y `json.loads` falla.
- **`pywin32` trae ruedas atadas a la versión de Python** (`cp314`, `cp313`…), así
  que un paquete offline solo sirve para la misma X.Y en el equipo destino.
  Documéntalo. Y como `pyautogui` se distribuye como sdist, incluye también
  `setuptools` y `wheel` en `vendor\` o la instalación sin internet fallará.
- **En `schtasks` usa `/sc daily`, no días de la semana**: sus abreviaturas
  cambian con el idioma de Windows. Deja que el propio agente salga si hoy no es
  día hábil. Y usa `/it`, porque la automatización de Office necesita un
  escritorio interactivo: la tarea no puede correr con el usuario desconectado.
- **Con la pantalla bloqueada, la simulacion de raton/teclado no llega al
  escritorio del usuario** (Windows conmuta al escritorio seguro), y la
  automatizacion de Office se vuelve poco fiable; solo la escritura de archivos y
  el cierre por mensajes de ventana siguen funcionando. Documenta que el equipo
  debe estar desbloqueado. Ofrece un refuerzo `SetThreadExecutionState`
  (`ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED`) para que no se
  apague la pantalla ni se suspenda mientras corre, activandolo y liberandolo
  desde el mismo hilo. No intentes desbloquear la pantalla: exigiria la
  contrasena.
- **"Pantalla encendida 24/7" es una pieza aparte del agente que trabaja de 9 a
  5**: un proceso "vigilia" que NO ejecuta acciones, solo sostiene
  `SetThreadExecutionState` en bucle y corre todo el dia. Registralo como su
  propia tarea `/sc onlogon` y lanzalo con `pythonw` (sin ventana de consola),
  desacoplado con `start ""`, para no dejar una consola abierta. Protegelo con un
  mutex con nombre (instancia unica), dale su propio archivo de parada distinto
  del DETENER de la jornada, y arrancalo tambien en el momento de instalar con
  `schtasks /run`.
- **`SetThreadExecutionState` NO evita el bloqueo, solo el apagado de pantalla y
  la suspension.** El bloqueo lo dispara la inactividad de teclado/raton. Durante
  la jornada lo enmascaran los movimientos de raton del agente; al terminar, deja
  de moverse y el equipo se bloquea aunque la pantalla siga encendida. Para
  evitarlo, la vigilia envia F15 (tecla inofensiva) cada ~45 s **solo fuera del
  horario laboral**: dentro del horario NO debe pulsar, porque el agente de
  trabajo, en otro proceso, lo tomaria como actividad humana y aplazaria todo (su
  deteccion de input sintetico es por-proceso y no ve el F15 de la vigilia).
  Ninguna de las dos cosas desbloquea una pantalla ya bloqueada; documenta ademas
  como desactivar el bloqueo en Windows por si una politica lo fuerza.
- **El usuario va a pensar que no hace nada.** Registra en pantalla qué está
  esperando y a qué hora, avisa explícitamente si lo abren fuera del horario, y
  deja un `pause` en el `.bat` cuando se abre con doble clic para que la ventana
  no se cierre sola.

## Criterios de aceptación

Antes de darlo por terminado, comprueba de verdad, ejecutando:

1. `--listar` distingue correctamente lo disponible de lo no disponible en este
   equipo, con el motivo.
2. `--plan` produce planes distintos en ejecuciones distintas, y el mismo plan
   con la misma `--semilla`.
3. Cada acción registrada funciona al menos una vez con `--accion`.
4. La rotación de archivos mueve de verdad un archivo que supere el umbral.
5. El bucle completo de la jornada funciona: comprime la jornada a dos o tres
   minutos en una configuración de prueba y verifícalo de punta a punta, incluido
   el aplazamiento por actividad del usuario, la espera hasta la hora de fin y que
   el cierre total en modo `simular` registre lo que cerraría.
6. El cierre real se prueba **acotado** a ventanas abiertas para la prueba, nunca
   contra el escritorio completo del equipo de desarrollo. Para el forzado usa
   ventanas propias deterministas (por ejemplo con tkinter): una normal, una que
   ignora el cierre y una que se esconde. Sin forzar deben quedar vivas las dos
   últimas; forzando no debe quedar ninguna. Si pruebas el flujo completo del
   agente sustituyendo la enumeración de ventanas, comprueba **antes** de cerrar
   que la sustitución quedó aplicada, o cerrarás el equipo entero.
7. El lanzador no deja pausa en modo tarea programada y sí con doble clic.
8. El paquete generado se instala en una carpeta limpia y arranca allí.

Entrega también un `README.md` en español con la tabla de acciones, la
configuración explicada, los límites de seguridad y las instrucciones para
llevarlo a otro equipo.
