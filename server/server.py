import math
import socket
import signal
import os
import time
import dotenv
import json

from alive_progress import alive_bar
from loguru import logger

from utils.download_status import DownloadStatus
from utils.status_codes import StatusCode
from utils.session import Session


class Server:
    def __init__(self):
        self.conn = None
        logger.info("INITIALIZING SERVER...")
        signal.signal(signal.SIGINT, self.handler)
        self.ip = None
        self.port = None
        self.start_path = os.getenv('SERVER_FILES_PATH')
        self.packet_size = int(os.getenv('SERVER_PACKET_SIZE'))
        self.packets_per_check = int(os.getenv('PACKETS_PER_CHECK'))
        self.start_time = time.time()
        self.addr = None
        self.current_session = None
        self.server_debug_loading = os.getenv('SERVER_DEBUG_LOADING') == 'true'
        self.enable_check = os.getenv('ENABLE_CHECK') == 'true'
        self.sessions: list = []
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
        self.data = bytes()

    def start_server(self, ip, port):
        try:
            self.ip = ip
            self.port = port
            logger.info("STARTING SERVER...")
            self.sock.bind((ip, port))
            logger.info("SOCKET BINDED")
            while True:
                self.listen()
        except Exception as e:
            logger.exception(e)

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

    def restore(self):
        try:
            logger.info('Check if there is need to restore session')
            session_id = self.conn.recv(self.packet_size).decode('utf-8')  # 1
            is_saved_session = False
            for session in self.sessions:
                if session.get_session_id() == session_id:
                    self.current_session = session
                    is_saved_session = True
                    break
            if is_saved_session:
                logger.warning('Previous session was unexpectedly disconnected. Trying to bring it back...')
                self.conn.send(StatusCode.err)  # 2
                self.conn.recv(self.packet_size)  # 3
                if self.current_session.is_downloading == DownloadStatus.none:
                    logger.info('Previous session is restored')
                    self.conn.send(StatusCode.ok)  # 4
                else:
                    logger.warning(
                        'Previous session had some unfinished downloading/uploading. Restoring that actions...')
                    self.conn.send(StatusCode.err)  # 4
                    sz = os.path.getsize(
                        self.start_path +
                        self.current_session.remote_current_file
                        .removeprefix('/')
                        .removeprefix('files/')
                    )
                    self.conn.send(  # 5
                        json.dumps(
                            {
                                'download': str(self.current_session.is_downloading == DownloadStatus.download).lower(),
                                'client_file_path': self.current_session.local_current_file,
                                'file_size': sz
                            }
                        ).encode('utf-8')
                    )
                    self.conn.recv(self.packet_size)  # 6
                    self.conn.send(StatusCode.ok)  # 7
                    self.conn.recv(self.packet_size)  # 8
                    remote_file_size: bytes = self.conn.recv(self.packet_size)  # 9
                    self.conn.send(StatusCode.ok)  # 10
                    if self.current_session.is_downloading == DownloadStatus.download:
                        self.restore_download(
                            self.start_path +
                            self.current_session.remote_current_file
                            .removeprefix('/')
                            .removeprefix('files/'),
                            int(remote_file_size.decode('utf-8')),
                            sz
                        )
                    else:
                        self.restore_upload(
                            self.start_path +
                            self.current_session.remote_current_file
                            .removeprefix('/')
                            .removeprefix('files/'),
                            sz,
                            int(remote_file_size.decode('utf-8'))
                        )
            else:
                logger.info('No need to restore session')
                self.current_session = Session(
                    self.ip,
                    self.port,
                    self.packet_size,
                    self.start_path,
                    self.start_time
                )
                self.current_session.set_session_id(session_id)
                self.sessions.append(self.current_session)
                self.conn.send(StatusCode.ok)  # 2
        except Exception as e:
            logger.exception(e)

    # That func stands for restoring downloading files from server from broken session
    def restore_download(self, abs_path: str, sz: int, full_sz: int):
        to_send = [i for i in range(math.ceil(sz / self.packet_size), math.ceil(full_sz / self.packet_size))]
        file = open(abs_path, 'rb')
        file.seek(sz)
        check = 0
        with alive_bar(len(to_send)) as bar:
            for _ in to_send:
                bar()
                data = file.read(self.packet_size)
                self.conn.send(data)
                if self.server_debug_loading:
                    time.sleep(0.001)
                if self.enable_check:
                    if check % self.packets_per_check == 0:
                        self.conn.recv(self.packet_size)
                    check += 1

    # That func stands for restoring uploading files to server from broken session
    def restore_upload(self, abs_path: str, sz: int, full_sz: int):
        p_bar = [i for i in range(math.ceil(sz / self.packet_size), math.ceil(full_sz / self.packet_size))]
        file = open(abs_path, 'ab')
        downloaded_bytes = 0
        check = 0
        with alive_bar(len(p_bar)) as bar:
            for i in range(math.ceil(sz / self.packet_size), math.ceil(full_sz / self.packet_size)):
                line = bytes()
                if full_sz - sz - downloaded_bytes >= self.packet_size:
                    while len(line) < self.packet_size:
                        buff = self.conn.recv(self.packet_size)
                        if not buff:
                            return
                        line += buff
                else:
                    while len(line) < full_sz - sz - downloaded_bytes:
                        buff = self.conn.recv(self.packet_size)
                        if not buff:
                            return
                        line += buff
                if self.enable_check:
                    if check % self.packets_per_check == 0:
                        self.conn.recv(self.packet_size)
                    check += 1
                downloaded_bytes += len(line)
                file.write(line)
                bar()

    def listen(self):
        logger.info("LISTENING FOR CONNECTIONS...")
        self.sock.listen(1)
        self.conn, self.addr = self.sock.accept()
        host, port = self.conn.getpeername()
        logger.info("ACCEPTED CONNECTION: ", f"{host}:{port}")
        self.restore()
        self.current_session.poll(self.conn)
        logger.warning(
            f"Session ended: Active: {self.current_session.is_active}, Shutdown: {self.current_session.is_requested_shutdown}"
        )
        if self.current_session.is_requested_shutdown:
            logger.info("Server performing shutdown...")
            exit(0)
        if not self.current_session.is_active:
            logger.info("Deleting session...")
            print([session.get_session_id() for session in self.sessions])
            self.sessions = list(
                filter(lambda x: x.get_session_id() != self.current_session.get_session_id(), self.sessions))
            print([session.get_session_id() for session in self.sessions])
            self.current_session = None

    def handler(self, signum, frame):
        print("Do you really want to shutdown server? [Y/n] ", end="", flush=True)
        res = input()
        if res.lower() == 'y':
            logger.info("Performing shutdown...")
            self.conn.close()
            exit(0)


if __name__ == "__main__":
    dotenv.load_dotenv()
    server = Server()
    server.start_server(os.getenv('SERVER_IP'), int(os.getenv('SERVER_PORT')))
