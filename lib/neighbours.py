#!/usr/bin/env python3

import subprocess
import re

from lib.respondd import Respondd
import lib.helper


class Neighbours(Respondd):
  def __init__(self, config):
    Respondd.__init__(self, config)

  def getStationDump(self, devList):
    j = {}

    for dev in devList:
      try:
        output = subprocess.check_output(["iw", "dev", dev, "station", "dump"])
        output_utf8 = output.decode("utf-8")
        lines = output_utf8.splitlines()

        mac = ""
        for line in lines:
          # Station 32:b8:c3:86:3e:e8 (on ibss3)
          ml = re.match(r"^Station ([0-9a-f:]+) \(on ([\w\d]+)\)", line, re.I)
          if ml:
            mac = ml.group(1)
            j[mac] = {}
          else:
            ml = re.match(r"^[\t ]+([^:]+):[\t ]+([^ ]+)", line, re.I)
            if ml:
              j[mac][ ml.group(1) ] = ml.group(2)
      except:
          pass
    return j

  def getMeshInterfaces(self, batmanDev):
    j = {}

    output = subprocess.check_output(["batctl", "-m", batmanDev, "if"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

    for line in lines:
      ml = re.match(r"^([^:]*)", line)
      dev = ml.group(1)
      j[dev] = lib.helper.getDevice_MAC(dev)

    return j

  def _get(self):
    j = {"batadv": {}}

    stationDump = None

    if 'mesh-wlan' in self._config:
      j["wifi"] = {}
      stationDump = self.getStationDump(self._config["mesh-wlan"])

    meshInterfaces = self.getMeshInterfaces(self._config['batman'])

    output = subprocess.check_output(["batctl", "-m", self._config['batman'], "o", "-n"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

    for line in lines:
      # * e2:ad:db:b7:66:63    2.712s   (175) be:b7:25:4f:8f:96 [mesh-vpn-l2tp-1]
      ml = re.match(r"^[ \*\t]*([0-9a-f:]+)[ ]*([\d\.]*)s[ ]*\(([ ]*\d*)\)[ ]*([0-9a-f:]+)[ ]*\[[ ]*(.*)\]", line, re.I)

      if ml:
        dev = ml.group(5)
        macOrigin = ml.group(1)
        macNexthop = ml.group(4)
        tq = ml.group(3)
        lastseen = ml.group(2)

        if macOrigin == macNexthop:
          if 'mesh-wlan' in self._config and dev in self._config["mesh-wlan"] and not stationDump is None:
            if not meshInterfaces[dev] in j["wifi"]:
              j["wifi"][ meshInterfaces[dev] ] = {}
              j["wifi"][ meshInterfaces[dev] ]["neighbours"] = {}

            if macOrigin in stationDump:
              j["wifi"][ meshInterfaces[dev] ]["neighbours"][macOrigin] = {
                "signal": stationDump[macOrigin]["signal"],
                "noise": 0, # TODO: fehlt noch
                "inactive": stationDump[macOrigin]["inactive time"]
              }

          if dev in meshInterfaces:
            if not meshInterfaces[dev] in j["batadv"]:
              j["batadv"][ meshInterfaces[dev] ] = {}
              j["batadv"][ meshInterfaces[dev] ]["neighbours"] = {}

            j["batadv"][ meshInterfaces[dev] ]["neighbours"][macOrigin] = {
              "tq": int(tq),
              "lastseen": float(lastseen)
            }

    return j

