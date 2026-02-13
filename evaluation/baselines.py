"""Baseline 算法集合"""

RANDOM = '''import numpy as np

def select_ports(K, N_selected, N_Ports, Pt, n, H_current, noise):
    port_sample = np.zeros((n, N_selected), dtype=int)
    for i in range(n):
        port_sample[i] = np.random.choice(N_Ports, N_selected, replace=False)
    return port_sample
'''.strip()

GREEDY_NORM = '''import numpy as np

def select_ports(K, N_selected, N_Ports, Pt, n, H_current, noise):
    port_sample = np.zeros((n, N_selected), dtype=int)
    for i in range(n):
        gains = np.linalg.norm(H_current[i], axis=1)
        port_sample[i] = np.argsort(gains)[-N_selected:][::-1]
    return port_sample
'''.strip()

LOCAL_SEARCH = '''import numpy as np

def select_ports(K, N_selected, N_Ports, Pt, n, H_current, noise):
    port_sample = np.zeros((n, N_selected), dtype=int)
    for i in range(n):
        H = H_current[i]
        gains = np.linalg.norm(H, axis=1)
        selected = list(np.argsort(gains)[-N_selected:])
        improved = True
        it = 0
        while improved and it < 50:
            improved = False
            it += 1
            H_sel = H[selected, :]
            cur = np.min(np.sum(np.abs(H_sel)**2, axis=0))
            for j in range(N_selected):
                best_p, best_s = selected[j], cur
                for p in range(N_Ports):
                    if p in selected:
                        continue
                    test = selected.copy()
                    test[j] = p
                    s = np.min(np.sum(np.abs(H[test, :])**2, axis=0))
                    if s > best_s:
                        best_s, best_p = s, p
                if best_p != selected[j]:
                    selected[j] = best_p
                    improved = True
                    break
        port_sample[i] = np.array(selected)
    return port_sample
'''.strip()

ALL_BASELINES = [
    ("random", RANDOM),
    ("greedy_norm", GREEDY_NORM),
    ("local_search", LOCAL_SEARCH),
]
