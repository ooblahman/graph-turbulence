''' Solution rendering for graphs ''' 

from typing import Callable, List
from pathlib import Path
import time
import webbrowser

from utils.bokeh import serve, bokeh_host, bokeh_port
from utils.zmq import *
from core.observable import System, SerializedSystem


def render_live(rs: List[List[SerializedSystem]]):
	'''Plot live simulation with Bokeh.
	Args:
		rs: list of (top-level) functions that produce `System`s when called.
	'''
	path = str(Path(__file__).parent / 'bokeh_server.py')
	proc = serve(path)
	ctx, tx = ipc_tx()

	try:
		print('Waiting for server to initialize...')
		# webbrowser.open_new_tab('http://{}:{}'.format(bokeh_host, bokeh_port))
		tx({'tag': 'init', 'systems': wire_pickle(rs)})
		print('Done.')
		while True: 
			time.sleep(1) # Let bokeh continue to handle interactivity while we wait
	finally:
		ctx.destroy()
		proc.terminate()