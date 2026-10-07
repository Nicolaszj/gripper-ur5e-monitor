#!/bin/sh
set -eu
if [ ! -f /data/gripper-flows.json ]; then
    cp /opt/gripper/flows.json /data/gripper-flows.json
fi
export FLOWS=/data/gripper-flows.json
exec /usr/src/node-red/entrypoint.sh --settings /opt/gripper/settings.js
