#!/usr/bin/env python3

import subprocess
import re

from lib.respondd import Respondd
import lib.helper


class Neighbours(Respondd):
  def __init__(self, config):
    Respondd.__init__(self, config)

  def getStationDump(self, dev_list):
    j = {}
    for dev in dev_list:
      try:
        # iw dev ibss3 station dump
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
              j[mac][ml.group(1)] = ml.group(2)
      except:
          pass
    return j

  def getMesh_Interfaces(self):
    j = {}
    output = subprocess.check_output(["batctl", "-m", self._config['batman'], "if"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

    for line in lines:
      dev_re = re.match(r"^([^:]*)", line)
      dev = dev_re.group(1)
      j[dev] = lib.helper.getDevice_MAC(dev)

    return j

  def _get(self):
    j = {"batadv": {}}
    stationDump = None
    if 'mesh-wlan' in self._config:
      j["wifi"] = {}
      stationDump = self.getStationDump(self._config["mesh-wlan"])

    mesh_ifs = self.getMesh_Interfaces()

    output = subprocess.check_output(["batctl", "-m", self._config['batman'], "o", "-n"])
    output_utf8 = output.decode("utf-8")
    lines = output_utf8.splitlines()

    for line in lines:
      # * e2:ad:db:b7:66:63    2.712s   (175) be:b7:25:4f:8f:96 [mesh-vpn-l2tp-1]
      ml = re.match(r"^[ \*\t]*([0-9a-f:]+)[ ]*([\d\.]*)s[ ]*\(([ ]*\d*)\)[ ]*([0-9a-f:]+)[ ]*\[[ ]*(.*)\]", line, re.I)

      if ml:
        dev = ml.group(5)
        mac_origin = ml.group(1)
        mac_nhop = ml.group(4)
        tq = ml.group(3)
        lastseen = ml.group(2)

        if mac_origin == mac_nhop:
          if 'mesh-wlan' in self._config and dev in self._config["mesh-wlan"] and not stationDump is None:
            if not mesh_ifs[dev] in j["wifi"]:
              j["wifi"][mesh_ifs[dev]] = {}
              j["wifi"][mesh_ifs[dev]]["neighbours"] = {}

            if mac_origin in stationDump:
              j["wifi"][mesh_ifs[dev]]["neighbours"][mac_origin] = {
                "signal": stationDump[mac_origin]["signal"],
                "noise": 0, # TODO: fehlt noch
                "inactive": stationDump[mac_origin]["inactive time"]
              }

          if dev in mesh_ifs:
            if not mesh_ifs[dev] in j["batadv"]:
              j["batadv"][mesh_ifs[dev]] = {}
              j["batadv"][mesh_ifs[dev]]["neighbours"] = {}

            j["batadv"][mesh_ifs[dev]]["neighbours"][mac_origin] = {
              "tq": int(tq),
              "lastseen": float(lastseen)
            }
    return j

