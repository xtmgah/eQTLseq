"""Implements run()."""

import numpy as _nmp

from eQTLseq.ModelNBinomGibbs import ModelNBinomGibbs as _ModelNBinomGibbs
from eQTLseq.ModelNormalGibbs import ModelNormalGibbs as _ModelNormalGibbs
from eQTLseq.ModelTraitNormalGibbs import ModelTraitNormalGibbs as _ModelTraitNormalGibbs

from eQTLseq.ModelTraitNormalVB import ModelTraitNormalVB as _ModelTraitNormalVB
from eQTLseq.ModelNormalVB import ModelNormalVB as _ModelNormalVB

import eQTLseq.utils as _utils


def run(Y, G, kind='eQTLs', mdl='Normal', alg='Gibbs', norm=True, n_iters=1000, n_burnin=None, s2_lims=(1e-12, 1e12),
        rel_tol=1e-6):
    """Run an estimation algorithm for a specified number of iterations."""
    n_burnin = round(n_iters * 0.5) if n_burnin is None else n_burnin
    assert kind in ('eQTLs', 'Trait')
    assert mdl in ('Normal', 'NBinom')
    assert alg in ('Gibbs', 'VB')

    # normalize data if necessary
    if mdl == 'NBinom' and norm:
        Y = _utils.normalise_RNAseq_data(Y.T)[0].T

    # prepare model
    Model = {
        'eQTLs': {
            'Normal': {'Gibbs': _ModelNormalGibbs, 'VB': _ModelNormalVB},
            'NBinom': {'Gibbs': _ModelNBinomGibbs}
        },
        'Trait': {
            'Normal': {'Gibbs': _ModelTraitNormalGibbs, 'VB': _ModelTraitNormalVB}
        }
    }[kind][mdl][alg]
    mdl = Model(Y=Y, G=G, n_iters=n_iters, n_burnin=n_burnin, s2_lims=s2_lims)

    # loop
    itr, err, traces0 = 0, 1, mdl.traces[0, :]
    while itr < n_iters and _nmp.any(err > rel_tol):
        itr = itr + 1
        mdl.update(itr)

        traces1 = mdl.traces[itr, :]
        err = _nmp.abs((traces1 - traces0) / traces0)
        traces0 = traces1

        print('Iteration {0} of {1}'.format(itr, n_iters), end='\r')

    #
    return mdl.traces, mdl.estimates
