import socket
import struct
import threading
import time
import select
# import netifaces
from datetime import datetime
import enum
import uuid

CAST = '172.26.255.255'
S_CAST = '172.26.255.255'
S_PORT = 5008
CAST_PORT = 5007
MULTICAST_TTL = 20
IS_ALL_GROUPS = False
IS_BROADCAST = True
SIGNAL_EXIT = False
SIGNAL_GLOBAL_EXIT = False
BLACK_LIST = []
nickname = 'Guest'
ip = ''
groups = []


class CMD(enum.Enum):
    join = 1
    leave = 2
    msg = 3
    unknown = 0


def receive(sock: socket.socket):
    ready = select.select([sock], [], [], 0.1)
    if ready[0]:
        data = sock.recv(10240).decode('utf-8')
        cmd, msg = parse_data(data)
        if cmd == CMD.join:
            print(f"{msg[0]} joined group")
        elif cmd == CMD.leave:
            print(f"{msg[0]} left group")
        elif cmd == CMD.msg:
            if nickname != msg[1]:
                print(f"{msg[0]} {msg[1]}: {msg[2]}")


def parse_data(data) -> (int, list):
    if data.startswith('join') and data.count('~') == 1:
        _, got_nickname = data.split('~')[:2]
        return CMD.join, [got_nickname]
    elif data.startswith('leave') and data.count('~') == 1:
        _, got_nickname = data.split('~')[:2]
        return CMD.leave, [got_nickname]
    elif data.startswith('msg'):
        data = data.removeprefix('msg~')
        date, got_nickname = data.split('~')[:2]
        msg = data.removeprefix(f'{date}~{got_nickname}~')
        return CMD.msg, [date, got_nickname, msg]
    else:
        return CMD.unknown, ['']


def send(sock: socket.socket):
    global SIGNAL_EXIT, nickname
    inp = input()
    if inp == '\\leave':
        sock.sendto(f'leave~{nickname}'.encode(), (CAST, CAST_PORT))
        SIGNAL_EXIT = True
        return
    sock.sendto(("msg~" + datetime.now().strftime("%d/%m/%Y %H:%M:%S") + f"~{nickname}~" + inp).encode(), (CAST, CAST_PORT))


def sender(sock: socket.socket):
    print(CAST, CAST_PORT)
    sock.sendto(f'join~{nickname}'.encode(), (CAST, CAST_PORT))
    while True:
        if SIGNAL_EXIT:
            break
        send(sock)


def receiver(sock: socket.socket):
    while True:
        if SIGNAL_EXIT:
            break
        receive(sock)


def list_groups(sock: socket.socket):
    users = set()
    times = 0
    max_times = 3
    last_len = len(users)
    sock.settimeout(0.1)
    try:
        while sock.recv(1024):
            pass
    except:
        pass
    sock.settimeout(None)
    while True:
        ready = select.select([sock], [], [], 3)
        if ready[0]:
            data = sock.recv(1024).decode('utf-8')
            users.add(data)
            print(users)
        else:
            break
        if last_len != len(users):
            last_len = len(users)
        else:
            times += 1
        if times >= max_times:
            break
    print("final", users)



def echo(sock: socket.socket):
    no = uuid.getnode()
    while True:
        sock.sendto(f'{no}~{nickname}'.encode(), (S_CAST, S_PORT))
        time.sleep(1)
        if SIGNAL_GLOBAL_EXIT:
            break


def main():
    global nickname, CAST, SIGNAL_EXIT, SIGNAL_GLOBAL_EXIT
    # info = netifaces.ifaddresses('en0')[netifaces.AF_INET][0]
    # CAST = info['broadcast']

    rcv_srv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    rcv_srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    rcv_srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    rcv_srv_sock.bind((S_CAST, S_PORT))

    snd_srv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    snd_srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    snd_srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    service = threading.Thread(target=echo, args=(snd_srv_sock,))
    service.start()

    while True:

        choice = input(f"Enter command\n")

        if choice == 'list':
            list_groups(rcv_srv_sock)

        # elif choice == 'info':
            # info = netifaces.ifaddresses('en0')[netifaces.AF_INET][0]
            # print(f"IP: {info['addr']}\nNetmask: {info['netmask']}\nBroadcast: {info['broadcast']}\n")

        elif choice == 'help':
            print('Available commands:\nlist - List all groups\nhelp - Show this message\nconnect - Connect to a group')

        elif choice == 'exit':
            break

        elif choice == 'connect':
            nickname = input('Enter nickname: ')
            if nickname == "" or nickname is None:
                nickname = 'Guest'

            sock_rcv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock_rcv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock_snd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock_snd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            if not IS_BROADCAST:
                CAST = '224.0.0.0'
                sock_snd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
                sock_rcv.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
                mreq = struct.pack("4sl", socket.inet_aton(CAST), socket.INADDR_ANY)
                sock_rcv.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            else:
                sock_snd.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                sock_rcv.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

            if IS_ALL_GROUPS:
                sock_rcv.bind(('', CAST_PORT))
            else:
                sock_rcv.bind((CAST, CAST_PORT))

            rcv_thread = threading.Thread(target=receiver, args=(sock_rcv,), daemon=True)
            snd_thread = threading.Thread(target=sender, args=(sock_snd,), daemon=True)

            rcv_thread.start()
            snd_thread.start()
            try:
                while True:
                    if SIGNAL_EXIT:
                        break
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
            finally:
                rcv_thread.join(0.1)
                snd_thread.join(0.1)
                sock_rcv.close()
                sock_snd.close()
            SIGNAL_EXIT = False
    SIGNAL_GLOBAL_EXIT = True
    service.join()
    rcv_srv_sock.close()
    snd_srv_sock.close()


if __name__ == '__main__':
    main()
