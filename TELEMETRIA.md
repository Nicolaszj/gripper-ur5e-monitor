# Contrato de telemetría v1

Una muestra es un objeto JSON; serial requiere JSON por línea y HTTP requiere
ese mismo objeto como cuerpo. Los números son valores numéricos, no strings.
Los flags son booleanos JSON (`true` / `false`), no `"Sí"`, `0` ni `"false"`.
Una medida no disponible se omite o se envía `null`; jamás se inventa cero.

## URL de recepción

`POST http://<IP-PC>:1880/api/telemetry` con `Content-Type: application/json`.
No necesita login ni token. En el mismo PC puedes usar `localhost`.
Respuesta 201: escritura confirmada; 400: JSON inválido; 409: duplicado;
429: reintentar; 502: almacenamiento no disponible.

## Metadatos

| Campo | Tipo / uso |
| --- | --- |
| device_id | Identificador estable, por ejemplo gripper-01 |
| boot_id | Cambia con cada reinicio del emisor |
| source | real o simulated |
| seq | Entero creciente por boot_id; identifica duplicados |
| sample_time_ms | Milisegundos monotónicos del emisor; no reloj Unix |
| calibration_id | Versión de calibración; obligatorio con opening_mm |

Identificadores: 1–64 caracteres, letras, números, `_`, `-` o `.`.
La aplicación pone la hora de almacenamiento del servidor. Si se transmite
serial sin metadatos, el puente aporta los necesarios; para derivadas exactas
usa boot_id y sample_time_ms de la ESP32 en lugar del tiempo del puente.
`sample_time_ms` no debe retroceder; usa tiempo de 64 bits o cambia boot_id
si reinicias/desbordas el contador. Solo enviar metadatos no es una muestra.

## Campos del gripper y AX-18A

| Dato | Campo JSON | Unidad / origen |
| --- | --- | --- |
| Apertura actual | opening_mm | mm, AX + geometría calibrada |
| Apertura objetivo | opening_target_mm | mm, consigna 0–85 |
| Fuerza actual | grip_force_n | N, celda/HX711 tarado y calibrado |
| Fuerza límite | force_limit_n | N, consigna |
| Velocidad lineal | opening_speed_mm_s | mm/s con signo; opcional, se deriva si procede |
| Objeto detectado | object_detected | booleano del controlador/sensor |
| Estado | gripper_state | idle, opening, closing, holding, fault o homing |
| Límite abierto | limit_open | booleano |
| Límite cerrado | limit_closed | booleano |
| Posición AX | ax_position_ticks | 0–1023 ticks |
| Posición AX | ax_position_deg | grados, 0–300 |
| Velocidad AX | ax_speed_rpm | rpm con signo ya decodificado |
| Carga AX | ax_load_pct | % con signo, indicador de carga estimada |
| Voltaje AX | ax_voltage_v | V, registro convertido a unidades |
| Temperatura AX | ax_temperature_c | °C |
| Algún motor bloqueado | motor_blocked | booleano del controlador |
| Error comunicación | communication_error | booleano del ESP32 |
| Sobrecorriente | overcurrent_alarm | booleano, umbral definido por hardware |
| Tiempo ciclo | cycle_time_s | s, ciclo completado o valor definido por firmware |

`motors` es un array opcional con id único 1–6:

| Campo de cada motor | Unidad |
| --- | --- |
| id | 1–6 |
| encoder_pulses | cuentas acumuladas con convención de decodificación documentada |
| encoder_deg | grados del eje elegido/calibrado |
| rpm | rpm con signo del eje elegido |
| current_a | A del INA219 |
| blocked | booleano del diagnóstico |

Es válido transmitir solo algunos motores/campos. Influx los guarda como
`m1_rpm`, `m6_current_a`, etc.; el dashboard muestra SIN DATOS para lo ausente.
`gripper_state` se almacena numéricamente: idle=0, opening=1, closing=2,
holding=3, fault=4, homing=5. Los booleanos se almacenan como 0/1.

## Ejemplo mínimo real

```json
{"device_id":"gripper-01","boot_id":"arranque-01","source":"real","seq":1,"sample_time_ms":1000,"motors":[{"id":1,"encoder_pulses":4172,"rpm":25.0}]}
```

Los valores son ilustrativos: sustituye por lecturas reales. El archivo
`examples/telemetry-demo.json` muestra todas las variables con origen simulated.

## Calibración y magnitudes

La apertura no se deduce únicamente de ángulo/ticks. Guarda pares medidos
(ticks, mm), aplica la geometría o interpolación del mecanismo y versiona
`calibration_id`. Comprueba con una referencia de longitud varios puntos en
0–85 mm y repeticiones en apertura/cierre. ±0,5 mm no se da por alcanzado.

El HX711 requiere tara y escala de fuerza. Si se calibra en masa, convierte a
newtons conforme al ensayo; no mandes gramos como N. INA219 debe tener escala
y shunt adecuados para cada rama. Bloqueo/sobrecorriente necesitan umbrales y
ventanas de tiempo en el controlador; el dashboard no los inventa.

Según ROBOTIS, Present Load es una estimación interna del actuador y no una
medida directa de fuerza. El emisor debe decodificar los registros del AX-18A
conforme al manual, incluyendo dirección en velocidad/carga. No envíes el
registro raw de dirección como si fuera rpm o porcentaje.

La velocidad derivada usa muestras consecutivas de apertura con mismo boot y
calibración, tiempo creciente y dt ≤2 s. Si se envía opening_speed_mm_s, se
conserva ese valor. Las muestras duplicadas/desordenadas no se almacenan.
Una apertura fuera de 0–85 mm se conserva y activa `opening_out_of_range`.
