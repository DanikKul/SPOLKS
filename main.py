from mpi4py import MPI
import numpy as np


def matrix_multiply(A, B):
    C = np.zeros((A.shape[0], B.shape[1]))
    for i in range(A.shape[0]):
        for j in range(B.shape[1]):
            for k in range(A.shape[1]):
                C[i][j] += A[i][k] * B[k][j]
    return C


comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
shape = 300

if rank == 0:
    A = np.random.randint(0, 10, (shape, shape))
    B = np.random.randint(0, 10, (shape, shape))
    chunk_size = A.shape[0] // size
    A_chunks = [A[i:i + chunk_size] for i in range(0, A.shape[0], chunk_size)]
    for i in range(1, size):
        comm.send(A_chunks[i], dest=i, tag=1)
        comm.send(B, dest=i, tag=2)
    C_partial = matrix_multiply(A_chunks[0], B)
    for i in range(1, size):
        C_pp = comm.recv(source=i, tag=3)
        C_partial = np.vstack((C_partial, C_pp))
    if A.shape[0] % size != 0:
        for i in range(len(A_chunks) % size):
            C_pp = matrix_multiply(A_chunks[i + size], B)
            C_partial = np.vstack((C_partial, C_pp))
    print(C_partial)
    print(np.matmul(A, B))
else:
    A_chunk = comm.recv(source=0, tag=1)
    B = comm.recv(source=0, tag=2)
    C_partial = matrix_multiply(A_chunk, B)
    comm.send(C_partial, dest=0, tag=3)
