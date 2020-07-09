import ujson
import zmq
import random
import numpy as np
from functools import partial
from threading import Thread
from tornado import gen
import networkx as nx
from networkx.readwrite.json_graph import node_link_graph
from matplotlib.colors import rgb2hex

from bokeh.plotting import figure, output_file, show, curdoc, from_networkx
from bokeh.models import ColumnDataSource, Slider, Select, Button, Oval
from bokeh.layouts import row, column, gridplot, widgetbox
from bokeh.models.widgets import Div

from utils.zmq import pubsub_rx
from diffusions.lib import heat_cmap

# Save curdoc() to make sure all threads see the same document.
doc = curdoc()

'''
Plot configuration
'''

tools = "ypan,ywheel_zoom,ywheel_pan,ybox_zoom,reset"
config = {
	'vmax': 1.0
}


'''
Layout UI
'''

t0 = Div(text='', style={'font-size':'200%'})
t1 = Div(text='Time:', style={'font-size':'150%'})
t2 = Div(text='N/A', style={'font-size':'150%'})
root = column(
	row([t0]),
	row([t1, t2]),
)
root.sizing_mode = 'stretch_both'
doc.add_root(root)

doc.title = 'Bokeh Server'
plots = {}

'''
Process messages
'''

@gen.coroutine
def update(msg):
	# print(msg)
	if msg['tag'] == 'init':
		t0.text = msg['title']
		G = node_link_graph(msg['graph'])
		G = nx.convert_node_labels_to_integers(G) # Bokeh cannot handle non-primitive node keys (eg. tuples)
		n = len(G)
		layout = nx.spring_layout(G, scale=0.9, center=(0,0), iterations=1000)
		for plot_key in msg['plots']:
			plot = figure(title=plot_key, x_range=(-1.1,1.1), y_range=(-1.1,1.1), tools=tools, toolbar_location=None)
			plot.axis.visible = None
			# plot.sizing_mode = 'stretch_both'
			renderer = from_networkx(G, lambda _: layout)
			renderer.node_renderer.glyph = Oval(height=0.1, width=0.1, fill_color='color')
			renderer.node_renderer.data_source.data = dict(
				index=list(range(n)),
				color=['#000000']*n,
			)
			plot.renderers.append(renderer)
			plots[plot_key] = plot
		root.children.append(row(list(plots.values())))
		if 'vmax' in msg:
			config['vmax'] = msg['vmax']
	elif msg['tag'] == 'data':
		t2.text = str(round(msg['t'], 2))
		for plot_key in msg['data'].keys():
			colors = [rgb2hex(heat_cmap(v / config['vmax'])) for v in msg['data'][plot_key]]
			plots[plot_key].renderers[0].node_renderer.data_source.data['color'] = colors

def stream_data():
	ctx, rx = pubsub_rx()
	try:
		while True:
			msg = rx()
			doc.add_next_tick_callback(partial(update, msg=msg))
	finally:
		ctx.destroy()

thread = Thread(target=stream_data)
thread.start()