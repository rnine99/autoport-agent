"""SINR Evaluator - evaluate port selection algorithms."""
import json
import sys
import os
import traceback
import tempfile
import importlib.util
import numpy as np

EVAL_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "evaluation")
sys.path.insert(0, EVAL_DIR)

_evaluator = None

def get_evaluator():
    global _evaluator
    if _evaluator is None:
        from evaluation import FasPortRateEvaluation
        _evaluator = FasPortRateEvaluation(timeout_seconds=60)
    return _evaluator

def evaluate_algorithm(algorithm_code):
    try:
        evaluator = get_evaluator()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', dir=EVAL_DIR, delete=False) as f:
            full_code = "import numpy as np\nfrom utility_objective_functions import sinr_balancing_power_constraint\n\n" + algorithm_code
            f.write(full_code)
            temp_path = f.name
        try:
            spec = importlib.util.spec_from_file_location("temp_algo", temp_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if not hasattr(module, 'select_ports'):
                return {"score": None, "success": False, "error": "Code must define select_ports()"}
            np.random.seed(2025)
            score = evaluator.evaluate(module.select_ports)
            return {"score": float(score), "success": True, "error": None}
        finally:
            os.unlink(temp_path)
    except Exception as e:
        return {"score": None, "success": False, "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()}

def get_baseline_scores():
    evaluator = get_evaluator()
    baselines = {}

    def random_select(K, N_selected, N_Ports, Pt, n, H, noise):
        return np.array([np.random.choice(N_Ports, N_selected, replace=False) for _ in range(n)])

    def greedy_select(K, N_selected, N_Ports, Pt, n, H, noise):
        port_sample = np.zeros((n, N_selected), dtype=int)
        for j in range(n):
            gains = np.sum(np.abs(H[j])**2, axis=1)
            port_sample[j] = np.argsort(gains)[-N_selected:]
        return port_sample

    np.random.seed(2025)
    baselines["random"] = float(evaluator.evaluate(random_select))
    np.random.seed(2025)
    baselines["greedy_channel_gain"] = float(evaluator.evaluate(greedy_select))
    return baselines

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--baselines", action="store_true")
    parser.add_argument("--eval", type=str)
    args = parser.parse_args()

    if args.baselines:
        print("Running baselines...")
        print(json.dumps(get_baseline_scores(), indent=2))
    elif args.eval:
        with open(args.eval) as f:
            code = f.read()
        print(json.dumps(evaluate_algorithm(code), indent=2))
