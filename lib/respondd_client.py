#!/usr/bin/env python3

import socket
import select
import struct
import json

from lib.ratelimit import rateLimit
from lib.nodeinfo import Nodeinfo
from lib.neighbours import Neighbours
from lib.statistics import Statistics

class ResponddClient:
  def __init__(self, config):
    self._config = config

    if 'rate_limit' in self._config:
      if 'rate_limit_burst' not in self._config:
        self._config['rate_limit_burst'] = 10
      self.__RateLimit = rateLimit(self._config['rate_limit'], self._config['rate_limit_burst'])
    else:
      self.__RateLimit = None

    self._nodeinfo = Nodeinfo(self._config)
    self._neighbours = Neighbours(self._config)
    self._statistics = Statistics(self._config)

    self._sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)

  def start(self):
    if_idx = socket.if_nametoindex(self._config['bridge'])
    group = socket.inet_pton(socket.AF_INET6, self._config['addr']) + struct.pack('I', if_idx)
    self._sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, group)

    self._sock.bind(('::', self._config['port']))

    while True:
      msg, sourceAddress = self._sock.recvfrom(2048)

      msgSplit = str(msg, 'UTF-8').split(' ')

      if msgSplit[0] == 'GET': # multi_request
        for request in msgSplit[1:]:
          self.sendResponse(sourceAddress, request, True)
      else: # single_request
        self.sendResponse(sourceAddress, msgSplit[0], False)

  def sendResponse(self, destAddress, responseType, withCompression):
    if self.__RateLimit is not None and not self.__RateLimit.limit():
      print('rate limit reached!')
      return

    responseClass = None
    if responseType == 'statistics':
      responseClass = self._statistics
    elif responseType == 'nodeinfo':
      responseClass = self._nodeinfo
    elif responseType == 'neighbours':
      responseClass = self._neighbours
    else:
      print('unknown command: ' + responseType)
      return

    if not self._config['dry_run']:
      if withCompression:
        self._sock.sendto(responseClass.getJSONCompressed(responseType), destAddress)
      else:
        self._sock.sendto(responseClass.getJSON(responseType), destAddress)

    if self._config['verbose'] or self._config['dry_run']:
      print('%35s %5d %13s: ' % (destAddress[0], destAddress[1], responseType), end='')
      print(json.dumps(responseClass.getStruct(responseType), sort_keys=True, indent=4))

