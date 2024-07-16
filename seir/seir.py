# import numpy as np
# import torch
# import matplotlib.pyplot as plt
# from sklearn.gaussian_process import GaussianProcessRegressor
# from sklearn.gaussian_process.kernels import RBF, Matern, RationalQuadratic, ExpSineSquared, DotProduct, ConstantKernel
# from botorch.models.model import Model
# from botorch.acquisition import UpperConfidenceBound
# from botorch.optim import optimize_acqf
# from torch import nn
# from torch.distributions import Normal

# # device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
# device = torch.device("cpu")

# # Encodes inputs of the form (x_i,y_i) into representations, r_i.
# class REncoder(nn.Module):
#     def __init__(self, in_dim, out_dim, init_func=torch.nn.init.normal_):
#         super(REncoder, self).__init__()
#         self.l1_size = 16
#         self.l2_size = 8
#         self.l1 = nn.Linear(in_dim, self.l1_size)
#         self.l2 = nn.Linear(self.l1_size, self.l2_size)
#         self.l3 = nn.Linear(self.l2_size, out_dim)
#         self.a1 = nn.Sigmoid()
#         self.a2 = nn.Sigmoid()
#         if init_func is not None:
#             init_func(self.l1.weight)
#             init_func(self.l2.weight)
#             init_func(self.l3.weight)
        
#     def forward(self, inputs):
#         return self.l3(self.a2(self.l2(self.a1(self.l1(inputs)))))

# # Converts aggregated representations, r, into parameters, (mu, sigma), of the latent variable, z.
# class ZEncoder(nn.Module):
#     def __init__(self, in_dim, out_dim, init_func=torch.nn.init.normal_):
#         super(ZEncoder, self).__init__()
#         self.m1_size = out_dim
#         self.logvar1_size = out_dim
#         self.m1 = nn.Linear(in_dim, self.m1_size)
#         self.logvar1 = nn.Linear(in_dim, self.m1_size)
#         if init_func is not None:
#             init_func(self.m1.weight)
#             init_func(self.logvar1.weight)
        
#     def forward(self, inputs):
#         return self.m1(inputs), self.logvar1(inputs)
    
# # Converts the latent variable, z, and the targets, x*, into predictions, y*.
# class Decoder(nn.Module):
#     def __init__(self, in_dim, out_dim, init_func=torch.nn.init.normal_):
#         super(Decoder, self).__init__()
#         self.l1_size = 8
#         self.l2_size = 16
#         self.l1 = nn.Linear(in_dim, self.l1_size)
#         self.l2 = nn.Linear(self.l1_size, self.l2_size)
#         self.l3 = nn.Linear(self.l2_size, out_dim)
#         if init_func is not None:
#             init_func(self.l1.weight)
#             init_func(self.l2.weight)
#             init_func(self.l3.weight)
#         self.a1 = nn.Sigmoid()
#         self.a2 = nn.Sigmoid()
        
#     def forward(self, x_pred, z):
#         zs_reshaped = z.unsqueeze(-1).expand(z.shape[0], x_pred.shape[0]).transpose(0,1)
#         xpred_reshaped = x_pred
#         xz = torch.cat([xpred_reshaped, zs_reshaped], dim=1)
#         return self.l3(self.a2(self.l2(self.a1(self.l1(xz))))).squeeze(-1)

# # The whole neural process architecture.
# class DCRNNModel(nn.Module):
#     def __init__(self, x_dim, y_dim, r_dim, z_dim, init_func=torch.nn.init.normal_):
#         super().__init__()
#         self.repr_encoder = REncoder(x_dim + y_dim, r_dim)
#         self.z_encoder = ZEncoder(r_dim, z_dim)
#         self.decoder = Decoder(x_dim + z_dim, y_dim)
#         self.z_mu_all = 0
#         self.z_logvar_all = 0
#         self.z_mu_context = 0
#         self.z_logvar_context = 0
#         self.zs = 0
#         self.zdim = z_dim
    
#     # Generate parameters for q(z|C U T).
#     def data_to_z_params(self, x, y):
#         xy = torch.cat([x, y], dim=1)
#         rs = self.repr_encoder(xy)
#         r_agg = rs.mean(dim=0)
#         return self.z_encoder(r_agg)
    
#     # Sample z from the parameters.
#     def sample_z(self, mu, logvar, n=1):
#         if n == 1:
#             eps = torch.autograd.Variable(logvar.data.new(self.zdim).normal_()).to(device)
#         else:
#             eps = torch.autograd.Variable(logvar.data.new(n, self.zdim).normal_()).to(device)
#         std = 0.1 + 0.9 * torch.sigmoid(logvar)
#         return mu + std * eps

#     # Calculate the KL divergence between q(z|C U T) and q(z|C)
#     def KLD_gaussian(self):
#         mu_q, logvar_q, mu_p, logvar_p = self.z_mu_all, self.z_logvar_all, self.z_mu_context, self.z_logvar_context
#         std_q = 0.1 + 0.9 * torch.sigmoid(logvar_q)
#         std_p = 0.1 + 0.9 * torch.sigmoid(logvar_p)
#         p = Normal(mu_p, std_p)
#         q = Normal(mu_q, std_q)
#         return torch.distributions.kl_divergence(p, q).sum()
        
