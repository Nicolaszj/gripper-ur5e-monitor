"""Genera el flujo de Node-RED y el dashboard provisionado de Grafana."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def save(path, value):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

tab = "gripper-flow"
flows = [{"id": tab, "type": "tab", "label": "ESP32 → InfluxDB", "disabled": False}]
def add(id, type, name, wires, **kwargs):
    flows.append(dict(id=id, type=type, z=tab, name=name, wires=wires, **kwargs))

add("ingress", "http in", "POST telemetría", [["validate"]], url="/api/telemetry", method="post", upload=False, swaggerDoc="", x=130, y=100)
add("validate", "function", "Validar telemetría", [["write"], ["response"]], outputs=2, x=360, y=100, func='''
const t = global.get('telemetry');
let key;
try {
  const body = typeof msg.payload === 'string' ? JSON.parse(msg.payload) : msg.payload;
  key = `${body.device_id}:${body.source}`;
  const pending = flow.get('pending') || {};
  if (pending[key]) { msg.statusCode=429; msg.payload={error:'Muestra en proceso; reintentar'}; return [null,msg]; }
  const latest = flow.get('latest') || {};
  const sample = t.normalize(body, latest[key]);
  pending[key] = true; flow.set('pending', pending);
  msg.sampleKey = key; msg.sample = sample.next;
  msg.method = 'POST';
  msg.url = `${env.get('INFLUX_URL')}/api/v2/write?org=${encodeURIComponent(env.get('INFLUX_ORG'))}&bucket=${encodeURIComponent(env.get('INFLUX_BUCKET'))}&precision=ms`;
  msg.headers = {'Authorization':`Token ${env.get('INFLUX_TOKEN')}`, 'Content-Type':'text/plain; charset=utf-8'};
  msg.payload = sample.line;
  return [msg,null];
} catch (error) {
  msg.statusCode=error.status || 400; msg.payload={error:error.message}; return [null,msg];
}''', initialize="flow.set('pending', {});", finalize="", libs=[])
add("write", "http request", "Guardar en InfluxDB", [["result"]], method="use", ret="txt", paytoqs="ignore", url="", tls="", persist=False, proxy="", insecureHTTPParser=False, authType="", senderr=False, headers=[], requestTimeout="5000", x=600, y=100)
add("result", "function", "Confirmar escritura", [["response"]], outputs=1, x=820, y=100, func='''
const pending=flow.get('pending') || {}; delete pending[msg.sampleKey]; flow.set('pending',pending);
if (msg.statusCode === 204) {
  const latest=flow.get('latest') || {}; latest[msg.sampleKey]=msg.sample; flow.set('latest',latest);
  msg.statusCode=201; msg.payload={stored:true,device_id:msg.sample.device_id,source:msg.sample.source,seq:msg.sample.seq};
} else {
  msg.statusCode=502; msg.payload={stored:false,error:'InfluxDB no confirmo la escritura; reintentar la misma muestra'};
}
msg.headers={'Content-Type':'application/json'}; return msg;''')
add("catch-write", "catch", "Fallo de escritura", [["failed"]], scope=["write"], uncaught=False, x=610, y=180)
add("failed", "function", "Respuesta sin filtrar secretos", [["response"]], outputs=1, x=850, y=180, func='''
const pending=flow.get('pending') || {}; delete pending[msg.sampleKey]; flow.set('pending',pending);
msg.statusCode=502; msg.payload={stored:false,error:'Almacenamiento no disponible; reintentar'};
msg.headers={'Content-Type':'application/json'}; return msg;''')
add("response", "http response", "Respuesta API", [], statusCode="", headers={"Content-Type":"application/json"}, x=1090, y=100)
add("health-in", "http in", "Health", [["health"]], url="/api/health", method="get", upload=False, swaggerDoc="", x=130, y=300)
add("health", "function", "Estado servicio", [["response"]], outputs=1, x=370, y=300, func="msg.payload={service:'maximiliano-estudiante',version:'1.0.0',status:'up'}; msg.statusCode=200; return msg;")
add("status-in", "http in", "Últimas muestras", [["status"]], url="/api/status", method="get", upload=False, swaggerDoc="", x=140, y=400)
add("status", "function", "Estado y antigüedad", [["response"]], outputs=1, x=390, y=400, func='''
msg.statusCode=200; msg.payload={samples:Object.values(flow.get('latest') || {}).map(s => ({
  ...s,age_s:(Date.now()-s.received_at_ms)/1000,stale:Date.now()-s.received_at_ms>5000
}))}; return msg;''')
save("node-red/flows.json", flows)

DS = {"type":"influxdb","uid":"gripper-influx"}
panels=[]
next_id=1
y=0
def row(title):
    global next_id, y
    panels.append({"id":next_id,"type":"row","title":title,"collapsed":False,"panels":[],"gridPos":{"x":0,"y":y,"w":24,"h":1}})
    next_id+=1; y+=1

def query(fields, instant=False, age=False):
    filtering = ' or '.join(f'r._field == "{field}"' for field in fields)
    q = f'''from(bucket: "gripper")
  |> range(start: {'-5s' if instant else 'v.timeRangeStart'}, stop: {'now()' if instant else 'v.timeRangeStop'})
  |> filter(fn: (r) => r._measurement == "gripper" and r.device_id == "${{device}}" and r.source == "${{source}}")
  |> filter(fn: (r) => {filtering})
  |> group(columns: ["_field"])
'''
    if age:
        q=q.replace('range(start: -5s, stop: now())','range(start: -24h, stop: now())')
        q+='  |> last()\n  |> map(fn: (r) => ({r with _value: float(v: uint(v: now()) - uint(v: r._time)) / 1000000000.0}))\n'
    elif instant: q+='  |> last()\n'
    else: q+='  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)\n'
    return q

def panel(title, fields, x, width=6, kind="stat", unit="none", max_value=None, mappings=None, description="", height=5, instant=True, age=False):
    global next_id
    defaults={"unit":unit,"decimals":2,"noValue":"SIN DATOS", "color":{"mode":"palette-classic"},
              "thresholds":{"mode":"absolute","steps":[{"color":"green","value":None}]},"mappings":mappings or []}
    if max_value is not None: defaults.update(min=0,max=max_value)
    opts={"reduceOptions":{"calcs":["lastNotNull"],"fields":"","values":False},"orientation":"auto","textMode":"auto","colorMode":"value","graphMode":"none","justifyMode":"auto"}
    if kind=="timeseries": opts={"legend":{"displayMode":"list","placement":"bottom","showLegend":True},"tooltip":{"mode":"multi","sort":"none"}}
    if kind=="gauge": opts={"reduceOptions":{"calcs":["lastNotNull"],"fields":"","values":False},"showThresholdLabels":False,"showThresholdMarkers":True,"orientation":"auto"}
    panels.append({"id":next_id,"type":kind,"title":title,"description":description,"datasource":DS,
      "gridPos":{"x":x,"y":y,"w":width,"h":height},"fieldConfig":{"defaults":defaults,"overrides":[]},"options":opts,
      "targets":[{"refId":"A","datasource":DS,"query":query(fields,instant,age)}]})
    next_id+=1

binary=[{"type":"value","options":{"0":{"text":"NO","color":"green"},"1":{"text":"SÍ","color":"red"}}}]
switch=[{"type":"value","options":{"0":{"text":"OFF","color":"gray"},"1":{"text":"ON","color":"blue"}}}]
state=[{"type":"value","options":{str(i):{"text":text,"color":color} for i,(text,color) in enumerate([
  ("REPOSO","blue"),("ABRIENDO","green"),("CERRANDO","orange"),("SUJETANDO","purple"),("FALLO","red"),("HOMING","yellow")])}}]
row("GRIPPER · datos principales")
panel("Apertura actual",["opening_mm"],0,kind="gauge",unit="lengthmm",max_value=85,description="Referencia PDS 0–85 mm. ±0,5 mm es objetivo de validación, no precisión demostrada.")
panel("Apertura objetivo",["opening_target_mm"],6,unit="lengthmm",max_value=85)
panel("Fuerza actual",["grip_force_n"],12,unit="forceN",description="Celda + HX711 calibrados. No se obtiene fuerza en N de Present Load del AX-18A.")
panel("Límite de fuerza",["force_limit_n"],18,unit="forceN")
y+=5
panel("Velocidad de apertura/cierre",["opening_speed_mm_s"],0,unit="suffix:mm/s")
panel("Objeto detectado",["object_detected"],6,mappings=[{"type":"value","options":{"0":{"text":"NO","color":"gray"},"1":{"text":"SÍ","color":"green"}}}])
panel("Estado gripper",["gripper_state"],12,mappings=state)
panel("Tiempo de ciclo",["cycle_time_s"],18,unit="s")
y+=5
panel("Apertura · actual / objetivo",["opening_mm","opening_target_mm"],0,12,"timeseries","lengthmm",height=8,instant=False)
panel("Fuerza · actual / límite",["grip_force_n","force_limit_n"],12,12,"timeseries","forceN",height=8,instant=False)
y+=8
row("SEGURIDAD · estados informativos, no funciones de parada certificadas")
for idx,(title,field,mp) in enumerate([
  ("Límite abierto","limit_open",switch),("Límite cerrado","limit_closed",switch),
  ("Motor bloqueado","motor_blocked",binary),("Error comunicación","communication_error",binary),
  ("Sobrecorriente","overcurrent_alarm",binary),("Apertura fuera de referencia","opening_out_of_range",binary)]):
    panel(title,[field],(idx%3)*8,8,mappings=mp)
    if idx in [2,5]: y+=5
panel("Antigüedad última muestra",["received_at_ms"],0,12,unit="s",age=True,description="Más de 5 s: dato obsoleto. SIN DATOS si no hay muestras en las últimas 24 h.")
panels[-1]['fieldConfig']['defaults']['thresholds']['steps'].append({"color":"red","value":5})
panel("Temperatura AX-18A",["ax_temperature_c"],12,12,unit="celsius",description="El límite de alarma debe fijarse según la ficha y el diseño. No se presupone un umbral seguro.")
y+=5
row("AX-18A · diagnóstico")
for idx,(title,field,unit) in enumerate([
 ("Posición AX · ticks","ax_position_ticks","none"),("Posición AX · grados","ax_position_deg","degree"),
 ("Velocidad AX","ax_speed_rpm","rotrpm"),("Carga AX · indicador","ax_load_pct","percent"),
 ("Voltaje AX","ax_voltage_v","volt")]):
    panel(title,[field],(idx%3)*8,8,unit=unit,description="Present Load es diagnóstico estimado del actuador; no fuerza medida en N." if field=='ax_load_pct' else '')
    if idx==2: y+=5
y+=5
row("MOTORES M1–M6 · encoders y corriente")
for title,suffix,unit in [("Encoder · pulsos","encoder_pulses","none"),("Encoder · grados","encoder_deg","degree"),
 ("Velocidad","rpm","rotrpm"),("Corriente","current_a","amp"),("Bloqueo","blocked","none")]:
    for i in range(1,7): panel(f"M{i} · {title}",[f"m{i}_{suffix}"],(i-1)*4,4,unit=unit,mappings=binary if suffix=='blocked' else None)
    y+=5
panel("Velocidad M1–M6",[f"m{i}_rpm" for i in range(1,7)],0,12,"timeseries","rotrpm",height=8,instant=False)
panel("Corriente M1–M6",[f"m{i}_current_a" for i in range(1,7)],12,12,"timeseries","amp",height=8,instant=False)

save("grafana/dashboards/gripper.json",{
  "uid":"gripper-estudiante","title":"Maximiliano Estudiante · Gripper","schemaVersion":41,"version":1,
  "description":"Monitor del gripper. Real y simulado separados. Datos actuales caducan a los 5 s. Calibración de apertura pendiente de verificación física.",
  "tags":["ESP32","gripper","maximiliano-estudiante"],"timezone":"America/Bogota","refresh":"5s",
  "time":{"from":"now-15m","to":"now"},"editable":True,"panels":panels,
  "templating":{"list":[
    {"name":"source","label":"Origen","type":"custom","query":"real,simulated","current":{"text":"real","value":"real"},"options":[{"text":s,"value":s,"selected":s=='real'} for s in ['real','simulated']]},
    {"name":"device","label":"Dispositivo","type":"query","datasource":DS,"refresh":1,
     "query":'import "influxdata/influxdb/schema"\nschema.tagValues(bucket: "gripper", tag: "device_id", start: -30d)',
     "current":{"text":"gripper-01","value":"gripper-01"},"multi":False,"includeAll":False}
  ]}})
print(f"Generados flows.json y dashboard ({len(panels)} paneles).")
