#!/usr/bin/env python3

import json
import zlib

import lib.helper

class Respondd:
  def __init__(self, config):
    self._config = config
    self._aliases = {}
    try:
      with open("alias.json", 'r') as cfg_handle:
        self._aliases = json.load(cfg_handle)
    except IOError:
      raise
      pass

  def getNode_ID(self):
    if 'node_id' in self._aliases["nodeinfo"]:
      return self._aliases["nodeinfo"]["node_id"]
    else:
      return lib.helper.getDevice_MAC(self._config["batman"]).replace(':', '')

  def getJSON(self, root=None):
    print(root)
    j = self.get()
    j['node_id'] = self.getNode_ID()
    if not root is None:
      j_tmp = j
      j = {}
      j[root] = j_tmp
    return bytes(json.dumps(j, separators=(',', ':')), 'UTF-8')

  def getJSONCompressed(self, root=None):
    return self.compress(self.getJSON(root))

  def compress(self, data):
    encoder = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15) # The data may be decompressed using zlib and many zlib bindings using -15 as the window size parameter.
    gzip_data = encoder.compress(data)
    gzip_data = gzip_data + encoder.flush()
    return gzip_data

  def get(self):
    return {}
  pass
