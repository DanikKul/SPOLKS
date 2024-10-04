import socket
import struct
import threading

MCAST_GRP = '224.1.1.1'
MCAST_PORT = 5007
MULTICAST_TTL = 2
IS_ALL_GROUPS = True


def receive(sock: socket.socket):
    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    while True:
        print(sock.recv(10240))


def send(sock: socket.socket):
    sock.sendto(b'', MCAST_GRP)


def sender():
    pass


def receiver(sock: socket.socket):
    while True:
        receive(sock)


def main():
    nickname = input('Enter nickname: ')
    if nickname == "" or nickname is None:
        nickname = 'Guest'

    sock_rcv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock_rcv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_rcv.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
    if IS_ALL_GROUPS:
        sock_rcv.bind(('', MCAST_PORT))
    else:
        sock_rcv.bind((MCAST_GRP, MCAST_PORT))

    sock_snd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock_snd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock_snd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)

    rcv_thread = threading.Thread(target=receiver, args=(sock_rcv, ))
    snd_thread = threading.Thread(target=sender, args=(sock_snd, ))

    rcv_thread.start()
    snd_thread.start()

    rcv_thread.join()
    snd_thread.join()
