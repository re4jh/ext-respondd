#!/usr/bin/env python3

import socket
#import netifaces as netif
import subprocess
import re

from lib.respondd import Respondd
import lib.helper


class Statistics(Respondd):
  def __init__(self, config):
    Respondd.__init__(self, config)

  def getClients(self):
    j = {"total": 0, "wifi": 0}

    batmanMAC = lib.helper.getDevice_MAC(self._config['batman'])

    output = subprocess.check_output(["batctl", "-m", self._config['batman'], "tl", "-n"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

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
        if not batmanMAC == ml.group(1): # Filter bat0
          if not ml.group(1).startswith('33:33:') and not ml.group(1).startswith('01:00:5e:'): # Filter Multicast
            j["total"] += 1
            if ml.group(2)[4] == 'W':
              j["wifi"] += 1

    return j

  def getTraffic(self): # TODO: design rework needed!
    return (lambda fields: dict(
      (key, dict(
        (type_, int(value_))
        for key_, type_, value_ in fields
        if key_ == key))
      for key in ['rx', 'tx', 'forward', 'mgmt_rx', 'mgmt_tx']
  ))(list(
      (
        key.replace('_bytes', '').replace('_dropped', ''),
        'bytes' if key.endswith('_bytes') else 'dropped' if key.endswith('_dropped') else 'packets',
        value
      )
      for key, value in map(lambda s: list(map(str.strip, s.split(': ', 1))), lib.helper.call(['ethtool', '-S', self._config['batman']])[1:])
    ))

  def getMemory(self): # TODO: design rework needed!
    return dict(
      (key.replace('Mem', '').lower(), int(value.split(' ')[0]))
      for key, value in map(lambda s: map(str.strip, s.split(': ', 1)), open('/proc/meminfo').readlines())
      if key in ('MemTotal', 'MemFree', 'Buffers', 'Cached')
    )

  def getFastd(self):
    dataFastd = b""

    try:
      sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
      sock.connect(config["fastd_socket"])
    except socket.error as err:
      print("socket error: ", sys.stderr, err)
      return None

    while True:
      data = sock.recv(1024)
      if not data:
        break
      dataFastd += data

    sock.close()
    return json.loads(dataFastd.decode("utf-8"))

  def getMeshVPNPeers(self):
    j = {}

    if "fastd_socket" in self._config:
      fastd = self.getFastd()
      for peer in fastd["peers"].values():
        if peer["connection"]:
          j[peer["name"]] = {
            "established": peer["connection"]["established"]
          }
        else:
          j[peer["name"]] = None

      return j
    else:
      return None

  def getGateway(self):
    j = None

    output = subprocess.check_output(["batctl", "-m", self._config['batman'], "gwl", "-n"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

    for line in lines:
      gw_line = re.match(r"^(\*|=>) +([0-9a-f:]+) \([\d ]+\) ([0-9a-f:]+)", line)
      if gw_line:
        j = {}
        j["gateway"] = gw_line.group(2)
        j["gateway_nexthop"] = gw_line.group(3)

    return j

  def _get(self):
    j = {
      "clients":  self.getClients(),
      "traffic": self.getTraffic(),
      "idletime": float(open('/proc/uptime').read().split(' ')[1]),
      "loadavg": float(open('/proc/loadavg').read().split(' ')[0]),
      "memory": self.getMemory(),
      "processes": dict(zip(('running', 'total'), map(int, open('/proc/loadavg').read().split(' ')[3].split('/')))),
      "uptime": float(open('/proc/uptime').read().split(' ')[0]),
      "mesh_vpn" : { # HopGlass-Server: node.flags.uplink = parsePeerGroup(_.get(n, 'statistics.mesh_vpn'))
        "groups": {
          "backbone": {
            "peers": self.getMeshVPNPeers()
          }
        }
      }
    }

    gateway = self.getGateway()
    if gateway != None:
      j = lib.helper.merge(j, gateway)

    return j

