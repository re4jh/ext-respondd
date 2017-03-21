#!/usr/bin/env python3

# Code-Base: https://github.com/ffggrz/ffnord-alfred-announce
#          + https://github.com/freifunk-mwu/ffnord-alfred-announce
#          + https://github.com/FreifunkBremen/respondd

import sys
import socket
import select
import struct
import subprocess
import argparse
import re

# Force encoding to UTF-8
import locale                                         # Ensures that subsequent open()s
locale.getpreferredencoding = lambda _=None: 'UTF-8'  # are UTF-8 encoded.


import json
import zlib

import netifaces as netif

def toUTF8(line):
    return line.decode("utf-8")

def call(cmdnargs):
    output = subprocess.check_output(cmdnargs)
    lines = output.splitlines()
    lines = [toUTF8(line) for line in lines]
    return lines

def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        d = dict(a)
        d.update({k: merge(a.get(k, None), b[k]) for k in b})
        return d

    if isinstance(a, list) and isinstance(b, list):
        return [merge(x, y) for x, y in itertools.izip_longest(a, b)]

    return a if b is None else b

def getGateway():
#/sys/kernel/debug/batman_adv/bat0/gateways
    output = subprocess.check_output(["batctl","-m",config['batman'],"gwl","-n"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()
    gw = None

    for line in lines:
        gw_line = re.match(r"^=> +([0-9a-f:]+) ", line)
        if gw_line:
            gw = gw_line.group(1)

    return gw

def getClients():
#/sys/kernel/debug/batman_adv/bat0/transtable_local
    output = subprocess.check_output(["batctl","-m",config['batman'],"tl","-n"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()
    batadv_mac = getDevice_MAC(config['batman'])

    j = {"total": 0, "wifi": 0}

    for line in lines:
        # batman-adv -> translation-table.c -> batadv_tt_local_seq_print_text
        # R = BATADV_TT_CLIENT_ROAM
        # P = BATADV_TT_CLIENT_NOPURGE
        # N = BATADV_TT_CLIENT_NEW
        # X = BATADV_TT_CLIENT_PENDING
        # W = BATADV_TT_CLIENT_WIFI
        # I = BATADV_TT_CLIENT_ISOLA
        # . = unset
        # * c0:11:73:b2:8f:dd   -1 [.P..W.]   1.710   (0xe680a836)
        ml = re.match(r"^\s\*\s([0-9a-f:]+)\s+-\d\s\[([RPNXWI\.]+)\]", line, re.I)
        if ml:
            if not batadv_mac == ml.group(1): # Filter bat0
                j["total"] += 1
                if ml.group(2)[4] == 'W':
                    j["wifi"] += 1

    return j

def getDevice_Addresses(dev):
    l = []

    try:
        for ip6 in netif.ifaddresses(dev)[netif.AF_INET6]:
            raw6 = ip6['addr'].split('%')
            l.append(raw6[0])
    except:
        pass

    return l

def getDevice_MAC(dev):
    try:
        interface = netif.ifaddresses(dev)
        mac = interface[netif.AF_LINK]
        return mac[0]['addr']
    except:
        return None

def getMesh_Interfaces():
    j = {}
    output = subprocess.check_output(["batctl","-m",config['batman'],"if"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

    for line in lines:
        dev_re = re.match(r"^([^:]*)", line)
        dev = dev_re.group(1)
        j[dev] = getDevice_MAC(dev)

    return j

def getBat0_Interfaces():
    j = {}
    output = subprocess.check_output(["batctl","-m",config['batman'],"if"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

    for line in lines:
        dev_line = re.match(r"^([^:]*)", line)
        nif = dev_line.group(0)

        if_group = ""
        if "fastd" in config and nif == config["fastd"]: # keep for compatibility
            if_group = "tunnel"
        elif nif.find("l2tp") != -1:
            if_group = "l2tp"
        elif ("mesh-vpn" in config and nif in config["mesh-vpn"]):
            if_group = "tunnel"
        elif "mesh-wlan" in config and nif in config["mesh-wlan"]:
            if_group = "wireless"
        else:
            if_group = "other"

        if not if_group in j:
            j[if_group] = []

        j[if_group].append(getDevice_MAC(nif))

    return j

def getTraffic(): # BUG: falsches interfaces?
    return (lambda fields:
        dict(
            (key, dict(
                (type_, int(value_))
                for key_, type_, value_ in fields
                    if key_ == key))
            for key in ['rx', 'tx', 'forward', 'mgmt_rx', 'mgmt_tx']
        )
    )(list(
        (
            key.replace('_bytes', '').replace('_dropped', ''),
            'bytes' if key.endswith('_bytes') else 'dropped' if key.endswith('_dropped') else 'packets',
            value
        )
        for key, value in map(lambda s: list(map(str.strip, s.split(': ', 1))), call(['ethtool', '-S', config['batman']])[1:])
    ))

def getMemory():
    return dict(
        (key.replace('Mem', '').lower(), int(value.split(' ')[0]))
        for key, value in map(lambda s: map(str.strip, s.split(': ', 1)), open('/proc/meminfo').readlines())
        if key in ('MemTotal', 'MemFree', 'Buffers', 'Cached')
    )

def getFastd():
    fastd_data = b""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(config["fastd_socket"])
    except socket.error as err:
        print("socket error: ", sys.stderr, err)
        return None

    while True:
        data = sock.recv(1024)
        if not data: break
        fastd_data+= data

    sock.close()
    return json.loads(fastd_data.decode("utf-8"))

def getMeshVPNPeers():
    j = {}
    if "fastd_socket" in config:
        fastd = getFastd()
        for peer, v in fastd["peers"].items():
            if v["connection"]:
                j[v["name"]] = {
                    "established": v["connection"]["established"],
                }
            else:
                j[v["name"]] = None

        return j
    else:
        return None

def getNode_ID():
    if 'node_id' in aliases["nodeinfo"]:
        return aliases["nodeinfo"]["node_id"]
    else:
        return getDevice_MAC(config["batman"]).replace(':','')

def getStationDump(dev_list):
    j = {}
    for dev in dev_list:
        try:
            # iw dev ibss3 station dump
            output = subprocess.check_output(["iw","dev",dev,"station", "dump"], stderr=STDOUT)
            output_utf8 = output.decode("utf-8")
            lines = output_utf8.splitlines()

            mac=""
            for line in lines:
                # Station 32:b8:c3:86:3e:e8 (on ibss3)
                ml = re.match('^Station ([0-9a-f:]+) \(on ([\w\d]+)\)', line, re.I)
                if ml:
                    mac = ml.group(1)
                    j[mac] = {}
                else:
                    ml = re.match('^[\t ]+([^:]+):[\t ]+([^ ]+)', line, re.I)
                    if ml:
                        j[mac][ml.group(1)] = ml.group(2)
        except:
            pass
    return j

def getNeighbours():
# https://github.com/freifunk-gluon/packages/blob/master/net/respondd/src/respondd.c
    j = { "batadv": {}}
    stationDump = None
    if 'mesh-wlan' in config:
        j["wifi"] = {}
        stationDump = getStationDump(config["mesh-wlan"])

    mesh_ifs = getMesh_Interfaces()
    with open("/sys/kernel/debug/batman_adv/" + config['batman'] + "/originators", 'r') as fh:
        for line in fh:
            #62:e7:27:cd:57:78 0.496s   (192) de:ad:be:ef:01:01 [  mesh-vpn]: de:ad:be:ef:01:01 (192) de:ad:be:ef:02:01 (148) de:ad:be:ef:03:01 (148)
            ml = re.match(r"^([0-9a-f:]+)[ ]*([\d\.]*)s[ ]*\(([ ]*\d*)\)[ ]*([0-9a-f:]+)[ ]*\[[ ]*(.*)\]", line, re.I)

            if ml:
                dev = ml.group(5)
                mac_origin = ml.group(1)
                mac_nhop = ml.group(4)
                tq = ml.group(3)
                lastseen = ml.group(2)

                if mac_origin == mac_nhop:
                    if 'mesh-wlan' in config and dev in config["mesh-wlan"] and not stationDump is None:
                        if not mesh_ifs[dev] in j["wifi"]:
                            j["wifi"][mesh_ifs[dev]] = {}
                            j["wifi"][mesh_ifs[dev]]["neighbours"] = {}

                        if mac_origin in stationDump:
                            j["wifi"][mesh_ifs[dev]]["neighbours"][mac_origin] = {
                                "signal": stationDump[mac_origin]["signal"],
                                "noise": 0, # BUG: fehlt noch
                                "inactive": stationDump[mac_origin]["inactive time"],
                        }

                    if dev in mesh_ifs:
                        if not mesh_ifs[dev] in j["batadv"]:
                            j["batadv"][mesh_ifs[dev]] = {}
                            j["batadv"][mesh_ifs[dev]]["neighbours"] = {}

                        j["batadv"][mesh_ifs[dev]]["neighbours"][mac_origin] = {
                            "tq": int(tq),
                            "lastseen": float(lastseen),
                        }
    return j

def getCPUInfo():
    j = {}
    with open("/proc/cpuinfo", 'r') as fh:
        for line in fh:
            ml = re.match(r"^(.+?)[\t ]+:[\t ]+(.*)$", line, re.I)

            if ml:
                j[ml.group(1)] = ml.group(2)
    return j

# ======================== Output =========================
# =========================================================

def createNodeinfo():
    j = {
        "node_id": getNode_ID(),
        "hostname": socket.gethostname(),
        "network": {
            "addresses": getDevice_Addresses(config['bridge']),
            "mesh": {
                "bat0": {
                    "interfaces": getBat0_Interfaces(),
                },
            },
            "mac": getDevice_MAC(config["batman"]),
            "mesh_interfaces": list(getMesh_Interfaces().values()),
        },
        "software": {
            "firmware": {
                "base": call(['lsb_release','-is'])[0],
                "release": call(['lsb_release','-ds'])[0],
            },
            "batman-adv": {
                "version": open('/sys/module/batman_adv/version').read().strip(),
#                "compat": # /lib/gluon/mesh-batman-adv-core/compat
            },
            "fastd": {
                "version": call(['fastd','-v'])[0].split(' ')[1],
                "enabled": True,
            },
            "status-page": {
                "api": 0,
            },
            "autoupdater": {
#                "branch": "stable",
                "enabled": False,
            },
        },
        "hardware": {
            "model": getCPUInfo()["model name"],
            "nproc": int(call(['nproc'])[0]),
        },
#        "vpn": True,
        "owner": {},
        "system": {},
        "location": {},
    }
    return merge(j, aliases["nodeinfo"])

def createStatistics():
    j = {
        "node_id": getNode_ID(),
        "clients":  getClients(),
        "traffic": getTraffic(),
        "idletime": float(open('/proc/uptime').read().split(' ')[1]),
        "loadavg": float(open('/proc/loadavg').read().split(' ')[0]),
        "memory": getMemory(),
        "processes": dict(zip(('running', 'total'), map(int, open('/proc/loadavg').read().split(' ')[3].split('/')))),
        "uptime": float(open('/proc/uptime').read().split(' ')[0]),
        "mesh_vpn" : { # HopGlass-Server: node.flags.uplink = parsePeerGroup(_.get(n, 'statistics.mesh_vpn'))
            "groups": {
                "backbone": {
                    "peers": getMeshVPNPeers(),
                },
            },
        },
    }

    gateway = getGateway()
    if gateway != None:
        j["gateway"] = gateway
    
    return j

def createNeighbours():
#/sys/kernel/debug/batman_adv/bat0/originators
    j = {
        "node_id": getNode_ID(),
    }
    j = merge(j, getNeighbours())
    return j

def sendResponse(request, compress):
    json_data = {}

#https://github.com/freifunk-gluon/packages/blob/master/net/respondd/src/respondd.c
    if request == 'statistics':
        json_data[request] = createStatistics()
    elif request == 'nodeinfo':
        json_data[request] = createNodeinfo()
    elif request == 'neighbours':
        json_data[request] = createNeighbours()
    else:
        print("unknown command: " + request)
        return

    json_str = bytes(json.dumps(json_data, separators=(',', ':')), 'UTF-8')

    if compress:
        encoder = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15) # The data may be decompressed using zlib and many zlib bindings using -15 as the window size parameter.
        gzip_data = encoder.compress(json_str)
        gzip_data = gzip_data + encoder.flush()
        sock.sendto(gzip_data, sender)
    else:
        sock.sendto(json_str, sender)

    if options["verbose"]:
        print(json.dumps(json_data, sort_keys=True, indent=4))

# ===================== Mainfunction ======================
# =========================================================

parser = argparse.ArgumentParser()

parser.add_argument( '-d', '--debug', action='store_true', help='Debug Output',required=False,)
parser.add_argument( '-v', '--verbose', action='store_true', help='Verbose Output',required=False)

args = parser.parse_args()
options = vars(args)

config = {}
try:
    with open("config.json", 'r') as cfg_handle:
        config = json.load(cfg_handle)
except IOError:
    raise

aliases = {}
try:
    with open("alias.json", 'r') as cfg_handle:
        aliases = json.load(cfg_handle)
except IOError:
    raise

if options["debug"]:
    print(json.dumps(createNodeinfo(), sort_keys=True, indent=4))
    print(json.dumps(createStatistics(), sort_keys=True, indent=4))
    print(json.dumps(createNeighbours(), sort_keys=True, indent=4))
    #print(json.dumps(getFastd(config["fastd_socket"]), sort_keys=True, indent=4))
    #print(json.dumps(getMesh_VPN(), sort_keys=True, indent=4))
    sys.exit(1)


if 'addr' in config:
    addr = config['addr']
else:
    addr = 'ff02::2'

if 'addr' in config:
    port = config['port']
else:
    port = 1001

if_idx = socket.if_nametoindex(config["bridge"])
group = socket.inet_pton(socket.AF_INET6, addr) + struct.pack("I", if_idx)

sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, group)
sock.bind(('::', port))

# =========================================================

while True:
    if select.select([sock],[],[],1)[0]:
        msg, sender = sock.recvfrom(2048)
        if options["verbose"]:
          print(msg)

        msg_spl = str(msg, 'UTF-8').split(" ")

        if msg_spl[0] == 'GET': # multi_request
            for request in msg_spl[1:]:
                sendResponse(request, True)
        else: # single_request
            sendResponse(msg_spl[0], False)

