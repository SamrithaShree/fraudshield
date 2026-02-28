"""
Temporal Graph Engine
- Directed graph with timestamped edges
- Sliding window subgraph extraction (30-minute window)
- Depth-bounded BFS (≤3 hops) for journey path detection
"""

import networkx as nx
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List, Dict, Optional, Tuple


class TemporalGraphEngine:
    def __init__(self, window_minutes: int = 60, max_depth: int = 4):
        self.graph = nx.MultiDiGraph()
        self.window_minutes = window_minutes
        self.max_depth = max_depth
        self.transactions: List[Dict] = []
        self._ts_index: Dict[str, List[int]] = defaultdict(list)  # account → tx indices

    def add_transaction(self, tx: Dict) -> None:
        """Add transaction to graph and update indices."""
        idx = len(self.transactions)
        self.transactions.append(tx)

        src, dst = tx["source"], tx["destination"]
        ts = datetime.fromisoformat(tx["timestamp"].replace("Z", ""))

        # Add nodes with metadata
        for node, account_type, age, country in [
            (src, tx.get("account_type", "personal"), tx.get("account_age", 365), tx.get("country_code", "IN")),
            (dst, tx.get("account_type", "personal"), tx.get("account_age", 365), tx.get("country_code", "IN"))
        ]:
            if not self.graph.has_node(node):
                self.graph.add_node(node, account_type=account_type, account_age=age, country=country)

        # Add edge
        self.graph.add_edge(
            src, dst,
            transaction_id=tx["transaction_id"],
            amount=tx["amount"],
            timestamp=ts,
            channel=tx["channel"],
            tx_idx=idx
        )

        # Update temporal index
        self._ts_index[src].append(idx)
        self._ts_index[dst].append(idx)

    def get_window_transactions(self, account: str, reference_time: datetime) -> List[Dict]:
        """Get all transactions for an account within 30-minute window."""
        cutoff = reference_time - timedelta(minutes=self.window_minutes)
        result = []
        for idx in self._ts_index.get(account, []):
            tx = self.transactions[idx]
            ts = datetime.fromisoformat(tx["timestamp"].replace("Z", ""))
            if cutoff <= ts <= reference_time:
                result.append(tx)
        return result

    def extract_local_subgraph(self, account: str, reference_time: datetime) -> nx.MultiDiGraph:
        """Extract local subgraph: all transactions in 30-min window touching this account."""
        subgraph = nx.MultiDiGraph()
        cutoff = reference_time - timedelta(minutes=self.window_minutes)
        visited_accounts = set()

        # BFS up to max_depth from the account
        queue = [(account, 0)]
        visited_accounts.add(account)

        while queue:
            current, depth = queue.pop(0)
            if depth >= self.max_depth:
                continue

            # Check outgoing and incoming edges
            for neighbor in list(self.graph.successors(current)) + list(self.graph.predecessors(current)):
                for edge_data in self._get_edges_in_window(current, neighbor, cutoff, reference_time):
                    src = edge_data.get("_src")
                    dst = edge_data.get("_dst")
                    subgraph.add_edge(src, dst, **{k: v for k, v in edge_data.items() if not k.startswith("_")})

                if neighbor not in visited_accounts:
                    visited_accounts.add(neighbor)
                    queue.append((neighbor, depth + 1))

        return subgraph

    def _get_edges_in_window(self, node_a, node_b, cutoff, ref_time):
        """Get edges between node_a and node_b within time window."""
        result = []
        # Check both directions
        for src, dst in [(node_a, node_b), (node_b, node_a)]:
            if self.graph.has_edge(src, dst):
                for key, data in self.graph[src][dst].items():
                    ts = data.get("timestamp")
                    if ts and cutoff <= ts <= ref_time:
                        result.append({**data, "_src": src, "_dst": dst})
        return result

    def bfs_journey_paths(self, account: str, reference_time: datetime) -> List[Dict]:
        """
        Depth-bounded BFS to extract money flow journey paths.
        Returns paths with: hop_count, duration, channel_switches, cashout_flag
        """
        subgraph = self.extract_local_subgraph(account, reference_time)
        paths = []

        def dfs(current, path, edge_chain, visited_in_path, current_time):
            """DFS to find all forward paths."""
            if len(edge_chain) >= self.max_depth:
                return

            for neighbor in subgraph.successors(current):
                if neighbor in visited_in_path:
                    continue
                for key, edata in subgraph[current][neighbor].items():
                    e_ts = edata.get("timestamp")
                    if e_ts and e_ts > current_time:
                        new_path = path + [neighbor]
                        new_edges = edge_chain + [edata]
                        new_visited = visited_in_path | {neighbor}

                        # Record this path
                        if len(new_edges) >= 1:
                            paths.append(self._compute_path_features(
                                path[0], new_path, new_edges
                            ))

                        dfs(neighbor, new_path, new_edges, new_visited, e_ts)

        # Start DFS from the target account and up to 2 levels of predecessors
        start_nodes = {account}
        for pred in subgraph.predecessors(account):
            start_nodes.add(pred)
            for pred2 in subgraph.predecessors(pred):
                start_nodes.add(pred2)
            for pred3 in subgraph.predecessors(pred):
                for pred4 in subgraph.predecessors(pred3):
                    start_nodes.add(pred4)

        for start in start_nodes:
            cutoff = reference_time - timedelta(minutes=self.window_minutes)
            dfs(start, [start], [], {start}, cutoff)

        # Deduplicate and sort by hop_count desc
        seen = set()
        unique_paths = []
        for p in paths:
            key = (p["start"], p["end"], p["hop_count"])
            if key not in seen:
                seen.add(key)
                unique_paths.append(p)

        return sorted(unique_paths, key=lambda x: x["hop_count"], reverse=True)

    def _compute_path_features(self, start: str, path: List[str], edges: List[Dict]) -> Dict:
        """Compute journey features for a detected path."""
        channels = [e.get("channel", "") for e in edges]
        amounts = [e.get("amount", 0) for e in edges]
        timestamps = [e.get("timestamp") for e in edges]

        # Time duration
        duration_minutes = 0
        if len(timestamps) >= 2 and timestamps[0] and timestamps[-1]:
            duration_minutes = (timestamps[-1] - timestamps[0]).total_seconds() / 60

        # Channel switches
        channel_switches = sum(1 for i in range(1, len(channels)) if channels[i] != channels[i-1])

        # Cashout flag: last channel is ATM or "external"
        cashout_flag = channels[-1] == "ATM" if channels else False

        # Unique senders (sources in path)
        unique_senders = len(set(path[:-1]))

        return {
            "start": start,
            "end": path[-1],
            "path": path,
            "hop_count": len(edges),
            "total_time_minutes": round(duration_minutes, 2),
            "channel_sequence": channels,
            "channel_switch_count": channel_switches,
            "unique_senders": unique_senders,
            "cashout_flag": cashout_flag,
            "amount_sequence": amounts,
            "entry_amount": amounts[0] if amounts else 0,
            "exit_amount": amounts[-1] if amounts else 0,
        }

    def get_neighbor_accounts(self, account: str, hops: int = 1) -> List[str]:
        """Get accounts within N hops of target."""
        neighbors = set()
        current_level = {account}
        for _ in range(hops):
            next_level = set()
            for node in current_level:
                if self.graph.has_node(node):
                    next_level.update(self.graph.successors(node))
                    next_level.update(self.graph.predecessors(node))
            next_level -= {account}
            neighbors.update(next_level)
            current_level = next_level
        return list(neighbors)


if __name__ == "__main__":
    engine = TemporalGraphEngine()
    # Quick test
    from datetime import datetime
    tx = {
        "transaction_id": "TXN_TEST001",
        "source": "ACC_A",
        "destination": "ACC_B",
        "amount": 5000,
        "timestamp": "2024-01-15T10:00:00Z",
        "channel": "UPI",
        "account_type": "personal",
        "account_age": 365,
        "country_code": "IN"
    }
    engine.add_transaction(tx)
    print("Graph nodes:", list(engine.graph.nodes()))
    print("Graph edges:", list(engine.graph.edges(data=True)))
    print("✓ Temporal Graph Engine OK")
