function Control(div) {
	this.id = undefined;
	this.div = div;
	this.frames = [];
	this.time = undefined;
	this.startTime = 0;
	this.fps = 1.0;
	this.playing = false;
	return this;
}

Control.prototype = {
	initialize: function(id) {
		this.id = id;
		this.fetch_data();
	},

	fetch_data: function(time) {
		if (this.data_socket === undefined) {
			this.open_data_socket(time);
			return;
		}

		var msg = {
			'time': 3.0,
			'id': this.id,
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
			console.log(event.data);
			this.handle_data(event.data);
		}.bind(this);
	},

	handle_data: function(data) {

		this.fetchingFrames = false;
		if (!this.playing)
			this.simple_loop();
	},

	simple_loop: function() {
		var self = this;
		if (this.index > this.frames.length) {
			this.paused = true;
		}

		setTimeout(function() {
			self.simple_loop();
		}, 50);

		setTimeout(function() {
			self.play(self.frames[self.index]);
			self.index += 1;
			if (!self.fetchingFrames) {
				self.fetchingFrames = true;
				self.fetch_data(self.frames[self.frames.length -1].nexttime);
			}

			self.simple_loop();
		}, 1000.0 / this.fps);
	},
	play: function(frame) {
		this.time = frame.time;
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
	var config = getURLVariables().config.split('/')[0];
	console.debug(config);
	if (config === "")
		console.log("Nothing");
	else {
		window.control = new Control('div1');
		window.control.initialize(config);
	}
});
