import  numpy as np

def sinr_balancing_power_constraint(bs_antenna_num,user_num, channel_bs_user, power_constr, noise_variance):

 

    SINR_target=np.ones((user_num,1))
    threshold = 1e-5
    iter_num = 1  # iteration index
    converg = 0  # convergence indicator

    # uplink power
    qt = np.zeros(user_num)
    ws2 = np.zeros((bs_antenna_num, user_num), dtype=complex)

    while not converg and iter_num<100:
        # update ws2
        T = noise_variance * np.eye(bs_antenna_num).astype(complex)
        T = T + np.conj(channel_bs_user)@np.diag(qt)@channel_bs_user.T


        SINR_U = np.zeros(user_num)
        for k in range(user_num):
            ws2[:, k] = np.linalg.inv(T) @ np.conj(channel_bs_user[:, k])  # uplink beamforming
            ws2[:, k] /= np.linalg.norm(ws2[:, k])
            SINR_U[k] = qt[k] * abs(np.conj(ws2[:, k]).T @ np.conj(channel_bs_user[:, k]))**2 / (
                abs(np.conj(ws2[:, k]).T @ T @ ws2[:, k]) - qt[k] * abs(np.conj(ws2[:, k]).T @ np.conj(channel_bs_user[:, k]))**2
            )

        # uplink downlink duality
        D = np.zeros((user_num, user_num))
        for x in range(user_num):

            a1= (np.abs(np.conj(ws2[:, x]).T @ np.conj(channel_bs_user[:, x]) ))**2

            D[x, x] = SINR_target[x,0] / ( a1 / noise_variance)

        F = np.zeros((user_num, user_num))
        for x in range(user_num):
            for x2 in range(user_num):
                if x2 != x:
                    b1 = (abs(np.conj(ws2[:, x2]).T @ np.conj(channel_bs_user[:, x])))**2
                    F[x, x2] = b1 / noise_variance
                else:
                    F[x, x2] = 0

        u = np.ones(user_num)
        de = np.ones(user_num)

        X = np.block([[D @ F.T, D @ de[:, np.newaxis]], [u @ D @ F.T / power_constr, u @ D @ de / power_constr]])
        b,a = np.linalg.eig(X)
        err = np.max(np.real(np.diag(b)))
        d = np.argmax(b) #np.argmax(np.real(np.diag(b)))

        qtemp = a[:, d]
        qt = qtemp / qtemp[user_num]
        qt = np.real(qt[:user_num])


        if iter_num > 1:
            err_temp = abs(err - err_prev) / abs(err_prev)
            if err_temp < threshold:
                converg = 1

        err_prev = err
        iter_num += 1

    X = np.block([[D @ F, D @ de[:, np.newaxis]], [u @ D @ F / power_constr, u @ D @ de / power_constr]])
    b,a = np.linalg.eig(X)
    la2 = np.max(np.real(np.diag(b)))
    d =  np.argmax(b) #np.argmax(np.real(np.diag(b)))
    ptemp = a[:, d]
    pt = ptemp / ptemp[user_num]
    pt = np.real(pt[:user_num])


    # downlink beamforming
    w_dl = np.zeros((bs_antenna_num, user_num), dtype=complex)
    for k in range(user_num):
        w_dl[:, k] = ws2[:, k] * np.sqrt(pt[k])

    # downlink SINR
    SINR_DL = np.zeros(user_num)
    for k in range(user_num):
        SINR_DL[k] = abs(channel_bs_user[:, k].T @ w_dl[:, k])**2 / (
            np.linalg.norm(np.concatenate((channel_bs_user[:, k].T @ w_dl, [np.sqrt(noise_variance)])))**2 -
            abs(channel_bs_user[:, k].T @ w_dl[:, k])**2
        )
    # print(SINR_DL)
    sinr_min = np.min(SINR_DL)

    return sinr_min#, w_dl, ws2, SINR_DL, qt, pt




