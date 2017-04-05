from netCDF4 import Dataset
from utils import get_log

import logging
import os
import time

import memcache


log = logging.getLogger(__file__)
log.setLevel(logging.DEBUG)
handler = logging.FileHandler('log.txt')
handler.setFormatter(logging.Formatter(
	'%s(asctime)s - %(levelname)s - %(message)s'
))
log.addHandler(handler)

server_log = get_log('bottle')


def gen_cache_key(dataset, variable, bus_id, offset, data_type):
	"""Return a key for memcached."""
	return ':'.join(map(str, (dataset, variable, bus_id, offset, data_type)))


def check_query(query):
	bus_from = None
	bus_to = None

	if "component" in query and query["component"] is not None:
		component = query["component"]
	else:
		component = 'Bus'

	if "bus_ids" in query and query["bus_ids"] is not None and query["bus_ids"] > 0:
		num_buses = query["bus_ids"]
	else:
		raise Exception("No bus_ids")

	if "time_range" in query and query["time_range"] > 0:
		time_range = query["time_range"]
	else:
		raise Exception("No time_range")

	if "dataset_name" in query and query["dataset_name"] != "" and query["dataset_name"] is not None:
		dataset_name = str(query["dataset_name"])
	else:
		raise Exception("No dataset_name")

	if "variable" in query and query["variable"] is not None:
		variable_list = query["variable"]
	else:
		raise Exception("No variable")

	if "offset" in query and query["variable"] is not None:
		offset = query["offset"]
	else:
		raise Exception("No offset")

	if "type" in query and query["type"] is not None:
		data_type = query["type"]
	else:
		data_type = "vars"

	if component == 'Line':
		if 'from' in query and 'to' in query:
			bus_from = query['from']
			bus_to = query['to']

	return component, num_buses, time_range, dataset_name, variable_list, offset, data_type, bus_from, bus_to


def return_line(rv, data_dir, dataset_name, data_type, component, variable_list,
					num_buses, new_time, end_time, time_delta, bus_from, bus_to):
	rv['data'] = {}

	scan_time = new_time
	# Grab intermediate keys

	while True:

		for var in variable_list:

			data_path = os.path.join(str(data_dir), dataset_name, data_type, component, str(bus_from), str(bus_to), var,
									str(num_buses), 'time_' + str(scan_time) + '.nc')

			if not os.path.exists(data_path):
				rv["error"] = "Error: file doesn't exist"
				continue

			nc = Dataset(data_path, 'r')
			values = nc.variables['data'][:]
			nc.close()

			try:
				values = values.tolist()
			except AttributeError:
				pass

			if var not in rv['data']:
				rv['data'][var] = []

			rv['data'][var].extend(values)

		if (end_time - scan_time) <= 0:
			break

		scan_time = scan_time + time_delta
	return rv


def return_component(rv, data_dir, dataset_name, data_type, component, variable_list,
						num_buses, new_time, end_time, time_delta):
	rv['data'] = {}

	scan_time = new_time
	# Grab intermediate keys

	while True:

		for var in variable_list:

			data_path = os.path.join(str(data_dir), dataset_name, data_type,
									component, var, str(num_buses), 'time_' + str(scan_time) + '.nc')

			if not os.path.exists(data_path):
				rv["error"] = "Error: file doesn't exist"
				continue

			nc = Dataset(data_path, 'r')
			values = nc.variables['data'][:]
			nc.close()

			try:
				values = values.tolist()
			except AttributeError:
				pass

			if var not in rv['data']:
				rv['data'][var] = []

			rv['data'][var].extend(values)

		if (end_time - scan_time) <= 0:
			break

		scan_time = scan_time + time_delta
	return rv


