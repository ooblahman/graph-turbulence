''' ZMQ utilities ''' 

import ujson
import zmq

zmq_pubsub_port = 8079
zmq_pubsub_topic = '0'

def dict_to_pubsub(mp, topic=zmq_pubsub_topic):
    return topic + ' ' + ujson.dumps(mp)

def pubsub_to_dict(msg, topic=zmq_pubsub_topic):
    return ujson.loads(msg[len(topic)+1:])

def pubsub_tx():
	ctx = zmq.Context()
	sock = ctx.socket(zmq.PUB)
	sock.bind('tcp://127.0.0.1:{}'.format(zmq_pubsub_port))
	tx = lambda msg: sock.send_string(dict_to_pubsub(msg))
	return ctx, tx

def pubsub_rx():
	ctx = zmq.Context()
	sock_recv = ctx.socket(zmq.SUB)
	sock_recv.connect('tcp://127.0.0.1:{}'.format(zmq_pubsub_port))
	sock_recv.setsockopt_string(zmq.SUBSCRIBE, zmq_pubsub_topic)
	rx = lambda: pubsub_to_dict(sock_recv.recv_string())
	return ctx, rx