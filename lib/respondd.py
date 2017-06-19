#!/usr/bin/env python3

import json
import zlib

import lib.helper

class Respondd:
  def __init__(self, config):
    self._config = config
    self._aliasOverlay = {}
    try:
      with open("alias.json", 'r') as fh:
        self._aliasOverlay = json.load(fh)
    except IOError:
      raise
      pass

  def getNode_ID(self):
    if 'node_id' in self._aliasOverlay["nodeinfo"]:
      return self._aliasOverlay["nodeinfo"]["node_id"]
    else:
      return lib.helper.getDevice_MAC(self._config["batman"]).replace(':', '')

  def getStruct(self, rootName=None):
    j = self._get()
    j['node_id'] = self.getNode_ID()
    if not rootName is None:
      j_tmp = j
      j = {}
      j[rootName] = j_tmp
    return j

  def getJSON(self, rootName=None):
    return bytes(json.dumps(self.getStruct(rootName), separators=(',', ':')), 'UTF-8')

  def getJSONCompressed(self, rootName=None):
    return self.compress(self.getJSON(rootName))

  def compress(self, data):
    encoder = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15) # The data may be decompressed using zlib and many zlib bindings using -15 as the window size parameter.
    dataGzip = encoder.compress(data)
    dataGzip+= encoder.flush()
    return dataGzip

  def _get(self):
    return {}
  pass
