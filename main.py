import socket
import struct
import threading
import time
import select
from datetime import datetime
import enum
import uuid
import os
import netifaces

CAST = '224.1.1.1'
S_CAST = '172.26.255.255'
S_PORT = 59999
CAST_PORT = 50000
MULTICAST_TTL = 90
IS_ALL_GROUPS = False
IS_BROADCAST = False
SIGNAL_EXIT = False
SIGNAL_GLOBAL_EXIT = False
BLACK_LIST = set()
ECHO_FLAG = True
nickname = os.getlogin()
ip = ''
groups = []
current_group = 'Not connected'


class CMD(enum.Enum):
    join = 1
    leave = 2
    msg = 3
    unknown = 0


def receive(sock: socket.socket):
    global BLACK_LIST
    ready = select.select([sock], [], [], 0.1)
    if ready[0]:
        data = sock.recv(10240).decode('utf-8')
        cmd, msg = parse_data(data)
        if cmd == CMD.join:
            print(f"{msg[0]} joined group")
        elif cmd == CMD.leave:
            print(f"{msg[0]} left group")
        elif cmd == CMD.msg:
            if nickname != msg[1] and msg[1] not in BLACK_LIST:
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
    global SIGNAL_EXIT, nickname, BLACK_LIST
    inp = input()
    if inp == '\\leave':
        sock.sendto(f'leave~{nickname}'.encode(), (CAST, CAST_PORT))
        SIGNAL_EXIT = True
        return
    elif inp.startswith('\\blacklist'):
        inp = inp.removeprefix('\\blacklist ')
        BLACK_LIST.add(inp)
        return
    elif inp.startswith('\\whitelist'):
        inp = inp.removeprefix('\\whitelist ')
        try:
            BLACK_LIST.remove(inp)
        except KeyError:
            print('No such member in blacklist')
        return
    elif inp.startswith('\\help'):
        print(
            '\\leave - leaves the group\n'
            '\\blacklist <name> - blacklists host\n'
            '\\whitelist <name> - whitelists host\n'
            '\\help - shows this message\n'
        )
        return
    sock.sendto(("msg~" + datetime.now().strftime("%d/%m/%Y %H:%M:%S") + f"~{nickname}~" + inp).encode(),
                (CAST, CAST_PORT))


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
        ready = select.select([sock], [], [], 2)
        if ready[0]:
            data = sock.recv(1024).decode('utf-8')
            users.add(data)
        else:
            break
        if last_len != len(users):
            last_len = len(users)
        else:
            times += 1
        if times >= max_times:
            break

    for user in users:
        uid, nickname, group = user.split('~')
        if group != 'Not connected':
            print(f"{nickname} is online and joined group {group}")
        else:
            print(f"{nickname} is online and not joined any group")
    print()


def echo(sock: socket.socket):
    no = uuid.getnode()
    while ECHO_FLAG:
        sock.sendto(f'{no}~{nickname}~{current_group}'.encode(), (S_CAST, S_PORT))
        time.sleep(1)
        if SIGNAL_GLOBAL_EXIT:
            break


def main():
    global nickname, CAST, SIGNAL_EXIT, SIGNAL_GLOBAL_EXIT, current_group, ip, S_CAST, ECHO_FLAG

    ifaces = netifaces.interfaces()
    print('Choose network interface')
    for i in range(len(ifaces)):
        print(f"[{i + 1}]: {ifaces[i]}")
    choice_if = int(input())
    iface = ifaces[choice_if - 1]

    info = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]
    print(f"ip: {info['addr']}\nnetmask: {info['netmask']}\nbroadcast: {info['broadcast']}\n")
    ip = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']
    S_CAST = info['broadcast']

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

        choice = input(f"Enter command (Type `help` to show all commands)\n")

        if choice == 'list':
            list_groups(rcv_srv_sock)

        elif choice == 'info':
            info = netifaces.ifaddresses(ifaces[choice_if - 1])[netifaces.AF_INET][0]
            print(f"ip: {info['addr']}\nNetmask: {info['netmask']}\nBroadcast: {info['broadcast']}\n")

        elif choice == 'help':
            print(
                'Available commands:\n'
                'connect - Connect to a group\n'
                'list - List all groups\n'
                'help - Show this message\n'
                'nickname - Change nickname\n'
                'info - Show info about interface\n'
                'change - Change multicast group\n'
                'interface - Select new network interface\n'
                'exit - Exit the program\n'
            )

        elif choice == 'interface':
            ifaces = netifaces.interfaces()
            print('Choose network interface')
            for i in range(len(ifaces)):
                print(f"[{i + 1}]: {ifaces[i]}")
            choice_if = int(input())
            iface = ifaces[choice_if - 1]
            info = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]
            print(f"ip: {info['addr']}\nnetmask: {info['netmask']}\nbroadcast: {info['broadcast']}\n")
            ip = netifaces.ifaddresses(iface)[netifaces.AF_INET][0]['addr']
            S_CAST = info['broadcast']
            while service.is_alive():
                print("Trying to kill service...")
                ECHO_FLAG = False
                service.join(2)
            rcv_srv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            rcv_srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            rcv_srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            rcv_srv_sock.bind((S_CAST, S_PORT))

            snd_srv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            snd_srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            snd_srv_sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            print("Starting new service...")
            ECHO_FLAG = True
            service = threading.Thread(target=echo, args=(snd_srv_sock,))
            service.start()
            print("Service started")

        elif choice == 'exit':
            break

        elif choice == 'change':
            if IS_BROADCAST:
                print('Unable to change group. IS_BROADCAST set to true.')
            else:
                CAST = input('Enter multicast IP: \n')

        elif choice == 'nickname':
            nickname = input('Enter nickname: ')
            if nickname == "" or nickname is None:
                nickname = 'Guest'

        elif choice == 'connect':
            current_group = CAST

            if nickname == "" or nickname is None:
                nickname = 'Guest'

            sock_rcv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock_rcv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock_snd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock_snd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            if not IS_BROADCAST:
                # sock_snd.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
                sock_snd.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, MULTICAST_TTL)
                # sock_rcv.setsockopt(socket.SOL_IP, socket.IP_MULTICAST_IF, socket.inet_aton(ip))
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
            current_group = 'Not connected'
    SIGNAL_GLOBAL_EXIT = True
    service.join()
    rcv_srv_sock.close()
    snd_srv_sock.close()


if __name__ == '__main__':
    main()