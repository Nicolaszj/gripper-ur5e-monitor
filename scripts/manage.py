"""Preparar y desplegar el stack Docker, sin paquetes Python externos."""
import argparse
from pathlib import Path
import secrets
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def init():
    path = ROOT / '.env'
    if path.exists():
        print('.env ya existe; se conservan las credenciales.')
        return
    values = {'ADMIN_USER':'maximiliano', 'ADMIN_PASSWORD':secrets.token_hex(12),
              'INFLUX_TOKEN':secrets.token_hex(32),
              'NODE_RED_CREDENTIAL_SECRET':secrets.token_hex(32),'INGRESS_BIND_IP':'0.0.0.0','DASHBOARD_BIND_IP':'0.0.0.0'}
    path.write_text(''.join(f'{k}={v}\n' for k,v in values.items()), encoding='utf-8')
    (ROOT/'credenciales.txt').write_text(
        'Usuario de administración Node-RED, InfluxDB y Grafana: '+values['ADMIN_USER']+'\n'+
        'Contraseña: '+values['ADMIN_PASSWORD']+'\n'+
        'Telemetría y dashboard: acceso sin login ni token.\n',encoding='utf-8')
    print('Credenciales generadas en .env y credenciales.txt (no subir a Git).')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('accion',choices=['init','up','demo','down','estado','logs'])
    args=parser.parse_args()
    init()
    if args.accion=='init': return
    commands={'up':['up','-d','--build','--wait'],
              'demo':['--profile','demo','up','-d','--build','--wait'],
              'down':['--profile','demo','down'],
              'estado':['--profile','demo','ps'],
              'logs':['logs','--tail','100']}
    subprocess.run(['docker','compose',*commands[args.accion]],cwd=ROOT,check=True)
    if args.accion in ['up','demo']:
        print('Grafana: http://localhost:3000/d/gripper-estudiante')
        print('Node-RED: http://localhost:1880/editor · InfluxDB: http://localhost:8086')
        print('Dashboard y POST http://<IP-PC>:1880/api/telemetry sin login ni token. Demo: origen simulated.')

if __name__=='__main__': main()
