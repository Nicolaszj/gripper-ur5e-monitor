'use strict';
const numeric = {
  opening_mm: [-1000, 1000], opening_target_mm: [0, 85],
  grip_force_n: [-10000, 10000], force_limit_n: [0, 10000],
  opening_speed_mm_s: [-10000, 10000], cycle_time_s: [0, 86400],
  ax_position_ticks: [0, 1023], ax_position_deg: [0, 300],
  ax_speed_rpm: [-10000, 10000], ax_load_pct: [-100, 100],
  ax_voltage_v: [0, 100], ax_temperature_c: [-40, 200]
};
const flags = ['object_detected', 'limit_open', 'limit_closed', 'motor_blocked',
  'communication_error', 'overcurrent_alarm'];
const states = ['idle', 'opening', 'closing', 'holding', 'fault', 'homing'];
const motorFields = {
  encoder_pulses: [-Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER],
  encoder_deg: [-1e12, 1e12], rpm: [-10000, 10000], current_a: [0, 1000]
};

function fail(message, status = 400) {const error = new Error(message); error.status = status; throw error;}
function identifier(value, label) {
  if (typeof value !== 'string' || !/^[A-Za-z0-9_.-]{1,64}$/.test(value)) fail(`${label} invalido`);
  return value;
}
function number(value, range, key) {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < range[0] || value > range[1]) fail(`${key} invalido`);
  return value;
}
function boolean(value, key) {if (typeof value !== 'boolean') fail(`${key} requiere booleano`); return value ? 1 : 0;}

function normalize(p, previous, now = Date.now()) {
  if (!p || typeof p !== 'object' || Array.isArray(p)) fail('Se requiere un objeto JSON');
  const device = identifier(p.device_id, 'device_id');
  const boot = identifier(p.boot_id, 'boot_id');
  if (!['real', 'simulated'].includes(p.source)) fail('source debe ser real o simulated');
  const seq = number(p.seq, [0, Number.MAX_SAFE_INTEGER], 'seq');
  const uptime = number(p.sample_time_ms, [0, Number.MAX_SAFE_INTEGER], 'sample_time_ms');
  if (!Number.isSafeInteger(seq) || !Number.isSafeInteger(uptime)) fail('seq y sample_time_ms deben ser enteros');
  if (previous && previous.boot_id === boot && (seq <= previous.seq || uptime < previous.sample_time_ms)) fail('Muestra duplicada o fuera de orden', 409);
  const allowed = new Set([...Object.keys(numeric), ...flags, 'gripper_state', 'motors', 'device_id',
    'boot_id', 'source', 'seq', 'sample_time_ms', 'calibration_id']);
  for (const key of Object.keys(p)) if (!allowed.has(key)) fail(`Campo desconocido: ${key}`);
  const fields = {};
  for (const [key, range] of Object.entries(numeric)) if (p[key] != null) fields[key] = number(p[key], range, key);
  for (const key of flags) if (p[key] != null) fields[key] = boolean(p[key], key);
  if (p.gripper_state != null) {
    if (!states.includes(p.gripper_state)) fail('gripper_state invalido');
    fields.gripper_state = states.indexOf(p.gripper_state);
  }
  if (p.motors != null) {
    if (!Array.isArray(p.motors) || p.motors.length > 6) fail('motors debe tener hasta seis elementos');
    const ids = new Set();
    for (const m of p.motors) {
      if (!m || typeof m !== 'object' || Array.isArray(m)) fail('Motor invalido');
      const id = number(m.id, [1, 6], 'motor.id');
      if (!Number.isInteger(id) || ids.has(id)) fail('Identificador de motor duplicado/invalido');
      ids.add(id);
      for (const key of Object.keys(m)) if (!['id', 'blocked', ...Object.keys(motorFields)].includes(key)) fail(`Campo de motor desconocido: ${key}`);
      for (const [key, range] of Object.entries(motorFields)) if (m[key] != null) fields[`m${id}_${key}`] = number(m[key], range, key);
      if (m.blocked != null) fields[`m${id}_blocked`] = boolean(m.blocked, 'blocked');
    }
  }
  if (!Object.keys(fields).length) fail('No hay mediciones ni estados en la muestra');
  if (fields.opening_mm != null && !p.calibration_id) fail('opening_mm requiere calibration_id');
  const calibration = p.calibration_id ? identifier(p.calibration_id, 'calibration_id') : 'not-provided';
  if (fields.opening_mm != null) fields.opening_out_of_range = fields.opening_mm < 0 || fields.opening_mm > 85 ? 1 : 0;
  const dt = previous && previous.boot_id === boot ? uptime - previous.sample_time_ms : 0;
  if (fields.opening_speed_mm_s == null && fields.opening_mm != null && previous && previous.calibration_id === calibration && previous.opening_mm != null && dt > 0 && dt <= 2000) {
    fields.opening_speed_mm_s = (fields.opening_mm - previous.opening_mm) * 1000 / dt;
  }
  const next = {device_id: device, source: p.source, boot_id: boot, seq, sample_time_ms: uptime,
    received_at_ms: now, calibration_id: calibration, opening_mm: fields.opening_mm ?? null, fields};
  const tags = `device_id=${device},source=${p.source},calibration_id=${calibration}`;
  const line = `gripper,${tags} ${Object.entries({...fields, seq, sample_time_ms: uptime, received_at_ms: now})
    .map(([k, v]) => `${k}=${v}`).join(',')} ${now}`;
  return {line, next, fields};
}

module.exports = {normalize, numeric, flags, states, motorFields};
