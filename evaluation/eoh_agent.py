"""
EoH Agent v2 — Agent-Driven Algorithm Design Engine

vs v1 的改进:
  1. OFE 追踪和 baseline 完全对齐（全局计数器包装 SINR）
  2. 新增 ablate operator（组件消融测试）
  3. 新增 reflect operator（阶段性总结，提炼 design principles）
  4. 输出 trajectory CSV，可直接画 OFE vs score 对比图
  5. 更好的 stagnation 处理（连续无改善 → 自动触发 analyze/reflect）
  6. 清晰的 per-round OFE/LLM 日志

用法:
    cd evaluation/
    python eoh_agent.py --quick                    # 500 OFE 快速测试
    python eoh_agent.py --budget 3000              # 3000 OFE
    python eoh_agent.py --budget 5000 --model deepseek-chat

对比实验:
    python eoh_agent.py --budget 750000            # 和 baseline 同预算
"""

import os
import sys
import json
import time
import io
import re
import contextlib
import argparse
import numpy as np
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from evaluate_detailed import (
    DetailedEvaluator, EvalResult, extract_code,
    get_ofe, reset_ofe,
)
from search_graph import SearchGraph, Node
from knowledge_base import KnowledgeBase
from baselines import ALL_BASELINES


# ============ LLM Client ============

class LLMClient:
    """OpenAI-compatible LLM 调用"""

    def __init__(self, api_key=None, model="deepseek-chat",
                 base_url="https://api.deepseek.com", temperature=0.7):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.calls = 0
        self.tokens = 0

    def generate(self, prompt: str, system: str = None, temperature: float = None) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})

        resp = client.chat.completions.create(
            model=self.model, messages=msgs,
            temperature=temperature or self.temperature,
            max_tokens=3000,
        )
        self.calls += 1
        if resp.usage:
            self.tokens += resp.usage.total_tokens
        return resp.choices[0].message.content


# ============ Budget ============

class Budget:
    def __init__(self, max_ofe=5000, max_llm=200):
        self.max_ofe = max_ofe
        self.max_llm = max_llm
        self.llm = 0
        self.t0 = time.time()

    @property
    def ofe(self):
        """OFE 从全局计数器读取（包含算法内部 SINR 调用）"""
        return get_ofe()

    def use_llm(self):
        self.llm += 1

    def done(self):
        return self.ofe >= self.max_ofe or self.llm >= self.max_llm

    def summary(self):
        elapsed = time.time() - self.t0
        return (f"## Budget: OFE {self.ofe}/{self.max_ofe} "
                f"({self.ofe/self.max_ofe*100:.0f}%), "
                f"LLM {self.llm}/{self.max_llm}, "
                f"{elapsed:.0f}s elapsed")


# ============ Operator Prompts ============

SYSTEM = """You are an expert algorithm designer for wireless port selection.
RULES:
1. ONLY import numpy (as np). NO scipy/sklearn/etc.
2. def select_ports(K, N_selected, N_Ports, Pt, n, H_current, noise) → (n, N_selected) int array
3. H_current: (n, N_Ports, K) complex channel matrix
4. Each row: N_selected unique indices in [0, N_Ports-1]
5. sinr_balancing_power_constraint(N_selected, K, H_sub, Pt, noise) is available to call.
6. WARNING: Each call to sinr_balancing_power_constraint costs 1 OFE. Budget-aware algorithms preferred."""


def prompt_draft(kb_summary, direction):
    return f"""{kb_summary}

## Task: Design a NEW algorithm from scratch.
## Direction: {direction}
## Output: Complete Python function only. No explanation."""


def prompt_improve(parent_code, parent_score, diagnosis, kb_summary, directive):
    return f"""{kb_summary}

## Current Algorithm (score={parent_score:.4f}):
```python
{parent_code}
```

## Diagnosis:
{diagnosis}

## Improvement: {directive}
## Output: Improved function only. No explanation."""


def prompt_crossover(code_a, score_a, code_b, score_b, kb_summary, directive):
    return f"""{kb_summary}

## Algorithm A (score={score_a:.4f}):
```python
{code_a}
```
## Algorithm B (score={score_b:.4f}):
```python
{code_b}
```
## Crossover: {directive}
## Output: New combined function only. No explanation."""


