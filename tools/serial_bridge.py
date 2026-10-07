"""ESP32 serial -> JSON HTTP Node-RED, usando solo biblioteca estándar."""
import argparse
import json
import os
import re
import select
import time
import urllib.request
import urllib.error
import uuid



class PuertoLinux:
    def __init__(self, port):
        import termios
        self.fd=os.open(port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
        try:
            attrs=termios.tcgetattr(self.fd)
            attrs[0]=0; attrs[1]=0; attrs[2]=termios.CS8|termios.CREAD|termios.CLOCAL
            attrs[3]=0; attrs[4]=termios.B115200; attrs[5]=termios.B115200
            attrs[6][termios.VMIN]=0; attrs[6][termios.VTIME]=0
            termios.tcsetattr(self.fd,termios.TCSANOW,attrs)
        except Exception:
            os.close(self.fd); raise
    def leer(self):
        ready,_,_=select.select([self.fd],[],[],0.1)
        if not ready: return b''
        data=os.read(self.fd,4096)
        if not data: raise OSError('Dispositivo serie desconectado')
        return data
    def cerrar(self): os.close(self.fd)


def parse_line(line, legacy=False):
    if line.lstrip().startswith('{'):
        body=json.loads(line)
        if not isinstance(body,dict): raise ValueError('JSON debe ser un objeto')
        if body.get('source','real')!='real': raise ValueError('El puente de hardware solo acepta source=real')
        return body
    if legacy:
        match=re.search(r'Conteo:\s*(-?\d+).*RPM salida:\s*(-?\d+(?:\.\d+)?)',line)
        if match:
            return {'motors':[{'id':1,'encoder_pulses':int(match[1]),'rpm':float(match[2])}]}
    return None  # Diagnósticos, ACK y texto no se convierten en medidas.


def publish(body,url):
    data=json.dumps(body,allow_nan=False).encode('utf-8')
    for attempt in range(3):
        request=urllib.request.Request(url,data=data,method='POST',headers={
            'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(request,timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as error:
            if error.code==409: return 409  # Ya recibido / muestra antigua.
            if error.code!=429 and error.code<500:
                raise ValueError(f'HTTP {error.code}: {error.read().decode()[:300]}')
        except (urllib.error.URLError,TimeoutError):
            pass
        if attempt<2: time.sleep(0.25*(attempt+1))
    raise OSError('No se confirmó almacenamiento tras tres intentos')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--puerto',required=True,help='COM4 en Windows o /dev/ttyUSB0 en Linux')
    parser.add_argument('--device',default='gripper-01')
    parser.add_argument('--legacy-encoder',action='store_true',help='Importa únicamente conteo/RPM M1 del firmware anterior')
    parser.add_argument('--url',default=os.environ.get('TELEMETRY_URL','http://localhost:1880/api/telemetry'))
    args=parser.parse_args()
    url=args.url
    boot='bridge-'+uuid.uuid4().hex[:12]; seq=0; start=time.monotonic()
    while True:
        port=None
        try:
            if os.name=='nt':
                from windows_serial import PuertoSerie
                port=PuertoSerie(args.puerto)
            else: port=PuertoLinux(args.puerto)
            print(f'Conectado {args.puerto} a 115200 8N1; enviando a Node-RED',flush=True)
            pending=bytearray()
            while True:
                pending.extend(port.leer())
                while b'\n' in pending:
                    raw,_,rest=pending.partition(b'\n'); pending=bytearray(rest)
                    try:
                        body=parse_line(raw.decode('utf-8'),args.legacy_encoder)
                        if body is None: continue
                        body.setdefault('device_id',args.device); body.setdefault('boot_id',boot)
                        body.setdefault('source','real'); body.setdefault('seq',seq)
                        body.setdefault('sample_time_ms',int((time.monotonic()-start)*1000))
                        code=publish(body,url)
                        print(f"seq={body['seq']} HTTP {code}",flush=True)
                        seq+=1
                    except (ValueError,UnicodeDecodeError,OSError) as error:
                        print(f'Muestra descartada: {error}',flush=True)
                if len(pending)>65536:
                    pending.clear(); print('Trama demasiado larga; descartada',flush=True)
        except OSError as error:
            print(f'Serial no disponible: {error}; reintentando en 2 s',flush=True)
            time.sleep(2)
        finally:
            if port: port.cerrar()

if __name__=='__main__':
    try: main()
    except KeyboardInterrupt: print('\nPuente detenido.')