def sinr_balancing_power_constraint_v0(bs_antenna_num, user_num, channel_bs_user, power_constr, noise_variance):
    SINR_target=np.ones((user_num,1))
    threshold = 1e-5
    iter_num = 1  # iteration index
    converg = 0  # convergence indicator

    # uplink power
    qt = np.zeros(user_num)
    ws2 = np.zeros((bs_antenna_num, user_num), dtype=complex)

    while not converg and iter_num<100:
        # update ws2
        T = noise_variance * np.eye(bs_antenna_num).astype(complex)
        T = T + np.conj(channel_bs_user)@np.diag(qt)@channel_bs_user.T


        SINR_U = np.zeros(user_num)
        for k in range(user_num):
            ws2[:, k] = np.linalg.inv(T) @ np.conj(channel_bs_user[:, k])  # uplink beamforming
            ws2[:, k] /= np.linalg.norm(ws2[:, k])
            SINR_U[k] = qt[k] * abs(np.conj(ws2[:, k]).T @ np.conj(channel_bs_user[:, k]))**2 / (
                abs(np.conj(ws2[:, k]).T @ T @ ws2[:, k]) - qt[k] * abs(np.conj(ws2[:, k]).T @ np.conj(channel_bs_user[:, k]))**2
            )

        # uplink downlink duality
        D = np.zeros((user_num, user_num))
        for x in range(user_num):

            a1= (np.abs(np.conj(ws2[:, x]).T @ np.conj(channel_bs_user[:, x]) ))**2

            D[x, x] = SINR_target[x,0] / ( a1 / noise_variance)

        F = np.zeros((user_num, user_num))
        for x in range(user_num):
            for x2 in range(user_num):
                if x2 != x:
                    b1 = (abs(np.conj(ws2[:, x2]).T @ np.conj(channel_bs_user[:, x])))**2
                    F[x, x2] = b1 / noise_variance
                else:
                    F[x, x2] = 0

        u = np.ones(user_num)
        de = np.ones(user_num)

        X = np.block([[D @ F.T, D @ de[:, np.newaxis]], [u @ D @ F.T / power_constr, u @ D @ de / power_constr]])
        b,a = np.linalg.eig(X)
        err = np.max(np.real(np.diag(b)))
        d = np.argmax(b) #np.argmax(np.real(np.diag(b)))

        qtemp = a[:, d]
        qt = qtemp / qtemp[user_num]
        qt = np.real(qt[:user_num])


        if iter_num > 1:
            err_temp = abs(err - err_prev) / abs(err_prev)
            if err_temp < threshold:
                converg = 1

        err_prev = err
        iter_num += 1

    X = np.block([[D @ F, D @ de[:, np.newaxis]], [u @ D @ F / power_constr, u @ D @ de / power_constr]])
    b,a = np.linalg.eig(X)
    la2 = np.max(np.real(np.diag(b)))
    d =  np.argmax(b) #np.argmax(np.real(np.diag(b)))
    ptemp = a[:, d]
    pt = ptemp / ptemp[user_num]
    pt = np.real(pt[:user_num])


    # downlink beamforming
    w_dl = np.zeros((bs_antenna_num, user_num), dtype=complex)
    for k in range(user_num):
        w_dl[:, k] = ws2[:, k] * np.sqrt(pt[k])

    # downlink SINR
    SINR_DL = np.zeros(user_num)
    for k in range(user_num):
        SINR_DL[k] = abs(channel_bs_user[:, k].T @ w_dl[:, k])**2 / (
            np.linalg.norm(np.concatenate((channel_bs_user[:, k].T @ w_dl, [np.sqrt(noise_variance)])))**2 -
            abs(channel_bs_user[:, k].T @ w_dl[:, k])**2
        )
    # print(SINR_DL)
    sinr_min = np.min(SINR_DL)

    return sinr_min#, w_dl, ws2, SINR_DL, qt, pt


