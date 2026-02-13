"""
扩展评估器 v2 — per-instance 诊断 + 全局 OFE 追踪

关键改进 (vs v1):
  1. 全局 OFE 计数器包装 sinr_balancing_power_constraint
     → 算法内部调用 SINR 也计入 OFE（和 baseline 的 TrackedSINRFunction 一致）
  2. 评估前后记录 OFE delta → 知道每次评估的真实开销
  3. 支持 trajectory 输出 → 可画 OFE vs score 对比图

OFE 对齐说明:
  baseline (complexity_tracker_v3.py) 用 TrackedSINRFunction 全局替换 sinr 函数，
  所以 local_search 类算法每个 instance 调 50 次 SINR = 2500 OFE/次评估。
  我们必须用同样方式计数，否则对比不公平。
"""

import os
import sys
import ast
import re
import time
import hashlib
import threading
import numpy as np
import scipy.io
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(__file__))

# ============ 全局 OFE 计数器 (和 baseline 的 complexity_tracker_v3 对齐) ============

_ofe_lock = threading.Lock()
_ofe_count = 0


def get_ofe() -> int:
    with _ofe_lock:
        return _ofe_count


def reset_ofe():
    global _ofe_count
    with _ofe_lock:
        _ofe_count = 0


def _increment_ofe():
    global _ofe_count
    with _ofe_lock:
        _ofe_count += 1


# 原始 SINR 函数（保存一份未包装的）
from utility_objective_functions import sinr_balancing_power_constraint as _raw_sinr


def _tracked_sinr(*args, **kwargs):
    """包装版 SINR — 每次调用 OFE +1（和 baseline TrackedSINRFunction 等价）"""
    _increment_ofe()
    return _raw_sinr(*args, **kwargs)


def install_ofe_tracking():
    """
    全局替换 sinr_balancing_power_constraint 为带追踪的版本。
    
    效果：
    - evaluation.py 的评估调用会被计数
    - 算法内部 import 后调用也会被计数（因为替换的是模块级别引用）
    - 和 baseline 的 TrackedSINRFunction + _inject_tracked_sinr 完全等价
    """
    import utility_objective_functions
    utility_objective_functions.sinr_balancing_power_constraint = _tracked_sinr

    # 替换所有已加载模块中的引用（和 baseline TrackedEvaluation._inject_tracked_sinr 一样）
    for mod_name, mod in sys.modules.items():
        if mod and hasattr(mod, 'sinr_balancing_power_constraint'):
            if mod.sinr_balancing_power_constraint is not _tracked_sinr:
                mod.sinr_balancing_power_constraint = _tracked_sinr


# ============ 评估结果 ============

@dataclass
class EvalResult:
    """评估结果 — 比原 evaluation.py 的 float 丰富得多"""
    score: float
    instance_scores: np.ndarray = None
    port_selections: np.ndarray = None
    status: str = "valid"           # "valid" | "error" | "timeout"
    error_msg: str = ""
    eval_time_s: float = 0.0
    ofe_count: int = 0              # 这次评估消耗的 OFE（含算法内部 SINR 调用）

    # 诊断
    worst_5_idx: np.ndarray = None
    best_5_idx: np.ndarray = None
    score_std: float = 0.0
    min_score: float = 0.0

    def diagnosis(self) -> str:
        if self.status != "valid":
            return f"FAILED: {self.error_msg[:150]}"
        lines = [
            f"score={self.score:.4f} (std={self.score_std:.4f}, min={self.min_score:.4f})",
        ]
        if self.worst_5_idx is not None and self.instance_scores is not None:
            worst_scores = [f"{self.instance_scores[i]:.3f}" for i in self.worst_5_idx]
            lines.append(f"worst instances: {list(self.worst_5_idx)} (scores: {worst_scores})")
        return "\n".join(lines)


# ============ 代码工具 ============

