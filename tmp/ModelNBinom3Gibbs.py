"""Implements ModelNBinomGibbs2."""

import numpy as _nmp
import numpy.random as _rnd
import scipy.special as _spc


class ModelNBinom3Gibbs(object):
    """A negative binomial model estimated using Gibbs sampling."""

    def __init__(self, **args):
        """TODO."""
        Z, G = args['Z'], args['G']
        _, n_genes = Z.shape
        _, n_markers = G.shape

        # initial conditions
        self.tau = _nmp.ones(n_genes)
        self.eta = _nmp.ones(n_markers)
        self.zeta = _nmp.ones((n_genes, n_markers))
        self.beta = _rnd.randn(n_genes, n_markers) / n_markers
        self.mu_phi, self.tau_phi, self.phi = 0, 1, _nmp.exp(_rnd.randn(n_genes))
        self.mu = _nmp.mean(Z * _nmp.exp(-G.dot(self.beta.T)), 0)

        self.beta_sum, self.beta2_sum = _nmp.zeros((n_genes, n_markers)), _nmp.zeros((n_genes, n_markers))
        self.phi_sum, self.phi2_sum = _nmp.zeros(n_genes), _nmp.zeros(n_genes)
        self.mu_sum, self.mu2_sum = _nmp.zeros(n_genes), _nmp.zeros(n_genes)

    def update(self, itr, **args):
        """TODO."""
        Z, G = args['Z'], args['G']
        beta_thr, s2_lims = args['beta_thr'], args['s2_lims']

        # update beta
        self.beta = _sample_beta(Z, G, self.mu, self.phi, self.beta, self.tau, self.zeta, self.eta,
                                 beta_thr, s2_lims)

        # update tau, zeta and eta
        self.tau = _sample_tau(self.beta, self.zeta, self.eta)
        self.tau = _nmp.clip(self.tau, 1 / s2_lims[1], 1 / s2_lims[0])

        self.zeta = _sample_zeta(self.beta, self.tau, self.eta)
        self.zeta = _nmp.clip(self.zeta, 1 / s2_lims[1], 1 / s2_lims[0])

        self.eta = _sample_eta(self.beta, self.tau, self.zeta)
        self.eta = _nmp.clip(self.eta, 1 / s2_lims[1], 1 / s2_lims[0])

        # sample mu and phi
        self.mu = _sample_mu(Z, G, self.phi, self.beta)
        self.phi = _sample_phi(Z, G, self.mu, self.phi, self.beta, self.mu_phi, self.tau_phi)

        # sample mu_phi and tau_phi
        self.mu_phi, self.tau_phi = _sample_mu_tau_phi(self.phi)

        if(itr > args['n_burnin']):
            self.phi_sum += self.phi
            self.mu_sum += self.mu
            self.beta_sum += self.beta

            self.phi2_sum += self.phi**2
            self.mu2_sum += self.mu**2
            self.beta2_sum += self.beta**2

    def get_estimates(self, **args):
        """TODO."""
        N = args['n_iters'] - args['n_burnin']
        phi_mean, mu_mean, beta_mean = self.phi_sum / N, self.mu_sum / N, self.beta_sum / N

        phi_var, mu_var = self.phi2_sum / N - phi_mean**2, self.mu2_sum / N - mu_mean**2
        beta_var = self.beta2_sum / N - beta_mean**2

        return {
            'phi': phi_mean, 'phi_var': phi_var,
            'mu': mu_mean, 'mu_var': mu_var,
            'beta': beta_mean, 'beta_var': beta_var
        }

    def get_state(self, **args):
        """TODO."""
        return _nmp.sqrt((self.beta**2).sum())


def _sample_phi(Z, G, mu, phi, beta, mu_phi, tau_phi):
    n_samples, n_genes = Z.shape
    means = mu * _nmp.exp(G.dot(beta.T))

    # sample proposals from the prior
    alpha = 1 / phi
    pi = means / (alpha + means)

    phi_ = _nmp.exp(mu_phi + _rnd.randn(n_genes) / _nmp.sqrt(tau_phi))
    alpha_ = 1 / phi_
    pi_ = means / (alpha_ + means)

    # compute loglik
    loglik = (_spc.gammaln(Z + alpha) - _spc.gammaln(alpha) + alpha * _nmp.log1p(-pi) + Z * _nmp.log(pi)).sum(0)
    loglik_ = (_spc.gammaln(Z + alpha_) - _spc.gammaln(alpha_) + alpha_ * _nmp.log1p(-pi_) + Z * _nmp.log(pi_)).sum(0)

    # Metropolis step
    idxs = _nmp.log(_rnd.rand(n_genes)) < loglik_ - loglik
    phi[idxs] = phi_[idxs]

    #
    return phi


def _sample_mu(Z, G, phi, beta, a=0.5, b=0.5):
    n_samples, _ = Z.shape

    Z = Z * _nmp.exp(-G.dot(beta.T))
    alpha = 1 / phi

    c1 = a + Z.sum(0)
    c2 = b + n_samples * alpha

    pi = _rnd.beta(c1, c2)
    mu = alpha * pi / (1 - pi)

    #
    return mu


def _sample_mu_tau_phi(phi):
    n_genes = phi.size
    log_phi = _nmp.log(phi)
    log_phi2 = log_phi**2

    # sample tau_phi
    shape = 0.5 * n_genes
    rate = 0.5 * log_phi2.sum()
    tau_phi = _rnd.gamma(shape, 1 / rate)

    # sample mu_phi, given tau_phi
    mean = log_phi.sum() / n_genes
    prec = n_genes * tau_phi
    mu_phi = _rnd.normal(mean, 1 / _nmp.sqrt(prec))

    #
    return mu_phi, tau_phi


