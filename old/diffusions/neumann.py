import networkx as nx
import numpy as np
import matplotlib.pyplot as plt
from scipy.sparse import csc_matrix
from scipy.sparse.linalg import expm
import pdb
import seaborn as sns
from itertools import repeat

from utils import set_seed
from diffusions.lib import *

set_seed(1001)

""" Regular grid example """
n = 7
G = nx.grid_2d_graph(n,n)

# Boundary
dS = [(i,0) for i in range(n)] + [(i,n-1) for i in range(n)] + [(0,j) for j in range(n)] + [(n-1,j) for j in range(n)]

# Initial condition: no internal heat
u0 = np.zeros(n*n)

# Increasingly heated boundary
bc = dict(zip(dS, repeat(0.1)))

# Solve
u = solve_exact(G, u0, neumann_bc=bc)

# Plot snapshots
plot_snapshots(G, u, 1.0, 5)


plt.show()