import networkx as nx
from collections.abc import Iterable
from collections import defaultdict, Counter


from .Drawing import draw
import numpy as np


class Genealogical(object):

    def __init__(self, graph=None):
        if graph is None:
            self.graph = nx.DiGraph()
        else:
            self.graph = graph

    @property
    def n_individuals(self):
        return len(self.nodes)

    @property
    def edges(self):
        return list(self.graph.edges())

    @property
    def nodes(self):
        return list(self.graph.nodes())

    @property
    def attributes(self):
        return list(list(self.graph.nodes(data=True))[0][1].keys())

    def get_edge_attributes(self, attr):
        return nx.get_edge_attributes(self.graph, attr)

    def siblings(self, node):
        """
        Get the siblings of node `node`
        :param node:
        :return:
        """
        return list(set([
            child for parent in self.predecessors(node)
            for child in self.successors(parent) if child != node
        ]))

    def parents(self, node):
        return list(self.graph.predecessors(node))

    def predecessors(self, node, k=1, include_intermediates=False, include_founders=False):
        """
        Get predecessors that are up to `k` steps away from `node`. If `include_intermediates`
        is true, this method also returns nodes that are <`k` steps away from `node`. If
        `include_founders` is True, this method returns founders that are less than `k`
        steps away from `node`.
        """

        predecessors = nx.single_source_shortest_path_length(self.graph.reverse(), node,
                                                             cutoff=k)

        if include_intermediates:
            return list(predecessors.keys())
        else:

            pred_list = []

            for nn, dist in predecessors.items():
                if dist == k:
                    pred_list.append(nn)
                elif include_founders and len(self.graph.predecessors(nn)) == 0:
                    pred_list.append(nn)

            return pred_list

    def successors(self, node, k=1, include_intermediates=False, include_leaves=False):
        """
        Get successors that are up to `k` steps away from `node`. If `include_intermediates`
        is true, this method also returns nodes that are <`k` steps away from `node`. If
        `include_leaves` is True, this method returns leaves that are less than `k`
        steps away from `node`.
        """

        successors = nx.single_source_shortest_path_length(self.graph, node,
                                                           cutoff=k)

        if include_intermediates:
            return list(successors.keys())
        else:

            succ_list = []

            for nn, dist in successors.items():
                if dist == k:
                    succ_list.append(nn)
                elif include_leaves and len(self.graph.successors(nn)) == 0:
                    succ_list.append(nn)

            return succ_list

    def filter_nodes(self, predicate):
        node_list = []
        for node, data in self.graph.nodes(data=True):
            if predicate(node, data):
                node_list.append(node)
        return node_list

    def get_node_attributes(self, attr, node=None):

        node_attr = nx.get_node_attributes(self.graph, attr)

        if node is None:
            return node_attr
        else:
            try:
                return node_attr[node]
            except KeyError:
                return {}

    def nodes_at_generation_view(self, k):
        time = self.get_node_attributes('time')
        G = self.graph
        return nx.subgraph_view(G, lambda n: time[n] == k)

    def nodes_at_generation(self, k):
        return list(self.nodes_at_generation_view(k).nodes)        

    def founders_view(self):
        G = self.graph
        return nx.subgraph_view(G, lambda n: not any(G.predecessors(n)))

    def founders(self):
        """
        Get a list of nodes that don't have predecessors
        """
        return list(self.founders_view().nodes)

    def probands_view(self):
        G = self.graph
        return nx.subgraph_view(G, lambda n: not any(G.successors(n)))
        
    def probands(self):
        """Get a list of individuals with no children"""
        return list(self.probands_view().nodes)

    def trace_edges(self, forward=True, source=None):
        """Trace edges in a breadth-first-search
        Yields a pair of `(node, neighbor)`
        Note:
        Note that the same edge can appear in the tracing more than once
        For `forward=True` iteration, start at founders (nodes with no predecessors), and yield `(node, child)` pairs
        For `forward=False` iteration, start at probands (nodes with no successors), and yeild `(node, parent)` pairs.
        Optional `source` argument can be used to specify the starting nodes
        
        Parameters
        ----------
        forward: boolean
            Direction of iteration:
            - `Forward=True` - from parents to children, yielding `(node, child)` pairs
            - `Forward=False` - from children to parents, , yielding `(node, parent)` pairs
        source: [int]
            Iterable of node IDs to initialize the iteration. By default, direction-specific source nodes are chosen
        
        Yields
        -------
        pair of `(node, neighbor)` node IDs, for each edge
        """
        if source is None:
            if forward:
                source = self.founders_view().nodes
            else:
                source = self.probands_view().nodes

        neighbors = self.graph.successors if forward else self.graph.predecessors
        
        curr_gen = set(source)
        next_gen = set()

        while curr_gen:
            for node in curr_gen:
                for neighbor in neighbors(node):
                    yield node, neighbor
                    next_gen.add(neighbor)
            curr_gen = next_gen
            next_gen = set()

    def infer_depth(self, forward=True):
        """Infer depth of each node.

        If ``forward=True``, founders (nodes without parents) have depth ``0``, each child: ``1 +
        max(parental_depth)``

        If ``forward=False``, probands (nodes without children) have depth ``0``, each parent: ``1 +
        max(children_depth)``


        Args:
            forward=True: start at founders (no parents in pedigree), iterate descendants (down)
            forward=False: start at probands (no children in pedigree), iterate parents (up)

        Returns:
            dict: mapping from nodes to depth

        """
        depth = defaultdict(int)
        # forward is in the first (default) argument to trace_edges()
        for node, child in self.trace_edges(forward=forward):
            d = depth[node]            
            if depth[child] <= d:
                depth[child] = d + 1

        return depth

    def iter_edges(self, forward=True, source=None):
        """Iterate all the edges of the genealogy, yielding each edge exactly once"""
        visited_edges = set()
        if source is None:
            if forward:
                source = self.founders_view().nodes
            else:
                source = self.probands_view().nodes

        neighbors = self.graph.successors if forward else self.graph.predecessors

        for node, neighbor in self.trace_edges(forward, source):
            if (node, neighbor) not in visited_edges:
                visited_edges.add((node, neighbor))
                yield node, neighbor

    def iter_nodes(self, forward=True, source=None):
        if source is None:
            if forward:
                source = self.founders_view().nodes
            else:
                source = self.probands_view().nodes

        visited_nodes = set()
        # iterate source
        for node in source:
            if node not in visited_nodes:
                visited_nodes.add(node)
                yield node
        # iterate neighbors (child or parent of each node, depending on direction)
        for _, node in self.iter_edges(forward, source):
            if node not in visited_nodes:
                visited_nodes.add(node)
                yield node

    def get_num_paths_to_target(self, target=None, include_target=True):
        """
        Get the number of paths connecting all nodes in a Genealogical object
        to the `target` nodes. If `target` is None, use the probands
        by default.

        This method is an optimized version of the `get_probands_under()` method,
        with O(n) runtime.
        """

        if target is None:
            target = self.probands()
        elif not isinstance(target, Iterable) or type(target) == str:
            target = [target]

        pts = {}
        nodes = self.infer_depth()

        for n in sorted(nodes, key=nodes.get, reverse=True):

            n_succ = self.successors(n)

            if n in target:
                pts[n] = {n: 1}
            elif len(n_succ) == 0:
                pts[n] = {}
            else:

                pts[n] = sum(
                    (Counter(pts[suc]) for suc in n_succ),
                    Counter()
                )

        pts = {k: dict(v) for k, v in pts.items() if len(v) > 0}

        if not include_target:
            for t in target:
                del pts[t]

        return pts

    def get_probands_under(self, nodes=None, climb_up_step=0):

        if nodes is None:
            nodes = self.nodes
        elif not isinstance(nodes, Iterable) or type(nodes) == str:
            nodes = [nodes]

        ntp = {}  # Nodes to probands

        for n in nodes:

            ntp[n] = set()

            base_set = self.predecessors(n, climb_up_step, include_founders=True)
            n_set = []
            for ns in base_set:
                n_set += self.successors(ns)

            if len(n_set) == 0:
                ntp[n].add(n)
            else:
                while len(n_set) > 0:
                    nn, nn_children = n_set[0], self.successors(n_set[0])

                    if len(nn_children) > 0:
                        n_set.extend(nn_children)
                    else:
                        ntp[n].add(nn)

                    del n_set[0]

        return ntp

    def draw(self, **kwargs):
        return draw(self.graph, **kwargs)

    def similarity(self):
        # A kinship-like distance function
        n = self.n_individuals        
        K = np.zeros((n,n), dtype=float)

        for i in range(n):
            K[i,i] = 0.5
            for j in range(i+1, n):
                # this should not be necessary
                if any(self.graph.predecessors(j)):
                    p = next(self.graph.predecessors(j))
                    K[i,j] = (K[i,p]/2)
                    K[j,i] = K[i,j]
        return K
