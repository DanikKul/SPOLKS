from mpi4py import MPI
import numpy as np


def matrix_multiply(A, B):
    # C = np.zeros((A.shape[0], B.shape[1]))
    # for i in range(A.shape[0]):
    #     for j in range(B.shape[1]):
    #         for k in range(A.shape[1]):
    #             C[i][j] += A[i][k] * B[k][j]
    return A.dot(B)


comm = MPI.COMM_WORLD
rank = comm.Get_rank()
size = comm.Get_size()
shape = 3000
print(f"Process {rank} on processor {MPI.Get_processor_name()}")

if rank == 0:
    A = np.random.randint(0, 10, (shape, shape))
    B = np.random.randint(0, 10, (shape, shape))

    # t1 = MPI.Wtime()
    # C = matrix_multiply(A, B)
    # t2 = MPI.Wtime()
    # print(f"One-thread: {t2 - t1} sec")

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
    print(C_partial)

    comm.Barrier()

    reqsA = [MPI.Request()] * shape
    reqsB = [MPI.Request()] * shape
    reqsC = [MPI.Request()] * shape
    t1 = MPI.Wtime()
    chunk_size = A.shape[0] // size
    A_chunks = [A[i] for i in range(shape)]
    workers = comm.size - 1
    bufsize = 1 << 30

    for i in range(workers):
        reqsB[i] = comm.isend(B, dest=i + 1, tag=0)
    for i in range(shape):
        reqsA[i] = comm.isend(A_chunks[i], dest=i % workers + 1, tag=i // workers + 1)
    tt1 = MPI.Wtime()
    for i in range(shape):
        reqsC[i] = comm.irecv(bufsize, source=i % workers + 1, tag=i // workers + 1)

    succeded_lst = [False] * shape
    i = 0
    C = np.zeros_like(A)
    while True:
        if i == shape:
            if all(succeded_lst):
                break
            i = 0
        if succeded_lst[i] == False:
            success, Cpart = reqsC[i].test()
            # print(success)
            if success == True:
                succeded_lst[i] = True
                C[i] = Cpart
        # print(i)
        i += 1
    # tt2 = MPI.Wtime()
    # print(f"Test: {tt2 - tt1} sec")
    t2 = MPI.Wtime()
    print(f"Non-blocking parallel: {t2 - t1} sec")
    print(C)
else:
    A_chunk = comm.recv(source=0, tag=1)
    B = comm.recv(source=0, tag=2)
    C_partial = matrix_multiply(A_chunk, B)
    comm.send(C_partial, dest=0, tag=3)

    comm.Barrier()
    bufsize = 1 << 30
    reqB = comm.irecv(bufsize, source=0, tag=0)
    workers = comm.size - 1
    add = 1 if (shape % workers) >= rank else 0
    reqsA = [MPI.Request()] * (shape // workers + add)
    for i in range(shape // workers + add):
        reqsA[i] = comm.irecv(bufsize, source=0, tag=i + 1)

    partials = []
    B = reqB.wait()

    # print(f"Rank {rank} len {len(reqsA)}")
    for i in range(len(reqsA)):
        A_chunk = reqsA[i].wait()
        # tt1 = MPI.Wtime()
        partials.append(matrix_multiply(np.expand_dims(A_chunk, axis=0), B))
        reqsA[i] = comm.isend(partials[i], dest=0, tag=i + 1)
        # tt2 = MPI.Wtime()
        # print(f"Rank {rank} waited {tt2 - tt1} sec")


