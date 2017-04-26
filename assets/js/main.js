function Control(div, replay) {
	this.id = undefined;
	this.div = div;
	this.replay = replay;
	this.frames = {};
	this.devices = [];
	this.time = undefined;
	this.startTime = 0;
	this.fps = 3.0;
	this.index = 0;
	this.playing = false;
	this.timestep = 1;
	return this;
}

Control.prototype = {
	hide_chart: function(name) {
		$('#' + this.div + '> #' + name).addClass('hidden');
		$('#' + this.div + '> #controls > select').append("<option value='" + name + "'>" + name + "</option>");
	},

	remove_chart: function(name) {
		var chart = this.charts[name];
		if (chart === undefined)
			return;

		delete this.charts[name];
		chart.destroy();
		$('#' + this.div + '> #controls > select').append("<option value='" + name + "'>" + name + "</option>");
	},

	add_chart: function(name, num) {
		var self = this;
		var div = document.createElement('div');
		div.id = name;
		$('#' + self.div).append(div);
		$('#' + self.div + '> #' + name).addClass('chart');
		$('#' + self.div + '> #' + name).addClass('hidden');

		self.charts[name] = new Highcharts.chart({
				chart: {
					type: 'spline',
					marginLeft: 40,
					spacingTop: 20,
					spacingBottom: 20,
					renderTo: div
				},
				title: {
					text: name,
					align: 'left',
					margin: 0,
					x: 30
				},
				credits: {
					enabled: false
				},
				xAxis: {
					crosshair: true,
					labels: {
						format: '{value} sec'
					}
				},
				yAxis: {

				},
				series: [{
					data: [],
					name: name,
					fillOpacity: 0.3,
				},
				{
					data: [],
					name: name,
					fillOpacity: 0.3,
				}
				],

				exporting: {
					buttons: {
						removeButton: {
							text: "Remove",
							onclick: function() {
								var name = this.userOptions.title.text;
								self.hide_chart(name);
							},
							symbolFill: '#FF0000'
						}
					}
				}
			});


		if (self.devices.length == 1) {
			self.charts[name].series[1].remove();
		}
	},

	initialize: function(id, config, config2) {
		if (!id) id = "run1";
		var self = this;
		this.id = id;
		this.device = config.id;
		this.devices.push(this.device);
		self.frames[config.id] = [];

		if (config2 !== undefined) {
			this.device2 = config2.id;
			this.devices.push(this.device2);
			self.frames[config2.id] = [];
		}

		this.categories = []; //[ 'delta', 'theta', 'lowAlpha'];
		this.types = []; //['highAlpha', 'lowBeta' ];

		self.setupHandlers();
		this.charts = {};

		/* TODO Fix this later. */
		for (i = 0; i < config.waveTypes.length; i++) {
			self.categories.push(config.waveTypes[i]);
		}

		self.categories.forEach(function(name) {
			self.add_chart(name, 2);
		});

		self.categories.forEach(function(name, i) {
			if (i < 3)
				self.show_chart(name);
			else
				self.types.push(name);
		});

		self.types.forEach(function(type) {
			$('#' + self.div + ' > #controls > select').append('<option value=' + type + '>' + type + '</>');
		});

		self.fetch_data();
	},


	fetch_data: function(time) {
		if (this.data_socket === undefined) {
			this.open_data_socket(time);
			return;
		}

		var msg = {
			'time': 3.0,
			'id': this.id,
			'devices': []
		};

		this.devices.forEach(function(d) {
			console.log(d);
			msg.devices.push(d);
		});

		this.data_socket.send(JSON.stringify(msg));
	},

	open_data_socket: function(time) {
		var address;
		if (this.replay)
			address = 'ws://cepsltb7.curent.utk.edu:9121/ws/fetch';
		else
			address = 'ws://localhost:9000/';

		this.data_socket = new WebSocket(address);

		this.data_socket.onopen = function(event) {
			this.fetch_data(time);
		}.bind(this);

		this.data_socket.onmessage = function(event) {
			console.log('recieved message');
			msg = JSON.parse(event.data);
			if (msg.error) {
				console.error(msg.error);
				return;
			}

			if (this.replay)
				this.handle_data(msg);
			else {
				console.log("LIVE MODE");
			}
		}.bind(this);
	},

	handle_data: function(data) {
		var self = this;
		this.fetchingFrames = false;

		Object.keys(data.devices).forEach(function(key) {
			var id = 1;
			if (key === "device1")
				id = 0;

			data.devices[key].forEach(function(frame, i) {
				if (self.frames[key].length === 0)
					frame.time = 0;
				else
					frame.time = self.frames[key][self.frames[key].length - 1].time + self.timestep;

				self.frames[key].push(frame);
			});
		});

		if (!this.playing) {
			this.playing = true;
			this.simple_loop();
		}
	},

	simple_loop: function() {
		var self = this;
		if (this.paused) {
			console.log("playback is paused");
			setTimeout(function() {
				self.simple_loop();
			}, 50);
			return;
		}

		if (this.index >= this.frames.length) {
			console.log("setting pause = true");
			this.paused = true;
			this.simple_loop();
			return;
		}

		setTimeout(function() {
			self.devices.forEach(function(device, i) {
				self.play(self.frames[device][self.index], i);
			});

			self.index += 1;
			if (!self.fetchingFrames && self.index >= (self.frames.length / 3)) {
				console.log('fetching');
				self.fetchingFrames = true;
				//self.fetch_data(self.frames[self.frames.length -1].time + self.timestep);
			}

			self.simple_loop();
		}, 1000.0 / this.fps);
	},

	play: function(frame, id) {
		this.time = frame.time;
		for (var key in frame) {
			if (this.charts[key] === undefined)
				continue;
			console.debug('adding point');
			this.charts[key].series[id].addPoint([this.time, frame[key] / 1000.0]);
		}
	},

	show_chart: function(wave) {
		$('#' + this.div + '> #' + wave).removeClass('hidden');
	},

	setupHandlers: function() {
		var self = this;
		$('#' + self.div +'> #controls > select').on('change', function() {
			if ($(this).val() === "")
				return;
			self.show_chart($(this).val());
			$("#" + self.div + " > #controls > select > option[value='" + $(this).val() + "']").remove();
			$('html, body').animate({
				scrollTop: $(document).height()
			}, 1000);
		});
	}
};

