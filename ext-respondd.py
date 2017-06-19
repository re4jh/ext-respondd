#!/usr/bin/env python3

import json


from lib.respondd_client import ResponddClient


config = {}
try:
    with open("config.json", 'r') as cfg_handle:
        config = json.load(cfg_handle)
except IOError:
    raise

extResponddClient = ResponddClient(config)
extResponddClient.start()

