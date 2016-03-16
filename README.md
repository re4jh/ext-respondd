respondd Status for Servers
---------------------------------

A gluon compatible status script for respondd in python.

## Dependencies

 * lsb_release
 * ethtool
 * python3.3
 * python3-netifaces
 * py-cpuinfo

## Setup

Adjust config.json
Adjust aliases.json

Create systemd Startup-File:
/etc/systemd/system/ext-respondd.service
```
[Unit]
Description=ext-respondd (respondd Status for Servers)
After=syslog.target network.target

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=/usr/local/src/ext-respondd
ExecStart=/usr/local/src/ext-respondd/ext-respondd.py

[Install]
WantedBy=multi-user.target
```

systemctl enable ext-respondd
systemctl start ext-respondd
