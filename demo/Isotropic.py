from __future__ import print_function
from spectralDNS import config, get_solver, solve
import numpy as np
from numpy import array, pi, zeros, sum, float64, sin, cos
from numpy.linalg import norm
import warnings

try:
    import matplotlib.pyplot as plt

except ImportError:
    warnings.warn("matplotlib not installed")
    plt = None

def initialize(solver, context):
    if 'NS' in config.params.solver:
        initialize1(solver, context)

    else:
        initialize2(solver, context)
    config.params.t = 0.0
    config.params.tstep = 0

    c = context
    #
    c.mask = np.where(c.K2 <= config.params.Kf2, 1, 0)
    c.target_energy = energy_fourier(solver.comm, c.U_hat)

def initialize1(solver, context):
    c = context
    u0 = np.prod(config.params.N)/np.prod(config.params.L)
    if 'shenfun' in config.params.solver:
        u0 /= np.prod(config.params.N)

    np.random.seed(solver.rank)
    c.U_hat[:] = np.random.sample(c.U_hat.shape)*2j*np.pi
    c.U_hat[:] = u0/(2*np.pi)*c.K2*np.exp(-c.K2/config.params.a0**2)*np.exp(c.U_hat)
    if solver.rank == 0:
        c.U_hat[:, 0, 0, 0] = 0.0

    # Set Nyquist frequency to zero
    Nq0 = np.nonzero(-config.params.N[0]//2==c.K[0][:,0,0])[0]
    Nq1 = np.nonzero(-config.params.N[1]//2==c.K[1][0,:,0])[0]
    if len(Nq0) == 1:
        c.U_hat[:, Nq0[0]] = 0
    if len(Nq1) == 1:
        c.U_hat[:, :, Nq1[0]] = 0
    c.U_hat[..., -1] = 0

    U = solver.get_velocity(**c)
    U_hat = solver.set_velocity(**c)
    # project to zero divergence
    U_hat[:] -= (c.K[0]*U_hat[0]+c.K[1]*U_hat[1]+c.K[2]*U_hat[2])*c.K_over_K2

def initialize2(solver, context):
    c = context
    u0 = np.prod(config.params.N)/np.prod(config.params.L)
    if 'shenfun' in config.params.solver:
        u0 /= np.prod(config.params.N)

    np.random.seed(solver.rank)
    c.U_hat[:] = np.random.sample(c.U_hat.shape)*2j*np.pi
    c.U_hat[:] = u0/(2*np.pi)*c.K2*np.exp(-c.K2/config.params.a0**2)*np.exp(c.U_hat)
    if solver.rank == 0:
        c.U_hat[:, 0, 0, 0] = 0.0

    # Set Nyquist frequency to zero
    Nq0 = np.nonzero(-config.params.N[0]//2==c.K[0][:,0,0])[0]
    Nq1 = np.nonzero(-config.params.N[1]//2==c.K[1][0,:,0])[0]
    if len(Nq0) == 1:
        c.U_hat[:, Nq0[0]] = 0
    if len(Nq1) == 1:
        c.U_hat[:, :, Nq1[0]] = 0
    c.U_hat[..., -1] = 0
    c.W_hat = solver.cross2(c.W_hat, c.K, c.U_hat)

    U = solver.get_velocity(**c)
    U_hat = solver.set_velocity(**c)

    # project to zero divergence
    U_hat[:] -= (c.K[0]*U_hat[0]+c.K[1]*U_hat[1]+c.K[2]*U_hat[2])*c.K_over_K2
    c.W_hat = solver.cross2(c.W_hat, c.K, U_hat)

def energy_fourier(comm, a):
    N = config.params.N
    result = 2*np.sum(np.abs(a[..., 1:-1])**2) + np.sum(np.abs(a[..., 0])**2) + np.sum(np.abs(a[..., -1])**2)
    result =  comm.allreduce(result)
    if 'shenfun' in config.params.solver:
        return result*np.prod(N)
    else:
        return result/np.prod(N)

def spectrum(solver, context):
    c = context
    uiui = np.zeros(c.U_hat[0].shape)
    uiui[..., 1:-1] = 2*np.sum((c.U_hat[...,1:-1]*np.conj(c.U_hat[..., 1:-1])).real, axis=0)
    uiui[..., 0] = np.sum((c.U_hat[..., 0]*np.conj(c.U_hat[..., 0])).real, axis=0)
    uiui[..., -1] = np.sum((c.U_hat[..., -1]*np.conj(c.U_hat[..., -1])).real, axis=0)
    if 'shenfun' in config.params.solver:
        uiui *= (2*np.pi*c.K2*np.prod(config.params.N))
    else:
        uiui *= (2*np.pi*c.K2/np.prod(config.params.N))

    # Create bins for Ek
    Nb = int(np.sqrt(sum((config.params.N/2)**2)))
    bins = range(0, Nb)
    z = np.digitize(np.sqrt(context.K2), bins, right=True)
    #bins = np.unique(np.sqrt(context.K2))
    #z = np.digitize(np.sqrt(context.K2), bins, right=True)
    #Nb = len(bins)

    # Sample
    Ek = np.zeros(Nb)
    for i in range(1, Nb):
        ii = np.where(z == i)
        Ek[i] = np.sum(uiui[ii]) / len(ii[0])

    Ek = solver.comm.allreduce(Ek)

    ## Rij
    #for i in range(3):
        #c.U[i] = c.FFT.ifftn(c.U_hat[i], c.U[i])
    #X = c.FFT.get_local_mesh()
    #R = np.sqrt(X[0]**2 + X[1]**2 + X[2]**2)
    ## Sample
    #Rii = np.zeros_like(c.U)
    #Rii[0] = c.FFT.ifftn(np.conj(c.U_hat[0])*c.U_hat[0], Rii[0])
    #Rii[1] = c.FFT.ifftn(np.conj(c.U_hat[1])*c.U_hat[1], Rii[1])
    #Rii[2] = c.FFT.ifftn(np.conj(c.U_hat[2])*c.U_hat[2], Rii[2])

    #R11 = np.sum(Rii[:, :, 0, 0] + Rii[:, 0, :, 0] + Rii[:, 0, 0, :], axis=0)/3

    #Nr = 20
    #rbins = np.linspace(0, 2*np.pi, Nr)
    #rz = np.digitize(R, rbins, right=True)
    #RR = np.zeros(Nr)
    #for i in range(Nr):
        #ii = np.where(rz == i)
        #RR[i] = np.sum(Rii[0][ii] + Rii[1][ii] + Rii[2][ii]) / len(ii[0])

    #Rxx = np.zeros((3, config.params.N[0]))
    #for i in range(config.params.N[0]):
        #Rxx[0, i] = (c.U[0] * np.roll(c.U[0], -i, axis=0)).mean()
        #Rxx[1, i] = (c.U[0] * np.roll(c.U[0], -i, axis=1)).mean()
        #Rxx[2, i] = (c.U[0] * np.roll(c.U[0], -i, axis=2)).mean()

    return Ek, bins

k = []
w = []
im1 = None
kold = zeros(1)

energy_target = None
energy_new = None
def update(context):
    global k, w, im1, energy_target, energy_new
    c = context
    params = config.params
    solver = config.solver
    curl_hat = c.work[(c.U_hat, 2, True)]

    if energy_target is None:
        energy_target = energy_fourier(solver.comm, c.U_hat)
    else:
        energy_target = energy_new

    if params.solver == 'VV':
        c.U_hat = solver.cross2(c.U_hat, c.K_over_K2, c.W_hat)

    energy_new = energy_fourier(solver.comm, c.U_hat)
    energy_lower = energy_fourier(solver.comm, c.U_hat*c.mask)
    energy_upper = energy_new - energy_lower

    alpha2  = (energy_target - energy_upper) /energy_lower
    alpha = np.sqrt(alpha2)

    c.dU[:] = alpha*c.mask*c.U_hat
    c.U_hat *= (alpha*c.mask + (1-c.mask))
    #c.U_hat[:] -= (c.K[0]*c.U_hat[0]+c.K[1]*c.U_hat[1]+c.K[2]*c.U_hat[2])*c.K_over_K2

    energy_new = energy_fourier(solver.comm, c.U_hat)

    if params.solver == 'VV':
        c.W_hat = solver.cross2(c.W_hat, c.K, c.U_hat)

    if (params.tstep % params.compute_energy == 0 or
          params.tstep % params.plot_step == 0 and params.plot_step > 0):
        U = solver.get_velocity(**c)
        curl = solver.get_curl(**c)
        if params.solver == 'NS':
            P = solver.get_pressure(**c)

    K = c.K
    if plt is not None:
        if params.tstep % params.plot_step == 0 and solver.rank == 0 and params.plot_step > 0:
            div_u =  c.work[(U[0], 3, True)]
            if hasattr(c, 'FFT'):
                div_u = c.FFT.ifftn(1j*(K[0]*c.U_hat[0]+K[1]*c.U_hat[1]+K[2]*c.U_hat[2]), div_u)
            else:
                div_u = c.T.backward(1j*(K[0]*c.U_hat[0]+K[1]*c.U_hat[1]+K[2]*c.U_hat[2]), div_u)

            if im1 is None:
                plt.figure()
                #im1 = plt.contourf(c.X[1][:,:,0], c.X[0][:,:,0], div_u[:,:,10], 100)
                im1 = plt.contourf(c.X[1][:,:,0], c.X[0][:,:,0], c.U[0,:,:,10], 100)
                plt.colorbar(im1)
                plt.draw()
                globals().update(im1=im1)
            else:
                im1.ax.clear()
                #im1.ax.contourf(c.X[1][:,:,0], c.X[0][:,:,0], div_u[:,:,10], 100)
                im1.ax.contourf(c.X[1][:,:,0], c.X[0][:,:,0], c.U[0,:,:,10], 100)
                im1.autoscale()
            plt.pause(1e-6)

    if params.tstep % params.compute_spectrum == 0:
        Ek, bins = spectrum(solver, context)
        context.hdf5file.f = h5py.File(context.hdf5file.fname, driver='mpio', comm=solver.comm)
        context.hdf5file.f['Turbulence/Ek'].create_dataset(str(params.tstep), data=Ek)
        context.hdf5file.f.close()

    if params.tstep % params.compute_energy == 0:
        dx, L = params.dx, params.L
        if 'NS' in params.solver:
            #ww = solver.comm.reduce(sum(curl*curl)/np.prod(params.N)/2)

            #curl_hat = c.work[(c.U_hat, 2, True)]
            #curl_hat = solver.cross2(curl_hat, K, c.U_hat)
            #ww = energy_fourier(solver.comm, params.N, curl_hat)/np.prod(params.N)/2

            duidxj = c.work[(((3,3)+c.U[0].shape), c.float, 0)]
            for i in range(3):
                for j in range(3):
                    if hasattr(c, 'FFT'):
                        duidxj[i,j] = c.FFT.ifftn(1j*K[j]*c.U_hat[i], duidxj[i,j])
                    else:
                        duidxj[i,j] = c.T.backward(1j*K[j]*c.U_hat[i], duidxj[i,j])

            ww2 = solver.comm.reduce(sum(duidxj*duidxj))

            ddU = c.work[(((3,)+c.U[0].shape), c.float, 0)]
            dU = solver.ComputeRHS(c.dU, c.U_hat, solver, **c)
            for i in range(3):
                if hasattr(c, 'FFT'):
                    ddU[i] = c.FFT.ifftn(dU[i], ddU[i])
                else:
                    ddU[i] = c.T.backward(dU[i], ddU[i])

            ww3 = solver.comm.reduce(sum(ddU*U))

            ##if solver.rank == 0:
                ##print('W ', params.nu*ww, params.nu*ww2, ww3, ww-ww2)
            curl_hat = solver.cross2(curl_hat, K, c.U_hat)
            dissipation = energy_fourier(solver.comm, curl_hat)
            div_u =  c.work[(c.U[0], 3, True)]
            if hasattr(c, 'FFT'):
                div_u = c.FFT.ifftn(1j*(K[0]*c.U_hat[0]+K[1]*c.U_hat[1]+K[2]*c.U_hat[2]), div_u)
            else:
                div_u = c.T.backward(1j*(K[0]*c.U_hat[0]+K[1]*c.U_hat[1]+K[2]*c.U_hat[2]), div_u)

            div_u = np.sum(div_u**2)
            div_u2 = energy_fourier(solver.comm, 1j*(K[0]*c.U_hat[0]+K[1]*c.U_hat[1]+K[2]*c.U_hat[2]))

            kold[0] = energy_new
            if solver.rank == 0:
                k.append(energy_new)
                w.append(dissipation)
                print(params.t, alpha, energy_new, dissipation*params.nu, ww2*params.nu, ww3, div_u, div_u2)

        if 'VV' in params.solver:
            div_u =  c.work[(c.U[0], 3, True)]
            div_u = c.FFT.ifftn(1j*(K[0]*c.U_hat[0]+K[1]*c.U_hat[1]+K[2]*c.U_hat[2]), div_u)
            div_u = np.sum(div_u**2)
            div_u2 = energy_fourier(solver.comm, 1j*(K[0]*c.U_hat[0]+K[1]*c.U_hat[1]+K[2]*c.U_hat[2]))
            if solver.rank == 0:
                print(params.t, alpha, energy_new, div_u, div_u2)

    #if params.tstep % params.compute_energy == 1:
        #if 'NS' in params.solver:
            #kk2 = comm.reduce(sum(U.astype(float64)*U.astype(float64))*dx[0]*dx[1]*dx[2]/L[0]/L[1]/L[2]/2)
            #if rank == 0:
                #print 0.5*(kk2-kold[0])/params.dt


if __name__ == "__main__":
    import h5py
    config.update(
        {
        'nu': 0.005,             # Viscosity
        'dt': 0.005,                 # Time step
        'T': 0.05,                   # End time
        'L': [2.*pi, 2.*pi, 2.*pi],
        'M': [7, 7, 7],
        'checkpoint': 100,
        'write_result': 100,
        #'decomposition': 'pencil',
        #'Pencil_alignment': 'Y',
        #'P1': 2
        },  "triplyperiodic"
    )
    config.triplyperiodic.add_argument("--compute_energy", type=int, default=10)
    config.triplyperiodic.add_argument("--compute_spectrum", type=int, default=10)
    config.triplyperiodic.add_argument("--plot_step", type=int, default=1000)
    config.triplyperiodic.add_argument("--Kf2", type=int, default=2)
    config.triplyperiodic.add_argument("--a0", type=float, default=5.5)
    sol = get_solver(update=update, mesh="triplyperiodic")

    context = sol.get_context()
    initialize(sol, context)
    Ek, bins = spectrum(sol, context)
    context.hdf5file.fname = "NS_isotropic_{}_{}_{}.h5".format(*config.params.M)
    context.hdf5file.f = h5py.File(context.hdf5file.fname, driver='mpio', comm=sol.comm)
    context.hdf5file._init_h5file(config.params, sol)
    context.hdf5file.f.create_group("Turbulence")
    context.hdf5file.f["Turbulence"].create_group("Ek")
    bins = np.array(bins)
    context.hdf5file.f["Turbulence"].create_dataset("bins", data=bins)
    context.hdf5file.f.close()
    solve(sol, context)

    #context.hdf5file._init_h5file(config.params, **context)
    #context.hdf5file.f.close()