#     # Forward pass through the neural process.
#     def forward(self, x_t, x_c, y_c, x_ct, y_ct):
#         self.z_mu_all, self.z_logvar_all = self.data_to_z_params(x_ct, y_ct)
#         self.z_mu_context, self.z_logvar_context = self.data_to_z_params(x_c, y_c)
#         self.zs = self.sample_z(self.z_mu_all, self.z_logvar_all)
#         return self.decoder(x_t, self.zs)

# # Mean Absolute Error loss.
# def MAE(pred, target):
#     loss = torch.abs(pred - target)
#     return loss.mean()

# def random_split_context_target(x,y, n_context):
#     """Helper function to split randomly into context and target"""
#     ind = np.arange(x.shape[0])
#     mask = np.random.choice(ind, size=n_context, replace=False)
#     return x[mask], y[mask], np.delete(x, mask, axis=0), np.delete(y, mask, axis=0)

# # Wrapper class to integrate Neural Process with BoTorch.
# class NeuralProcessModel(Model):
#     def __init__(self, x_dim, y_dim, r_dim, z_dim):
#         super().__init__()
#         self.model = DCRNNModel(x_dim, y_dim, r_dim, z_dim).to(device)
#         self.opt = torch.optim.Adam(self.model.parameters(), lr=1e-3)
    
#     # Train the neural process.
#     def fit(self, x_train, y_train, n_epochs):
#         x_train = x_train.clone().detach().requires_grad_(True).to(device)
#         y_train = y_train.clone().detach().requires_grad_(True).to(device)
#         for epoch in range(n_epochs):
#             self.opt.zero_grad()
#             x_context, y_context, x_target, y_target = random_split_context_target(x_train, y_train, int(len(y_train) * 0.1))
#             x_c = x_context.clone().detach().requires_grad_(True).to(device)
#             x_t = x_target.clone().detach().requires_grad_(True).to(device)
#             y_c = y_context.clone().detach().requires_grad_(True).to(device)
#             y_t = y_target.clone().detach().requires_grad_(True).to(device)
#             x_ct = torch.cat([x_c, x_t], dim=0).to(device)
#             y_ct = torch.cat([y_c, y_t], dim=0).to(device)
#             y_pred = self.model(x_t, x_c, y_c, x_ct, y_ct)
#             train_loss = MAE(y_pred, y_t) + self.model.KLD_gaussian()
#             train_loss.backward()
#             self.opt.step()
    
#     # Generate the posterior distribution needed for BoTorch.
#     def posterior(self, x, observation_noise=False):
#         x = torch.tensor(x, dtype=torch.float32).to(device)
#         y_pred = self.model.decoder(x, self.model.zs)
#         return Normal(y_pred, torch.tensor([1e-3], dtype=torch.float32).to(device))

# # Generate SEIR data
# num_days = 101
# num_simulations = 30
# beta = np.repeat(np.expand_dims(np.linspace(1.1, 4.0, 30), 1), 9, 1)
# epsilon = np.repeat(np.expand_dims(np.linspace(0.25, 0.65, 9), 0), 30, 0)
# beta_epsilon = np.stack([beta, epsilon], -1)
# beta_epsilon_train = beta_epsilon.reshape(-1, 2)

# beta = np.repeat(np.expand_dims(np.linspace(1.14, 3.88, 5), 1), 3, 1)
# epsilon = np.repeat(np.expand_dims(np.linspace(0.29, 0.59, 3), 0), 5, 0)
# beta_epsilon = np.stack([beta, epsilon], -1)
# beta_epsilon_val = beta_epsilon.reshape(-1, 2)

# beta = np.repeat(np.expand_dims(np.linspace(1.24, 3.98, 5), 1), 3, 1)
# epsilon = np.repeat(np.expand_dims(np.linspace(0.31, 0.61, 3), 0), 5, 0)
# beta_epsilon = np.stack([beta, epsilon], -1)

# gamma = 0.5

# # SEIR model with clipping to handle overflow and invalid value issues
# def seir_model(num_days, beta, epsilon):
#     seir_array = np.zeros((num_days, 4))
#     seir_array[0] = [0.99, 0.01, 0, 0]  # Initial conditions: S, E, I, R

#     for t in range(num_days - 1):
#         S_to_E = beta * seir_array[t][0] * seir_array[t][1]
#         E_to_I = epsilon * seir_array[t][1]
#         I_to_R = gamma * seir_array[t][2]

#         S_to_E = np.clip(S_to_E, 0, 1)
#         E_to_I = np.clip(E_to_I, 0, 1)
#         I_to_R = np.clip(I_to_R, 0, 1)

#         seir_array[t + 1][0] = seir_array[t][0] - S_to_E
#         seir_array[t + 1][1] = seir_array[t][1] + S_to_E - E_to_I
#         seir_array[t + 1][2] = seir_array[t][2] + E_to_I - I_to_R
#         seir_array[t + 1][3] = seir_array[t][3] + I_to_R

