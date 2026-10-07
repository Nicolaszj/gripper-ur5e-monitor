"""Cliente serie Windows sin paquetes externos: ctypes + API Win32."""

import argparse
import ctypes as c
from ctypes import wintypes as w
import os
import time


class DCB(c.Structure):
    _fields_ = [("DCBlength", w.DWORD), ("BaudRate", w.DWORD), ("flags", w.DWORD),
                ("wReserved", w.WORD), ("XonLim", w.WORD), ("XoffLim", w.WORD),
                ("ByteSize", w.BYTE), ("Parity", w.BYTE), ("StopBits", w.BYTE),
                ("XonChar", c.c_char), ("XoffChar", c.c_char), ("ErrorChar", c.c_char),
                ("EofChar", c.c_char), ("EvtChar", c.c_char), ("wReserved1", w.WORD)]


class Timeouts(c.Structure):
    _fields_ = [(nombre, w.DWORD) for nombre in (
        "ReadIntervalTimeout", "ReadTotalTimeoutMultiplier", "ReadTotalTimeoutConstant",
        "WriteTotalTimeoutMultiplier", "WriteTotalTimeoutConstant")]


class PuertoSerie:
    def __init__(self, puerto):
        if os.name != "nt":
            raise RuntimeError("Este cliente usa la API serial de Windows.")
        self.api = c.WinDLL("kernel32", use_last_error=True)
        self.api.CreateFileW.argtypes = [w.LPCWSTR, w.DWORD, w.DWORD, c.c_void_p,
                                        w.DWORD, w.DWORD, w.HANDLE]
        self.api.CreateFileW.restype = w.HANDLE
        self.api.BuildCommDCBW.argtypes = [w.LPCWSTR, c.POINTER(DCB)]
        self.api.BuildCommDCBW.restype = w.BOOL
        self.api.GetCommState.argtypes = [w.HANDLE, c.POINTER(DCB)]
        self.api.GetCommState.restype = w.BOOL
        self.api.SetCommState.argtypes = [w.HANDLE, c.POINTER(DCB)]
        self.api.SetCommState.restype = w.BOOL
        self.api.SetCommTimeouts.argtypes = [w.HANDLE, c.POINTER(Timeouts)]
        self.api.SetCommTimeouts.restype = w.BOOL
        for nombre in ("ReadFile", "WriteFile"):
            funcion = getattr(self.api, nombre)
            funcion.argtypes = [w.HANDLE, c.c_void_p, w.DWORD, c.POINTER(w.DWORD), c.c_void_p]
            funcion.restype = w.BOOL
        self.api.CloseHandle.argtypes = [w.HANDLE]
        self.api.CloseHandle.restype = w.BOOL
        self.handle = self.api.CreateFileW("\\\\.\\" + puerto, 0xC0000000, 0,
                                           None, 3, 0, None)
        if self.handle == c.c_void_p(-1).value:
            self.handle = None
            raise c.WinError(c.get_last_error())
        try:
            dcb = DCB()
            dcb.DCBlength = c.sizeof(DCB)
            self.comprobar(self.api.GetCommState(self.handle, c.byref(dcb)))
            self.comprobar(self.api.BuildCommDCBW(
                "baud=115200 parity=n data=8 stop=1 xon=off octs=off odsr=off dtr=off rts=off",
                c.byref(dcb)))
            self.comprobar(self.api.SetCommState(self.handle, c.byref(dcb)))
            limites = Timeouts(0xFFFFFFFF, 0, 100, 0, 1000)
            self.comprobar(self.api.SetCommTimeouts(self.handle, c.byref(limites)))
        except Exception:
            self.cerrar()
            raise

    @staticmethod
    def comprobar(resultado):
        if not resultado:
            raise c.WinError(c.get_last_error())

    def enviar(self, comando):
        if "\n" in comando or "\r" in comando or "\0" in comando:
            raise ValueError("Envia solo un comando por llamada, sin saltos ni NUL.")
        datos = (comando + "\n").encode("ascii")
        if len(datos) > 95:
            raise ValueError("Comando demasiado largo.")
        buffer = c.create_string_buffer(datos)
        escritos = w.DWORD()
        self.comprobar(self.api.WriteFile(self.handle, buffer, len(datos), c.byref(escritos), None))
        if escritos.value != len(datos):
            raise OSError("Escritura incompleta en el puerto serie")

    def leer(self):
        buffer = c.create_string_buffer(1024)
        recibidos = w.DWORD()
        self.comprobar(self.api.ReadFile(self.handle, buffer, 1024, c.byref(recibidos), None))
        return buffer.raw[:recibidos.value]

    def cerrar(self):
        if self.handle is not None:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cerrar()


def puertos():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DEVICEMAP\SERIALCOMM") as clave:
            indice = 0
            while True:
                try:
                    nombre, valor, _ = winreg.EnumValue(clave, indice)
                except OSError:
                    break
                print(f"{valor}: {nombre}")
                indice += 1
            if indice == 0:
                print("No aparecen puertos serie.")
    except FileNotFoundError:
        print("No aparecen puertos serie.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puertos", action="store_true")
    parser.add_argument("--puerto", help="COM del comunicador USB-TTL, por ejemplo COM5")
    parser.add_argument("--comando", help='Ejemplo: "STATUS", "ALL 20 -20 0" o "STOP"')
    parser.add_argument("--segundos", type=float, default=0, help="Duracion de lectura, 0 = continuo")
    args = parser.parse_args()
    if os.name != "nt":
        parser.error("Este programa requiere Windows")
    if args.puertos:
        puertos()
        return
    if not args.puerto or args.segundos < 0:
        parser.error("Indica --puerto COMx y una duracion no negativa")
    try:
        with PuertoSerie(args.puerto) as puerto:
            if args.comando:
                puerto.enviar(args.comando)
            print(f"Monitor {args.puerto}, 115200 8N1. Ctrl+C para salir.", flush=True)
            inicio = time.monotonic()
            pendiente = bytearray()
            while not args.segundos or time.monotonic() - inicio < args.segundos:
                pendiente.extend(puerto.leer())
                while b"\n" in pendiente:
                    linea, _, resto = pendiente.partition(b"\n")
                    pendiente = bytearray(resto)
                    print(linea.decode("ascii", errors="replace").rstrip("\r"), flush=True)
                if len(pendiente) > 8192:
                    print(pendiente.decode("ascii", errors="replace"), flush=True)
                    pendiente.clear()
    except KeyboardInterrupt:
        print("\nMonitor cerrado.")
    except (OSError, ValueError, RuntimeError) as error:
        raise SystemExit(f"Error: {error}")


if __name__ == "__main__":
    main()
