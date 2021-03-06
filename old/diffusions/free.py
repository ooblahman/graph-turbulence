import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import expm
import pdb
import seaborn as sns

from utils import set_seed
from diffusions.lib import *

set_seed(1001)

""" Regular grid example """
n = 7
G = nx.grid_2d_graph(n,n)

# Initial condition: single heated node
u0 = np.zeros(n*n)
u0[np.random.randint(0,n**2)] = 1.0

# Solve
u = solve_exact(G, u0)

# Plot snapshots
# plot_snapshots(G, u, 1.0, 5, absolute_colors=False)
plot_live(G, u, 2.0, dt=0.01)

plt.show()