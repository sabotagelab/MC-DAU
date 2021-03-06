# -*- coding: utf-8 -*-
"""
Created on Fri May 15 13:43:53 2020

@author: Colin
"""

from tqdm import trange, tqdm
from joblib import Parallel, delayed
from igraph import *
import multiprocessing
import numpy as np
import cvxpy as cp


def generateGraph(num_vertices, prob_edges, min_weight, max_weight):
    # make random graph
    g = Graph.Erdos_Renyi(num_vertices, prob_edges, directed=True, loops=False)
        
    # remove terminal vertices from graph
    g.vs["od"] = g.vs.degree(mode=OUT, loops=False)
    for vertex in g.vs.select(od_lt=2):
        vertex["current"] = True
        # connect a random vertex to this one and this one to another one
        from_vert = np.random.choice(g.vs.select(current_ne=True))
        g.add_edge(from_vert, vertex)
        to_vert = np.random.choice(g.vs.select(current_ne=True))
        g.add_edge(vertex, to_vert)
        vertex["current"] = False
        
    # min and max weight values
    w_min = min_weight
    w_max = max_weight
    
    # find the number of edges, and assign weights
    g.ecount()
    # change to np.random.random for non-integer weights
    weights = np.random.randint(w_min, w_max, g.ecount())
    # weights = (np.random.random(g.ecount()) - 0.5) * 20000.0
    g.es["weight"] = weights
    g.es["label"] = weights

    # plot(g)
    return g



def generateHistories(graph, num_histories, history_len, discount_factor):
    # generate some histories
    weights = graph.es["weight"]
    num_cores = multiprocessing.cpu_count()
    histories = Parallel(n_jobs=num_cores,verbose=5)(delayed(_perHistory)(graph, weights, i, history_len, discount_factor) for i in trange(num_histories))

    return histories
    
    
def _perHistory(graph, weights, i, history_len, discount_factor):
    # perform random walk on given graph, starting at node "1"
    walk = graph.random_walk(0, history_len)
    # perform random walk on given graph, starting from random node
    # walk = graph.random_walk(np.random.randint(0, graph.vcount()))
    edges = []
    # compute accumulated value of the walk
    value = 0
    for depth in range(len(walk)-1):
        from_vertex = walk[depth]
        to_vertex = walk[depth + 1]
        edge_tuple = ([from_vertex], [to_vertex])
        edge = graph.es.find(_between=edge_tuple)
        factor = discount_factor ** depth
        edge_weight = weights[edge.index]
        value += factor * edge_weight
        edges.append(edge.index)
    return [edges, value]
    
    
def solveWeights(graph, histories, discount_factor):
    # make list of edges, whose weights will be solved for
    weights = cp.Variable(graph.ecount())
    
    # create value equations for each history
    values = np.zeros((len(histories), graph.ecount()))
    for h, history in tqdm(enumerate(histories)):
        word = history[0]
        for depth, edge in enumerate(word):
            factor = discount_factor ** depth
            values[h, edge] += factor

    sums = np.array(histories)[:, 1]

    val_w = values @ weights
    cost = cp.sum_squares(val_w - sums)
    
    prob = cp.Problem(cp.Minimize(cost))
    prob.solve()

    norm = cp.norm(weights.value - graph.es["weight"], p=2).value
    # Print result.
    print("\nThe optimal value is", prob.value)
    print("The optimal x is")
    print(weights.value)
    print("The norm of the residual is ", norm)
    print(prob.status)
    return {"optimal": prob.value, "weights": weights.value, "values": values,
            "norm": norm, "status": prob.status}


if __name__ == "__main__":
    g = generateGraph(5, 0.5, -5.0, 5.0)
    # h = generateHistories(g, 1000, 3000, 0.5)
    # solveWeights(g, h, 0.5)
