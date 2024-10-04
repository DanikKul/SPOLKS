import socket
import struct
import threading
import time
from datetime import datetime

MCAST_GRP = '224.0.0.0'
MCAST_PORT = 5007
MULTICAST_TTL = 15
IS_ALL_GROUPS = True
nickname = 'Guest'


def receive(sock: socket.socket):
    mreq = struct.pack("4sl", socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    while True:
        data = sock.recv(10240).decode('utf-8')
        date, got_nickname, msg = data.split('~')
        if nickname != got_nickname:
            print(f"{date} {got_nickname}: {msg}")


def send(sock: socket.socket):
    sock.sendto((datetime.now().strftime("%d/%m/%Y %H:%M:%S") + f"~{nickname}~" + input()).encode(), (MCAST_GRP, MCAST_PORT))


def sender(sock: socket.socket):
    while True:
        send(sock)


def receiver(sock: socket.socket):
    while True:
        receive(sock)


def main():
    global nickname
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

    rcv_thread = threading.Thread(target=receiver, args=(sock_rcv, ), daemon=True)
    snd_thread = threading.Thread(target=sender, args=(sock_snd, ), daemon=True)

    rcv_thread.start()
    snd_thread.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        rcv_thread.join(0.1)
        snd_thread.join(0.1)
        sock_rcv.close()
        sock_snd.close()


if __name__ == '__main__':
    main()