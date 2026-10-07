const test = require('node:test');
const assert = require('node:assert/strict');
const {normalize} = require('../node-red/telemetry');
const base = {device_id:'gripper-01',boot_id:'b1',source:'real',seq:1,sample_time_ms:1000};
test('datos parciales no inventan medidas ni estados',()=>{
  const result=normalize({...base,motors:[{id:1,rpm:12}]},null,10000);
  assert.deepEqual(result.fields,{m1_rpm:12});
  assert.ok(!result.line.includes('opening_mm'));
});
test('derivada usa tiempo del emisor y no latencia HTTP',()=>{
  const first=normalize({...base,opening_mm:20,calibration_id:'c1'},null,10000);
  const next=normalize({...base,seq:2,sample_time_ms:1500,opening_mm:25,calibration_id:'c1'},first.next,17000);
  assert.equal(next.fields.opening_speed_mm_s,10);
});
test('reinicio, cambio de calibracion y hueco no generan derivadas falsas',()=>{
  const p=normalize({...base,opening_mm:20,calibration_id:'c1'},null).next;
  for(const changes of [{boot_id:'b2'}, {calibration_id:'c2'}, {sample_time_ms:4000}]) {
    const result=normalize({...base,seq:2,sample_time_ms:1500,opening_mm:25,calibration_id:'c1',...changes},p);
    assert.equal(result.fields.opening_speed_mm_s,undefined);
  }
});
test('duplicado y fuera de orden no alteran el historico',()=>{
  const p=normalize({...base,grip_force_n:2},null).next;
  assert.throws(()=>normalize({...base,grip_force_n:2},p),e=>e.status===409);
  assert.throws(()=>normalize({...base,seq:2,sample_time_ms:900,grip_force_n:2},p));
});
test('bool no se confunde con string y rechaza NaN y motores duplicados',()=>{
  for(const fields of [{object_detected:'false'},{grip_force_n:NaN},
    {motors:[{id:1,rpm:2},{id:1,rpm:3}]},{opening_mm:20},{inventado:1}]) {
    assert.throws(()=>normalize({...base,...fields},null));
  }
});
test('se conservan excedencias de apertura para mostrarlas',()=>{
  const r=normalize({...base,opening_mm:86,calibration_id:'c1'},null);
  assert.equal(r.fields.opening_out_of_range,1);
});
