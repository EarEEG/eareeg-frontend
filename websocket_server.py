'''
Basic Flask server
'''

from flask import Flask
from flask_socketio import SocketIO, send, emit
app = Flask(__name__)
socketio = SocketIO(app)

@app.route("/")
def index():
    return "Hello World!"

@socketio.on("data")
def handle_data(json):
    print("Recieved JSON:\n", json)
    emit("data", json, broadcast=True)

@socketio.on('connect')
def test_connect():
    print("Connected to host")
    emit('connected', {'data': 'Connected'})

@socketio.on('disconnect')
def test_disconnect():
    print('Client disconnected')


if __name__ == "__main__":
    socketio.run(app)
