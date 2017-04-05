#!/usr/bin/env python


from bottle import Bottle
from bottle.ext.websocket import websocket, GeventWebSocketServer

from utils import get_data_path

import json
import os


app = Bottle()


@app.get('/ws/fetch', apply=[websocket])
def fetch(ws):
	"""Receives request for either replayed or simulation data."""
	connection = True

	while connection:
		message = ws.receive()
		rv = {}
		if message is not None:
			query = json.loads(message)
			run_id = str(query['id'])
			device_id = str(query['device'])
			time = str(query['time'])
			path = data_dir
			run_path = os.path.join(path, run_id)
			device_path = os.path.join(run_path, device_id)
			data_path = os.path.join(device_path, time + ".json")

			try:
				with open(data_path, "r") as f:
					data = json.load(f)
					rv['data'] = data
			except:
				rv['error'] = 'Data not found'

			ws.send(json.dumps(rv))


@app.get('/ws/load', apply=[websocket])
def ws_init(ws):
	"""Find requested simulation data and return Sysparam and Sysname, else return error."""
	connection = True

	print "ws_init"
	while connection:
		message = ws.receive()
		rv = {}
		if message is not None:
			query = json.loads(message)
			run_id = str(query['id'])
			path = data_dir
			run_path = os.path.join(path, run_id)
			sys_path = os.path.join(run_path, 'config.json')

			# Find simulation and return Sysparam and Sysname
			if os.path.exists(sys_path):
				try:
					with open(sys_path, 'r') as param_fp:
						rv['config'] = json.loads(param_fp.read())
				except:
					rv['error'] = "No Config found"

			# Send through websocket whether requested sim is running
			# Find way to tell this
			else:
				if True:
					rv['Status'] = "Simulation running"
				else:
					rv['error'] = "Simulation not running"
			ws.send(json.dumps(rv))

		else:  # message is None
			connection = False

if __name__ == "__main__":
	data_dir = get_data_path()
	app.run(host='cepsltb7.curent.utk.edu', port='9121', server=GeventWebSocketServer)
