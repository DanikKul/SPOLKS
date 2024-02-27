import math
import os
import socket
import time
import uuid
import json

import dotenv
from alive_progress import alive_bar

from utils.status_codes import StatusCode


class Client:
    def __init__(self):
        self.server_port = None
        self.server_ip = None
        self.client_ip = None
        self.client_debug_loading = os.getenv('CLIENT_DEBUG_LOADING') == 'true'
        self.sock = socket.socket(
            family=socket.AF_INET,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP
        )
        self.sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_REUSEADDR,
            1
        )
        self.sock.setsockopt(
            socket.SOL_SOCKET,
            socket.SO_KEEPALIVE,
            1
        )
        self.start_path = os.getenv('CLIENT_FILES_PATH')
        self.packet_size = int(os.getenv('CLIENT_PACKET_SIZE'))
        self.packets_per_check = int(os.getenv('PACKETS_PER_CHECK'))
        self.enable_check = os.getenv('ENABLE_CHECK') == 'true'
        self.session_id = str(uuid.uuid4())
        session_file = os.getenv('CLIENT_SESSION_FILE')
        if os.path.exists(session_file) and os.path.isfile(session_file):
            with open(session_file, 'r+') as file:
                self.session_id = file.read()
        else:
            with open(session_file, 'w+') as file:
                file.write(self.session_id)
        print(self.session_id)

    # That func binds socket and start session
    def start_session(self, client_ip: str, server_ip: str, server_port: int):
        self.client_ip = client_ip
        self.server_ip = server_port
        self.server_port = server_port
        try:
            print("STARTING SESSION...")
            self.sock.bind((client_ip, 0))
            print("SOCKET BINDED")
            self.sock.connect((server_ip, server_port))
            self.listen()
        except Exception as e:
            print(e)
        finally:
            self.sock.close()

    # Wrapper for processing input
    def process(self, inp):
        self.sock.send(inp.encode('utf-8'))
        if (self.synchronize_recv()) == StatusCode.cmd_start:
            self.synchronize_send()
            if inp.startswith('download'):
                self.download(inp)
            elif inp.startswith('upload'):
                self.upload(inp)
            else:
                print(self.sock.recv(self.packet_size).decode('utf-8'))
            self.synchronize_send()
        if (self.synchronize_recv()) == StatusCode.cmd_end:
            self.synchronize_send()

    def handle_logout(self):
        session_file = os.getenv('CLIENT_SESSION_FILE')
        if os.path.exists(session_file) and os.path.isfile(session_file):
            os.remove(session_file)
        self.sock.close()

    """
    RESTORING SESSION
    #1 S <- C [session_id]
           if no need to restore session
    #2     S -> C [ok]
           ... (create new session)
           if there is need to restore session
    #2     S -> C [err]
    #3     S <- C [ok]
               if there is no need to restore upload/download
    #4         S -> C [ok]
               ... (continue session)
               if there is need to restore upload/download
    #4         S -> C [err]
    #5         S -> C [object] ({download: true/false, client_file_path: str, file_size: int})
    #6         S <- C [ok]
    #7         S -> C [ok]
    #8         S <- C [ok]
    #9         S <- C [amount of downloaded bytes]
    #10        S -> C [ok]
               ... (download/upload process)
    """

    # That func stands for restoring broken sessions and redirect program to download/upload missing files
    def restore(self):
        dct = {}
        self.sock.send(self.session_id.encode('utf-8'))
        response = self.sock.recv(1)
        if response == StatusCode.ok:
            print('created new session')
            return
        elif response == StatusCode.err:
            print('restoring previous session')
            self.sock.send(StatusCode.ok)
            if self.sock.recv(1) == StatusCode.ok:
                print('restored session')
                return
            self.sock.send(StatusCode.ok)
            dct_str = self.sock.recv(self.packet_size).decode('utf-8')
            dct = json.loads(dct_str)
            self.sock.send(StatusCode.ok)
            self.sock.recv(1)
            file_path: str = dct['client_file_path'].removeprefix('/').removeprefix('files/')
            print("Unfinished downloading/uploading:", file_path)
            sz = os.path.getsize(self.start_path + file_path)
            print('sended size', sz)
            self.sock.send(str(sz).encode('utf-8'))
            self.sock.recv(1)
            if dct['download'] == 'true':
                print('restoring download')
                self.restore_download(self.start_path + file_path, sz, int(dct['file_size']))
            elif dct['download'] == 'false':
                print('restoring upload')
                self.restore_upload(self.start_path + file_path, int(dct['file_size']), sz)

    # Func for restoring downloading files from broken session
    def restore_download(self, abs_path: str, sz: int, full_sz: int):
        p_bar = [i for i in range(math.ceil(sz / self.packet_size), math.ceil(full_sz / self.packet_size))]
        file = open(abs_path, 'ab')
        downloaded_bytes = 0
        check = 0
        with alive_bar(len(p_bar)) as bar:
            try:
                for i in range(math.ceil(sz / self.packet_size), math.ceil(full_sz / self.packet_size)):
                    line = bytes()
                    if full_sz - sz - downloaded_bytes >= self.packet_size:
                        while len(line) < self.packet_size:
                            buff = self.sock.recv(self.packet_size)
                            if not buff:
                                return
                            line += buff
                    else:
                        while len(line) < full_sz - sz - downloaded_bytes:
                            buff = self.sock.recv(self.packet_size)
                            if not buff:
                                return
                            line += buff
                    if self.enable_check:
                        if check % self.packets_per_check == 0:
                            self.sock.send(StatusCode.ok)
                        check += 1
                    downloaded_bytes += len(line)
                    file.write(line)
                    bar()
            except Exception as e:
                print(e)

    # Func for restoring uploading files from broken session
    def restore_upload(self, abs_path: str, sz: int, full_sz: int):
        to_send = [i for i in range(math.ceil(sz / self.packet_size), math.ceil(full_sz / self.packet_size))]
        file = open(abs_path, 'rb')
        file.seek(sz)
        check = 0
        with alive_bar(len(to_send)) as bar:
            for _ in to_send:
                bar()
                data = file.read(self.packet_size)
                self.sock.send(data)
                if self.client_debug_loading:
                    time.sleep(0.001)
                if self.enable_check:
                    if check % self.packets_per_check == 0:
                        self.sock.recv(1)
                    check += 1

    def listen(self):
        self.restore()
        while True:
            inp = input(" > ")
            self.process(inp)
            if inp == 'logout' or inp == 'shutdown':
                self.handle_logout()
                break

    def synchronize_recv(self):
        response = StatusCode.none
        try:
            self.sock.settimeout(0.1)
            response = self.sock.recv(1)
        except Exception as e:
            pass
        finally:
            self.sock.settimeout(None)
            return response


    def synchronize_send(self):
        try:
            self.sock.settimeout(0.5)
            self.sock.send(StatusCode.ok)
        except Exception as e:
            pass
        finally:
            self.sock.settimeout(None)

    # That func stands for downloading files from server in current session
    def download(self, inp: str):
        if self.synchronize_recv() != StatusCode.ok:
            print("Can't download file: Wrong args")
            return
        if self.synchronize_recv() != StatusCode.ok:
            print("Can't download file: Wrong paths")
            return
        self.synchronize_send()
        sz = self.sock.recv(self.packet_size).decode('utf-8')
        file = None
        try:
            file = open(f'{self.start_path + inp.split(" ")[2].removeprefix("/").removeprefix("files/")}', 'wb')
        except Exception as e:
            self.sock.send(StatusCode.err)
            return
        sz = int(sz)
        p_bar = [i for i in range(math.ceil(sz / self.packet_size))]
        self.synchronize_send()
        downloaded_bytes = 0
        check = 0
        with alive_bar(len(p_bar)) as bar:
            for i in range(math.ceil(sz / self.packet_size)):
                line = bytes()
                if sz - downloaded_bytes >= self.packet_size:
                    while len(line) < self.packet_size:
                        buff = self.sock.recv(self.packet_size)
                        if not buff:
                            return
                        line += buff
                else:
                    while len(line) < sz - downloaded_bytes:
                        buff = self.sock.recv(self.packet_size)
                        if not buff:
                            return
                        line += buff
                downloaded_bytes += len(line)
                file.write(line)
                if self.enable_check:
                    if check % self.packets_per_check == 0:
                        self.synchronize_send()
                    check += 1
                bar()
        file.close()

    # That func stands for uploading files to server in current session
    def upload(self, inp: str):
        try:
            rel_path = inp.split(' ')[2]
        except Exception as e:
            self.sock.send(StatusCode.err)
            self.sock.recv(1)
            print('Wrong args')
            return
        rel_path = rel_path.removeprefix('/').removeprefix('files/')
        abs_path = self.start_path + rel_path
        if os.path.exists(abs_path) and os.path.isfile(abs_path):
            print('Uploading', abs_path)
            self.sock.send(StatusCode.ok)
            file = open(abs_path, "rb")
            data = file.read(1)
            sz = os.path.getsize(abs_path)
            if self.synchronize_recv() != StatusCode.ok:
                print("Server didn't reply on ok")
                return
            self.sock.send(f"{sz}".encode('utf-8'))
            if self.synchronize_recv() != StatusCode.ok:
                print("Server didn't reply on size")
                return
            if not data:
                return
            to_send = [i for i in range(math.ceil(sz / self.packet_size))]
            print(math.ceil(sz / self.packet_size), sz)
            check = 0
            with alive_bar(len(to_send)) as bar:
                for _ in to_send:
                    bar()
                    data = file.read(self.packet_size)
                    self.sock.send(data)
                    if self.client_debug_loading:
                        time.sleep(0.001)
                    if self.enable_check:
                        if check % self.packets_per_check == 0:
                            self.synchronize_recv()
                        check += 1
            file.close()
        else:
            print("Wrong paths")
            self.sock.send(StatusCode.err)
            self.synchronize_recv()


if __name__ == "__main__":
    dotenv.load_dotenv()
    client = Client()
    client.start_session(
        os.getenv('CLIENT_IP'),
        os.getenv('SERVER_IP'),
        int(os.getenv('SERVER_PORT'))
    )