def prompt_debug(code, error, attempt):
    return f"""## Faulty Code (attempt {attempt}/3):
```python
{code}
```
## Error: {error}
## Fix it. Keep the algorithmic idea. Output fixed function only."""


def prompt_ablate(code, score):
    return f"""## Algorithm (score={score:.4f}):
```python
{code}
```

## Task: Identify the 2-3 key components/techniques in this algorithm.
For each component, create a simplified version WITHOUT it (ablation).

Return EXACTLY this format:
COMPONENT_1: <name>
```python
<ablated code without component 1>
```
COMPONENT_2: <name>
```python
<ablated code without component 2>
```"""


def prompt_reflect(kb_summary, graph_summary, recent_log):
    return f"""{graph_summary}

{kb_summary}

## Recent Actions:
{recent_log}

## Task: Synthesize what we've learned into 2-3 high-level design principles.
Each principle should be a specific, actionable guideline for algorithm design.

Also identify 1-2 promising directions we haven't tried yet.

Format:
PRINCIPLE: <specific guideline>
PRINCIPLE: <specific guideline>
DIRECTION: <unexplored approach>"""


def prompt_decide(state):
    return f"""{state}

You are the experiment manager. Pick the SINGLE best next action.

Operators:
- draft: New algorithm from scratch (specify direction)
- improve <node_id>: Refine existing (specify what to change)
- crossover <node_a> <node_b>: Combine two algorithms
- debug <node_id>: Fix a failed algorithm
- analyze: Run analysis code on channel data (0 OFE cost)
- ablate <node_id>: Test which components matter (costs OFE but produces insights)
- reflect: Consolidate insights into principles (0 OFE cost)

Strategy:
- Stagnating >5 rounds? → reflect then try fresh direction or analyze
- Stagnating >3 rounds? → analyze or ablate best to understand why stuck
- Best improving? → keep improving best
- Two different high-scoring approaches? → crossover
- Debuggable failures with good ideas? → debug them
- Low budget (<20%)? → improve current best only
- After major insight? → draft new algorithm using it

RESPOND EXACTLY:
OPERATOR: <name>
TARGET: <node_id(s) or none>
DIRECTION: <1-2 sentence specific instruction>"""


# ============ Agent Engine ============

