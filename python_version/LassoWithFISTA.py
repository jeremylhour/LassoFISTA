#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compute Lasso solution with FISTA Algo

NB : numba does not seem to improve the performance.

Created on Fri Jul 30 09:55:30 2021

@author: jeremylhour
"""
import numpy as np
from scipy.stats import norm
from time import time

from tqdm import tqdm

from numba import njit

# ------------------------------------------------------------------------
# AUXILIARY FUNCTIONS
# ------------------------------------------------------------------------
@njit
def proximal(x, delta, nopen):
    """
    proximal operator
    
    @param x (np.array): coefficient
    @param delta (float): lasso penalty
    @param nopen (list of int): variables that should not be penalized
    """
    y = np.maximum(np.absolute(x)-delta, np.zeros(len(x))) * np.sign(x)
    y[nopen] = x[nopen]
    return y

@njit
def LeastSq(beta, y, X):
    """
    Computes the least squares objective function
    
    @param beta (np.array): coefficient
    @param y (np.array): outcome
    @param X (np.array): regressors
    """
    eps = y - X @ beta
    return np.mean(eps**2)

@njit
def LeastSqgrad(beta, y, X):
    """
    Computes the least squares gradient
    
    @param beta (np.array): coefficient
    @param y (np.array): outcome
    @param X (np.array): regressors
    """
    return -2*(y - X @ beta) @ X / len(X)

@njit
def LassoObj(beta, y, X, delta, nopen):
    """
    Computes Lasso objective function
    
    @param beta (np.array): coefficient
    @param y (np.array): outcome
    @param X (np.array): regressors
    @param delta (float): lasso penalty
    @param nopen (list of int): variables that should not be penalized
    """
    if len(nopen)>0:
        return LeastSq(beta, y, X) + delta*np.sum(np.absolute(np.delete(beta, nopen)))
    else:
        return LeastSq(beta, y, X) + delta*np.sum(np.absolute(beta))
     
@njit 
def reweight(X, W):
    """
    reweights observations
    
    @param X (np.array):
    @param W (np.array): one-dimensional, of length X.shape[1]
    """
    return np.diag(np.sqrt(W)) @ X

# ------------------------------------------------------------------------
# DGP
# ------------------------------------------------------------------------
@njit
def DGP(n, p, rho=.4):
    """
    DGP :
        simulates some data
        
    @param n (int): number of observations
    @param p (int): dimension
    @param rho (float): correaltion coefficient between two consecutive error terms
    """
    Sigma = np.zeros((p, p))
    for k in range(p):
        for j in range(p):
            Sigma[k,j] = rho**np.absolute(k-j)
    Sigma_chol = np.linalg.cholesky(Sigma)
    
    beta = np.zeros(p)
    for j in range(1, int(p/2)):
        beta[j] = 1*(-1)**(j) / j**2
    
    # SIMULATE
    #X = np.random.multivariate_normal(np.zeros(p), Sigma, n)
    draws = np.array([np.random.normal() for b in range(n*p)])
    X = np.reshape(draws, (n, p)) @ np.transpose(Sigma_chol)
    y = X @ beta + np.array([np.random.normal() for b in range(n)])
    X = np.hstack((np.ones((n, 1)), X))
    return y, X

# ------------------------------------------------------------------------
# MAIN FUNCTIONS
# ------------------------------------------------------------------------
@njit
def computeLasso(y, X, Lambda, W, betaInit, nopen=[0], tol=1e-8, maxIter=1000, trace=False):
    """
    Computes the Lasso solution using FISTA algorithm
    
    @param y (np.array): outcome
    @param X (np.array): regressors
    @param Lambda (float): Lasso penalty
    @param W
    @param betaInit (np.array): initial values
    @param nopen (np.array): default value does not penalize the constant
    @param tol (float): tolerance
    @param maxIter (int): maximum number of iterations
    @param trace (bool): if True, print results
    """
    y, X = reweight(y, W), reweight(X, W)
    
    ### Set Algo. Values
    eta = 1/np.max(2* np.linalg.eigvals(np.transpose(X) @ X)/len(X))
    theta = 1
    theta_0 = theta
    beta, v = betaInit, betaInit
    convergenceFISTA = False
  
    k = 0
    while k <= maxIter:
        k += 1
        theta_0 = theta
        theta = (1+np.sqrt(1+4*theta_0**2))/2
        delta = (1-theta_0)/theta
    
        beta_0 = beta
        beta = proximal(v - eta*LeastSqgrad(v,y,X), Lambda*eta, nopen)
    
        v = (1-delta)*beta + delta*beta_0
    
        # Show objective function value
        if trace & (k%100 == 0):
            print("Objective Func. Value at iteration",k,":",LassoObj(beta,y,X,Lambda,nopen))
        if np.absolute(LassoObj(beta,y,X,Lambda,nopen)-LassoObj(beta_0,y,X,Lambda,nopen)) < tol:
            # Break if convergence
            convergenceFISTA = True
            break
    return beta, convergenceFISTA

def LassoFISTA(y, X, Lambda, nopen=[0], tol=1e-8, maxIter=1000, trace=False, W=None, betaInit=None):
    """
    Wrapper around Lasso solution using FISTA algorithm
    
    @param y (np.array): outcome
    @param X (np.array): regressors
    @param Lambda (float): Lasso penalty
    @param nopen (np.array): default value does not penalize the constant
    @param tol (float): tolerance
    @param maxIter (int): maximum number of iterations
    @param trace (bool): print results
    @param W
    @param betaInit (np.array): initial values
    """
    # Setting default values
    if W is None:
        W = np.ones(len(X))
    if betaInit is None:
        betaInit =  np.zeros(X.shape[1])
    
    # Compute solution
    beta, convergenceFISTA = computeLasso(y=y,
                                          X=X,
                                          Lambda=Lambda,
                                          W=W,
                                          betaInit=betaInit,
                                          nopen=nopen,
                                          tol=tol,
                                          maxIter=maxIter,
                                          trace=trace)
    
    objFuncVal = LassoObj(beta, y, X, Lambda, nopen)
    sqLossVal = LeastSq(beta, y, X)
    l1norm = np.sum(np.absolute(beta))
    return beta, objFuncVal, sqLossVal, l1norm, convergenceFISTA


if __name__ == '__main__':
    np.random.seed(999)
    n = 10000
    p = 500
    
    y, X = DGP(n=n, p=p)
    
    # COMPUTE LASSO
    c, g = 2, .1/np.log(np.max(X.shape))
    Lambda = c*norm.ppf(1-.5*g/len(X))/np.sqrt(len(X))
    
    print('First time (includes compiling)')
    start_time = time()
    betaL, valL, lossL, l1normL, cvFL = LassoFISTA(y, X, Lambda, nopen=np.array([0]), tol=1e-6, maxIter=1e6, trace=True)
    print("--- {:.2f} seconds ---".format(time() - start_time))
    
    print('Second time')
    y, X = DGP(n=n, p=p)
    start_time = time()
    betaL, valL, lossL, l1normL, cvFL = LassoFISTA(y, X, Lambda, nopen=np.array([0]), tol=1e-6, maxIter=1e6, trace=True)
    print("--- {:.2f} seconds ---".format(time() - start_time))
    
    print("Repeated 100 times")
    start_time = time()
    for b in tqdm(range(100)):
        betaL, valL, lossL, l1normL, cvFL = LassoFISTA(y, X, Lambda, nopen=np.array([0]), tol=1e-6, maxIter=1e6, trace=True)
    print("--- {:.2f} seconds ---".format(time() - start_time))