#         seir_array[t + 1] = np.clip(seir_array[t + 1], 0, 1)

#     return seir_array

# # Create synthetic data
# num_days = 100
# x_train = []
# y_train = []

# for i in range(num_simulations):
#     for j in range(num_simulations):
#         if i < beta.shape[0] and j < beta.shape[1]:  # Check dimensions
#             seir_result = seir_model(num_days, beta[i][j], epsilon[i][j])
#             x_train.append(np.array([beta[i][j], epsilon[i][j]]))
#             y_train.append(seir_result[:, 2])  # Infected individuals

# x_train = np.array(x_train)
# y_train = np.array(y_train)

# # Normalize data
# x_mean = x_train.mean(axis=0)
# x_std = x_train.std(axis=0)
# y_mean = y_train.mean(axis=0)
# y_std = y_train.std(axis=0)

# x_train = (x_train - x_mean) / x_std
# y_train = (y_train - y_mean) / y_std

# # Convert data to torch tensors
# x_tensors = torch.tensor(x_train, dtype=torch.float32).to(device)
# y_tensors = torch.tensor(y_train, dtype=torch.float32).to(device)

# # Train the model
# model = NeuralProcessModel(2, num_days, 128, 128)
# model.fit(x_tensors, y_tensors, n_epochs=500)

# # Make predictions
# x_test = np.array([[1.5, 0.4], [2.5, 0.5], [3.5, 0.6]])
# x_test = (x_test - x_mean) / x_std
# posterior = model.posterior(x_test)
# y_pred = posterior.mean

# # Plot predictions
# for i in range(len(x_test)):
#     plt.plot(y_pred[i].detach().cpu().numpy() * y_std + y_mean, label=f'Test {i+1}')
# plt.legend()
# plt.show()



# -*- coding: utf-8 -*-
"""2D_iclr2022_SIR_NP_LIG_heldout.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1uBHJpKv6m3l356qoyajxyf2bRBM9VETY
"""

# Commented out IPython magic to ensure Python compatibility.
import numpy as np
from numpy.random import binomial
import torch
import matplotlib.pyplot as plt
# %matplotlib inline
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import (RBF, Matern, RationalQuadratic,
                                              ExpSineSquared, DotProduct,
                                              ConstantKernel)
from botorch.models.model import Model
from botorch.acquisition import UpperConfidenceBound
from botorch.optim import optimize_acqf
import torch.nn as nn
from torch.distributions import Normal
from sklearn import preprocessing
from scipy.stats import multivariate_normal

# device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
device = torch.device("cpu")


large = 25; med = 19; small = 12
params = {'axes.titlesize': large,
          'legend.fontsize': 20,
          'figure.figsize': (27, 8),
          'axes.labelsize': med,
          'xtick.labelsize': med,
          'ytick.labelsize': med,
          'figure.titlesize': med}
plt.rcParams.update(params)

"""# generate y ( sequence) using SEIR model:"""

def seir (num_days, beta_epsilon_flatten, num_simulations):
    mu = 1 #0.4
    all_cmpts = ['S', 'E', 'I', 'R', 'F']
    all_cases = ['E', 'I', 'R', 'F']

    x = range(num_days)

    ## model parameters
    ## initialization of california
    N = 100000 #39512000

    ## save the number of death (mean, std) for each senario
    train_mean_list = []
    train_std_list = []
    train_list = []

    for i in range (len(beta_epsilon_flatten)):
        init_I = int(2000) #2000
        init_R = int(0) #0
        init_E = int(2000) #2000

        ## save the number of individuals in each cmpt everyday
        dic_cmpts = dict()
        for cmpt in all_cmpts:
            dic_cmpts[cmpt] = np.zeros((num_simulations, num_days)).astype(int)

        dic_cmpts['S'][:, 0] = N - init_I - init_R - init_E
        dic_cmpts['I'][:, 0] = init_I
        dic_cmpts['E'][:, 0] = init_E
        dic_cmpts['R'][:, 0] = init_R
        

        ## save the number of new individuals entering each cmpt everyday
        dic_cases = dict()
        for cmpt in all_cmpts[1:]:
            dic_cases[cmpt] = np.zeros((num_simulations, num_days))

        ## run simulations
        for simu_id in range(num_simulations):
            for t in range(num_days-1):
                ## SEIR: stochastic
                flow_S2E = binomial(dic_cmpts['S'][simu_id, t], beta_epsilon_flatten[i,0] * dic_cmpts['I'][simu_id, t] / N)
                flow_E2I = binomial(dic_cmpts['E'][simu_id, t], beta_epsilon_flatten[i,1])
                flow_I2R = binomial(dic_cmpts['I'][simu_id, t], mu)
