template_program = '''
import numpy as np
from utility_objective_functions import sinr_balancing_power_constraint

def select_ports(K, N_selected, N_Ports, Pt, n, H, noise):
    """
    Select N_selected ports to maximize SINR.

    Args:
        K: number of users
        N_selected: number of ports to select
        N_Ports: total available ports
        Pt: transmit power
        n: number of channel realizations
        H: channel matrix, shape (n, N_Ports, K), complex
        noise: noise power

    Returns:
        port_sample: shape (n, N_selected), dtype=int

    NOTE: sinr_balancing_power_constraint is already imported! Do NOT redefine it.
    Usage: score = sinr_balancing_power_constraint(N_selected, K, H_j[ports,:], Pt, noise)
    """
    port_sample = np.zeros((n, N_selected), dtype=int)

    for j in range(n):
        H_j = H[j]  # shape: (N_Ports, K), complex

        # TODO: Your algorithm
        ports = np.random.choice(N_Ports, N_selected, replace=False)

        port_sample[j] = ports

    return port_sample
'''

task_description = """Design an algorithm to select ports that maximizes SINR.

IMPORTANT: sinr_balancing_power_constraint is already imported. Do NOT redefine it!
Just call it directly:
    score = sinr_balancing_power_constraint(N_selected, K, H_j[ports,:], Pt, noise)
    Higher score = better selection.

BASELINE METHODS:

1. Random: ports = np.random.choice(N_Ports, N_selected, replace=False)

2. Greedy: Select ports with highest channel gain
    gains = np.sum(np.abs(H_j)**2, axis=1)
    ports = np.argsort(gains)[-N_selected:]

3. Local Search: Start from a solution, try replacing one port with another,
    evaluate the new selection, keep it if score improves, repeat until no improvement.

YOUR GOAL: Design an algorithm that beats these baselines and maximize the score.

Hints:
- Greedy is fast but may not be optimal
- Local search can improve a solution but needs a good starting point
- You can call sinr_balancing_power_constraint multiple times to compare selections

Return shape (n, N_selected) int array. Do NOT redefine sinr_balancing_power_constraint."""
