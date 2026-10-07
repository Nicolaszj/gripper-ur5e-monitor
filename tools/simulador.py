"""Publica mediciones ficticias etiquetadas simulated; no conecta hardware."""
import json
import math
import os
from pathlib import Path
import time
import urllib.request
import urllib.error
import uuid

def read_env():
    result={}
    path=Path(__file__).resolve().parents[1]/'.env'
    if path.exists():
        for line in path.read_text(encoding='utf-8').splitlines():
            if '=' in line and not line.startswith('#'):
                key,value=line.split('=',1); result[key]=value
    return result

def sample(seq, uptime, boot):
    phase=(uptime/1000)%12
    opening=85 if phase<2 else max(20,85-(phase-2)*16.25) if phase<6 else 20 if phase<9 else min(85,20+(phase-9)*21.67)
    holding=6<=phase<9
    return {'device_id':'gripper-01','boot_id':boot,'source':'simulated','seq':seq,
      'sample_time_ms':uptime,'calibration_id':'DEMO-NO-CALIBRADO',
      'opening_mm':round(opening,3),'opening_target_mm':20 if phase<9 else 85,
      'grip_force_n':round(18+math.sin(phase)*0.3,3) if holding else 0.0,'force_limit_n':25,
      'object_detected':holding,'gripper_state':'holding' if holding else 'idle' if phase<2 else 'closing' if phase<6 else 'opening',
      'limit_open':opening>=85,'limit_closed':False,'ax_position_ticks':round(opening/85*900),
      'ax_position_deg':round(opening/85*263.9,2),'ax_speed_rpm':0 if holding or phase<2 else 12,
      'ax_load_pct':35 if holding else 10,'ax_voltage_v':11.8,'ax_temperature_c':round(35+math.sin(phase),2),
      'motor_blocked':False,'communication_error':False,'overcurrent_alarm':False,'cycle_time_s':12.0,
      'motors':[{'id':i,'encoder_pulses':round(opening*30+i*5),'encoder_deg':round(opening*3.5,2),
         'rpm':0 if holding or phase<2 else round(10+i+math.sin(phase),2),'current_a':round(0.08+i*0.008,3),'blocked':False} for i in range(1,7)]}

def main():
    url=os.environ.get('TELEMETRY_URL','http://localhost:1880/api/telemetry')
    boot='demo-'+uuid.uuid4().hex[:12]; start=time.monotonic(); seq=0
    while True:
        body=sample(seq,int((time.monotonic()-start)*1000),boot)
        request=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=5) as response:
                print(f'SIMULATED seq={seq} guardado HTTP {response.status}',flush=True)
        except (urllib.error.URLError,TimeoutError) as error:
            print(f'No se pudo guardar: {error}',flush=True)
        seq+=1; time.sleep(0.5)

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: pass
