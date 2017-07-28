#!/usr/bin/env python3

import socket
import select
import struct
import json
import time
import re

import lib.helper

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

  @staticmethod
  def joinMCAST(sock, addr, ifname):
    group = socket.inet_pton(socket.AF_INET6, addr)
    if_idx = socket.if_nametoindex(ifname)
    sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, group + struct.pack('I', if_idx))

  def start(self):
    self._sock.bind(('::', self._config['port']))

    lines = lib.helper.call(['batctl', '-m', self._config['batman'], 'if'])
    for line in lines:
      lineMatch = re.match(r'^([^:]*)', line)
      self.joinMCAST(self._sock, self._config['addr'], lineMatch.group(1))

    self.joinMCAST(self._sock, self._config['addr'], self._config['bridge'])

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

    tStart = time.time()

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
        self._sock.sendto(responseClass.getJSON(), destAddress)

    if self._config['verbose'] or self._config['dry_run']:
      print('%14.3f %35s %5d %13s %5.3f: ' % (tStart, destAddress[0], destAddress[1], responseType, time.time() - tStart), end='')
      print(json.dumps(responseClass.getStruct(responseType), sort_keys=True, indent=4))

