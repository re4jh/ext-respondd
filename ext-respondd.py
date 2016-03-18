#!/usr/bin/env python3

# Code-Base: https://github.com/ffggrz/ffnord-alfred-announce
#          + https://github.com/freifunk-mwu/ffnord-alfred-announce
#          + https://github.com/FreifunkBremen/respondd

import json
import socket
import subprocess
import re
import netifaces as netif
from cpuinfo import cpuinfo

# Force encoding to UTF-8
import locale                                         # Ensures that subsequent open()s
locale.getpreferredencoding = lambda _=None: 'UTF-8'  # are UTF-8 encoded.

import sys

import struct
import select
import zlib

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

def getGateway(batadv_dev):
#/sys/kernel/debug/batman_adv/bat0/gateways
    output = subprocess.check_output(["batctl","-m",batadv_dev,"gwl","-n"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()
    gw = None

    for line in lines:
        gw_line = re.match(r"^=> +([0-9a-f:]+) ", line)
        if gw_line:
            gw = gw_line.group(1)

    return gw

def getClients(batadv_dev):
#/sys/kernel/debug/batman_adv/bat0/transtable_local
    output = subprocess.check_output(["batctl","-m",batadv_dev,"tl","-n"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

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
            j["total"] += 1
            if ml.group(2)[4] == 'W':
                j["wifi"] += 1

    return j

def getAddresses(bridge_dev):
    ip_addrs = netif.ifaddresses(bridge_dev)
    ip_list = []

    try:
        for ip6 in netif.ifaddresses(bridge_dev)[netif.AF_INET6]:
            raw6 = ip6['addr'].split('%')
            ip_list.append(raw6[0])
    except:
        pass

    return ip_list

def getMac_mesh(fastd_dev,meshmode=False):
    interface = netif.ifaddresses(fastd_dev)
    mesh = []
    mac = None

    try:
        mac = interface[netif.AF_LINK]
        mesh.append(mac[0]['addr'])
    except:
        KeyError

    if meshmode:
        return mesh
    else:
        return mac[0]['addr']

def getMesh_interfaces(batadv_dev):
    output = subprocess.check_output(["batctl","-m",batadv_dev,"if"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()
    mesh = []

    for line in lines:
        dev_line = re.match(r"^([^:]*)", line)
        interface = netif.ifaddresses(dev_line.group(0))
        mac = interface[netif.AF_LINK]
        mesh.append(mac[0]['addr'])

    return mesh

def getBat0_mesh(batadv_dev):
    output = subprocess.check_output(["batctl","-m",batadv_dev,"if"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()
    j = {"tunnel" : []}

    for line in lines:
        dev_line = re.match(r"^([^:]*)", line)
        nif = dev_line.group(0)
        interface = netif.ifaddresses(nif)
        mac = interface[netif.AF_LINK]
        j["tunnel"].append(mac[0]['addr'])

    return j

def getTraffic(batadv_dev):
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
        for key, value in map(lambda s: list(map(str.strip, s.split(': ', 1))), call(['ethtool', '-S', batadv_dev])[1:])
    ))

def getMemory():
    return dict(
        (key.replace('Mem', '').lower(), int(value.split(' ')[0]))
        for key, value in map(lambda s: map(str.strip, s.split(': ', 1)), open('/proc/meminfo').readlines())
        if key in ('MemTotal', 'MemFree', 'Buffers', 'Cached')
    )

def getFastd(fastd_socket): # Unused
    fastd_data = b""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(fastd_socket)
    except socket.error as err:
        print("socket error: ", sys.stderr, err)
        sys.exit(1)

    while True:
        data = sock.recv(1024)
        if not data: break
        fastd_data+= data

    sock.close()
    return json.loads(fastd_data.decode("utf-8"))

def getNode_id(dev):
    if 'node_id' in aliases["nodeinfo"]:
        return aliases["nodeinfo"]["node_id"]
    else:
        return mac_mesh(dev).replace(':','')

def getNeighbours():
# https://github.com/freifunk-gluon/packages/blob/master/net/respondd/src/respondd.c
# wenn Originators.mac == next_hop.mac dann
    j = {}
    with open("/sys/kernel/debug/batman_adv/" + batadv_dev + "/originators", 'r') as fh:
        for line in fh:
            #62:e7:27:cd:57:78 0.496s   (192) de:ad:be:ef:01:01 [  mesh-vpn]: de:ad:be:ef:01:01 (192) de:ad:be:ef:02:01 (148) de:ad:be:ef:03:01 (148)
            ml = re.match(r"^([0-9a-f:]+)[ ]*([\d\.]*)s[ ]*\((\d*)\)[ ]*([0-9a-f:]+)[ ]*\[[ ]*(.*)\]", line, re.I)
            if ml:
                if ml.group(1) == ml.group(4):
                    j[ml.group(1)] = {
                        "tq": int(ml.group(3)),
                        "lastseen": float(ml.group(2)),
                    }
    return j

# ======================== Output =========================
# =========================================================

def createNodeinfo():
    j = {
        "node_id": getNode_id(fastd_dev),
        "hostname": socket.gethostname(),
        "network": {
            "addresses": getAddresses(bridge_dev),
            "mesh": {
                "bat0": {
                    "interfaces": getBat0_mesh(batadv_dev),
                },
            },
            "mac": getMac_mesh(fastd_dev),
            "mesh_interfaces": getMesh_interfaces(batadv_dev),
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
            "model": cpuinfo.get_cpu_info()["brand"],
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
        "node_id": getNode_id(fastd_dev),
        "gateway" : getGateway(batadv_dev), # BUG: wenn man ein Gateway ist, was soll man dann hier senden?
        "clients":  getClients(batadv_dev),
        "traffic": getTraffic(batadv_dev),
        "idletime": float(open('/proc/uptime').read().split(' ')[1]),
        "loadavg": float(open('/proc/loadavg').read().split(' ')[0]),
        "memory": getMemory(),
        "processes": dict(zip(('running', 'total'), map(int, open('/proc/loadavg').read().split(' ')[3].split('/')))),
        "uptime": float(open('/proc/uptime').read().split(' ')[0]),
#        "mesh_vpn": { # getFastd
#            "groups": {
#                "backbone": {
#                    "peers": {
#                        "vpn1": None,
#                        "vpn2": {
#                            "established": 1000,
#                        },
#                        "vpn3": None,
#                    },
#                },
#            },
#        },
    }
    return j


def createNeighbours():
#/sys/kernel/debug/batman_adv/bat0/originators

    j = {
        "node_id": getNode_id(fastd_dev),
        "batadv": { # Testing
            getMac_mesh(fastd_dev): {
                "neighbours": getNeighbours(),
            },
            #"wifi": {},
        },
    }
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

    print(json.dumps(json_data, sort_keys=True, indent=4))

# ===================== Mainfunction ======================
# =========================================================

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


batadv_dev = config['batman']
fastd_dev  = config['fastd']
bridge_dev = config['bridge']

#print(json.dumps(getFastd(config["fastd_socket"]), sort_keys=True, indent=4))
#print(json.dumps(createNodeinfo(), sort_keys=True, indent=4))
#print(json.dumps(createStatistics(), sort_keys=True, indent=4))
#print(json.dumps(createNeighbours(), sort_keys=True, indent=4))
#print(merge(createNodeinfo(), aliases["nodeinfo"]))
#print(createStatistics())
#sys.exit(1)


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
        msg, sender = sock.recvfrom(2048) # buffer > mtu !?!? -> egal, da eh nur ein GET kommt welches kleiner ist als 1024 ist
#        try:
#            msg = zlib.decompress(msg, -15) # The data may be decompressed using zlib and many zlib bindings using -15 as the window size parameter.
#        except zlib.error:
#            pass
        print(msg)

        msg_spl = str(msg, 'UTF-8').split(" ")

        # BUG: Es koennen auch Anfragen wie "GET statistics nodeinfo" existieren (laut gluon doku)
        if msg_spl[0] == 'GET': # multi_request
            for request in msg_spl[1:]:
                sendResponse(request, True)
        else: # single_request
            sendResponse(msg_spl[0], False)

