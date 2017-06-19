#!/usr/bin/env python3

import socket
import netifaces as netif
import subprocess
import re

from lib.respondd import Respondd
import lib.helper


class Nodeinfo(Respondd):
  def __init__(self, config):
    Respondd.__init__(self, config)

  def getDevice_Addresses(self, dev):
    l = []
    try:
      for ip6 in netif.ifaddresses(dev)[netif.AF_INET6]:
        raw6 = ip6['addr'].split('%')
        l.append(raw6[0])

      for ip in netif.ifaddresses(dev)[netif.AF_INET]:
        raw = ip['addr'].split('%')
        l.append(raw[0])
    except:
      pass

    return l

  def getBat0_Interfaces(self):
    j = {}
    output = subprocess.check_output(["batctl", "-m", self._config['batman'], "if"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

    for line in lines:
      dev_line = re.match(r"^([^:]*)", line)
      nif = dev_line.group(0)

      if_group = ""
      if "fastd" in self._config and nif == self._config["fastd"]: # keep for compatibility
        if_group = "tunnel"
      elif nif.find("l2tp") != -1:
        if_group = "l2tp"
      elif "mesh-vpn" in self._config and nif in self._config["mesh-vpn"]:
        if_group = "tunnel"
      elif "mesh-wlan" in self._config and nif in self._config["mesh-wlan"]:
        if_group = "wireless"
      else:
        if_group = "other"

      if not if_group in j:
        j[if_group] = []

      j[if_group].append(lib.helper.getDevice_MAC(nif))

    if "l2tp" in j:
      if "tunnel" in j:
        j["tunnel"] = j["tunnel"] + j["l2tp"]
      else:
        j["tunnel"] = j["l2tp"]

    return j

  def getCPUInfo(self):
    j = {}
    with open("/proc/cpuinfo", 'r') as fh:
      for line in fh:
        ml = re.match(r"^(.+?)[\t ]+:[\t ]+(.*)$", line, re.I)

        if ml:
          j[ml.group(1)] = ml.group(2)
    return j

  def _get(self):
    j = {
      "hostname": socket.gethostname(),
      "network": {
        "addresses": self.getDevice_Addresses(self._config['bridge']),
        "mesh": {
          "bat0": {
            "interfaces": self.getBat0_Interfaces()
          }
        },
        "mac": lib.helper.getDevice_MAC(self._config["batman"])
      },
      "software": {
        "firmware": {
          "base": lib.helper.call(['lsb_release', '-is'])[0],
          "release": lib.helper.call(['lsb_release', '-ds'])[0]
        },
        "batman-adv": {
          "version": open('/sys/module/batman_adv/version').read().strip(),
#                "compat": # /lib/gluon/mesh-batman-adv-core/compat
        },
        "status-page": {
          "api": 0
        },
        "autoupdater": {
          "enabled": False
        }
      },
      "hardware": {
        "model": self.getCPUInfo()["model name"],
        "nproc": int(lib.helper.call(['nproc'])[0])
      },
      "owner": {},
      "system": {},
      "location": {}
    }

    if 'mesh-vpn' in self._config and len(self._config["mesh-vpn"]) > 0:
      try:
        j["software"]["fastd"] = {
          "version": lib.helper.call(['fastd', '-v'])[0].split(' ')[1],
          "enabled": True
        }
      except:
        pass
    return lib.helper.merge(j, self._aliases["nodeinfo"])


