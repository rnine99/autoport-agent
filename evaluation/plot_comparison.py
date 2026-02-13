"""
对比图绘制 — Agent vs Baseline 的 OFE vs Best Score 曲线

用法:
    python plot_comparison.py runs/agent_xxx/trajectory.csv logs/multiisland_xxx/

输出:
    comparison.png — OFE (x轴) vs Best Score (y轴)
"""

import sys
import csv
import json
from pathlib import Path


def load_agent_trajectory(csv_path: str) -> list:
    """加载 agent trajectory.csv"""
    data = []
    with open(csv_path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data.append({
                'ofe': int(row['ofe']),
                'best_score': float(row['best_score']),
            })
    return data


def load_baseline_trajectory(log_dir: str) -> list:
    """
    从 baseline 的 island_*/algorithms_list.json 重建 trajectory。
    
    Baseline 没有直接输出 OFE vs score CSV，
    但 algorithms_list.json 里每个算法有 ofe 和 score 字段。
    """
    log_dir = Path(log_dir)
    all_points = []

    for island_dir in sorted(log_dir.glob("island_*")):
        algo_list = island_dir / "algorithms_list.json"
        if not algo_list.exists():
            continue
        data = json.loads(algo_list.read_text())
        for algo in data.get('algorithms', []):
            all_points.append({
                'ofe': algo.get('ofe', 0),
                'score': algo.get('score', float('-inf')),
            })

    if not all_points:
        print(f"WARNING: No algorithm data found in {log_dir}")
        return []

    # Sort by OFE and compute running best
    all_points.sort(key=lambda x: x['ofe'])
    best = float('-inf')
    trajectory = []
    for p in all_points:
        if p['score'] > best:
            best = p['score']
        trajectory.append({'ofe': p['ofe'], 'best_score': best})

    return trajectory


def plot(agent_data, baseline_data, output_path="comparison.png"):
    """生成对比图"""
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed. Printing text comparison instead.\n")
        text_compare(agent_data, baseline_data)
        return

    fig, ax = plt.subplots(figsize=(10, 6))

    if agent_data:
        ofe = [d['ofe'] for d in agent_data]
        score = [d['best_score'] for d in agent_data]
        ax.plot(ofe, score, 'b-', linewidth=2, label='Agent (ours)')

    if baseline_data:
        ofe = [d['ofe'] for d in baseline_data]
        score = [d['best_score'] for d in baseline_data]
        ax.plot(ofe, score, 'r--', linewidth=2, label='EoH Baseline')

    ax.set_xlabel('OFE (Objective Function Evaluations)', fontsize=12)
    ax.set_ylabel('Best Score (min-SINR)', fontsize=12)
    ax.set_title('Agent vs EoH Baseline: Sample Efficiency', fontsize=14)
    ax.legend(fontsize=12)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    print(f"Plot saved: {output_path}")


def text_compare(agent_data, baseline_data):
    """文本对比（当 matplotlib 不可用时）"""
    print("=" * 50)
    print("OFE vs Best Score Comparison")
    print("=" * 50)

    checkpoints = [100, 500, 1000, 2000, 3000, 5000]
    print(f"{'OFE':>8} {'Agent':>10} {'Baseline':>10} {'Δ':>8}")
    print("-" * 40)

    for cp in checkpoints:
        a_score = "-"
        b_score = "-"
        delta = ""

        if agent_data:
            matches = [d for d in agent_data if d['ofe'] <= cp]
            if matches:
                a_score = f"{matches[-1]['best_score']:.4f}"

        if baseline_data:
            matches = [d for d in baseline_data if d['ofe'] <= cp]
            if matches:
                b_score = f"{matches[-1]['best_score']:.4f}"

        if a_score != "-" and b_score != "-":
            d = float(a_score) - float(b_score)
            delta = f"{d:+.4f}"

        print(f"{cp:>8} {a_score:>10} {b_score:>10} {delta:>8}")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python plot_comparison.py <agent_trajectory.csv> [baseline_log_dir]")
        print()
        print("Examples:")
        print("  python plot_comparison.py runs/agent_xxx/trajectory.csv")
        print("  python plot_comparison.py runs/agent_xxx/trajectory.csv logs/multiisland_xxx/")
        sys.exit(1)

    agent_csv = sys.argv[1]
    baseline_dir = sys.argv[2] if len(sys.argv) > 2 else None

    agent_data = load_agent_trajectory(agent_csv)
    baseline_data = load_baseline_trajectory(baseline_dir) if baseline_dir else []

    if not agent_data and not baseline_data:
        print("No data to plot")
        sys.exit(1)

    output = str(Path(agent_csv).parent / "comparison.png")
    plot(agent_data, baseline_data, output)
    text_compare(agent_data, baseline_data)
