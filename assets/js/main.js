function Control(div) {
	this.id = undefined;
	this.div = div;
	this.frames = [];
	this.time = undefined;
	this.startTime = 0;
	this.fps = 3.0;
	this.index = 0;
	this.playing = false;
	this.timestep = 1;
	return this;
}

Control.prototype = {
	initialize: function(id) {
		var self = this;
		this.id = id;
		this.categories = [ 'delta', 'theta', 'lowAlpha'];
//, 'theta', 'lowAlpha', 'highAlpha', 'lowBeta' ];

		this.charts = {};
		this.categories.forEach(function(name) {
			var div = document.createElement('div');
			div.id = name;
			$('#' + self.div).append(div);
			//$('#' + name).addClass('chart');

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
					}]
				});
		});
		this.fetch_data();
	},


	fetch_data: function(time) {
		if (this.data_socket === undefined) {
			this.open_data_socket(time);
			return;
		}

		var msg = {
			'time': 3.0,
			'id': 'test',
			'device': "device1"
		};

		this.data_socket.send(JSON.stringify(msg));
	},

	open_data_socket: function(time) {
		var address = 'ws://cepsltb7.curent.utk.edu:9121/ws/fetch';
		this.data_socket = new WebSocket(address);
		this.data_socket.onopen = function(event) {
			this.fetch_data(time);
		}.bind(this);
		this.data_socket.onmessage = function(event) {
			console.log('recieved message');
			msg = JSON.parse(event.data);
			if (msg.error) {
				consle.error(msg.error);
				return;
			}
			this.handle_data(msg.data);
		}.bind(this);
	},

	handle_data: function(data) {
		var self = this;
		this.fetchingFrames = false;
		data.forEach(function(frame, i) {
			if (self.frames.length === 0)
				frame.time = 0;
			else
				frame.time = self.frames[self.frames.length - 1].time + self.timestep;
			self.frames.push(frame);
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
			self.play(self.frames[self.index]);
			console.log(self.frames.length);
			self.index += 1;
			if (!self.fetchingFrames && self.index >= (self.frames.length / 3)) {
				console.log('fetching');
				self.fetchingFrames = true;
				self.fetch_data(self.frames[self.frames.length -1].time + self.timestep);
			}

			self.simple_loop();
		}, 1000.0 / this.fps);
	},

	play: function(frame) {
		this.time = frame.time;
		for (var key in frame) {
			if (this.charts[key] === undefined)
				continue;
			this.charts[key].series[0].addPoint(frame[key] / 1000.0);
		}

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
	$('#div1').css('width', '50%');
	$('#div2').css('display', '');
}

$(document).ready(function() {
	var config;
	var num = 1;
	try {
		var options = getURLVariables();
		num = options.num.split('/')[0];
	} catch(e) {
		num = 1;
	}

	if (num > 2 || num <= 0)
		num = 2;

	if (config === "")
		console.log("Nothing");
	else {
		if (num == 1) {
			window.control1 = new Control('div1');
			window.control1.initialize(config);
		} else {
			resizeDivs();
			window.control1 = new Control('div1');
			window.control2 = new Control('div2');
			window.control1.initialize(config);
			window.control2.initialize(config);
		}
	}
});
