"""Implements ModelPoissonGibbs."""

import numpy as _nmp
import numpy.random as _rnd

from eQTLseq.ModelNormalStdGibbs import ModelNormalStdGibbs as _ModelNormalStdGibbs


class ModelPoisson2Gibbs(_ModelNormalStdGibbs):
    """An overdispersed Poisson model estimated using Gibbs sampling."""

    def __init__(self, **args):
        """TODO."""
        super().__init__(**args)

        Z = args['Z']
        n_samples, n_genes = Z.shape

        # initial conditions
        self.Y = _rnd.randn(n_samples, n_genes)

        self.mu = _nmp.mean(Z * _nmp.exp(-self.Y), 0)
        self.mu_sum, self.mu2_sum = _nmp.zeros(n_genes), _nmp.zeros(n_genes)
        self.Y_sum, self.Y2_sum = _nmp.zeros((n_samples, n_genes)), _nmp.zeros((n_samples, n_genes))

    def update(self, itr, **args):
        """TODO."""
        Z, G = args['Z'], args['G']

        # sample mu
        self.mu = _sample_mu(Z, self.Y)

        # sample Y
        self.Y = _sample_Y(Z, G, self.mu, self.Y, self.beta)
        self.Y = self.Y - _nmp.mean(self.Y, 0)

        # update beta, tau, zeta and eta
        GTY = G.T.dot(self.Y)
        super().update(itr, GTY=GTY, **args)

        if(itr > args['n_burnin']):
            self.Y_sum += self.Y
            self.Y2_sum += self.Y**2
            self.mu_sum += self.mu
            self.mu2_sum += self.mu**2

    def get_estimates(self, **args):
        """TODO."""
        n_iters, n_burnin = args['n_iters'], args['n_burnin']

        #
        N = n_iters - n_burnin
        mu_mean, Y_mean = self.mu_sum / N, self.Y_sum / N
        mu_var, Y_var = self.mu2_sum / N - mu_mean**2, self.Y2_sum / N - Y_mean**2

        extra = super().get_estimates(n_iters=n_iters, n_burnin=n_burnin)

        return {'mu': mu_mean, 'mu_var': mu_var, 'Y': Y_mean.T, 'Y_var': Y_var.T, **extra}

    def get_state(self, **args):
        """TODO."""
        return super().get_state()


def _sample_mu(Z, Y):
    n_samples, _ = Z.shape
    Z = Z * _nmp.exp(-Y)
    mu = _rnd.gamma(Z.sum(0), 1 / n_samples)

    #
    return mu


def _sample_Y(Z, G, mu, Y, beta):
    n_samples, n_genes = Z.shape

    # sample proposals from a normal prior
    means = mu * _nmp.exp(Y)

    Y_ = _rnd.normal(G.dot(beta.T), 1)
    means_ = mu * _nmp.exp(Y_)

    # compute loglik
    loglik = Z * _nmp.log(means) - means
    loglik_ = Z * _nmp.log(means_) - means_

    # do Metropolis step
    idxs = _nmp.log(_rnd.rand(n_samples, n_genes)) < loglik_ - loglik
    Y[idxs] = Y_[idxs]

    #
    return Y
