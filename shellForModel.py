# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.4.2
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %%
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
#### TODO install geopandas
#import geopandas as gp
from sklearn.preprocessing import normalize, MinMaxScaler
from scipy.sparse import coo_matrix, csr_matrix


# %% [markdown]
# Read in standardized csv files and merge them into one Dataframe

# %%
df_form = pd.read_csv("formationout.csv")
df_well = pd.read_csv("out.csv")
#Merge the 2 CSVs by API number
df_merged = df_well.merge(df_form, how = "left", on = "API Number")
#drop well number identifier since we are using API number
df_merged.drop(columns="Well Number", inplace = True)
print(df_merged.head())

# %% [markdown]
# Taking a sample of the Dataframe to holdout 

# %%
df_holdout = df_merged.sample(frac=0.2, random_state=4242001)
print(df_holdout.head())
#make list of API numbers that we held out
heldout_APIs = []
for i in df_holdout["API Number"]:
    heldout_APIs.append(i)
print(len(heldout_APIs))
#now we need to go back to our original Dataframe and set the vals we are holding out to 0
df_merged_heldout = df_merged.copy()
np.random.seed(4242001)
#the random form aliases we are holding out
h = np.random.randint(0, 59, 5)
#
#hold out these tops, but keep rest of data intact
#
#query by heldout APIs and find subset dataframe
df_merged_heldout[df_merged_heldout["API Number"].isin(heldout_APIs)]["Form Alias"].replace(h, float("NaN"), inplace=True)
#ser = subset["Form Alias"]
#set random form alias h to NaN
#ser.replace(h, float("NaN"))


# %%
len(df_holdout["API Number"].unique())
df_holdout.sort_values(by=["API Number", "Form Alias"])

# %% [markdown]
# Make a sparse matrix from the Dataframe heldout

# %%
D_df = df_merged_heldout.pivot_table("Top MD","Form Alias","API Number").fillna(0)

# %% [markdown]
# Trying different ways of normalizing R, demeaning and normalizing with SKLearn

# %%
mms = MinMaxScaler()
R = D_df.values
target_vals = df_holdout["Top MD"]
well_depth_mean = np.mean(R, axis = 1)
R_normalize = mms.fit_transform(R, target_vals)
R_demeaned = R - well_depth_mean.reshape(-1, 1)

# %% [markdown]
# Create binarized matrix with values of 1 where there are depth values in the sparse matrix R and values of 0 where there are not depth values in the sparse matrix R.

# %%
from sklearn.preprocessing import binarize
A = binarize(R)


# %% [markdown]
# This is the code that runs Alternating Least Squares factorization

# %%
#ALS factorization from 
# https://github.com/mickeykedia/Matrix-Factorization-ALS/blob/master/ALS%20Python%20Implementation.py
# here items are the formation and users are the well
def runALS(A, R, n_factors, n_iterations, lambda_):
    """
    Runs Alternating Least Squares algorithm in order to calculate matrix.
    :param A: User-Item Matrix with ratings
    :param R: User-Item Matrix with 1 if there is a rating or 0 if not
    :param n_factors: How many factors each of user and item matrix will consider
    :param n_iterations: How many times to run algorithm
    :param lambda_: Regularization parameter
    :return:
    """
    print("Initiating ")
    lambda_ = lambda_
    n_factors = n_factors
    n, m = A.shape
    n_iterations = n_iterations
    Users = 5 * np.random.rand(n, n_factors)
    Items = 5 * np.random.rand(n_factors, m)

    def get_error(A, Users, Items, R):
        # This calculates the MSE of nonzero elements
        return np.sum((R * (A - np.dot(Users, Items))) ** 2) / np.sum(R)

    MSE_List = []

    print("Starting Iterations")
    for iter in range(n_iterations):
        for i, Ri in enumerate(R):
            Users[i] = np.linalg.solve(
                np.dot(Items, np.dot(np.diag(Ri), Items.T))
                + lambda_ * np.eye(n_factors),
                np.dot(Items, np.dot(np.diag(Ri), A[i].T)),
                ).T
        print(
            "Error after solving for User Matrix:",
            get_error(A, Users, Items, R),
            )

        for j, Rj in enumerate(R.T):
            Items[:, j] = np.linalg.solve(
                np.dot(Users.T, np.dot(np.diag(Rj), Users))
                + lambda_ * np.eye(n_factors),
                np.dot(Users.T, np.dot(np.diag(Rj), A[:, j])),
                )
        print(
            "Error after solving for Item Matrix:",
             get_error(A, Users, Items, R),
            )

        MSE_List.append(get_error(A, Users, Items, R))
        print("%sth iteration is complete..." % iter)
    return Users, Items, MAE
    
    # fig = plt.figure()
    # ax = fig.add_subplot(111)
    # plt.plot(range(1, len(MSE_List) + 1), MSE_List); plt.ylabel('Error'); plt.xlabel('Iteration')
    # plt.title('Python Implementation MSE by Iteration \n with %d formations and %d wells' % A.shape);
    # plt.savefig('Python MSE Graph.pdf', format='pdf')
    # plt.show()


