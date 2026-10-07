# Verificación local — 6 de octubre de 2026

- Docker Desktop / Linux iniciado; InfluxDB, Node-RED, Grafana y simulador levantados.
- Healthchecks correctos de InfluxDB, Node-RED y Grafana; simulador en ejecución.
- 6 pruebas de validación y derivadas de telemetría correctas.
- 3 pruebas del puente serial correctas.
- Escritura HTTP confirmada y lectura real de la muestra en InfluxDB.
- Ingreso POST y consulta GET de estado sin login ni API key verificados.
- Rechazo verificado de booleano inválido y muestra duplicada.
- Dashboard y 55 consultas de paneles verificados sin cookie de sesión ni credenciales.
- Puertos 1880 y 3000 publicados en todas las interfaces del host para acceso por URL.
- Dashboard abierto en navegador y visualizado con origen simulated.

Los datos observados durante esta validación son **simulados**. No se ha conectado
en esta prueba el hardware del gripper, ni verificado la exactitud de apertura,
fuerza, corriente o encoders. El perfil serial de Docker Linux está incluido;
la conexión de un dispositivo físico no se ha ensayado en este host Windows.
