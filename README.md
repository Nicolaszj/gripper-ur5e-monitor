# Maximiliano Estudiante · Monitor del gripper

Aplicación Docker con **Node-RED + InfluxDB 2 + Grafana**. Recibe telemetría del
ESP32, guarda el histórico y muestra los 21 grupos de datos solicitados,
incluyendo M1–M6. Incluye un simulador separado de los datos reales.

## Inicio rápido

Necesitas Docker Desktop con contenedores Linux y Python 3.
Desde PowerShell:

```powershell
cd 'C:\Users\maxim\OneDrive\filosofo\Documents\ChatGPT\New\maximiliano-estudiante'
python scripts/manage.py demo
```

Esto genera credenciales si no existen, construye Node-RED y levanta los
servicios con datos ficticios. Abre:

- **Grafana:** http://localhost:3000/d/gripper-estudiante
- **Node-RED:** http://localhost:1880/editor
- **InfluxDB:** http://localhost:8086

El dashboard abre **sin login**. En Grafana selecciona
**Origen = simulated** y **Dispositivo = gripper-01** para ver la demo.
El origen predeterminado es `real`. No mezcles la demo con las mediciones reales.

Para levantar sin simulador: `python scripts/manage.py up`. Si ya arrancaste
la demo, detenla con `docker compose stop simulador` para pasar a hardware.
Para apagar todo conservando datos: `python scripts/manage.py down`.
Para consultar contenedores: `python scripts/manage.py estado`.

## Conectar el ESP32 por USB / TTL en Windows

El ESP32 debe emitir una **línea JSON terminada en LF** por cada muestra.
El formato completo está en **TELEMETRIA.md**. La app no implementa todavía
las lecturas físicas de AX-18A, HX711, INA219 ni los seis encoders en la ESP32:
esas mediciones debe generarlas tu firmware y el hardware conectado.

```powershell
python tools/windows_serial.py --puertos
python tools/serial_bridge.py --puerto COM4
```

El puente usa únicamente la biblioteca estándar de Python, abre el puerto a
115200 8N1 y envía los JSON a la URL de Node-RED sin login ni token. En Windows corre en
el host porque Docker Desktop Linux no recibe un COM de Windows directamente.
El almacenamiento y dashboard sí están en contenedores. Cierra otros monitores
que estén usando ese COM. No se envían comandos a los actuadores.

Para importar el texto del firmware anterior de este chat:

```powershell
python tools/serial_bridge.py --puerto COM4 --legacy-encoder
```

Ese modo solo publica **encoder y RPM de M1**; el resto queda sin datos.
El firmware TTL que solo responde `OK` / `STATE` no proporciona sensores;
esas respuestas no se convierten en distancias, fuerzas ni velocidades.

## Serial completamente en Docker, en Linux

Conecta el USB del ESP32 al host Linux y configura `SERIAL_DEVICE` en `.env`:

```text
SERIAL_DEVICE=/dev/ttyUSB0
```

```sh
docker compose --profile serial up -d --build
```

Usa el dispositivo real, por ejemplo `/dev/ttyACM0`. El contenedor lo recibe como
`/dev/ttyESP`. Este perfil no sirve para mapear COM4 de Windows sin USB forwarding.

## HTTP directo desde ESP32

Entrada: **POST http://<IP-PC>:1880/api/telemetry**, `Content-Type: application/json`.
**Sin login, contraseña ni API key.** Puerto 1880 abierto a la red local de forma
predeterminada (`INGRESS_BIND_IP=0.0.0.0`). Desde el propio PC usa `localhost`;
desde el ESP32 usa la IP LAN del PC. El dashboard también abre sin login en
`http://<IP-PC>:3000/d/gripper-estudiante`. El editor administrativo de Node-RED
usará las credenciales de `credenciales.txt`.

Prueba una publicación HTTP desde Python, sin instalar librerías:

```powershell
python tools/http_sender.py --url http://localhost:1880/api/telemetry --file examples/telemetry-demo.json
python tools/serial_bridge.py --puerto COM4 --url http://localhost:1880/api/telemetry
```