#                 print(t,flow_R2F)
                dic_cmpts['S'][simu_id, t+1] = dic_cmpts['S'][simu_id, t] - flow_S2E
                dic_cmpts['E'][simu_id, t+1] = dic_cmpts['E'][simu_id, t] + flow_S2E - flow_E2I
                dic_cmpts['I'][simu_id, t+1] = dic_cmpts['I'][simu_id, t] + flow_E2I - flow_I2R
                dic_cmpts['R'][simu_id, t+1] = dic_cmpts['R'][simu_id, t] + flow_I2R
                # dic_cmpts['F'][simu_id, t+1] = dic_cmpts['F'][simu_id, t] + flow_R2F

            
                ## get new cases per day
                dic_cases['E'][simu_id, t+1] = flow_S2E # exposed
                dic_cases['I'][simu_id, t+1] = flow_E2I # infectious
                dic_cases['R'][simu_id, t+1] = flow_I2R # removed
                # dic_cases['F'][simu_id, t+1] = flow_R2F # death 
        
        # rescale_cares_E = dic_cmpts['E'][...,1:]/N
        rescale_cares_I = dic_cmpts['I'][...,1:]/N*100
        # rescale_cares_R = dic_cmpts['R'][...,1:]/N

        train_list.append(rescale_cares_I)
        train_mean_list.append(np.mean(rescale_cares_I,axis=0))
        train_std_list.append(np.std(rescale_cares_I,axis=0))        

    train_meanset = np.stack(train_mean_list,0)
    train_stdset = np.stack(train_std_list,0)
    train_set = np.stack(train_list,0)
    return train_set, train_meanset, train_stdset

num_days = 101
num_simulations = 30
beta = np.repeat(np.expand_dims(np.linspace(1.1, 4.0, 30),1),9,1)
epsilon = np.repeat(np.expand_dims(np.linspace(0.25, 0.65, 9),0),30,0)
beta_epsilon = np.stack([beta,epsilon],-1)
beta_epsilon_train = beta_epsilon.reshape(-1,2)

beta = np.repeat(np.expand_dims(np.linspace(1.14, 3.88, 5),1),3,1)
epsilon = np.repeat(np.expand_dims(np.linspace(0.29, 0.59, 3),0),5,0)
beta_epsilon = np.stack([beta,epsilon],-1)
beta_epsilon_val = beta_epsilon.reshape(-1,2)

beta = np.repeat(np.expand_dims(np.linspace(1.24, 3.98, 5),1),3,1)
epsilon = np.repeat(np.expand_dims(np.linspace(0.31, 0.61, 3),0),5,0)
beta_epsilon = np.stack([beta,epsilon],-1)
beta_epsilon_test = beta_epsilon.reshape(-1,2)



"""# CNP"""

#reference: https://chrisorm.github.io/NGP.html
class REncoder(torch.nn.Module):
    """Encodes inputs of the form (x_i,y_i) into representations, r_i."""
    
    def __init__(self, in_dim, out_dim, init_func = torch.nn.init.normal_):
        super(REncoder, self).__init__()
        self.l1_size = 16 #16
        self.l2_size = 8 #8
        
        self.l1 = torch.nn.Linear(in_dim, self.l1_size)
        self.l2 = torch.nn.Linear(self.l1_size, self.l2_size)
        self.l3 = torch.nn.Linear(self.l2_size, out_dim)
        self.a1 = torch.nn.Sigmoid()
        self.a2 = torch.nn.Sigmoid()
        
        if init_func is not None:
            init_func(self.l1.weight)
            init_func(self.l2.weight)
            init_func(self.l3.weight)
        
    def forward(self, inputs):
        return self.l3(self.a2(self.l2(self.a1(self.l1(inputs)))))

class ZEncoder(torch.nn.Module):
    """Takes an r representation and produces the mean & standard deviation of the 
    normally distributed function encoding, z."""
    def __init__(self, in_dim, out_dim, init_func=torch.nn.init.normal_):
        super(ZEncoder, self).__init__()
        self.m1_size = out_dim
        self.logvar1_size = out_dim
        
        self.m1 = torch.nn.Linear(in_dim, self.m1_size)
        self.logvar1 = torch.nn.Linear(in_dim, self.m1_size)

        if init_func is not None:
            init_func(self.m1.weight)
            init_func(self.logvar1.weight)
        
    def forward(self, inputs):
        

        return self.m1(inputs), self.logvar1(inputs)
    
class Decoder(torch.nn.Module):
    """
    Takes the x star points, along with a 'function encoding', z, and makes predictions.
    """
    def __init__(self, in_dim, out_dim, init_func=torch.nn.init.normal_):
        super(Decoder, self).__init__()
        self.l1_size = 8 #8
        self.l2_size = 16 #16
        
        self.l1 = torch.nn.Linear(in_dim, self.l1_size)
        self.l2 = torch.nn.Linear(self.l1_size, self.l2_size)
        self.l3 = torch.nn.Linear(self.l2_size, out_dim)
        
        if init_func is not None:
            init_func(self.l1.weight)
            init_func(self.l2.weight)
            init_func(self.l3.weight)
        
        self.a1 = torch.nn.Sigmoid()
        self.a2 = torch.nn.Sigmoid()
        
    def forward(self, x_pred, z):
        """x_pred: No. of data points, by x_dim
        z: No. of samples, by z_dim
        """
        zs_reshaped = z.unsqueeze(-1).expand(z.shape[0], x_pred.shape[0]).transpose(0,1)
        xpred_reshaped = x_pred
        
        xz = torch.cat([xpred_reshaped, zs_reshaped], dim=1)

        return self.l3(self.a2(self.l2(self.a1(self.l1(xz))))).squeeze(-1)

