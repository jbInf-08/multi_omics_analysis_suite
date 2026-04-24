"""
Asynchronous / synchronous Boolean network helpers.

Intended for small teaching models; large attractor searches should use
specialized tools or reduce the network before exhaustive enumeration.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Dict, Iterable, List, Literal, Optional, Tuple


RegMode = Literal["AND", "OR"]


@dataclass(frozen=True)
class Regulation:
    target: str
    sources: Tuple[str, ...]
    mode: RegMode = "AND"


class BooleanNetwork:
    """
    Update selected targets from regulator species with AND/OR semantics.
    Nodes not appearing as any ``target`` are pass-through (copied from state).
    """

    def __init__(self, regulations: Iterable[Regulation]):
        self.regulations: Tuple[Regulation, ...] = tuple(regulations)

    def nodes(self) -> List[str]:
        seen = set()
        order: List[str] = []
        for r in self.regulations:
            for n in (*r.sources, r.target):
                if n not in seen:
                    seen.add(n)
                    order.append(n)
        return order

    def step(self, state: Dict[str, int]) -> Dict[str, int]:
        new = dict(state)
        for r in self.regulations:
            vals = [int(bool(state.get(s, 0))) for s in r.sources]
            if r.mode == "AND":
                val = 1 if vals and all(v == 1 for v in vals) else 0
            else:
                val = 1 if any(v == 1 for v in vals) else 0
            new[r.target] = val
        return new


class BooleanSimulation:
    """Iterate a :class:`BooleanNetwork` from an initial binary state."""

    def __init__(self, network: BooleanNetwork, initial: Optional[Dict[str, int]] = None):
        self.network = network
        base = {n: 0 for n in network.nodes()}
        if initial:
            base.update({k: 1 if v else 0 for k, v in initial.items()})
        self.state = base

    def run(self, steps: int = 20) -> List[Dict[str, int]]:
        traj: List[Dict[str, int]] = [dict(self.state)]
        for _ in range(max(0, steps)):
            self.state = self.network.step(self.state)
            traj.append(dict(self.state))
        return traj


class AttractorAnalysis:
    """Exhaustive state-space scan for networks with at most ``max_nodes`` binary nodes."""

    @staticmethod
    def _bits_from_state(state: Dict[str, int], nodes: List[str]) -> Tuple[int, ...]:
        return tuple(int(bool(state[n])) for n in nodes)

    @classmethod
    def find_attractors(
        cls,
        network: BooleanNetwork,
        max_nodes: int = 14,
    ) -> Dict[str, object]:
        nodes = network.nodes()
        if len(nodes) > max_nodes:
            return {
                "ok": False,
                "reason": "too_many_nodes",
                "n_nodes": len(nodes),
                "max_nodes": max_nodes,
            }

        all_bits = list(product((0, 1), repeat=len(nodes)))
        index = {bits: i for i, bits in enumerate(all_bits)}
        edges: List[int] = []
        for bits in all_bits:
            st = {n: b for n, b in zip(nodes, bits)}
            nxt = network.step(st)
            nkey = cls._bits_from_state(nxt, nodes)
            edges.append(index[nkey])

        n_states = len(all_bits)
        attractor_signatures: set[frozenset[Tuple[int, ...]]] = set()
        attractors: List[List[Tuple[int, ...]]] = []

        for start in range(n_states):
            path: List[int] = []
            pos: Dict[int, int] = {}
            cur = start
            while cur not in pos:
                pos[cur] = len(path)
                path.append(cur)
                cur = edges[cur]
            cycle = path[pos[cur] :]
            sig = frozenset(all_bits[i] for i in cycle)
            if sig not in attractor_signatures:
                attractor_signatures.add(sig)
                attractors.append([all_bits[i] for i in cycle])

        return {
            "ok": True,
            "n_states": n_states,
            "attractor_state_tuples": attractors,
            "nodes": nodes,
        }