# %%
U, Vt, MAE_list = runALS(R_normalize, A, 20, 20, 0.1)

# %% [markdown]
# Below finds the index of the minimum of the maximum error after each set of iterations. This is the optimal value for the parameter n_factors.

# %%
#MAE_max = []
#get a list of the max errors from each value of n_factor
#for i in MAE_list:
    #MAE_max.append(max(i))
#The index of the minimum max error is the optimal n_factor value
#print(MAE_max.index(min(MAE_max)))

# %%
recommendations = np.dot(U, Vt)
recsys_df = pd.DataFrame(data = recommendations[0:, 0:], index = D_df.index,
                        columns = D_df.columns)
recsys_df.head()

# %%
stacked = recsys_df.T.reset_index().stack(level=0)
stacked.index
#look at dropping multi level index

# %% [markdown]
# Plot the recommended depths for all formations for the first 5 wells vs the actual depths

# %%
D_df_normalized = mms.fit_transform(D_df.iloc[0:, 1].values.reshape(-1,1))
for i in range(5):
    plt.scatter(recsys_df.iloc[0:, i].values, D_df_normalized) #plot predicted vs actual
    plt.xlabel('predicted depth')
    plt.ylabel('actual depth')
    plt.plot(np.arange(0,recsys_df.iloc[0:,i].max()))
    #denormalized and printed error for manuscript
    print(median_absolute_error(mms.inverse_transform(recsys_df.iloc[0:, i].values.reshape(-1,1)), D_df.iloc[0:, 1].values))

# %% [markdown]
# Tough part, check predictions against known and use MAE error metric

# %%
#print(recsys_df)
recsys_df_toJoin = recsys_df.T.reset_index()
print(recsys_df_toJoin)

# %%
actual = df_merged[(df_merged["API Number"].isin(heldout_APIs)) & (df_merged["Form Alias"] == 0.0)]
predicted = recsys_df_toJoin[(recsys_df_toJoin["API Number"].isin(heldout_APIs))][0.0]
actual

# %%
from sklearn.metrics import median_absolute_error
MAE = []
for i in range(0, int( df_merged.iloc[0:, 5].max() + 1 )):
    act_list = []
    pred_list = []
    #loop through all formation aliases
    #get actual df form alias i
    actual = df_merged[df_merged["Form Alias"] == float(i)]
    #get predicted df form alias i
    predicted = pd.DataFrame(recsys_df_toJoin[float(i)])
    #add API Number column to new dataframe
    #predicted = predicted.assign(API=recsys_df_toJoin["API Number"])
    #query by API Number now
    #actual = actual[actual["API Number"].isin(heldout_APIs)]
    #predicted = predicted[predicted["API"].isin(heldout_APIs)]
    #MAE.append( median_absolute_error( actual["Top MD"], mms.inverse_transform(predicted[float(i)].values.reshape(1, -1)) ) )


# %%
recsys_df_toJoin.head()

# %% [markdown]
# Predicted depths

# %%
recsys_df.iloc[0:, 1]

# %% [markdown]
# Actual depths

# %%
D_df.iloc[0:, 1]

# %%
plt.scatter(df_merged.Easting, df_merged.Northing, c = df_merged.iloc[0:, 6])
plt.colorbar()
plt.xlabel("Northing")
plt.ylabel("Easting")



# %%
