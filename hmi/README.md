# HMI del gripper

Interfaz del equipo para el monitor del gripper. Usa la misma telemetría que el
dashboard de Grafana y muestra los mismos datos: gripper, AX-18A y M1–M6.

## Uso

```powershell
python scripts/manage.py demo
```

- HMI: http://localhost:8080
- Grafana: http://localhost:3000/d/gripper-estudiante

En la demo hay que elegir Origen = Simulado. Por defecto abre en Real, igual
que Grafana.

En el servidor se despliega igual, con Docker:

```sh
docker compose up -d --build
```

Si el 8080 está ocupado, poner `HMI_PORT=8090` (o el que sea) en `.env`.

## Notas

- El servicio `hmi` está en `compose.override.yaml`. Docker Compose lo carga
  junto con `compose.yaml`, no hay que pasar nada extra.
- La página lee `GET /api/status` de Node-RED cada 0,4 s. Solo lee, no manda
  comandos al gripper.
- Si la última muestra tiene más de 5 s los valores salen como "Sin datos".
- Las gráficas son del último minuto. El histórico completo está en Grafana.
- El dibujo del gripper es ilustrativo, se arma con `opening_mm`.
