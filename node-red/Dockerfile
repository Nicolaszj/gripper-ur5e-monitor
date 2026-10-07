FROM nodered/node-red:4.1.0
COPY --chown=node-red:node-red settings.js telemetry.js flows.json start.sh /opt/gripper/
ENTRYPOINT ["/bin/sh", "/opt/gripper/start.sh"]
