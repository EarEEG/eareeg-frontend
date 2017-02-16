require.config({
	baseUrl: '/static/js',
	paths: {
		jquery: 'vendor/jquery/dist/jquery',
	},
});

require(['jquery'], function ($) {
$(document).ready(function() {
	window.alert('here');
});
});
