const crypto = require('crypto');
const equal = (a, b) => {
  const x = crypto.createHash('sha256').update(String(a)).digest();
  const y = crypto.createHash('sha256').update(String(b)).digest();
  return crypto.timingSafeEqual(x, y);
};
const user = name => name === process.env.ADMIN_USER ? {username: name, permissions: '*'} : null;
module.exports = {
  flowFile: '/data/gripper-flows.json',
  flowFilePretty: true,
  uiPort: 1880,
  httpAdminRoot: '/editor',
  httpNodeRoot: '/',
  apiMaxLength: '64kb',
  credentialSecret: process.env.NODE_RED_CREDENTIAL_SECRET,
  adminAuth: {
    type: 'credentials',
    users: async name => user(name),
    authenticate: async (name, password) => equal(password, process.env.ADMIN_PASSWORD) ? user(name) : null,
    default: async () => null
  },
  contextStorage: {default: {module: 'localfilesystem'}},
  functionGlobalContext: {telemetry: require('./telemetry')},
  logging: {console: {level: 'info', metrics: false, audit: false}}
};
