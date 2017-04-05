#!/usr/bin/env python

from multiprocessing import Process, Pipe
from bottle import Bottle
from bottle.ext.websocket import websocket, GeventWebSocketServer

from utils import get_data_path, get_run_path, get_log

import json
import os
import socket
import time

import DataServer
import memcache


app = Bottle()
log = get_log('bottle')


@app.get('/ws/fetch', apply=[websocket])
def fetch(ws):
	"""Receives request for either replayed or simulation data."""
	prefetch_set = False
	connection = True
	process_list = []
	parent_conn = None
	mc = memcache.Client(['localhost:11211'], debug=0)
	DS = DataServer.DataServer(5, True, True)
	join_diff = 0

	while connection:
		message = ws.receive()
		if message is not None:
			total_time = time.time()
			query = json.loads(message)
			serial_time = time.time() - total_time

			if prefetch_set:
				# Kill prefetching
				parent_conn.send("quit")
				for i in range(len(process_list)):
					join_time = time.time()
					process_list[i].join()
					join_diff += time.time() - join_time
				prefetch_set = False
				process_list = []

			rv, prefetch_list = DS.parseQuery(query, mc, data_dir)

			# Check the length of the data array. If length is 0 and there is a file error,
			# Then check if the simulation is running. Else return remaining data.
			length = 0
			try:
				# Checks data if bus
				length = len(rv['data'][0][rv['data'][0].keys()[0]])
				# KeyError is for index 0 after 'data'
			except KeyError:
				try:
					# Checks data if component
					length = len(rv['data'][rv['data'].keys()[0]])
					# IndexErrors are for .keys()[0]
				except IndexError:
					pass
			except IndexError:
				pass

			log.debug("length: {}".format(length))
			if 'error' in rv and rv['error'] == "Error: file doesn't exist" and length is 0:
				path = os.path.join(run_dir, 'sim_list.sock')
				sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
				sock.connect(path)
				sim_id = str(query['dataset_name'])
				sim_list = json.loads(sock.recv(4096))
				if sim_id in sim_list:
					rv['Status'] = "Simulation running"
					rv['error'] = None
				else:
					rv['error'] = "Simulation not running"
			elif 'error' in rv and rv['error'] == "Error: file doesn't exist":
				rv.pop('error', None)

			# Return memcached stats
			stats = mc.get_stats()
			rv['mem_bytes'] = stats[0][1]['bytes']
			rv['mem_hits'] = stats[0][1]['get_hits']
			rv['mem_misses'] = stats[0][1]['get_misses']

			# Send back the data
			rv['original_message'] = query

			tmp_time = time.time()
			send_msg = json.dumps(rv)
			serial_time += time.time() - tmp_time

			tmp_time = time.time()
			ws.send(send_msg)
			network_time = time.time() - tmp_time

			log.debug("total: {}".format(time.time() - total_time))
			log.debug("join: {}".format(join_diff))
			log.debug("serial: {}".format(serial_time))
			log.debug("network: {}".format(network_time))
			log.debug("")

			# Prefetch after sending data
			# Prefetch[0]: Whether or not to prefetch
			# Prefetch[1]: Dataset
			# Prefetch[2]: Variable
			# Prefetch[3]: Bus_id
			# Prefetch[4]: Starting timestep for prefetching
			# Prefetch[5]: Number of buses
			# Prefetch[6]: Data type

			if prefetch_list[0]:
				prefetch_set = True
				parent_conn, child_conn = Pipe()
				process_list = []
				for i in range(10):
					buses_per_process = (prefetch_list[5] / 10) + 1
					proc = Process(target=DS.prefetch,
									args=(child_conn, prefetch_list[1],
										prefetch_list[2], prefetch_list[3],
										prefetch_list[4], buses_per_process,
										i * buses_per_process, data_dir, prefetch_list[6])
									)
					proc.start()
					process_list.append(proc)

		else:  # If message is None
			connection = False
			if prefetch_set:
				parent_conn.send("quit")
				for i in range(len(process_list)):
					process_list[i].join()
			prefetch_set = False
			break


@app.get('/ws/load', apply=[websocket])
def ws_init(ws):
	"""Find requested simulation data and return Sysparam and Sysname, else return error."""
	connection = True

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
	data_dir = "" #get_data_path()
	#run_dir = "" #get_run_path()
	app.run(host='localhost', port='9121', server=GeventWebSocketServer)
