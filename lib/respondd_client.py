#!/usr/bin/env python3

from lib.ratelimit import rateLimit
from lib.nodeinfo import Nodeinfo
from lib.neighbours import Neighbours
from lib.statistics import Statistics

import socket
import select
import struct

class ResponddClient:
  def __init__(self, config):
    self._config = config

    if 'addr' in self._config:
        addr = self._config['addr']
    else:
        addr = 'ff02::2:1001'

    if 'addr' in self._config:
        port = self._config['port']
    else:
        port = 1001

    if_idx = socket.if_nametoindex(self._config["bridge"])
    group = socket.inet_pton(socket.AF_INET6, addr) + struct.pack("I", if_idx)

    self._sock = socket.socket(socket.AF_INET6, socket.SOCK_DGRAM)
    self._sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_JOIN_GROUP, group)
    self._sock.bind(('::', port))

    if 'rate_limit' in self._config:
      if not 'rate_limit_burst' in self._config:
        self._config['rate_limit_burst'] = 10
      self.__RateLimit = rateLimit(self._config['rate_limit'], self._config['rate_limit_burst'])
    else:
      self.__RateLimit = None

    self._nodeinfo = Nodeinfo(self._config)
    self._neighbours = Neighbours(self._config)
    self._statistics = Statistics(self._config)

  def start(self):
    while True:
      if select.select([self._sock], [], [], 1)[0]:
        msg, sender = self._sock.recvfrom(2048)
#        if options["verbose"]:
#          print(msg)

        msg_spl = str(msg, 'UTF-8').split(" ")

        if msg_spl[0] == 'GET': # multi_request
          for req in msg_spl[1:]:
            self.sendResponse(sender, req, True)
        else: # single_request
          self.sendResponse(sender, msg_spl[0], False)

  def sendResponse(self, sender, request, compress):
    if not self.__RateLimit is None and not self.__RateLimit.limit():
      print("rate limit reached!")
      return

    response = None
    if request == 'statistics':
      response = self._statistics
    elif request == 'nodeinfo':
      response = self._nodeinfo
    elif request == 'neighbours':
      response = self._neighbours
    else:
      print("unknown command: " + request)
      return

    if compress:
      sock.sendto(response.getJSONCompressed(request), sender)
    else:
      sock.sendto(response.getJSON(request), sender)

#      if options["verbose"]:
#          print(json.dumps(json_data, sort_keys=True, indent=4))

