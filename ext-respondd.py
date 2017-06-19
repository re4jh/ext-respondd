#!/usr/bin/env python3

import json
import argparse
import sys


from lib.respondd_client import ResponddClient

parser = argparse.ArgumentParser()

parser.add_argument('-d', '--test', action='store_true', help='Test Output', required=False)
parser.add_argument('-v', '--verbose', action='store_true', help='Verbose Output', required=False)

args = parser.parse_args()
options = vars(args)

config = {}
try:
  with open("config.json", 'r') as cfg_handle:
    config = json.load(cfg_handle)
except IOError:
  raise

if options["test"]:
  from lib.nodeinfo import Nodeinfo
  from lib.statistics import Statistics
  from lib.neighbours import Neighbours
  print(json.dumps(Nodeinfo(config).getStruct(), sort_keys=True, indent=4))
  print(json.dumps(Statistics(config).getStruct(), sort_keys=True, indent=4))
  print(json.dumps(Neighbours(config).getStruct(), sort_keys=True, indent=4))
  sys.exit(1)

if options["vebose"]:
  config["verbose"] = True

extResponddClient = ResponddClient(config)
extResponddClient.start()

