'''
Basic autobahn server
'''
# create the namespace for the messages

from autobahn.twisted.websocket import WebSocketServerProtocol

# most of this came from the code in the tutorial found 
# here: https://github.com/crossbario/autobahn-python
class earEEGServerProtocol(WebSocketServerProtocol):
    def onConnect(self, request):
        print("Client Connecting: {}".format(request.peer))

    def onOpen(self):
        print("WebSocket connection open")

    def onMessage(self, json, isBinary):
        print("Got message: {}".format(json))
        self.sendMessage(json)

    def onClose(self, wasClean, code, reason):
        print("Websocket Connection closed for reason: {}".format(reason))


# Boilerplate to get this to run
if __name__ == '__main__':

   import sys

   from twisted.python import log
   from twisted.internet import reactor
   log.startLogging(sys.stdout)

   from autobahn.twisted.websocket import WebSocketServerFactory
   factory = WebSocketServerFactory()
   factory.protocol = earEEGServerProtocol

   reactor.listenTCP(9000, factory)
   reactor.run()
