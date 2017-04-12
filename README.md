# respondd Status for Servers

> A gluon compatible status script for respondd in python.


## Dependencies

 * lsb_release
 * ethtool
 * python3.3
 * python3-netifaces
 * batman-adv


## Setup

### config.json
Startparameter for ext-respondd.  
Copy `config.json.example` to `config.json` and change it to match your server configuration.  
(`cp config.json.example config.json`)

 * `batman` (string) (Needed: typical bat0)
 * `bridge` (string) (Needed: typical br-client)
 * `mesh-wlan` (array of string) (Optional: Ad-Hoc batman-Mesh)
 * `mesh-vpn` (array of string) (Optional: fastd, GRE, L2TP batman-Mesh)
 * `fastd_socket` (string) (Optional: needed for uplink-flag)

### alias.json
Aliases to overwrite the returned server data.  
Copy `alias.json.example` to `alias.json` and input e.g. owner information.  
(`cp alias.json.example alias.json`)

The JSON content matches one block of the nodes.json, which is outputted by e.g. the [HopGlass-Server](https://github.com/hopglass/hopglass-server).

### ext-respondd.service
Register ext-respondd as a systemd service

```
cp ext-respondd.service.example /lib/systemd/system/ext-respondd.service
! modify the path inside of the ext-respondd.service !
systemctl enable ext-respondd
systemctl start ext-respondd
```


## Notes
Add this to your aliases.json in your [HopGlass-Server](https://github.com/hopglass/hopglass-server) if this a gateway.

```
  "gw2": {
    "nodeinfo": {
      "hostname": "Gateway 2",
      "node_id": "gw2"
    },
    "flags": {
      "gateway": true
    }
  }
```


## Related projects

Collecting data from respondd:
* [respond-collector](https://github.com/FreifunkBremen/respond-collector) written in Go
* [HopGlass Server](https://github.com/hopglass/hopglass-server) written in Node.js

Respondd for servers:
* [ffho-respondd](https://github.com/FreifunkHochstift/ffho-respondd) from Freifunk Hochstift (fork of ext-respondd)
* [ffnord-alfred-announce](https://github.com/ffnord/ffnord-alfred-announce) from FreiFunkNord
* [yanic](https://github.com/FreifunkBremen/yanic) from Freifunk Bremen
* [py-respondd](https://github.com/descilla/py-respondd)