class EoHAgent:
    """
    Agent-Driven Algorithm Design Engine v2

    主要改进:
    1. OFE 从全局计数器读取 → 和 baseline 公平对比
    2. 新增 ablate（消融测试）和 reflect（阶段性总结）operator
    3. trajectory CSV 输出
    4. 更好的 stagnation 处理
    """

    def __init__(self, llm: LLMClient, evaluator: DetailedEvaluator,
                 run_dir: str, budget: Budget):
        self.llm = llm
        self.ev = evaluator
        self.run_dir = Path(run_dir)
        self.run_dir.mkdir(parents=True, exist_ok=True)

        self.graph = SearchGraph(run_dir)
        self.kb = KnowledgeBase(run_dir)
        self.budget = budget

        self.kb.set_problem(evaluator.K, evaluator.N_selected, evaluator.N_Ports,
                            evaluator.Pt, evaluator.noise, evaluator.n)

        self.round = 0
        self.stagnation = 0
        self.log = []

        # Best score trajectory: [(ofe, best_score, llm_calls, timestamp)]
        self.best_trajectory = []
        self._t0 = time.time()

    # ===== Main Loop =====

    def run(self):
        print("=" * 60)
        print("EoH Agent v2 — Research-Driven Algorithm Design")
        print("=" * 60)
        print(f"Budget: OFE={self.budget.max_ofe}, LLM={self.budget.max_llm}")
        print(f"Problem: K={self.ev.K}, N_Ports={self.ev.N_Ports}, select {self.ev.N_selected}")
        print(f"Model: {self.llm.model}")
        print("=" * 60)

        self._phase0_analyze()
        self._phase1_seed()

        print("\n" + "=" * 60)
        print("Phase 2: Agent Search")
        print("=" * 60)

        while not self.budget.done():
            self.round += 1
            state = "\n\n".join([
                self.graph.summary(5), self.kb.summary(),
                self.budget.summary(),
                f"Round {self.round}, stagnation={self.stagnation}",
                "Recent: " + " | ".join(self.log[-5:]) if self.log else "",
            ])

            # Agent 决策
            self.budget.use_llm()
            resp = self.llm.generate(prompt_decide(state))
            decision = self._parse(resp)
            print(f"\n--- R{self.round} [{decision['op']}] "
                  f"OFE={self.budget.ofe} ---")
            print(f"  {decision['dir'][:80]}")

            # 执行
            node = self._execute(decision)

            # 学习
            if node:
                self._learn(node, decision)

            # 记录 best trajectory
            b = self.graph.best()
            self.best_trajectory.append({
                'ofe': self.budget.ofe,
                'best_score': b.score if b else float('-inf'),
                'llm_calls': self.budget.llm,
                'timestamp': time.time() - self._t0,
            })

            # Checkpoint
            if self.round % 5 == 0:
                self._checkpoint()

        self._finish()

    # ===== Phase 0: Problem Analysis =====

    def _phase0_analyze(self):
        print("\nPhase 0: Analyzing channel structure...")
        H = self.ev.get_H_train()
        n, N_Ports, K = H.shape

        # Port correlation vs spacing
        for sp in [1, 2, 4, 8]:
            corrs = []
            for i in range(min(N_Ports - sp, 20)):
                c = abs(np.vdot(H[0, i], H[0, i + sp])) / (
                    np.linalg.norm(H[0, i]) * np.linalg.norm(H[0, i + sp]) + 1e-10)
                corrs.append(c)
            mc = np.mean(corrs)
            print(f"  spacing={sp}: correlation={mc:.3f}")
            if mc > 0.5:
                self.kb.add_insight(
                    f"Spacing {sp}: high correlation ({mc:.2f}), need wider spacing",
                    "channel_analysis", "high")

        # Per-user quality
        user_norms = [np.mean([np.linalg.norm(H[j, :, k]) for j in range(n)])
                      for k in range(K)]
        weak = np.argsort(user_norms)[:2]
        self.kb.add_insight(
            f"Weakest users: {list(weak)} (norms: {[f'{user_norms[w]:.2f}' for w in weak]}). "
            f"These are min-SINR bottleneck.",
            "channel_analysis", "high")

        # Channel condition number distribution
        conds = [np.linalg.cond(H[j]) for j in range(n)]
        self.kb.add_insight(
            f"Channel condition number: mean={np.mean(conds):.1f}, "
            f"max={np.max(conds):.1f}. High condition = ill-conditioned → "
            f"port selection affects beamforming quality significantly.",
            "channel_analysis", "medium")

        print(f"  → {len(self.kb.insights)} insights from channel analysis")

    # ===== Phase 1: Seed =====

    def _phase1_seed(self):
        print("\nPhase 1: Seeding baselines")
        for name, code in ALL_BASELINES:
            if self.budget.done():
                break
            r = self.ev.evaluate(code)
            self.graph.add(code, name, r.score, r.status,
                           error_msg=r.error_msg, operator="baseline",
                           instance_scores=r.instance_scores.tolist()
                           if r.instance_scores is not None else [])
            status = f"{r.score:.4f}" if r.status == "valid" else "FAILED"
            print(f"  {name}: {status} (OFE={r.ofe_count})")

        # 2 LLM drafts with KB guidance
        directions = [
            "Combine channel quality (per-user gain) with spatial diversity. "
            "Start with top ports by total gain, then diversify.",
            "Use SINR-guided iterative selection: add one port at a time, "
            "always picking the port that maximizes min-SINR so far.",
        ]
        for d in directions:
            if self.budget.done():
                break
            self._do_draft(d)

        b = self.graph.best()
        print(f"\n  Seed done. Best: {b.score:.4f} [{b.id}], "
              f"total OFE={self.budget.ofe}" if b else "  No valid seed")

    # ===== Execution =====

    def _execute(self, dec) -> Node:
        op = dec['op']
        if op == 'draft':
            return self._do_draft(dec['dir'])
        elif op == 'improve':
            parent = self._resolve_target(dec['target'])
            return self._do_improve(parent, dec['dir']) if parent else None
        elif op == 'crossover':
            targets = dec.get('targets', [])
            a = self.graph.get(targets[0]) if len(targets) > 0 else None
            b = self.graph.get(targets[1]) if len(targets) > 1 else None
            if not a or not b:
                lb = self.graph.leaderboard(2)
                a = lb[0] if len(lb) > 0 else None
                b = lb[1] if len(lb) > 1 else a
            return self._do_crossover(a, b, dec['dir']) if a and b else None
        elif op == 'debug':
            target = self._resolve_target(dec['target'], failed=True)
            return self._do_debug(target) if target else None
        elif op == 'analyze':
            self._do_analyze(dec['dir'])
            return None
        elif op == 'ablate':
            target = self._resolve_target(dec['target'])
            if target:
                self._do_ablate(target)
            return None
        elif op == 'reflect':
            self._do_reflect()
            return None
        else:
            # Fallback: improve best
            parent = self.graph.best()
            return self._do_improve(parent, dec['dir']) if parent else None

    def _resolve_target(self, target_str, failed=False):
        if target_str and target_str.startswith('n_'):
            n = self.graph.get(target_str)
            if n:
                return n
        if failed:
            dbg = self.graph.failed_debuggable()
            return dbg[0] if dbg else None
        return self.graph.best()

    # ===== Operators =====

    def _do_draft(self, direction) -> Node:
        self.budget.use_llm()
        resp = self.llm.generate(
            prompt_draft(self.kb.summary(), direction), system=SYSTEM)
        try:
            code = extract_code(resp)
        except ValueError:
            self.log.append(f"draft: no code")
            return None

        r = self.ev.evaluate(code)
        node = self.graph.add(
            code, direction[:80], r.score, r.status,
            error_msg=r.error_msg, operator="draft",
            instance_scores=r.instance_scores.tolist()
            if r.instance_scores is not None else [],
            direction=direction)

        s = f"{r.score:.4f}" if r.status == "valid" else "FAILED"
        print(f"  → draft [{node.id}]: {s} (OFE+{r.ofe_count})")
        self.log.append(f"draft {node.id}:{s}")
        return node

    def _do_improve(self, parent, directive) -> Node:
        diag = ""
        if parent.instance_scores:
            sc = np.array(parent.instance_scores)
            worst = np.argsort(sc)[:5]
            diag = (f"score={parent.score:.4f}, min={np.min(sc):.3f}, "
                    f"std={np.std(sc):.3f}\n"
                    f"Worst instances: {list(worst)} "
                    f"(scores: {[f'{sc[i]:.3f}' for i in worst]})")

        self.budget.use_llm()
        resp = self.llm.generate(
            prompt_improve(parent.code, parent.score, diag,
                           self.kb.summary(), directive),
            system=SYSTEM)
        try:
            code = extract_code(resp)
        except ValueError:
            self.log.append(f"improve: no code")
            return None

        r = self.ev.evaluate(code)
        node = self.graph.add(
            code, directive[:80], r.score, r.status,
            error_msg=r.error_msg, parent_ids=[parent.id],
            operator="improve",
            instance_scores=r.instance_scores.tolist()
            if r.instance_scores is not None else [],
            direction=directive)

        s = f"{r.score:.4f}" if r.status == "valid" else "FAILED"
        delta = f" Δ={r.score - parent.score:+.4f}" if r.status == "valid" else ""
        print(f"  → improve [{node.id}]←[{parent.id}]: {s}{delta} (OFE+{r.ofe_count})")
        self.log.append(f"imp {node.id}:{s}{delta}")
        return node

    def _do_crossover(self, a, b, directive) -> Node:
        self.budget.use_llm()
        resp = self.llm.generate(
            prompt_crossover(a.code, a.score, b.code, b.score,
                             self.kb.summary(), directive),
            system=SYSTEM)
        try:
            code = extract_code(resp)
        except ValueError:
            self.log.append(f"xover: no code")
            return None

        r = self.ev.evaluate(code)
        node = self.graph.add(
            code, directive[:80], r.score, r.status,
            error_msg=r.error_msg, parent_ids=[a.id, b.id],
            operator="crossover",
            instance_scores=r.instance_scores.tolist()
            if r.instance_scores is not None else [])

        s = f"{r.score:.4f}" if r.status == "valid" else "FAILED"
        print(f"  → xover [{node.id}]←[{a.id}]+[{b.id}]: {s} (OFE+{r.ofe_count})")
        self.log.append(f"xover {node.id}:{s}")
        return node

    def _do_debug(self, failed) -> Node:
        failed.debug_attempts += 1
        self.budget.use_llm()
        resp = self.llm.generate(
            prompt_debug(failed.code, failed.error_msg, failed.debug_attempts),
            system=SYSTEM)
        try:
            code = extract_code(resp)
        except ValueError:
            return None

        r = self.ev.evaluate(code)
        node = self.graph.add(
            code, f"debug of {failed.id}", r.score, r.status,
            error_msg=r.error_msg, parent_ids=[failed.id], operator="debug",
            instance_scores=r.instance_scores.tolist()
            if r.instance_scores is not None else [])

        s = f"{r.score:.4f}" if r.status == "valid" else "STILL FAILED"
        print(f"  → debug [{node.id}]←[{failed.id}]: {s}")
        self.log.append(f"debug {node.id}:{s}")
        return node

    def _do_analyze(self, question):
        """让 LLM 写分析代码在 H_train 上执行（0 OFE）"""
        self.budget.use_llm()
        resp = self.llm.generate(
            f"Write numpy-only analysis code to investigate:\n{question}\n"
            f"Available: H_train shape ({self.ev.n},{self.ev.N_Ports},{self.ev.K}) complex, "
            f"K={self.ev.K}, N_Ports={self.ev.N_Ports}, N_selected={self.ev.N_selected}\n"
            f"Print results clearly. Code only, no explanation.")

        code = resp
        m = re.search(r"```(?:python)?\s*(.*?)```", resp, re.DOTALL)
        if m:
            code = m.group(1)

        try:
            env = {'np': np, 'numpy': np, 'H_train': self.ev.get_H_train(),
                   'K': self.ev.K, 'N_Ports': self.ev.N_Ports,
                   'N_selected': self.ev.N_selected}
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                exec(code, env)
            output = buf.getvalue()
            print(f"  → analyze: {output[:200]}")

            if output.strip():
                self.budget.use_llm()
                insight_resp = self.llm.generate(
                    f"Analysis output:\n{output[:1500]}\n\n"
                    f"Extract 1-3 key insights for algorithm design. Be specific and actionable.")
                for line in insight_resp.strip().split('\n'):
                    line = line.strip().lstrip('- •1234567890.')
                    if len(line) > 20:
                        self.kb.add_insight(line, f"analysis: {question[:30]}")

            self.log.append(f"analyze: {question[:30]}")
        except Exception as e:
            print(f"  → analyze FAILED: {e}")
            self.log.append(f"analyze FAIL")

    def _do_ablate(self, target: Node):
        """
        消融测试 — 移除算法的各组件，看分数变化多少。
        
        花费: 1 LLM call (生成消融版本) + N 次评估 (N=组件数)
        产出: 每个组件的重要性 → insights
        """
        self.budget.use_llm()
        resp = self.llm.generate(
            prompt_ablate(target.code, target.score), system=SYSTEM)

        # 解析消融版本
        components = []
        parts = re.split(r'COMPONENT_\d+:\s*', resp)[1:]
        for part in parts:
            lines = part.strip().split('\n')
            name = lines[0].strip() if lines else "unknown"
            try:
                code = extract_code(part)
                components.append((name, code))
            except ValueError:
                continue

        if not components:
            print(f"  → ablate: could not parse components")
            self.log.append("ablate: parse fail")
            return

        print(f"  → ablate [{target.id}]: testing {len(components)} components")
        for name, code in components:
            if self.budget.done():
                break
            r = self.ev.evaluate(code)
            if r.status == "valid":
                delta = target.score - r.score
                importance = "CRITICAL" if delta > 0.05 else "important" if delta > 0.01 else "minor"
                msg = (f"Ablation of '{name}': score drops {delta:+.4f} "
                       f"({target.score:.4f}→{r.score:.4f}) → {importance}")
                print(f"    {msg}")
                self.kb.add_insight(msg, f"ablate {target.id}", "high" if delta > 0.05 else "medium")
            else:
                print(f"    {name}: FAILED (component may be essential)")
                self.kb.add_insight(
                    f"'{name}' removal crashes → structurally essential",
                    f"ablate {target.id}", "high")

        self.log.append(f"ablate {target.id}: {len(components)} components")

    def _do_reflect(self):
        """
        阶段性反思 — 从 insights 提炼 design principles，识别未探索方向。
        花费: 1 LLM call, 0 OFE
        """
        self.budget.use_llm()
        recent = "\n".join(self.log[-10:]) if self.log else "No recent actions"
        resp = self.llm.generate(
            prompt_reflect(self.kb.summary(), self.graph.summary(5), recent))

        new_principles = 0
        new_directions = 0
        for line in resp.strip().split('\n'):
            line = line.strip()
            if line.startswith('PRINCIPLE:'):
                p = line.split(':', 1)[1].strip()
                if len(p) > 15:
                    self.kb.add_principle(p)
                    new_principles += 1
            elif line.startswith('DIRECTION:'):
                d = line.split(':', 1)[1].strip()
                if len(d) > 15:
                    self.kb.add_question(d)
                    new_directions += 1

        print(f"  → reflect: +{new_principles} principles, +{new_directions} directions")
        self.log.append(f"reflect: +{new_principles}P +{new_directions}D")

    # ===== Learning =====

    def _learn(self, node, dec):
        best = self.graph.best()
        if not best:
            return

        if node.status == "valid" and node.score >= best.score:
            self.stagnation = 0
            print(f"  ★ NEW BEST: {node.score:.4f}")

            # Compare with parent: per-instance delta
            if node.parent_ids and node.instance_scores:
                parent = self.graph.get(node.parent_ids[0])
                if parent and parent.instance_scores:
                    p_sc = np.array(parent.instance_scores)
                    n_sc = np.array(node.instance_scores)
                    improved = int(np.sum(n_sc > p_sc))
                    degraded = int(np.sum(n_sc < p_sc))
                    self.kb.add_insight(
                        f"{node.operator} '{node.thought[:40]}': "
                        f"+{improved}/-{degraded} instances, "
                        f"Δ={node.score - parent.score:+.4f}",
                        f"{node.id} vs {parent.id}", "high")
        else:
            self.stagnation += 1
            if node.status == "error":
                self.kb.add_failure(
                    dec.get('dir', node.thought)[:60],
                    float('-inf'), node.error_msg[:80], node.id)
            elif node.status == "valid" and node.score < best.score * 0.85:
                self.kb.add_failure(
                    dec.get('dir', node.thought)[:60],
                    node.score, "Much worse than best", node.id)

    # ===== Decision Parsing =====

    def _parse(self, resp) -> dict:
        dec = {'op': 'improve', 'target': None, 'targets': [], 'dir': ''}
        for line in resp.strip().split('\n'):
            line = line.strip()
            if line.startswith('OPERATOR:'):
                dec['op'] = line.split(':', 1)[1].strip().lower().split()[0]
            elif line.startswith('TARGET:'):
                val = line.split(':', 1)[1].strip()
                ids = [t for t in val.split() if t.startswith('n_')]
                dec['target'] = ids[0] if ids else None
                dec['targets'] = ids
            elif line.startswith('DIRECTION:'):
                dec['dir'] = line.split(':', 1)[1].strip()

        valid_ops = {'draft', 'improve', 'crossover', 'debug', 'analyze', 'ablate', 'reflect'}
        if dec['op'] not in valid_ops:
            dec['op'] = 'improve'
            b = self.graph.best()
            dec['target'] = b.id if b else None
            dec['dir'] = dec['dir'] or 'General improvement'
        return dec

    # ===== Checkpoint & Finish =====

    def _checkpoint(self):
        self.graph.save()
        self.kb.save()
        self._save_trajectory()
        b = self.graph.best()
        print(f"  [ckpt R{self.round}] best={b.score:.4f if b else 0} "
              f"OFE={self.budget.ofe} LLM={self.budget.llm} "
              f"nodes={len(self.graph.nodes)} insights={len(self.kb.insights)}")

    def _save_trajectory(self):
        """保存 best score trajectory 到 CSV（用于对比图）"""
        path = self.run_dir / "trajectory.csv"
        with open(path, 'w') as f:
            f.write('ofe,best_score,llm_calls,timestamp\n')
            for t in self.best_trajectory:
                f.write(f"{t['ofe']},{t['best_score']:.6f},"
                        f"{t['llm_calls']},{t['timestamp']:.1f}\n")

    def _finish(self):
        self.graph.save()
        self.kb.save()
        self._save_trajectory()
        self.ev.save_trajectory(str(self.run_dir / "eval_trajectory.csv"))

        best = self.graph.best()

        report = {
            'best_score': best.score if best else None,
            'best_id': best.id if best else None,
            'total_nodes': len(self.graph.nodes),
            'valid_nodes': sum(1 for n in self.graph.nodes.values() if n.status == "valid"),
            'ofe': self.budget.ofe,
            'llm_calls': self.budget.llm,
            'llm_tokens': self.llm.tokens,
            'elapsed_s': time.time() - self._t0,
            'rounds': self.round,
            'insights': len(self.kb.insights),
            'principles': self.kb.principles,
            'failures': len(self.kb.failures),
            'stagnation_at_end': self.stagnation,
        }
        (self.run_dir / "report.json").write_text(json.dumps(report, indent=2))
        if best:
            (self.run_dir / "best_algorithm.py").write_text(best.code)

        print("\n" + "=" * 60)
        print("DONE")
        print("=" * 60)
        if best:
            print(f"Best: {best.score:.4f} [{best.id}]")
            if best.instance_scores:
                sc = np.array(best.instance_scores)
                print(f"  min={np.min(sc):.4f} std={np.std(sc):.4f}")
        print(f"OFE: {self.budget.ofe} | LLM: {self.budget.llm} "
              f"({self.llm.tokens} tokens)")
        print(f"Nodes: {len(self.graph.nodes)} | "
              f"Insights: {len(self.kb.insights)} | "
              f"Principles: {len(self.kb.principles)}")
        print(f"Time: {time.time() - self._t0:.0f}s")
        print(f"Results: {self.run_dir}/")
        print(f"  trajectory.csv  ← 用于画 OFE vs score 对比图")
        print(f"  best_algorithm.py")
        print(f"  report.json")
        print(f"  graph.json + algorithms/")
        print(f"  knowledge_base.json")
        print("=" * 60)