def MAE(pred, target):
    loss = torch.abs(pred-target)
    return loss.mean()

class NeuralProcessModel(Model):
    def __init__(self, x_dim, y_dim, r_dim, z_dim):
        super().__init__()
        self.model = DCRNNModel(x_dim, y_dim, r_dim, z_dim).to(device)
        self.opt = torch.optim.Adam(self.model.parameters(), lr=1e-3)
    
    def fit(self, x_train, y_train, n_epochs):
        x_train = torch.tensor(x_train, dtype=torch.float32).to(device)
        y_train = torch.tensor(y_train, dtype=torch.float32).to(device)
        for epoch in range(n_epochs):
            self.opt.zero_grad()
            x_context, y_context, x_target, y_target = random_split_context_target(x_train, y_train, int(len(y_train) * 0.1))
            x_c = torch.tensor(x_context, dtype=torch.float32).to(device)
            x_t = torch.tensor(x_target, dtype=torch.float32).to(device)
            y_c = torch.tensor(y_context, dtype=torch.float32).to(device)
            y_t = torch.tensor(y_target, dtype=torch.float32).to(device)
            x_ct = torch.cat([x_c, x_t], dim=0).to(device)
            y_ct = torch.cat([y_c, y_t], dim=0).to(device)
            y_pred = self.model(x_t, x_c, y_c, x_ct, y_ct)
            train_loss = MAE(y_pred, y_t) + self.model.KLD_gaussian()
            train_loss.backward()
            self.opt.step()
    
    def posterior(self, x, observation_noise=False):
        x = torch.tensor(x, dtype=torch.float32).to(device)
        y_pred = self.model.decoder(x, self.model.zs)
        return Normal(y_pred, torch.tensor([1e-3], dtype=torch.float32).to(device))
    
class DCRNNModel(nn.Module):
    def __init__(self, x_dim, y_dim, r_dim, z_dim, init_func=torch.nn.init.normal_):
        super().__init__()
        self.repr_encoder = REncoder(x_dim+y_dim, r_dim) # (x,y)->r
        self.z_encoder = ZEncoder(r_dim, z_dim) # r-> mu, logvar
        self.decoder = Decoder(x_dim+z_dim, y_dim) # (x*, z) -> y*
        self.z_mu_all = 0
        self.z_logvar_all = 0
        self.z_mu_context = 0
        self.z_logvar_context = 0
        self.zs = 0
        self.zdim = z_dim
    
    def data_to_z_params(self, x, y):
        """Helper to batch together some steps of the process."""
        xy = torch.cat([x,y], dim=1)
        rs = self.repr_encoder(xy)
        r_agg = rs.mean(dim=0) # Average over samples
        return self.z_encoder(r_agg) # Get mean and variance for q(z|...)
    
    def sample_z(self, mu, logvar,n=1):
        """Reparameterisation trick."""
        if n == 1:
            eps = torch.autograd.Variable(logvar.data.new(z_dim).normal_()).to(device)
        else:
            eps = torch.autograd.Variable(logvar.data.new(n,z_dim).normal_()).to(device)
        
        # std = torch.exp(0.5 * logvar)
        std = 0.1+ 0.9*torch.sigmoid(logvar)
        return mu + std * eps

    def KLD_gaussian(self):
        """Analytical KLD between 2 Gaussians."""
        mu_q, logvar_q, mu_p, logvar_p = self.z_mu_all, self.z_logvar_all, self.z_mu_context, self.z_logvar_context

        std_q = 0.1+ 0.9*torch.sigmoid(logvar_q)
        std_p = 0.1+ 0.9*torch.sigmoid(logvar_p)
        p = torch.distributions.Normal(mu_p, std_p)
        q = torch.distributions.Normal(mu_q, std_q)
        return torch.distributions.kl_divergence(p, q).sum()
        

    def forward(self, x_t, x_c, y_c, x_ct, y_ct):
        """
        """
        
        self.z_mu_all, self.z_logvar_all = self.data_to_z_params(x_ct, y_ct)
        self.z_mu_context, self.z_logvar_context = self.data_to_z_params(x_c, y_c)
        self.zs = self.sample_z(self.z_mu_all, self.z_logvar_all)
        return self.decoder(x_t, self.zs)

def random_split_context_target(x,y, n_context):
    """Helper function to split randomly into context and target"""
    ind = np.arange(x.shape[0])
    mask = np.random.choice(ind, size=n_context, replace=False)
    return x[mask], y[mask], np.delete(x, mask, axis=0), np.delete(y, mask, axis=0)

