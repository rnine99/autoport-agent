"""
SearchGraph — DAG 搜索图

所有算法节点永久保留，支持多 parent（crossover），可追溯进化路径。
数据持久化在 {run_dir}/graph.json + {run_dir}/algorithms/*.py
"""

import json
import hashlib
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List
import numpy as np


@dataclass
class Node:
    id: str
    code: str
    thought: str                 # 算法思路简述
    score: float
    status: str                  # "valid" | "error"
    error_msg: str = ""
    parent_ids: list = field(default_factory=list)
    operator: str = ""           # draft | improve | crossover | debug | baseline
    instance_scores: list = field(default_factory=list)
    direction: str = ""          # agent 给的具体指令
    debug_attempts: int = 0
    code_hash: str = ""

    def __post_init__(self):
        if not self.code_hash and self.code:
            self.code_hash = hashlib.md5(self.code.encode()).hexdigest()[:12]


class SearchGraph:
    def __init__(self, run_dir: str):
        self.run_dir = Path(run_dir)
        self.algo_dir = self.run_dir / "algorithms"
        self.algo_dir.mkdir(parents=True, exist_ok=True)
        self.nodes: dict[str, Node] = {}
        self._next = 0

    def add(self, code: str, thought: str, score: float, status: str,
            error_msg="", parent_ids=None, operator="",
            instance_scores=None, direction="") -> Node:

        ch = hashlib.md5(code.encode()).hexdigest()[:12]
        for n in self.nodes.values():
            if n.code_hash == ch:
                return n  # 去重

        nid = f"n_{self._next:03d}"
        self._next += 1

        node = Node(
            id=nid, code=code, thought=thought, score=score,
            status=status, error_msg=error_msg,
            parent_ids=parent_ids or [], operator=operator,
            instance_scores=list(instance_scores) if instance_scores is not None else [],
            direction=direction, code_hash=ch,
        )
        self.nodes[nid] = node

        # 保存代码文件
        s = f"{score:.4f}" if score > float('-inf') else "failed"
        (self.algo_dir / f"{nid}_{operator}_{s}.py").write_text(code)
        return node

    def best(self) -> Optional[Node]:
        valid = [n for n in self.nodes.values() if n.status == "valid"]
        return max(valid, key=lambda n: n.score) if valid else None

    def leaderboard(self, k=10) -> List[Node]:
        valid = [n for n in self.nodes.values() if n.status == "valid"]
        return sorted(valid, key=lambda n: n.score, reverse=True)[:k]

    def get(self, nid: str) -> Optional[Node]:
        return self.nodes.get(nid)

    def failed_debuggable(self, max_attempts=3) -> List[Node]:
        return [n for n in self.nodes.values()
                if n.status == "error" and n.debug_attempts < max_attempts]

    def lineage(self, nid: str) -> List[Node]:
        path, seen = [], set()
        cur = self.nodes.get(nid)
        while cur and cur.id not in seen:
            seen.add(cur.id)
            path.append(cur)
            cur = self.nodes.get(cur.parent_ids[0]) if cur.parent_ids else None
        return list(reversed(path))

    def summary(self, top_k=5) -> str:
        lb = self.leaderboard(top_k)
        total = len(self.nodes)
        valid = sum(1 for n in self.nodes.values() if n.status == "valid")
        failed = total - valid

        lines = [f"## Search Graph: {total} nodes ({valid} valid, {failed} failed)"]
        if lb:
            lines.append(f"\n### Leaderboard (top {len(lb)}):")
            for i, n in enumerate(lb):
                p = f" ← {n.parent_ids}" if n.parent_ids else " (seed)"
                lines.append(f"  #{i+1} [{n.id}] score={n.score:.4f} op={n.operator}{p}")
                if n.thought:
                    lines.append(f"       idea: {n.thought[:100]}")
                if n.instance_scores:
                    sc = np.array(n.instance_scores)
                    lines.append(f"       min={np.min(sc):.3f} std={np.std(sc):.3f}")

        dbg = self.failed_debuggable()
        if dbg:
            lines.append(f"\n### Debuggable ({len(dbg)} nodes):")
            for n in dbg[:3]:
                lines.append(f"  [{n.id}] {n.error_msg[:80]}")

        return "\n".join(lines)

    def save(self):
        data = {}
        for nid, n in self.nodes.items():
            data[nid] = {
                'id': n.id, 'score': n.score, 'status': n.status,
                'operator': n.operator, 'parent_ids': n.parent_ids,
                'thought': n.thought, 'code_hash': n.code_hash,
                'error_msg': n.error_msg[:100], 'direction': n.direction[:100],
                'instance_scores_summary': {
                    'mean': float(np.mean(n.instance_scores)) if n.instance_scores else None,
                    'min': float(np.min(n.instance_scores)) if n.instance_scores else None,
                    'std': float(np.std(n.instance_scores)) if n.instance_scores else None,
                } if n.instance_scores else None,
            }
        (self.run_dir / "graph.json").write_text(json.dumps(data, indent=2))

    def load(self):
        path = self.run_dir / "graph.json"
        if not path.exists():
            return
        # Load graph.json + algorithm files for resume
        data = json.loads(path.read_text())
        for nid, info in data.items():
            # Try to find matching algorithm file
            pattern = f"{nid}_*"
            algo_files = list(self.algo_dir.glob(pattern))
            code = algo_files[0].read_text() if algo_files else ""
            node = Node(
                id=nid, code=code, thought=info.get('thought', ''),
                score=info['score'], status=info['status'],
                error_msg=info.get('error_msg', ''),
                parent_ids=info.get('parent_ids', []),
                operator=info.get('operator', ''),
                code_hash=info.get('code_hash', ''),
                direction=info.get('direction', ''),
            )
            self.nodes[nid] = node
            self._next = max(self._next, int(nid.split('_')[1]) + 1)
