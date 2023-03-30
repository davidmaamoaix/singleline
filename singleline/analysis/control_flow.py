import ast
import networkx as nx
from enum import Enum, auto
from typing import List, Tuple

from ..misc.types import VRet


class CFGLabels(Enum):
    """
    An enumeration of all possible labels in case a branching occurs at
    a node in the CFG.

    For instance, the `ast.If` node can have two outgoing edges labeled
    as `CFGLabels.IF` and `CFGLabels.ELSE`.
    """

    IF = auto()
    ELSE = auto()


# A hashable wrapper for `List[ast.AST]`.
# TODO: fix the types that involves `NodeBundle` (currently incorrect)
class NodeBundle:

    bundle: List[ast.AST]

    def __init__(self, bundle: List[ast.AST] = None):
        if bundle is None: bundle = []

        self.bundle = bundle

    def append(self, node: ast.AST):
        self.bundle.append(node)

    def flatten(self):
        self.bundle = NodeBundle._flatten(self.bundle)

    def is_empty(self) -> bool:
        return len(self.bundle) == 0

    @staticmethod
    def _flatten(xs: any) -> List[any]:
        res = []
        for x in xs:
            if isinstance(x, list):
                res.extend(NodeBundle.flatten(x))
            else:
                res.append(x)

        return res


class ControlFlowGraph:
    """
    Generates the control flow graph of the source program so that lambda
    and branching structures can be determined statically.
    """

    graph: nx.classes.DiGraph

    def __init__(self):
        self.graph = nx.classes.DiGraph()

        # entry point
        self.graph.add_node('main')

    def _analysis_pass(self, code: List[ast.AST]) -> Tuple(ast.AST, [ast.AST]):
        """
        Builds the control flow graph for a portion of code.

        Returns a tuple:
            - fst: the first node of the sub-graph representing the give code
            - snd: a list of all the possible ending nodes of the sub-graph

        Note that if a branch of the graph ends in a `return`, `break` or `continue`,
        it is treated as a "dead-end" ad will not be included in the out-flowing nodes
        of the sub-graph (i.e., the second value of the returned tuple).
        """

        code_segments = [NodeBundle()]
        interrupt = False
        for node in code:
            if ControlFlowGraph._is_compound_node(node):
                code_segments.append(node)
                code_segments.append(NodeBundle())
            else:
                code_segments[-1].append(node)

            if ControlFlowGraph._is_interrupt_node(node):
                interrupt = True
                break

        first = None # Entry node for `code`.
        prev = None # Out-flowing nodes from the previous block.

        for i in code_segments:
            curr_in, curr_out = self._expand_single_node(i)
            if first is None:
                first = curr_in
            
            if prev is not None:
                for in_node in prev:
                    self.graph.add_edge(in_node, curr_in)
            
            prev = curr_out

        # Dummy control-flow node.
        if first is None:
            node = NodeBundle()
            self.graph.add_node(node)
            return (node, [node])
        
        return (first, [] if interrupt else prev)
    
    def _expand_single_node(self, node) -> Tuple(ast.AST, [ast.AST]):
        """
        Adds the control-flow graph of `node` as a separate, disconnected
        sub-graph to `self.graph`, and returns the entry node and list of
        out-flowing nodes of the generated graph to be connected to the rest
        of the control-flow graph.
        """

        if isinstance(node, NodeBundle): # Straight line code.
            self.graph.add_node(node)
            return (node, [node])
        elif isinstance(node, ast.If): # If statement.
            self.graph.add_node(node)
            if_in, if_out = self._analysis_pass(node.body)
            else_in, else_out = self._analysis_pass(node.orelse)

            self.graph.add_edge(node, if_in, label=CFGLabels.IF)
            self.graph.add_edge(node, else_in, label=CFGLabels.ELSE)

            return (node, if_out + else_out)
        elif isinstance(node, ast.While):
            raise NotImplementedError
        elif isinstance(node, ast.For):
            raise NotImplementedError

    @staticmethod
    def _is_compound_node(node: ast.AST):
        types = [ast.If, ast.For, ast.While]
        return not any(isinstance(node, t) for t in types)
    
    @staticmethod
    def _is_interrupt_node(node: ast.AST):
        types = [ast.Break, ast.Continue, ast.Return]
        return any(isinstance(node, t) for t in types)