def sample_z(mu, logvar,n=1):
    """Reparameterisation trick."""
    if n == 1:
        eps = torch.autograd.Variable(logvar.data.new(z_dim).normal_())
    else:
        eps = torch.autograd.Variable(logvar.data.new(n,z_dim).normal_())
    
    std = 0.1+ 0.9*torch.sigmoid(logvar)
    return mu + std * eps

def data_to_z_params(x, y):
    """Helper to batch together some steps of the process."""
    xy = torch.cat([x,y], dim=1)
    rs = dcrnn.repr_encoder(xy)
    r_agg = rs.mean(dim=0) # Average over samples
    return dcrnn.z_encoder(r_agg) # Get mean and variance for q(z|...)

def test(x_train, y_train, x_test):
    with torch.no_grad():
      z_mu, z_logvar = data_to_z_params(x_train.to(device),y_train.to(device))
      
      output_list = []
      for i in range (len(x_test)):
          zsamples = sample_z(z_mu, z_logvar) 
          output = dcrnn.decoder(x_test[i:i+1].to(device), zsamples).cpu()
          output_list.append(output.detach().numpy())
    
    return np.concatenate(output_list)

def train(n_epochs, x_train, y_train, x_val, y_val, x_test, y_test, n_display=500, patience = 5000): #7000, 1000
    train_losses = []
    # mae_losses = []
    # kld_losses = []
    val_losses = []
    test_losses = []

    means_test = []
    stds_test = []
    N = 100000 #population
    min_loss = 0. # for early stopping
    wait = 0
    min_loss = float('inf')
    
    for t in range(n_epochs): 
        opt.zero_grad()
        #Generate data and process
        x_context, y_context, x_target, y_target = random_split_context_target(
                                x_train, y_train, int(len(y_train)*0.1)) #0.25, 0.5, 0.05,0.015, 0.01
        # print(x_context.shape, y_context.shape, x_target.shape, y_target.shape)    

        x_c = torch.from_numpy(x_context).float().to(device)
        x_t = torch.from_numpy(x_target).float().to(device)
        y_c = torch.from_numpy(y_context).float().to(device)
        y_t = torch.from_numpy(y_target).float().to(device)

        x_ct = torch.cat([x_c, x_t], dim=0).float().to(device)
        y_ct = torch.cat([y_c, y_t], dim=0).float().to(device)

        y_pred = dcrnn(x_t, x_c, y_c, x_ct, y_ct)

        train_loss = N * MAE(y_pred, y_t)/100 + dcrnn.KLD_gaussian()
        mae_loss = N * MAE(y_pred, y_t)/100
        kld_loss = dcrnn.KLD_gaussian()
        
        train_loss.backward()
        torch.nn.utils.clip_grad_norm_(dcrnn.parameters(), 5) #10
        opt.step()
        
        #val loss
        y_val_pred = test(torch.from_numpy(x_train).float(),torch.from_numpy(y_train).float(),
                      torch.from_numpy(x_val).float())
        val_loss = N * MAE(torch.from_numpy(y_val_pred).float(),torch.from_numpy(y_val).float())/100
        #test loss
        y_test_pred = test(torch.from_numpy(x_train).float(),torch.from_numpy(y_train).float(),
                      torch.from_numpy(x_test).float())
        test_loss = N * MAE(torch.from_numpy(y_test_pred).float(),torch.from_numpy(y_test).float())/100

        if t % n_display ==0:
            print('train loss:', train_loss.item(), 'mae:', mae_loss.item(), 'kld:', kld_loss.item())
            print('val loss:', val_loss.item(), 'test loss:', test_loss.item())

        if t % (n_display/10) ==0:
            train_losses.append(train_loss.item())
            val_losses.append(val_loss.item())
            test_losses.append(test_loss.item())
            # mae_losses.append(mae_loss.item())
            # kld_losses.append(kld_loss.item())

        #early stopping
        if val_loss < min_loss:
            wait = 0
            min_loss = val_loss
            
        elif val_loss >= min_loss:
            wait += 1
            if wait == patience:
                print('Early stopping at epoch: %d' % t)
                return train_losses, val_losses, test_losses, dcrnn.z_mu_all, dcrnn.z_logvar_all
        
    return train_losses, val_losses, test_losses, dcrnn.z_mu_all, dcrnn.z_logvar_all

def select_data(x_train, y_train, beta_epsilon_all, yall_set, score_array, selected_mask):

    mask_score_array = score_array*(1-selected_mask)
    # print('mask_score_array',mask_score_array)
    select_index = np.argmax(mask_score_array)
    print('select_index:',select_index)


    selected_x = beta_epsilon_all[select_index:select_index+1]
    selected_y = yall_set[select_index]

    x_train1 = np.repeat(selected_x,num_simulations,axis =0)
    x_train = np.concatenate([x_train, x_train1],0)
    
    y_train1 = selected_y.reshape(-1,100)
    y_train = np.concatenate([y_train, y_train1],0)
 
    selected_mask[select_index] = 1
    
    return x_train, y_train, selected_mask

