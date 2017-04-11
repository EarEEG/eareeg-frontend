#!/usr/bin/env python


from bottle import Bottle
from bottle.ext.websocket import websocket, GeventWebSocketServer

from utils import get_data_path

import json
import os


app = Bottle()


@app.get('/ws/run', apply=[websocket])
def run(ws):
	"""Recieves command to start recording from a device"""
	connection = True

	while connection:
		message = ws.receive()
		rv = {}
		if message is not None:
			print "message is not none", message

		ws.send(json.dumps(rv))


@app.get('/ws/fetch', apply=[websocket])
def fetch(ws):
	"""Receives request for either replayed or simulation data."""
	connection = True

	while connection:
		message = ws.receive()
		rv = {}
		rv['devices'] = {}
		if message is not None:
			query = json.loads(message)
			run_id = str(query['id'])
			devices = query['devices']
			for device in devices:
				print device
				data_path = os.path.join('assets', 'data', run_id, device + ".txt")
				print data_path

				try:
					with open(data_path, "r") as f:
						data = []
						for line in f:
							fields = line.strip().split()
							if fields[0] == "poorSignal":
								data.append({})
							data[len(data) - 1][fields[0]] = fields[1]
						rv['devices'][device] = data;
				except:
					rv['error'] = 'Data not found'

				ws.send(json.dumps(rv))


@app.get('/ws/init', apply=[websocket])
def ws_init(ws):
	"""Find requested simulation data and return Sysparam and Sysname, else return error."""
	connection = True

	while connection:
		message = ws.receive()
		rv = {}
		if message is not None:
			query = json.loads(message)
			run_id = str(query['run'])
			#path = data_dir
			#run_path = os.path.join(path, run_id)
			#sys_path = os.path.join(run_path, 'config.json')

			path = os.path.join('assets', 'data', run_id, 'config.json')
			# Find simulation and return Sysparam and Sysname
			if os.path.exists(path):
				try:
					with open(path, 'r') as f:
						rv['config'] = json.loads(f.read())
				except:
					rv['error'] = "No Config found"

			# Send through websocket whether requested sim is running
			# Find way to tell this
			else:
				if False:
					rv['Status'] = "Simulation running"
				else:
					rv['error'] = "Simulation not running"
			ws.send(json.dumps(rv))

		else:  # message is None
			connection = False

if __name__ == "__main__":
	data_dir = get_data_path()
	app.run(host='cepsltb7.curent.utk.edu', port='9121', server=GeventWebSocketServer)