# ============ CLI ============

def main():
    parser = argparse.ArgumentParser(description='EoH Agent v2')
    parser.add_argument('--budget', type=int, default=5000, help='Max OFE')
    parser.add_argument('--max-llm', type=int, default=200, help='Max LLM calls')
    parser.add_argument('--model', default='deepseek-chat')
    parser.add_argument('--base-url', default='https://api.deepseek.com')
    parser.add_argument('--api-key', default=None)
    parser.add_argument('--output', default=None)
    parser.add_argument('--quick', action='store_true', help='Quick: 500 OFE, 30 LLM')
    parser.add_argument('--temperature', type=float, default=0.7)
    args = parser.parse_args()

    if args.quick:
        args.budget = 500
        args.max_llm = 30

    run_dir = args.output or f"runs/agent_{time.strftime('%Y%m%d_%H%M%S')}"

    api_key = args.api_key or os.getenv("DEEPSEEK_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("ERROR: Set DEEPSEEK_API_KEY or OPENAI_API_KEY or --api-key")
        sys.exit(1)

    # 重置全局 OFE 计数器
    reset_ofe()

    llm = LLMClient(api_key=api_key, model=args.model,
                     base_url=args.base_url, temperature=args.temperature)
    evaluator = DetailedEvaluator()
    budget = Budget(max_ofe=args.budget, max_llm=args.max_llm)

    agent = EoHAgent(llm, evaluator, run_dir, budget)
    agent.run()


if __name__ == '__main__':
    main()
