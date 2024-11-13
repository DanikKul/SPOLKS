import mpi4py
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
shape = 500
print(f"Process {rank} on processor {MPI.Get_processor_name()}")

if rank == 0:
    A = np.random.randint(0, 10, (shape, shape))
    B = np.random.randint(0, 10, (shape, shape))

    t1 = MPI.Wtime()
    C = matrix_multiply(A, B)
    t2 = MPI.Wtime()
    print(f"One-thread: {t2 - t1} sec")

    t1 = MPI.Wtime()
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
    t2 = MPI.Wtime()
    print(f"Blocking parallel: {t2 - t1} sec")

    comm.Barrier()

    t1 = MPI.Wtime()
    chunk_size = A.shape[0] // size
    A_chunks = [A[i:i + chunk_size] for i in range(0, A.shape[0], chunk_size)]
    reqsA = []
    reqsB = []
    for i in range(1, size):
        reqsA.append(comm.isend(A_chunks[i], dest=i, tag=1))
        reqsB.append(comm.isend(B, dest=i, tag=2))
    C_partial = matrix_multiply(A_chunks[0], B)
    bufsize = 1 << 30
    for i in range(len(reqsA)):
        reqsA[i].wait()
        reqsB[i].wait()
    reqsC = []
    for i in range(1, size):
        C_pp = comm.irecv(bufsize, source=i, tag=3).wait()
        C_partial = np.vstack((C_partial, C_pp))
    if A.shape[0] % size != 0:
        for i in range(len(A_chunks) % size):
            C_pp = matrix_multiply(A_chunks[i + size], B)
            C_partial = np.vstack((C_partial, C_pp))
    t2 = MPI.Wtime()
    print(f"Non-blocking parallel: {t2 - t1} sec")
else:
    A_chunk = comm.recv(source=0, tag=1)
    B = comm.recv(source=0, tag=2)
    C_partial = matrix_multiply(A_chunk, B)
    comm.send(C_partial, dest=0, tag=3)

    comm.Barrier()

    bufsize = 1 << 30
    req_A = comm.irecv(bufsize, source=0, tag=1)
    B_req = comm.irecv(bufsize, source=0, tag=2)
    A_chunk = req_A.wait()
    B = B_req.wait()
    C_partial = matrix_multiply(A_chunk, B)
    comm.isend(C_partial, dest=0, tag=3).wait()

# import numpy
# from mpi4py import MPI
#
# comm = MPI.COMM_WORLD
# rank = comm.Get_rank()
#
# if rank == 0:
#     data = numpy.ones(5000)
#     print(data)
#     req = comm.isend(data, dest=1, tag=11)
#     req.wait()
# elif rank == 1:
#     req = comm.irecv(source=0, tag=11)
#     # data = req.wait()
#     # print(data)
#     success, data = req.test()
#     while not success:
#         success, data = req.test()
#         print(rank, data)