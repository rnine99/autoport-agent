"""知识库 — 5 层结构化记忆，持久化在 knowledge_base.json"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass
class Insight:
    content: str
    source: str
    confidence: str = "medium"   # high | medium | low

@dataclass
class FailedApproach:
    description: str
    score: float
    why_failed: str
    node_id: str


class KnowledgeBase:
    def __init__(self, run_dir: str):
        self.path = Path(run_dir) / "knowledge_base.json"
        self.problem: dict = {}
        self.insights: List[Insight] = []
        self.principles: List[str] = []
        self.failures: List[FailedApproach] = []
        self.questions: List[str] = []

    def set_problem(self, K, N_selected, N_Ports, Pt, noise, n_train):
        self.problem = {
            'K': K, 'N_selected': N_selected, 'N_Ports': N_Ports,
            'Pt': f"{Pt:.6g}", 'noise': noise, 'n_train': n_train,
            'grid': f"{int(N_Ports**0.5)}x{int(N_Ports**0.5)}",
        }

    def add_insight(self, content, source, confidence="medium"):
        self.insights.append(Insight(content, source, confidence))

    def add_principle(self, p):
        if p not in self.principles:
            self.principles.append(p)

    def add_failure(self, desc, score, why, node_id):
        self.failures.append(FailedApproach(desc, score, why, node_id))

    def add_question(self, q):
        self.questions.append(q)

    def summary(self, max_insights=5, max_failures=3) -> str:
        lines = ["## Knowledge Base"]
        p = self.problem
        lines.append(f"\n### Problem: {p.get('N_selected',8)} ports from "
                     f"{p.get('N_Ports',64)} ({p.get('grid','8x8')}), "
                     f"{p.get('K',8)} users")

        if self.principles:
            lines.append("\n### Proven Principles:")
            for pr in self.principles:
                lines.append(f"  ✓ {pr}")

        if self.insights:
            for ins in self.insights[-max_insights:]:
                lines.append(f"  • [{ins.confidence}] {ins.content}")

        if self.failures:
            lines.append(f"\n### Failed Approaches ({len(self.failures)}):")
            for fa in self.failures[-max_failures:]:
                s = f"{fa.score:.3f}" if fa.score > float('-inf') else "crashed"
                lines.append(f"  ✗ {fa.description} ({s}): {fa.why_failed}")

        if self.questions:
            lines.append(f"\n### Open Questions:")
            for q in self.questions[-3:]:
                lines.append(f"  ? {q}")

        return "\n".join(lines)

    def save(self):
        data = {
            'problem': self.problem,
            'insights': [{'content': i.content, 'source': i.source,
                          'confidence': i.confidence} for i in self.insights],
            'principles': self.principles,
            'failures': [{'description': f.description, 'score': f.score,
                          'why': f.why_failed, 'node': f.node_id}
                         for f in self.failures],
            'questions': self.questions,
        }
        self.path.write_text(json.dumps(data, indent=2, default=str))

    def load(self):
        if not self.path.exists():
            return
        d = json.loads(self.path.read_text())
        self.problem = d.get('problem', {})
        self.insights = [Insight(**i) for i in d.get('insights', [])]
        self.principles = d.get('principles', [])
        self.failures = [FailedApproach(f['description'], f['score'],
                                         f['why'], f['node'])
                         for f in d.get('failures', [])]
        self.questions = d.get('questions', [])
