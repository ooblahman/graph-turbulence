''' Class for specifying, running, and visualizing differential equations on graphs ''' 

import networkx as nx
import numpy as np
import pandas as pd
import scipy.integrate
from typing import Callable, List, Tuple, Union, Any, Dict
from networkx.readwrite.json_graph import node_link_data, node_link_graph
import ujson
import pdb
from matplotlib.colors import rgb2hex
import colorcet as cc
from itertools import count
from enum import Enum
from abc import ABC, abstractmethod
import math

from bokeh.plotting import figure, from_networkx
from bokeh.models import ColorBar, LinearColorMapper, BasicTicker, HoverTool, Arrow, VeeHead
from bokeh.models.glyphs import Oval, MultiLine
from bokeh.transform import linear_cmap

from utils import *

''' Basic types ''' 

Vertex = Any
Edge = Tuple[Vertex, Vertex]
Face = Tuple[Vertex, ...]
GeoObject = Union[Vertex, Edge]

''' Base observable definitions '''

class Observable(ABC):
	''' A real-valued function defined on a graph domain
	Note: abstract base class, not intended to be instantiated.
	''' 

	def __init__(self, G: nx.Graph, desc: str='', weight_key: str=None, default_weight=1.0):
		self.G = G
		self.init_domain()
		self.n = len(self.domain)
		self.integrator = None
		self.track_other = None
		self.y = np.zeros(len(self))
		self.y0 = lambda _: 0.
		self.t = 0.
		self.t0 = 0.
		self.init_kwargs = {}
		self.fixed_idx = []
		self.dirichlet_values = dict()
		self.neumann_values = dict()
		self.neumann_vec = np.zeros(len(self))
		self.plot = None
		self.desc = desc
		self.set_render_params()
		self.w_key = weight_key
		self.default_weight = default_weight
		self.nonphysical = lambda y: False

	@abstractmethod
	def init_domain(self):
		pass

	@abstractmethod
	def weight(self, x1: GeoObject, x2: GeoObject) -> float:
		pass

	def populate(self, f: Callable[[GeoObject], float]) -> np.ndarray:
		return np.array([f(x) for x in self.domain.keys()])

	''' ODE & updating ''' 

	def set_ode(self, f: Callable[[float], np.ndarray], order: int=1, max_step=np.inf):
		self.f = f
		self.order = order
		n = len(self)

		def g(t: float, y: np.ndarray):
			dydt = np.zeros_like(y)
			for i in range(order-1):
				dydt[n*i:n*(i+1)] = y[n*(i+1):n*(i+2)]
			dydt[n*(order-1):] = replace(f(t), self.fixed_idx, np.zeros_like(self.fixed_idx))
			return dydt
		self.g = g

		y0 = np.concatenate((self.y, np.zeros((self.order-1)*n)))
		for i, y0_i in enumerate(self.init_kwargs.values()):
				y0[(i+1)*n:(i+2)*n] = self.populate(y0_i)
		self.integrator = scipy.integrate.RK45(self.g, self.t, y0, np.inf, max_step=max_step)

	def track(self, other: 'Observable'):
		''' Track the values of another observable, assuming self.G is a subgraph ''' 
		assert type(self).__name__ == type(other).__name__, 'Cannot track observable of another type'
		assert self.integrator is None, 'Cannot track values and compute ODE together'
		assert all(k in other.domain for k in self.domain)
		self.track_other = other

	''' Initial & Boundary Conditions ''' 

	def set_initial(self, t0: float=0., y0: Callable[[GeoObject], float]=lambda _: 0., **kwargs):
		self.t0 = t0
		self.t = t0
		self.y0 = y0
		self.y = self.populate(y0)
		self.init_kwargs = kwargs
		# Setting initial values resets the integrator
		if self.integrator is not None: 
			assert len(kwargs) == self.order - 1, f'{len(kwargs)+1} initial conditions provided but {self.order} needed'
			self.set_ode(self.f, self.order)

	def set_boundary(self, dirichlet_values: Dict[GeoObject, float]={}, neumann_values: Dict[GeoObject, float]={}):
		intersect = dirichlet_values.keys() & neumann_values.keys()
		assert len(intersect) == 0, f'Dirichlet and Neumann conditions overlap on {intersect}'
		self.dirichlet_values = dirichlet_values
		self.neumann_values = neumann_values
		self.neumann_vec = replace(np.zeros(len(self)), [self.domain[k] for k in neumann_values], list(neumann_values.values()))
		self.fixed_idx = [self.domain[k] for k in dirichlet_values.keys()]
		fixed_vals = list(dirichlet_values.values())
		self.y = replace(self.y, self.fixed_idx, fixed_vals)
		# Setting boundary values resets the integrator
		if self.integrator is not None:
			self.set_ode(self.f, self.order)

	@property
	def boundary(self) -> List[GeoObject]:
		return list(self.dirichlet_values.keys()) + list(self.neumann_values.keys())

	''' Integration ''' 

	def step(self, dt: float):
		if self.integrator is not None:
			self.integrator.t_bound = self.t + dt
			self.integrator.status = 'running'
			while self.integrator.status != 'finished':
				self.integrator.step()
				self._measure_integrator()

	def measure(self) -> np.ndarray:
		if self.integrator is not None:
			self._measure_integrator()
			print(self.t)
		elif self.track_other is not None:
			self.t = self.track_other.t
			self.y = np.array([self.track_other(x) for x in self.domain])
		if self.plot is not None:
			self.render()
		if self.nonphysical(self.y):
			raise Exception('Non-physical solution')
		return self.y

	def _measure_integrator(self):
		# TODO: coupled `observables` referencing these states are currently receiving out-of-date values.
		# Should likely couple them into a single integrator. Create a `couple()` method.
		self.t = self.integrator.t
		self.y = self.integrator.y[:len(self)]

	def integrate(self, t0: float, tf: float):
		n = len(self)
		y0 = np.concatenate((self.y, np.zeros((self.order-1)*n)))
		for i, y0_i in enumerate(self.init_kwargs.values()):
				y0[(i+1)*n:(i+2)*n] = self.populate(y0_i)
		sol = scipy.integrate.solve_ivp(self.g, (t0, tf), y0)
		self.t = tf
		self.y = sol.y[:len(self)]
		return self.y

	def reset(self):
		if self.track_other is None:
			self.set_initial(t0=self.t0, y0=self.y0, **self.init_kwargs)
			self.set_boundary(self.dirichlet_values, self.neumann_values)
		else:
			self.set_initial(t0=self.track_other.t0, y0=self.track_other.y0)
			self.set_boundary(self.track_other.dirichlet_values, self.track_other.neumann_values)

	def set_nonphysical(self, f: Callable[[np.ndarray], bool]):
		self.nonphysical = f

	''' Builtins ''' 

	def __len__(self):
		return self.n

	def __call__(self, x: GeoObject):
		return self.y[self.domain[x]]

	''' Rendering ''' 

	def set_render_params(self, palette=cc.fire, lo=0., hi=1., layout_func=None, n_spring_iters=500, show_bar=True):
		self.palette = palette
		self.lo = lo
		self.hi = hi
		self.show_bar=show_bar
		if layout_func is None:
			self.layout_func = lambda G: nx.spring_layout(G, scale=0.9, center=(0,0), iterations=n_spring_iters, seed=1)
		else:
			self.layout_func = layout_func

	def create_plot(self):
		''' Create plot for rendering with Bokeh ''' 
		if self.plot is None:
			G = nx.convert_node_labels_to_integers(self.G) # Bokeh cannot handle non-primitive node keys (eg. tuples)
			self.layout = self.layout_func(G)
			plot = figure(x_range=(-1.1,1.1), y_range=(-1.1,1.1), tooltips=[])
			plot.axis.visible = None
			plot.xgrid.grid_line_color = None
			plot.ygrid.grid_line_color = None
			renderer = from_networkx(G, self.layout)
			plot.renderers.append(renderer)
			self.plot = plot
		return self.plot

	@abstractmethod
	def render(self):
		''' Render current values to the plot ''' 
		pass

