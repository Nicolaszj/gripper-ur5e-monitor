"""Verifica HTTP -> InfluxDB -> Grafana sobre el stack levantado."""
import base64
import csv
import io
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
env=dict(line.split('=',1) for line in (ROOT/'.env').read_text().splitlines() if '=' in line)

def request(url,method='GET',body=None,headers=None):
    if isinstance(body,dict): body=json.dumps(body).encode()
    req=urllib.request.Request(url,data=body,method=method,headers=headers or {})
    try:
        with urllib.request.urlopen(req,timeout=15) as res: return res.status,res.read()
    except urllib.error.HTTPError as error: return error.code,error.read()

def main():
    boot='test-'+uuid.uuid4().hex[:12]
    body={'device_id':'integration-test','boot_id':boot,'source':'simulated','seq':1,'sample_time_ms':1000,
          'grip_force_n':8.5,'opening_mm':42.5,'calibration_id':'TEST-NO-CALIBRADO',
          'motors':[{'id':6,'rpm':12.5,'current_a':0.15,'encoder_pulses':1234}]}
    headers={'Content-Type':'application/json'}
    assert request('http://127.0.0.1:1880/api/status')[0]==200
    code,data=request('http://127.0.0.1:1880/api/telemetry','POST',body,headers)
    assert code==201,(code,data)
    assert request('http://127.0.0.1:1880/api/telemetry','POST',body,headers)[0]==409
    bad=dict(body,seq=2,object_detected='false')
    assert request('http://127.0.0.1:1880/api/telemetry','POST',bad,headers)[0]==400
    query='from(bucket:"gripper") |> range(start:-5m) |> filter(fn:(r)=> r._measurement=="gripper" and r.device_id=="integration-test" and r._field=="m6_rpm") |> last()'
    code,data=request('http://127.0.0.1:8086/api/v2/query?org=maximiliano-estudiante','POST',query.encode(),
        {'Authorization':'Token '+env['INFLUX_TOKEN'],'Content-Type':'application/vnd.flux','Accept':'application/csv'})
    assert code==200,(code,data)
    assert '12.5' in data.decode()
    code,data=request('http://127.0.0.1:3000/api/dashboards/uid/gripper-estudiante')
    assert code==200,(code,data)
    dashboard=json.loads(data)['dashboard']
    assert len(dashboard['panels'])==59
    tested=0
    for panel in dashboard['panels']:
        if not panel.get('targets'): continue
        flux=panel['targets'][0]['query'].replace('${device}','gripper-01').replace('${source}','simulated')
        flux=flux.replace('v.timeRangeStart','-15m').replace('v.timeRangeStop','now()').replace('v.windowPeriod','1s')
        payload={'from':str(int(time.time()*1000)-900000),'to':str(int(time.time()*1000)),
          'queries':[{'refId':'A','datasource':{'type':'influxdb','uid':'gripper-influx'},'query':flux,'maxDataPoints':300,'intervalMs':1000}]}
        code,data=request('http://127.0.0.1:3000/api/ds/query','POST',payload,{'Content-Type':'application/json'})
        assert code==200,(panel['title'],code,data)
        result=json.loads(data)['results']['A']
        assert not result.get('error'),(panel['title'],result.get('error'))
        assert result.get('frames'),(panel['title'],'sin frames')
        if panel['title']!='Velocidad de apertura/cierre':
            assert any(any(column for column in frame.get('data',{}).get('values',[])) for frame in result['frames']),(panel['title'],'sin datos')
        tested+=1
    # Influx confirms every displayed field is queriable through the Grafana datasource.
    print(f'OK: ingreso y dashboard sin credenciales, escritura, duplicados, validación y {tested} consultas de paneles Grafana.')

if __name__=='__main__': main()