_CODE_BLOCK_RE = re.compile(r"```(?:python)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_code(text: str) -> str:
    """从 LLM 输出中提取 select_ports 函数"""
    m = _CODE_BLOCK_RE.search(text)
    if m:
        text = m.group(1).strip()
    idx = text.find("def select_ports")
    if idx >= 0:
        imports = []
        for line in text[:idx].split('\n'):
            s = line.strip()
            if s.startswith('import ') or s.startswith('from '):
                if any(k in s for k in ['numpy', 'math', 'random']):
                    imports.append(line)
        return '\n'.join(imports) + '\n\n' + text[idx:].strip()
    raise ValueError("No 'def select_ports' found")


def preprocess_code(code: str) -> str:
    """清理：移除危险 import，确保有 numpy"""
    lines = []
    for line in code.split('\n'):
        if 'import' in line:
            lower = line.lower()
            if any(f in lower for f in ['scipy', 'sklearn', 'evaluation',
                                         'sinr_balancing', 'utility_objective']):
                continue
        lines.append(line)
    code = '\n'.join(lines)
    if 'import numpy' not in code:
        code = 'import numpy as np\n\n' + code
    return code


def safety_check(code: str):
    """AST 安全检查"""
    allowed = {"numpy", "math", "random", "np"}
    forbidden = {"open", "exec", "eval", "compile", "__import__", "os", "sys", "subprocess"}
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in allowed:
                    raise ValueError(f"Disallowed import: {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] not in allowed:
                raise ValueError(f"Disallowed from-import: {node.module}")
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in forbidden:
                raise ValueError(f"Forbidden call: {node.func.id}()")


def compile_function(code: str):
    """编译代码，注入 tracked SINR 函数"""
    g: Dict[str, Any] = {
        "np": np, "numpy": np,
        "sinr_balancing_power_constraint": _tracked_sinr,  # 注入追踪版本
    }
    exec(code, g, g)
    fn = g.get("select_ports")
    if not callable(fn):
        raise ValueError("Code does not define callable select_ports")
    return fn


def validate_output(arr, n, N_selected, N_Ports) -> np.ndarray:
    arr = np.asarray(arr)
    if arr.shape != (n, N_selected):
        raise ValueError(f"Shape {arr.shape} != ({n}, {N_selected})")
    if not np.issubdtype(arr.dtype, np.integer):
        if np.all(np.isfinite(arr)) and np.allclose(arr, np.floor(arr)):
            arr = arr.astype(int)
        else:
            raise ValueError("Non-integer output")
    if arr.min() < 0 or arr.max() >= N_Ports:
        raise ValueError(f"Port index out of [0, {N_Ports-1}]")
    for i in range(n):
        if len(np.unique(arr[i])) != N_selected:
            raise ValueError(f"Row {i} has duplicate ports")
    return arr


def code_hash(code: str) -> str:
    return hashlib.md5(code.encode()).hexdigest()[:12]


# ============ 评估器 ============

class DetailedEvaluator:
    """
    扩展评估器 v2

    vs v1 的关键区别:
    - 构造时自动安装 OFE 追踪（全局替换 SINR 函数）
    - evaluate() 返回的 ofe_count 包含算法内部 SINR 调用
    - 支持 trajectory 追踪
    """

    def __init__(self, mat_path: str = None, n_train: int = 50):
        self.K = 8
        self.N_selected = self.K
        Port_N1 = 8
        self.N_Ports = Port_N1 * Port_N1
        self.noise = 1
        P_dBm = 20
        self.Pt = 10 ** ((P_dBm - 30) / 10)

        if mat_path is None:
            base = os.path.dirname(__file__)
            mat_path = os.path.join(
                base, f'FA_Channel/train_channel_N_{Port_N1}_U_{self.K}_W_2_S_1000_dBm.mat')

        data = scipy.io.loadmat(mat_path)
        H_all = np.transpose(data['Hmat'], (2, 1, 0))
        self.H_train = H_all[:n_train].astype(np.complex128)
        self.n = self.H_train.shape[0]

        # 安装全局 OFE 追踪
        install_ofe_tracking()

        # Trajectory: [(global_ofe, score, timestamp), ...]
        self.trajectory: List[dict] = []
        self._t0 = time.time()

    def evaluate(self, code: str, timeout_s: int = 300) -> EvalResult:
        """
        评估代码字符串，返回完整诊断。
        
        OFE 计数说明：
        - ofe_before = 评估前的全局 OFE
        - 算法执行期间，内部每次调用 sinr_balancing_power_constraint 都会 OFE +1
        - 评估后的 50 次 SINR 调用也会 OFE +1
        - ofe_delta = 总共消耗的 OFE（含算法内部 + 评估）
        """
        start = time.time()
        ofe_before = get_ofe()

        try:
            code = preprocess_code(code)
            safety_check(code)
            fn = compile_function(code)
            np.random.seed(2025)

            # 执行算法（内部的 SINR 调用会被全局计数器追踪）
            port_sample = fn(self.K, self.N_selected, self.N_Ports,
                             self.Pt, self.n, self.H_train, self.noise)
            ports = validate_output(port_sample, self.n, self.N_selected, self.N_Ports)

            # Per-instance SINR 评估（也会被追踪）
            instance_scores = np.zeros(self.n)
            for j in range(self.n):
                h = self.H_train[j, ports[j], :]
                instance_scores[j] = _tracked_sinr(
                    self.N_selected, self.K, h, self.Pt, self.noise)

            ofe_delta = get_ofe() - ofe_before
            sorted_idx = np.argsort(instance_scores)
            score = float(np.mean(instance_scores))

            # 记录 trajectory
            self.trajectory.append({
                'ofe': get_ofe(),
                'score': score,
                'timestamp': time.time() - self._t0,
            })

            return EvalResult(
                score=score,
                instance_scores=instance_scores,
                port_selections=ports,
                status="valid",
                eval_time_s=time.time() - start,
                ofe_count=ofe_delta,
                worst_5_idx=sorted_idx[:5],
                best_5_idx=sorted_idx[-5:],
                score_std=float(np.std(instance_scores)),
                min_score=float(np.min(instance_scores)),
            )

        except Exception as e:
            ofe_delta = get_ofe() - ofe_before
            return EvalResult(
                score=float("-inf"),
                status="error",
                error_msg=f"{type(e).__name__}: {str(e)[:200]}",
                eval_time_s=time.time() - start,
                ofe_count=ofe_delta,
            )

    def get_H_train(self):
        return self.H_train

    def save_trajectory(self, filepath: str):
        """保存 (ofe, best_score, timestamp) 到 CSV，用于画对比图"""
        best = float('-inf')
        with open(filepath, 'w') as f:
            f.write('ofe,score,best_score,timestamp\n')
            for t in self.trajectory:
                if t['score'] > best:
                    best = t['score']
                f.write(f"{t['ofe']},{t['score']:.6f},{best:.6f},{t['timestamp']:.1f}\n")
