import importlib.util
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from serial_bridge import parse_line

class Tests(unittest.TestCase):
    def test_diagnosticos_no_son_medidas(self):
        self.assertIsNone(parse_line('OK'))
        self.assertIsNone(parse_line('STATE 20 -20 0 1500 1',True))
    def test_encoder_legacy_solo_m1(self):
        p=parse_line('Conteo: 4172 | Vueltas: 1.000 | Sentido: + | RPM salida: 25.00',True)
        self.assertEqual(p,{'motors':[{'id':1,'encoder_pulses':4172,'rpm':25.0}]})
    def test_no_marcar_simulacion_como_hardware(self):
        with self.assertRaises(ValueError): parse_line('{"source":"simulated"}')

if __name__=='__main__': unittest.main()
