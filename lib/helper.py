#!/usr/bin/env python3

import netifaces as netif
import subprocess

def toUTF8(line):
    return line.decode("utf-8")

def call(cmdnargs):
    output = subprocess.check_output(cmdnargs)
    lines = output.splitlines()
    lines = [toUTF8(line) for line in lines]
    return lines

def merge(a, b):
  if isinstance(a, dict) and isinstance(b, dict):
    d = dict(a)
    d.update({k: merge(a.get(k, None), b[k]) for k in b})
    return d

  if isinstance(a, list) and isinstance(b, list):
    return [merge(x, y) for x, y in itertools.izip_longest(a, b)]

  return a if b is None else b

def getDevice_MAC(dev):
  try:
    interface = netif.ifaddresses(dev)
    mac = interface[netif.AF_LINK]
    return mac[0]['addr']
  except:
    return None
