#!/usr/bin/env python3

import json
import zlib

import lib.helper

class Respondd:
  def __init__(self, config):
    self._config = config
    self._aliasOverlay = {}
    try:
      with open('alias.json', 'r') as fh: # TODO: prevent loading more then once !
        self._aliasOverlay = json.load(fh)
    except IOError:
      print('can\'t load alias.json!')
      pass

  def getNodeID(self):
    if 'nodeinfo' in self._aliasOverlay and 'node_id' in self._aliasOverlay['nodeinfo']:
      return self._aliasOverlay['nodeinfo']['node_id']
    else:
      return lib.helper.getInterfaceMAC(self._config['batman']).replace(':', '')

  def getStruct(self, rootName=None):
    ret = self._get()
    ret['node_id'] = self.getNodeID()
    if rootName is not None:
      ret_tmp = ret
      ret = {}
      ret[rootName] = ret_tmp
    return ret

  def getJSON(self, rootName=None):
    return bytes(json.dumps(self.getStruct(rootName), separators=(',', ':')), 'UTF-8')

  def getJSONCompressed(self, rootName=None):
    return self.compress(self.getJSON(rootName))

  @staticmethod
  def compress(data):
    encoder = zlib.compressobj(zlib.Z_DEFAULT_COMPRESSION, zlib.DEFLATED, -15) # The data may be decompressed using zlib and many zlib bindings using -15 as the window size parameter.
    dataGzip = encoder.compress(data)
    dataGzip += encoder.flush()
    return dataGzip

  @staticmethod
  def _get():
    return {}

