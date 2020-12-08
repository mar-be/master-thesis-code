import networkx as nx
import random


def karger_algorithm(G, count):
    while len(G.nodes()) > count:
        u, v = random.choices(list(G.nodes()), k=2)
        G = nx.contracted_nodes(G, u, v, self_loops=False)
    return G