def calculate_score(x_train, y_train, beta_epsilon_all):
    x_train = torch.from_numpy(x_train).float()
    y_train = torch.from_numpy(y_train).float()

    # query z_mu, z_var of the current training data
    with torch.no_grad():
        z_mu, z_logvar = data_to_z_params(x_train.to(device),y_train.to(device))

        score_list = []
        for i in range(len(beta_epsilon_all)):
            # generate x_search
            x1 = beta_epsilon_all[i:i+1]
            x_search = np.repeat(x1,num_simulations,axis =0)
            x_search = torch.from_numpy(x_search).float()

            # generate y_search based on z_mu, z_var of current training data
            output_list = []
            for j in range (len(x_search)):
                zsamples = sample_z(z_mu, z_logvar) 
                output = dcrnn.decoder(x_search[j:j+1].to(device), zsamples).cpu()
                output_list.append(output.detach().numpy())

            y_search = np.concatenate(output_list)
            y_search = torch.from_numpy(y_search).float()

            x_search_all = torch.cat([x_train,x_search],dim=0)
            y_search_all = torch.cat([y_train,y_search],dim=0)

            # generate z_mu_search, z_var_search
            z_mu_search, z_logvar_search = data_to_z_params(x_search_all.to(device),y_search_all.to(device))
            
            # calculate and save kld
            mu_q, var_q, mu_p, var_p = z_mu_search,  0.1+ 0.9*torch.sigmoid(z_logvar_search), z_mu, 0.1+ 0.9*torch.sigmoid(z_logvar)

            std_q = torch.sqrt(var_q)
            std_p = torch.sqrt(var_p)

            p = torch.distributions.Normal(mu_p, std_p)
            q = torch.distributions.Normal(mu_q, std_q)
            score = torch.distributions.kl_divergence(p, q).sum()

            score_list.append(score.item())

        score_array = np.array(score_list)

    return score_array

"""BO search:"""

def mae_plot(mae, selected_mask,i,j):
    epsilon, beta  = np.meshgrid(np.linspace(0.25, 0.7, 10), np.linspace(1.1, 4.1, 31))
    selected_mask = selected_mask.reshape(30,9)
    mae_min, mae_max = 0, 1200

    fig, ax = plt.subplots(figsize=(16, 7))
    # f, (y1_ax) = plt.subplots(1, 1, figsize=(16, 10))

    c = ax.pcolormesh(beta-0.05, epsilon-0.025, mae, cmap='binary', vmin=mae_min, vmax=mae_max)
    ax.set_title('MAE Mesh')
    # set the limits of the plot to the limits of the data
    ax.axis([beta.min()-0.05, beta.max()-0.05, epsilon.min()-0.025, epsilon.max()-0.025])
    x,y = np.where(selected_mask==1)
    x = x*0.1+1.1
    y = y*0.05+0.25
    ax.plot(x, y, 'r*', markersize=15)
    fig.colorbar(c, ax=ax)
    ax.set_xlabel('Beta')
    ax.set_ylabel('Epsilon')
    plt.savefig('mae_plot_seed%d_itr%d.pdf' % (i,j))

def score_plot(score, selected_mask,i,j):
    epsilon, beta  = np.meshgrid(np.linspace(0.25, 0.7, 10), np.linspace(1.1, 4.1, 31))
    score_min, score_max = 0, 1
    selected_mask = selected_mask.reshape(30,9)
    score = score.reshape(30,9)
    fig, ax = plt.subplots(figsize=(16, 7))
    # f, (y1_ax) = plt.subplots(1, 1, figsize=(16, 10))

    c = ax.pcolormesh(beta-0.05, epsilon-0.025, score, cmap='binary', vmin=score_min, vmax=score_max)
    ax.set_title('Score Mesh')
    # set the limits of the plot to the limits of the data
    ax.axis([beta.min()-0.05, beta.max()-0.05, epsilon.min()-0.025, epsilon.max()-0.025])
    x,y = np.where(selected_mask==1)
    x = x*0.1+1.1
    y = y*0.05+0.25
    ax.plot(x, y, 'r*', markersize=15)
    fig.colorbar(c, ax=ax)
    ax.set_xlabel('Beta')
    ax.set_ylabel('Epsilon')
    plt.savefig('score_plot_seed%d_itr%d.pdf' % (i,j))

def MAE_MX(y_pred, y_test):
    N = 100000
    y_pred = y_pred.reshape(30,9, 30, 100)*N/100
    y_test = y_test.reshape(30,9, 30, 100)*N/100
    mae_matrix = np.mean(np.abs(y_pred - y_test),axis=(2,3))
    mae = np.mean(np.abs(y_pred - y_test))
    return mae_matrix, mae


beta_epsilon_all = beta_epsilon_train
yall_set, yall_mean, yall_std = seir(num_days,beta_epsilon_all,num_simulations)
y_all = yall_set.reshape(-1,100)
x_all = np.repeat(beta_epsilon_all,num_simulations,axis =0)