function getURLVariables() {
	var options = {};
	var query = window.location.search.substring(1);
	var variables = query.split('&');
	variables.forEach(function(param) {
		var pair = param.split('=');
		if (pair[0] !== '' && pair[1] !== undefined)
			options[pair[0]] = pair[1];
	});
	return options;
}

function resizeDivs() {
	$('#div1').css('width', '49%');
	$('#div2').css('display', '');
}

function startRun() {
	var address = 'ws://cepsltb7.curent.utk.edu:9121/ws/run';
	data_socket = new WebSocket(address);
	data_socket.onopen = function(event) {
		console.log("run socket is open");
		data_socket.send(JSON.stringify({msg: 'hi'}));
	};
	data_socket.onmessage = function(event) {
		console.log('recieved message');
		msg = JSON.parse(event.data);
		if (msg.error) {
			consle.error(msg.error);
			return;
		}
	};
}

function loadConfig(id) {
	configSocket = new WebSocket('ws://cepsltb7.curent.utk.edu:9121/ws/init');
	configSocket.onopen = function(event) {
		setTimeout(function() {
			configSocket.send(JSON.stringify({
				'run': id
			}));
		}, 50);
	};

	configSocket.onmessage = function(event) {
		var msg = JSON.parse(event.data);
		var i;
		if (msg.error) {
			console.error(msg.error);
			return;
		}

		if (msg.config.devices.length === 1) {
			window.control1 = new Control('div1', replay=true);
			window.control1.initialize(id, msg.config.devices[0]);
		} else {
			console.log("hereee");
			window.control1 = new Control('div1', replay=true);
			window.control1.initialize(id, msg.config.devices[0], msg.config.devices[1]);
		}
	};
}

function init(id) {
	var liveMode = false;
	if (id === undefined)
		liveMode = true;

	if (!liveMode) {
		loadConfig(id);
		return;
	}

	var config = {
		"devices": [
			{
				"id": "device1",
				"waveTypes": [
					"delta",
					"theta",
					"lowAlpha",
					"highAlpha",
					"lowBeta",
					"midGamma",
					"attention",
					"meditation"
				]
			},
		]
	};

	window.control1 = new Control('div1', replay=false);
	window.control1.initialize(id, config.devices[0]);
	/* Harcode config for live mode for now */
}

$(document).ready(function() {
	var config;
	var num = 1;
	var id;

	try {
		var options = getURLVariables();
		id = options.run.split('/')[0];
	} catch(e) { }

	init(id);
});