class DataServer:
	"""Listen on a websocket, serve requests, and prefetch data.

	Instance Variables:

	prefetch_blocks -- number of 'blocks' of data to prefetch
	prefetch_buses -- whether or not to prefetch additional buses
	prefetch_variables -- whether or not to prefetch additional variables
	client_counter -- counts clients
	test_counter -- for debugging purposes
	"""
	def __init__(self, prefetch_blocks, prefetch_buses, prefetch_variables):
		self.prefetch_blocks = prefetch_blocks
		self.prefetch_buses = prefetch_buses
		self.prefetch_variables = prefetch_variables
		self.client_counter = 0
		self.test_counter = 0

	def parseQuery(self, query, mc, data_dir):
		"""Return requested data given a specified query.

		query -- dict containing 'bus_ids', 'time_range', 'dataset_name',
									'variable', 'offset', 'time_resolution'
		"""
		# try:
		rv = {}
		rv["data"] = []
		prefetch_list = [0 for i in range(7)]
		prefetch_list[0] = False
		self.test_counter += 1

		# Check the query and set corresponding variables
		try:
			(component, num_buses, time_range,
			dataset_name, variable_list, offset,
			data_type, bus_from, bus_to) = check_query(query)
		except Exception as err:
			rv['error'] = str(err)
			return rv, prefetch_list

		# TODO: Add to check_query
		# resolution = query["time_resolution"]
		resolution = 0.033333333
		time_delta = 5

		stime = offset
		duration = int(time_range) * float(resolution)
		end_time = stime + duration

		rv["now"] = offset
		rv["next_time"] = int(offset + duration + (time_delta - ((offset + duration) % time_delta)))
		data_diff = 0

		# Calculate starting key time
		new_time = int(offset - (offset % time_delta))
		rv["time"] = new_time

		# Calculate ending key time
		end_new_time = int(end_time - (end_time % time_delta))
		rv['next_time2'] = end_new_time

		# Handle non-bus variables
		if component == 'Line':
			rv = return_line(rv, data_dir, dataset_name, data_type, component,
							variable_list, num_buses, new_time, end_new_time, time_delta, bus_from, bus_to)
			return rv, prefetch_list

		elif component != 'Bus':
			rv = return_component(rv, data_dir, dataset_name, data_type, component,
							variable_list, num_buses, new_time, end_new_time, time_delta)
			return rv, prefetch_list

		# Calculate intermediate keys
		key_list = []

		for k in range(len(variable_list)):
			variable = variable_list[k]

			for i in range(num_buses):
				new_key = gen_cache_key(dataset_name, variable, i + 1, new_time, data_type)
				key_list.append(new_key)

				scan_key = new_key
				scan_time = new_time
				# Grab intermediate keys
				while (end_new_time - scan_time) > 0:
					scan_time = scan_time + time_delta
					scan_key = gen_cache_key(dataset_name, variable, i + 1, scan_time, data_type)
					key_list.append(scan_key)

		# Get all keys, check if keys were retrieved, add data
		check_count = 0
		val = []
		pre_data_time = time.time()

		val = mc.get_multi(key_list)

		post_data_time = time.time()
		data_diff += post_data_time - pre_data_time

		for j in range(num_buses):
			rv['data'].append({})
			for var in variable_list:
				rv['data'][j][var] = []

		# Loop through key list checking if they are in cache, if not then find the corresponding file
		for i in range(len(key_list)):
			var = key_list[i].split(':')[1]
			bus = key_list[i].split(':')[2]

			if key_list[i] in val:
				rv['data'][int(bus) - 1][var].extend(val[key_list[i]].tolist())
				check_count += 1

			else:
				# Cache miss
				key = key_list[i]
				val_dataset = key.split(":")[0]
				variable = key.split(":")[1]
				bus_id = key.split(":")[2]
				fetch_time = key.split(":")[3]
				data_file = os.path.join(data_dir, val_dataset, data_type,
											'Bus', variable, bus_id,
											'time_' + fetch_time + '.nc')

				try:
					nc = Dataset(data_file, 'r')
				except IOError:
					rv["error"] = "Error: file doesn't exist"
					continue

				val_tmp = nc.variables['data'][:]
				check_count += 1
				mc.set(key, val_tmp)

				rv['data'][int(bus) - 1][var].extend(val_tmp.tolist())

		if check_count == 0:
			rv["error"] = "Error: data not found"

		rv['cache_time'] = data_diff
		server_log.debug("Cache: {}".format(data_diff))

		# If prefetching is enabled, then set prefetch params from last key found
		if self.prefetch_blocks > 0 and 'error' not in rv:
			# If prefetch is needed, set vars for future fct call
			key = key_list[-1]
			val_dataset = key.split(":")[0]
			variable = key.split(":")[1]
			bus_id = key.split(":")[2]
			fetch_time = key.split(":")[3]
			prefetch_list[0] = True
			prefetch_list[1] = val_dataset
			prefetch_list[2] = variable
			prefetch_list[3] = bus_id
			prefetch_list[4] = fetch_time
			prefetch_list[5] = num_buses
			prefetch_list[6] = data_type

		return rv, prefetch_list

	def prefetch(self, conn, dataset, variable, bus_id, fetch_time, num_buses, bus_start, data_dir, data_type):
		"""Prefetch data for future requests using multiprocesses.

		conn -- connection with parent process
		dataset -- dataset name
		variable -- variable for data
		bus_id -- last bus fetched by parseQuery
		fetch_time -- last time fetched by parseQuery
		num_buses -- number of buses requested
		bus_start -- the starting bus for current process
		"""

		# Parameters for prefetching
		mc = memcache.Client(['localhost:11211'], debug=0)
		prefetch_time = time.time()
		set_diff = 0

		set_count = 0

		incr = 5
		timestamp = int(fetch_time)
		key_diff = 0
		file_diff = 0
		data_diff = 0

		for i in range(self.prefetch_blocks):
			if conn.poll():
				log.debug("set_count: %s time: %s prefetch_time: %s bus_start: %s",
						str(set_count),
						str(timestamp),
						str(time.time() - prefetch_time),
						str(bus_start)
				)
				break

			timestamp += incr

			if self.prefetch_variables:
				for k in range(3):
					if conn.poll():
						log.debug("set_count: %s time: %s prefetch_time: %s bus_start: %s",
									str(set_count),
									str(timestamp),
									str(time.time() - prefetch_time),
									str(bus_start)
						)
						break

					if k == 0:
						variable = "V"
					if k == 1:
						variable = "w_Busfreq"
					if k == 2:
						variable = "theta"

					if self.prefetch_buses:
						for j in range(bus_start, bus_start + num_buses):
							if conn.poll():
								log.debug("set_count: %s time: %s prefetch_time: %s bus_start: %s",
											str(set_count),
											str(timestamp),
											str(time.time() - prefetch_time),
											str(bus_start)
								)
								break
							key_time = time.time()
							bus_id = str(j + 1)
							key = gen_cache_key(dataset, variable, bus_id, timestamp, data_type)
							key_diff += time.time() - key_time

							file_time = time.time()
							data_file = os.path.join(data_dir, dataset, data_type,
														'Bus', variable, bus_id,
														'time_' + str(timestamp) + '.nc')
							try:
								nc = Dataset(data_file, 'r')
							except IOError:
								log.debug("IOError: %s", str(data_file))
								continue
							file_diff += time.time() - file_time

							data_time = time.time()
							try:
								val = nc.variables['data'][:]
							except KeyError:
								log.debug("KeyError: %s", str(key))
								continue
							data_diff += time.time() - data_time
							nc.close()
							pre_set_time = time.time()
							mc.set(key, val)
							set_diff += time.time() - pre_set_time
							set_count += 1

					else:  # Buses = False
						if conn.poll():
							log.debug("set_count: %s time: %s prefetch_time: %s bus_start: %s",
										str(set_count),
										str(timestamp),
										str(time.time() - prefetch_time),
										str(bus_start)
							)
							break
						key = gen_cache_key(dataset, variable, bus_id, timestamp, data_type)
						file_time = time.time()
						data_file = os.path.join(data_dir, dataset, data_type,
													'Bus', variable, bus_id,
													'time_' + str(timestamp) + '.nc')
						try:
							nc = Dataset(data_file, 'r')
						except IOError:
							log.debug("IOError: %s", str(data_file))
							continue

						file_diff += time.time() - file_time

						val = nc.variables['data'][:]
						nc.close()
						pre_set_time = time.time()
						mc.set(key, val)
						set_diff += time.time() - pre_set_time
						set_count += 1

			else:  # Variables = False
				if self.prefetch_buses:
					for j in range(bus_start, bus_start + num_buses):
						if conn.poll():
							log.debug("set_count: %s time: %s prefetch_time: %s bus_start: %s",
										str(set_count),
										str(timestamp),
										str(time.time() - prefetch_time),
										str(bus_start)
							)
							break
						key_time = time.time()
						bus_id = str(j + 1)
						key = gen_cache_key(dataset, variable, bus_id, timestamp, data_type)
						key_diff += time.time() - key_time

						file_time = time.time()
						data_file = os.path.join(data_dir, dataset, data_type,
													'Bus', variable, bus_id,
													'time_' + str(timestamp) + '.nc')
						try:
							nc = Dataset(data_file, 'r')
						except IOError:
							log.debug("IOError: %s", str(data_file))
							continue

						file_diff += time.time() - file_time

						data_time = time.time()
						val = nc.variables['data'][:]
						data_diff += time.time() - data_time
						nc.close()

						pre_set_time = time.time()
						mc.set(key, val)
						set_diff += time.time() - pre_set_time
						set_count += 1

				else:  # Buses = False
					if conn.poll():
						log.debug("set_count: %s time: %s prefetch_time: %s bus_start: %s",
									str(set_count),
									str(timestamp),
									str(time.time() - prefetch_time),
									str(bus_start)
						)
						break
						key = gen_cache_key(dataset, variable, bus_id, timestamp, data_type)
					file_time = time.time()
					data_file = os.path.join(data_dir, dataset, data_type,
												'Bus', variable, bus_id,
												'time_' + str(timestamp) + '.nc')
					try:
						nc = Dataset(data_file, 'r')
					except IOError:
						log.debug("IOError: %s", str(data_file))
						continue

					file_diff += time.time() - file_time

					data_time = time.time()
					val = nc.variables['data'][:]
					data_diff += time.time() - data_time
					nc.close()

					pre_set_time = time.time()
					mc.set(key, val)
					set_diff += time.time() - pre_set_time
					set_count += 1

		log.debug("set_time: %s key_time: %s file_time: %s data_time: %s", str(set_diff), str(key_diff),
					str(file_diff), str(data_diff))
		if conn.poll():
			log.debug("set_count: %s prefetch did not end successfully: %s prefetch_time: %s bus_start: %s",
					str(set_count),
					str(timestamp),
					str(time.time() - prefetch_time),
					str(bus_start)
			)
		if not conn.poll():
			log.debug("set_count: %s prefetch did not end successfully: %s prefetch_time: %s bus_start: %s",
					str(set_count),
					str(timestamp),
					str(time.time() - prefetch_time),
					str(bus_start)
			)
