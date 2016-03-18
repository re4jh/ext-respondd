respondd Status for Servers
---------------------------------

A gluon compatible status script for respondd in python.

## Dependencies

 * lsb_release
 * ethtool
 * python3.3
 * python3-netifaces
 * py-cpuinfo
 * batman-adv

## Setup

### config.json
Startparameter for ext-respondd.  
Copy `config.json.example` to `config.json` and change it to match your server configuration.  
(`cp config.json.example config.json`)

 * `batman` (string)
 * `fastd` (string)
 * `bridge` (string)
 * `fastd_socket` (string)


### alias.json
Aliases to overwrite the returned server data.  
Copy `alias.json.example` to `alias.json` and input e.g. owner information.  
(`cp alias.json.example alias.json`)

The JSON content matches one block of the nodes.json, which is outputted by e.g. the [HopGlass-Server](https://github.com/plumpudding/hopglass-server).


### ext-respondd.service
Register ext-respondd as a systemd service

```
cp ext-respondd.service.example /lib/systemd/system/ext-respondd.service
! modify the path inside of the ext-respondd.service !
systemctl enable ext-respondd
systemctl start ext-respondd
```

## Notes
Add this to your aliases.json in your [HopGlass-Server](https://github.com/plumpudding/hopglass-server) if this a gateway.

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
