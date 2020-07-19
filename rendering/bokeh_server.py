''' Interactive plot for rendering time-indexed graph simulations ''' 

import numpy as np
from functools import partial
from threading import Thread
from tornado import gen
import dill as pickle

from bokeh.plotting import figure, output_file, show, curdoc, from_networkx
from bokeh.models import ColumnDataSource, Slider, Select, Button, Oval
from bokeh.layouts import row, column, gridplot, widgetbox
from bokeh.models.widgets import Div

from utils.zmq import pubsub_rx
from rendering import *

# Save curdoc() to make sure all threads see the same document.
doc = curdoc()


''' 
Variables
'''

plots = {}
renderers = []
render_callback = None
speed = 0.1 
viz_dt = 50 # update every ms

'''
UI
'''

t1 = Div(text='Time:', style={'font-size':'150%'})
t2 = Div(text='N/A', style={'font-size':'150%'})
reset_button = Button(label='⟲ Reset', width=60)
pp_button = Button(label='► Play', width=60)
speed_slider = Slider(start=-2.0, end=0.5, value=-1.0, step=0.1, title='Speed', width=300)

'''
Callbacks
'''
def update():
	global renderers, viz_dt
	for r in renderers:
		r.step(viz_dt * 1e-3 * speed)
		r.measure()
	t2.text = str(round(renderers[0].t, 3))

def reset_button_cb():
	global renderers
	for r in renderers:
		r.reset()
		r.measure()
	t2.text = str(round(renderers[0].t, 3))
reset_button.on_click(reset_button_cb)

def pp_button_cb():
	global viz_dt, render_callback
	if pp_button.label == '► Play':
		pp_button.label = '❚❚ Pause'
		render_callback = doc.add_periodic_callback(update, viz_dt)
	else:
		pp_button.label = '► Play'
		doc.remove_periodic_callback(render_callback)
pp_button.on_click(pp_button_cb)

def speed_slider_cb(attr, old, new):
	global speed
	speed = 10 ** speed_slider.value
speed_slider.on_change('value', speed_slider_cb)

'''
Layout
'''

root = column(
	row([t1, t2]),
	row([reset_button, pp_button, speed_slider]),
)
root.sizing_mode = 'stretch_both'
doc.add_root(root)
doc.title = 'Bokeh Server'

'''
Updates
'''

@gen.coroutine
def react(msg):
	global renderers, viz_dt
	# print(msg)
	if msg['tag'] == 'init':
		renderers = [pickle.loads(r.encode('latin1')) for r in msg['renderers']]
		for r in renderers:
			plots[r.desc] = r.create_plot()
		grid = gridplot(children=list(plots.values()), ncols=2, sizing_mode='scale_both', toolbar_location=None)
		root.children.append(grid)

def stream_data():
	ctx, rx = pubsub_rx()
	try:
		while True:
			msg = rx()
			doc.add_next_tick_callback(partial(react, msg=msg))
	finally:
		ctx.destroy()

thread = Thread(target=stream_data)
thread.start()
