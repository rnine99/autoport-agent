"""Standalone SINR evaluation (no llm4ad dependency)."""
import os
import numpy as np
import scipy.io
from utility_objective_functions import sinr_balancing_power_constraint


class FasPortRateEvaluation:
    def __init__(self, timeout_seconds=30):
        self.K = 8
        self.Selected_port = self.K
        Port_N1 = 8
        self.N_Ports = Port_N1 * Port_N1
        self.noise = 1
        P = 20  # dBm
        self.Pt = 10 ** ((P - 30) / 10)

        base_path = os.path.dirname(__file__)
        filename = os.path.join(
            base_path,
            f'FA_Channel/train_channel_N_{Port_N1}_U_{self.K}_W_2_S_1000_dBm.mat'
        )
        data = scipy.io.loadmat(filename)
        Htemp = np.transpose(data['Hmat'], (2, 1, 0))
        num_train = 50
        self.H_current = Htemp[:num_train, :, :]
        self.n = self.H_current.shape[0]

    def evaluate(self, func):
        np.random.seed(2025)
        population = func(
            self.K, self.Selected_port, self.N_Ports,
            self.Pt, self.n, self.H_current, self.noise
        )
        rewards = np.array([
            sinr_balancing_power_constraint(
                self.Selected_port, self.K,
                self.H_current[j, population[j, :].astype(int), :],
                self.Pt, self.noise
            ) for j in range(self.n)
        ])
        return np.sum(rewards) / self.n