Consulta las últimas muestras con `GET http://<IP-PC>:1880/api/status`.
Si Windows bloquea conexiones desde otro equipo, permite TCP 1880 y 3000 en
el firewall de la red privada.

Respuestas: 201 almacenado, 400 muestra inválida,
409 duplicada/fuera de orden, 429 muestra anterior en proceso, 502 fallo de DB.
El puente reintenta hasta tres veces. No tiene una cola persistente: ante una
caída prolongada las muestras se descartan y el dashboard queda obsoleto.

## Qué muestra

- Apertura actual/objetivo, fuerza actual/límite, velocidad lineal, objeto,
  estado del gripper y tiempo de ciclo.
- Límites abierto/cerrado, bloqueos, comunicación, sobrecorriente y antigüedad.
- Posición en ticks/grados, velocidad, carga, voltaje y temperatura del AX-18A.
- Pulsos/grados, RPM, corriente y bloqueo de cada motor M1–M6.
- Gráficas de apertura, fuerza, velocidades y corrientes.

Los valores instantáneos usan solo muestras de los últimos **5 segundos**;
si no hay medición reciente indican **SIN DATOS**. El histórico permanece.
La tabla de `GET /api/status` incluye antigüedad y flag `stale`; no requiere token.
Los avisos del dashboard son informativos, no una función de parada de seguridad.

**0–85 mm** es el rango de referencia del PDS. **±0,5 mm** es el objetivo de
precisión y necesita validación física. No se aplica una regla universal
ticks→mm: la geometría real requiere calibración. La velocidad puede derivarse
de apertura/tiempo del emisor, omitiendo reinicios, cambios de calibración y
huecos mayores de 2 s. Present Load del AX-18A no se convierte a fuerza en N.

## Datos, credenciales y edición

Influx retiene 30 días. Los volúmenes Docker guardan datos y configuración.
`docker compose down` conserva los volúmenes; no uses `down -v` si los necesitas.
`.env` y `credenciales.txt` se generan con claves aleatorias, se excluyen de Git
y no se deben compartir. Las credenciales iniciales de Influx/Grafana se aplican
al primer arranque del volumen: editar `.env` no rota usuarios ya creados.
Esta configuración local usa un token de administración de Influx compartido
por Node-RED/Grafana; antes de publicar, sustituye por tokens limitados de
escritura y lectura respectivamente. No incluye despliegue público ni TLS.

El flujo se copia al volumen la primera vez y después es editable en Node-RED.
El dashboard y datasource se provisionan automáticamente desde `grafana/`.
`scripts/build_assets.py` regenera sus archivos fuente. Si editas el dashboard
en Grafana, expórtalo a `grafana/dashboards/gripper.json` para conservar el cambio
en el proyecto. Cambiar el flujo fuente no reemplaza automáticamente tu flujo
ya editado en el volumen: impórtalo desde el editor.

## Verificación

```powershell
node --test tests/telemetry.test.js
python -m unittest discover -s tests -p 'test_*.py' -v
# Con el stack y simulador levantados:
python tests/integration.py
```

La prueba de integración publica una muestra simulada con dispositivo
`integration-test`, comprueba escritura real en Influx y ejecuta las consultas
de todos los paneles contra el datasource de Grafana.

## Archivos principales

```text
compose.yaml                  servicios Docker y volúmenes
node-red/                     flujo y validación del ingreso HTTP
grafana/                      dashboard y datasource
tools/serial_bridge.py        puerto ESP32 → Node-RED
tools/simulador.py            datos ficticios con source=simulated
scripts/manage.py             iniciar, detener, demo y credenciales
TELEMETRIA.md                 contrato de datos y unidades
tests/                        pruebas
```

## Documentación oficial usada

- [Node-RED en Docker](https://nodered.org/docs/getting-started/docker)
- [InfluxDB 2 en Docker Compose](https://docs.influxdata.com/influxdb/v2/install/use-docker-compose/)
- [Acceso anónimo Grafana](https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/anonymous-auth/)
- [Provisioning Grafana](https://grafana.com/docs/grafana/latest/administration/provisioning/)
- [AX-18A ROBOTIS](https://emanual.robotis.com/docs/en/dxl/ax/ax-18a/)
