import socket
import struct
import threading
import time
import select
from datetime import datetime
import enum

CAST = '224.0.0.0'
CAST_PORT = 5007
MULTICAST_TTL = 20
IS_ALL_GROUPS = True
IS_BROADCAST = True
SIGNAL_EXIT = False
nickname = 'Guest'
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


def check_groups():
    pass


def send(sock: socket.socket):
    global SIGNAL_EXIT
    inp = input()
    if inp == '\\leave':
        sock.sendto(f'leave~{nickname}'.encode(), (CAST, CAST_PORT))
        SIGNAL_EXIT = True
        return
    sock.sendto(("msg~" + datetime.now().strftime("%d/%m/%Y %H:%M:%S") + f"~{nickname}~" + inp).encode(), (CAST, CAST_PORT))


def sender(sock: socket.socket):
    sock.sendto(f'join~{nickname}'.encode(), (CAST, CAST_PORT))
    while True:
        if SIGNAL_EXIT:
            break
        send(sock)


def receiver(sock: socket.socket):
    mreq = struct.pack("4sl", socket.inet_aton(CAST), socket.INADDR_ANY)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    while True:
        if SIGNAL_EXIT:
            break
        receive(sock)


def main():
    global nickname, CAST, SIGNAL_EXIT
    while True:

        choice = input(f"Enter command\n")

        if choice == 'list':
            check_groups()

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
            if IS_ALL_GROUPS:
                sock_rcv.bind(('', CAST_PORT))
            else:
                sock_rcv.bind((CAST, CAST_PORT))

            sock_snd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock_snd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            if not IS_BROADCAST:
                CAST = '224.0.0.0'
                sock_snd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
                sock_rcv.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)

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


if __name__ == '__main__':
    main()