yval_set, yval_mean, yval_std = seir(num_days,beta_epsilon_val,num_simulations)
y_val = yval_set.reshape(-1,100)
x_val = np.repeat(beta_epsilon_val,num_simulations,axis =0)


ytest_set, ytest_mean, ytest_std = seir(num_days,beta_epsilon_test,num_simulations)
y_test = ytest_set.reshape(-1,100)
x_test = np.repeat(beta_epsilon_test,num_simulations,axis =0)

np.random.seed(3)
mask_init = np.zeros(len(beta_epsilon_all))
mask_init[:2] = 1

np.random.shuffle(mask_init)
selected_beta_epsilon = beta_epsilon_all[mask_init.astype('bool')]
x_train_init = np.repeat(selected_beta_epsilon,num_simulations,axis =0)

selected_y = yall_set[mask_init.astype('bool')]
y_train_init = selected_y.reshape(selected_y.shape[0]*selected_y.shape[1],selected_y.shape[2])

r_dim = 8
z_dim = 8 #8
x_dim = 2 #
y_dim = 100 #50
N = 100000 #population

ypred_allset = []
ypred_testset = []
mae_allset = []
maemetrix_allset = []
mae_testset = []
score_set = []
mask_set = []

for seed in range(1,3): #3
    np.random.seed(seed)
    dcrnn = DCRNNModel(x_dim, y_dim, r_dim, z_dim).to(device)
    opt = torch.optim.Adam(dcrnn.parameters(), 1e-3) #1e-3

    y_pred_test_list = []
    y_pred_all_list = []
    all_mae_matrix_list = []
    all_mae_list = []
    test_mae_list = []
    score_list = []
    mask_list = []

    x_train,y_train = x_train_init, y_train_init
    # selected_mask = init()
    selected_mask = np.copy(mask_init)
    
    for i in range(8): #8
        # print('selected_mask:', selected_mask)
        print('training data shape:', x_train.shape, y_train.shape)
        mask_list.append(np.copy(selected_mask))

        train_losses, val_losses, test_losses, z_mu, z_logvar = train(20000,x_train,y_train,x_val, y_val, x_test, y_test,500, 1500) #20000, 5000
        y_pred_test = test(torch.from_numpy(x_train).float(),torch.from_numpy(y_train).float(),
                          torch.from_numpy(x_test).float())
        y_pred_test_list.append(y_pred_test)

        test_mae = N * MAE(torch.from_numpy(y_pred_test).float(),torch.from_numpy(y_test).float())/100
        test_mae_list.append(test_mae.item())
        print('Test MAE:',test_mae.item())

        y_pred_all = test(torch.from_numpy(x_train).float(),torch.from_numpy(y_train).float(),
                          torch.from_numpy(x_all).float())
        y_pred_all_list.append(y_pred_all)
        mae_matrix, mae = MAE_MX(y_pred_all, y_all)
        
        
        all_mae_matrix_list.append(mae_matrix)
        all_mae_list.append(mae)
        print('All MAE:',mae)
        mae_plot(mae_matrix, selected_mask,seed,i)

        score_array = calculate_score(x_train, y_train, beta_epsilon_all)
        score_array = (score_array - np.min(score_array))/(np.max(score_array) - np.min(score_array))
        
        score_list.append(score_array)
        score_plot(score_array, selected_mask,seed,i)

        x_train, y_train, selected_mask = select_data(x_train, y_train, beta_epsilon_all, yall_set, score_array, selected_mask)

    y_pred_all_arr = np.stack(y_pred_all_list,0)
    y_pred_test_arr = np.stack(y_pred_test_list,0)
    all_mae_matrix_arr = np.stack(all_mae_matrix_list,0)
    all_mae_arr = np.stack(all_mae_list,0)
    test_mae_arr = np.stack(test_mae_list,0)
    score_arr = np.stack(score_list,0)
    mask_arr = np.stack(mask_list,0)

    ypred_allset.append(y_pred_all_arr)
    ypred_testset.append(y_pred_test_arr)
    maemetrix_allset.append(all_mae_matrix_arr)
    mae_allset.append(all_mae_arr)
    mae_testset.append(test_mae_arr)
    score_set.append(score_arr)
    mask_set.append(mask_arr)

ypred_allarr = np.stack(ypred_allset,0)
ypred_testarr = np.stack(ypred_testset,0) 
maemetrix_allarr = np.stack(maemetrix_allset,0) 
mae_allarr = np.stack(mae_allset,0)
mae_testarr = np.stack(mae_testset,0)
score_arr = np.stack(score_set,0)
mask_arr = np.stack(mask_set,0)

np.save('mae_testarr.npy',mae_testarr)
np.save('mae_allarr.npy',mae_allarr)
np.save('maemetrix_allarr.npy',maemetrix_allarr)

np.save('score_arr.npy',score_arr)
np.save('mask_arr.npy',mask_arr)

np.save('y_pred_all_arr.npy',ypred_allarr)
np.save('y_pred_test_arr.npy',ypred_testarr)

np.save('y_all.npy',y_all)
np.save('y_test.npy',y_test)