''' Observables on specific geometric objects ''' 

class VertexObservable(Observable):

	def init_domain(self):
		self.domain = dict(zip(self.G.nodes(), count()))
		self.laplacian = -nx.laplacian_matrix(self.G)

	def weight(self, x: Vertex, y: Vertex):
		if self.w_key is None:
			return self.default_weight
		else:
			return self.G[x][y][self.w_key]

	def create_plot(self):
		super().create_plot()
		self.plot.renderers[0].node_renderer.data_source.data['node'] = list(self.G.nodes())
		self.plot.renderers[0].node_renderer.data_source.data['node_data'] = self.y 
		self.plot.renderers[0].node_renderer.glyph = Oval(height=0.08, width=0.08, fill_color=linear_cmap('node_data', self.palette, self.lo, self.hi))
		if self.show_bar:
			cbar = ColorBar(color_mapper=LinearColorMapper(palette=self.palette, low=self.lo, high=self.hi), ticker=BasicTicker(), title=self.desc)
			self.plot.add_layout(cbar, 'right')
		self.plot.add_tools(HoverTool(tooltips=[(self.desc, '@node_data'), ('node', '@node')]))
		return self.plot

	def render(self):
		self.plot.renderers[0].node_renderer.data_source.data['node_data'] = self.y


class EdgeObservable(Observable):

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		# Weighted dual graph definition taken from Eq. 6, https://arxiv.org/pdf/0912.4389.pdf
		self.vertex_dual = nx.line_graph(self.G)
		off_diag = 1 - np.eye(len(self))
		inc = nx.incidence_matrix(self.G, oriented=True) # TODO: extract weights
		inv_deg = np.diag([(0. if self.G.degree[x] <= 1 else (1 / self.G.degree[x])) for x in self.G.nodes()])
		self.vertex_dual_adj = inc.T @ inv_deg @ inc @ off_diag

	def init_domain(self):
		self.domain = dict(zip(self.G.edges(), count()))
		self.orientation = np.ones(len(self.G.edges())) # Arbitrarily assign a +1 orientation to the edge ordering stored by networkx

	def weight(self, x: Edge, y: Edge):
		adj, x_i, y_i = self.vertex_dual_adj, self.domain[x], self.domain[y]
		return adj[x_i, y_i]

	def create_plot(self):
		super().create_plot()
		self.plot.renderers[0].edge_renderer.data_source.data['edge_data'] = self.y
		G = nx.convert_node_labels_to_integers(self.G)
		layout_coords = pd.DataFrame(
			[[self.layout[x1][0], self.layout[x1][1], self.layout[x2][0], self.layout[x2][1]] for (x1, x2) in G.edges()],
			columns=['x_start', 'y_start', 'x_end', 'y_end']
		)
		layout_coords['x_end'] = (layout_coords['x_end'] - layout_coords['x_start']) / 2 + layout_coords['x_start']
		layout_coords['y_end'] = (layout_coords['y_end'] - layout_coords['y_start']) / 2 + layout_coords['y_start']
		self.plot.renderers[0].edge_renderer.data_source.data['x_start'] = layout_coords['x_start']
		self.plot.renderers[0].edge_renderer.data_source.data['y_start'] = layout_coords['y_start']
		self.plot.renderers[0].edge_renderer.data_source.data['x_end'] = layout_coords['x_end']
		self.plot.renderers[0].edge_renderer.data_source.data['y_end'] = layout_coords['y_end']
		self.plot.renderers[0].edge_renderer.glyph = MultiLine(line_color=linear_cmap('edge_data', self.palette, self.lo, self.hi), line_width=5)
		if self.show_bar:
			cbar = ColorBar(color_mapper=LinearColorMapper(palette=self.palette, low=self.lo, high=self.hi), ticker=BasicTicker(), title=self.desc)
			self.plot.add_layout(cbar, 'right')
		arrows = Arrow(
			end=VeeHead(size=8), 
			x_start='x_start', y_start='y_start', x_end='x_end', y_end='y_end', line_width=0, 
			source=self.plot.renderers[0].edge_renderer.data_source
		)
		self.plot.add_layout(arrows)
		# self.plot.tooltips.append((self.desc, '@edge_data'))
		return self.plot

	def render(self):
		self.plot.renderers[0].edge_renderer.data_source.data['edge_data'] = self.y
		# TODO: render edge direction using: https://discourse.bokeh.org/t/hover-over-tooltips-on-network-edges/2439/7

	def __call__(self, e: Edge):
		if e in self.orientation:
			return super().__call__(e)
		else:
			return -super().__call__(e)


''' Multiple observables running concurrently on a graph ''' 

class System:
	def __init__(self, observables: List[Observable], desc=''):
		assert len(observables) > 0, 'Pass some observables'
		assert len(observables) == len(set([type(o) for o in observables])), 'Multiple observables on the same domain not currently supported'
		assert all([observables[0].G is o.G for o in observables]), 'All observables must be on the same graph instance'
		self.observables = observables
		self.plot = None
		self.desc = desc

	def create_plot(self):
		for i, p in enumerate(self.observables):
			if i == 0:
				self.plot = p.create_plot()
				self.plot.title.text = self.desc
			else:
				p.plot = self.plot
				p.create_plot()
		return self.plot

	def step(self, dt: float):
		for obs in self.observables:
			obs.step(dt)

	def measure(self) -> List[np.ndarray]:
		return [obs.measure() for obs in self.observables]

	def reset(self):
		for obs in self.observables:
			obs.reset()

	@property
	def t(self) -> float:
		return self.observables[0].t

SerializedSystem = Callable[[], System]