def _sample_beta_one_global(Z, G_j, G, mu, phi, beta_j, beta, tau, zeta_j, eta_j):
    """TODO."""
    _, n_genes = Z.shape

    alpha = 1 / phi
    m = mu * _nmp.exp(G.dot(beta.T))

    # sample proposals from a normal prior
    means = m * _nmp.exp(G_j[:, None] * beta_j)
    pi = means / (alpha + means)

    beta_j_ = _rnd.normal(0, 1 / _nmp.sqrt(tau * eta_j * zeta_j))
    means_ = m * _nmp.exp(G_j[:, None] * beta_j_)
    pi_ = means_ / (alpha + means_)

    # compute loglik
    loglik = (alpha * _nmp.log1p(-pi) + Z * _nmp.log(pi)).sum(0)
    loglik_ = (alpha * _nmp.log1p(-pi_) + Z * _nmp.log(pi_)).sum(0)

    # do Metropolis step
    idxs = _nmp.log(_rnd.rand(n_genes)) < loglik_ - loglik
    beta_j[idxs] = beta_j_[idxs]

    #
    return beta_j


def _sample_beta_one_local(Z, G_j, G, mu, phi, beta_j, beta, tau, zeta_j, eta_j, scale=0.01):
    """TODO."""
    _, n_genes = Z.shape

    alpha = 1 / phi
    m = mu * _nmp.exp(G.dot(beta.T))

    # sample proposals from a normal prior
    means = m * _nmp.exp(G_j[:, None] * beta_j)
    pi = means / (alpha + means)

    beta_j_ = beta_j + scale * _rnd.randn(n_genes)
    means_ = m * _nmp.exp(G_j[:, None] * beta_j_)
    pi_ = means_ / (alpha + means_)

    # compute loglik
    loglik = (alpha * _nmp.log1p(-pi) + Z * _nmp.log(pi)).sum(0) - 0.5 * tau * eta_j * zeta_j * beta_j**2
    loglik_ = (alpha * _nmp.log1p(-pi_) + Z * _nmp.log(pi_)).sum(0) - 0.5 * tau * eta_j * zeta_j * beta_j_**2

    # do Metropolis step
    idxs = _nmp.log(_rnd.rand(n_genes)) < loglik_ - loglik
    beta_j[idxs] = beta_j_[idxs]

    #
    return beta_j


def _sample_beta_one(Z, G_j, G, mu, phi, beta_j, beta, tau, zeta_j, eta_j):
    if _rnd.rand() < 0.5:
        beta_j = _sample_beta_one_local(Z, G_j, G, mu, phi, beta_j, beta, tau, zeta_j, eta_j)
    else:
        beta_j = _sample_beta_one_global(Z, G_j, G, mu, phi, beta_j, beta, tau, zeta_j, eta_j)

    return beta_j


def _sample_beta_(Z, G, mu, phi, beta, tau, zeta, eta):
    """TODO."""
    _, n_markers = G.shape

    idxs = _nmp.arange(n_markers)
    for j in _rnd.permutation(n_markers):
        not_j = j != idxs
        beta[:, j] = _sample_beta_one(Z, G[:, j], G[:, not_j], mu, phi, beta[:, j], beta[:, not_j], tau, zeta[:, j],
                                      eta[j])

    #
    return beta


def _sample_beta(Z, G, mu, phi, beta, tau, zeta, eta, beta_thr, s2_lims):
    """TODO."""
    # identify irrelevant genes and markers
    idxs = (_nmp.abs(beta) > beta_thr) & (zeta * eta * tau[:, None] < 1 / s2_lims[0])
    idxs[[0, 1], [0, 1]] = True  # just a precaution
    idxs_markers = _nmp.any(idxs, 0)
    idxs_genes = _nmp.any(idxs, 1)

    Z = Z[:, idxs_genes]
    G = G[:, idxs_markers]
    mu = mu[idxs_genes]
    phi = phi[idxs_genes]
    beta_ = beta[idxs_genes, :][:, idxs_markers]
    zeta = zeta[idxs_genes, :][:, idxs_markers]
    eta = eta[idxs_markers]
    tau = tau[idxs_genes]

    beta[_nmp.ix_(idxs_genes, idxs_markers)] = _sample_beta_(Z, G, mu, phi, beta_, tau, zeta, eta)

    #
    return beta


def _sample_tau(beta, zeta, eta):
    """TODO."""
    _, n_markers = beta.shape

    # sample zeta
    shape = 0.5 * n_markers
    rate = 0.5 * (eta * beta**2 * zeta).sum(1)
    tau = _rnd.gamma(shape, 1 / rate)

    ##
    return tau


def _sample_zeta(beta, tau, eta):
    """TODO."""
    # sample zeta
    shape = 0.5
    rate = 0.5 * eta * beta**2 * tau[:, None]
    zeta = shape / rate  # _rnd.gamma(shape, 1 / rate)

    ##
    return zeta


def _sample_eta(beta, tau, zeta):
    """TODO."""
    n_genes, _ = beta.shape

    # sample zeta
    shape = 0.5 * n_genes
    rate = 0.5 * (zeta * beta**2 * tau[:, None]).sum(0)
    eta = _rnd.gamma(shape, 1 / rate)

    ##
    return eta
