# AutoPort Agent - SINR Optimization

You are an expert algorithm designer for wireless communication systems.
Your goal: design port selection algorithms that maximize minimum SINR.

## Problem
- K=8 users, N_Ports=64 (8x8 antenna grid), select K=8 ports
- Channel matrix H: shape (n, 64, 8), complex-valued
- Objective: maximize min-SINR via sinr_balancing_power_constraint()
- Baselines: random=1.08, greedy=0.61

## Setup (run FIRST before anything else)
```bash
# Clone evaluation harness if not present
if [ ! -d "/home/daytona/evaluation" ]; then
    cd /home/daytona
    git clone https://github.com/rnine99/autoport-agent.git _repo
    cp -r _repo/evaluation /home/daytona/evaluation
    rm -rf _repo
fi
pip install numpy scipy
```

## Evaluation
The evaluation harness is at /home/daytona/evaluation/. To test an algorithm:

    import sys
    sys.path.insert(0, "/home/daytona/evaluation")
    from evaluation import FasPortRateEvaluation
    from utility_objective_functions import sinr_balancing_power_constraint
    import numpy as np

    def select_ports(K, N_selected, N_Ports, Pt, n, H, noise):
        port_sample = np.zeros((n, N_selected), dtype=int)
        for j in range(n):
            H_j = H[j]
            ports = np.random.choice(N_Ports, N_selected, replace=False)
            port_sample[j] = ports
        return port_sample

    e = FasPortRateEvaluation()
    np.random.seed(2025)
    score = e.evaluate(select_ports)
    print(f"Score: {score}")

## Rules
- NEVER redefine sinr_balancing_power_constraint
- Return shape (n, N_selected) int array, values 0 to N_Ports-1, no repeats per row
- You CAN call sinr_balancing_power_constraint inside your algorithm
- Higher score = better

## Workflow
1. Run Setup commands first
2. Run baselines to establish reference scores
3. Design algorithm, test, analyze score, improve, repeat
4. Save best algorithms to /home/daytona/algorithms/
5. Track scores: document what you tried and why
