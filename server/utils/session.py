import errno
import math
import os
import socket
import time
import uuid

from pathlib import Path
from alive_progress import alive_bar
from loguru import logger
from datetime import datetime as dt

# Local imports
from .status_codes import StatusCode
from .download_status import DownloadStatus
from .displayable_path import DisplayablePath
from .commands import Parser
from .exception.socket_exception import SocketException


class Session:
    def __init__(self, ip: str, port: int, packet_size: int, start_path: str, start_time: float):
        self.start_path = start_path
        logger.info(f"Starting session for {ip, port}")
        self.sock = None
        self.ip = ip
        self.port = port
        self.packet_size = packet_size
        self.parser = Parser()
        self.is_active = True
        self.is_requested_shutdown = False
        self.local_current_file = None
        self.remote_current_file = None
        self.server_debug_loading = os.getenv('SERVER_DEBUG_LOADING') == 'true'
        self.packets_per_check = int(os.getenv('PACKETS_PER_CHECK'))
        self.enable_check = os.getenv('ENABLE_CHECK') == 'true'
        self.is_downloading = DownloadStatus.none
        self.start_time = start_time
        self.__session_id = str(uuid.uuid4())
        self.data = bytes()

    def poll(self, sock: socket.socket):
        self.sock = sock
        recv = None
        while True:
            try:
                recv = self.receive()
                if not self.is_active:
                    logger.info("Client logged out")
                    self.close()
                    break
            except SocketException:
                logger.warning("Raised SocketException")
                break
            except IOError as e:
                logger.exception('Client disconnected unexpectedly')
                if e.errno == errno.EPIPE:
                    logger.error('Broken pipe')
                    break
                if e.errno == errno.EBADF:
                    logger.error('Bad file descriptor')
                    break
            except Exception as e:
                logger.exception(e)
                continue
            if recv is None or not recv:
                logger.error(f'Received empty data {type(recv)}')
                break
        self.sock.close()

    def receive(self) -> bytes:
        self.data = self.sock.recv(self.packet_size)
        logger.info(f"Got {self.data} from client")
        if not self.data:
            return self.data
        self.parser.parse(self.data)
        cmd = self.parser.get_cmd()
        logger.info(f"Processing cmd {cmd.upper()}")
        if cmd == "echo":
            self.handle_echo()
        elif cmd == "time":
            self.handle_time()
        elif cmd == "stime":
            self.handle_stime()
        elif cmd == "help":
            self.handle_help()
        elif cmd == 'tree':
            self.handle_tree()
        elif cmd == 'mkdir':
            self.handle_mkdir()
        elif cmd == 'rm':
            self.handle_remove()
        elif cmd == 'download':
            self.handle_download()
        elif cmd == 'upload':
            self.handle_upload()
        elif cmd == 'logout':
            self.handle_logout()
        elif cmd == 'shutdown':
            self.handle_shutdown()
        else:
            self.handle_bad_request()
        return self.data

    def get_session_id(self):
        return self.__session_id

    def set_session_id(self, session_id: str):
        self.__session_id = session_id

    """
    # Decorator to use with command handlers #
    Used to wrap any command to fit next pattern:
    S <- C (cmd)
    S -> C (cmd_start)
    S <- C (ok)
    S -> C (cmd_result)
    S <- C (ok)
    S -> C (cmd_end) 
    S <- C (next cmd)
    ...
    """

    @staticmethod
    def command(func):
        def inner(self):
            logger.info('Starting command execution')
            try:
                func(self)
            except Exception as e:
                logger.error(e)
            logger.info('Finishing command execution')

        return inner

    """
    # HANDLERS #
    """

    @command
    def handle_echo(self):
        self.send(
            ' '.join(self.parser.get_arg('args'))
            .replace('\n', '')
            .encode('utf-8')
        )

    @command
    def handle_logout(self):
        if not self.parser.check_args(0):
            self.send(b"Wrong arguments")
            return
        self.send(b"logging out...")
        logger.warning("Handling logout...")
        self.is_active = False

    @command
    def handle_shutdown(self):
        if not self.parser.check_args(0):
            self.send(b"Wrong arguments")
            return
        self.send(b"Performing server shutdown...")
        logger.warning("Handling shutdown...")
        self.is_active = False
        self.is_requested_shutdown = True

    @command
    def handle_bad_request(self):
        if not self.parser.check_args(0):
            self.send(b"Wrong arguments")
            return
        self.send(b"Bad request")

    @command
    def handle_time(self):
        if not self.parser.check_args(0):
            self.send(b"Wrong arguments")
            return
        self.send(dt.now().strftime("%m/%d/%Y, %H:%M:%S").encode('utf-8'))

    @command
    def handle_stime(self):
        if not self.parser.check_args(0):
            self.send(b"Wrong arguments")
            return
        self.send(time.strftime("%H:%M:%S", time.gmtime(round(time.time() - self.start_time))).encode('utf-8'))

    @command
    def handle_help(self):
        if not self.parser.check_args(0):
            self.send(b"Wrong arguments")
            return
        self.send("echo - return argument.                Args: [string...]\r\n"
                  "time - server time.                    Args: no args\r\n"
                  "stime - server uptime.                 Args: no args\r\n"
                  "tree - show files.                     Args: no args\r\n"
                  "mkdir - create directory.              Args: [dir_path]\r\n"
                  "rm - remove directory.                 Args: [dir_path]\r\n"
                  "download - download files from server. Args: [remote_dir_path local_dir_path]\r\n"
                  "upload - upload files to server.       Args: [remote_dir_path local_dir_path]\r\n"
                  "logout - disconnect from server.       Args: no args\r\n"
                  "shutdown - shutdown server.            Args: no args".encode('utf-8'))

    @command
    def handle_tree(self):
        if not self.parser.check_args(0):
            self.send(b"Wrong arguments")
            return
        self.send(self.list_files().encode('utf-8'))

    @command
    def handle_mkdir(self):
        if not self.parser.check_args(1):
            self.send(b"Wrong arguments")
            return
        try:
            self.create_dir()
            self.send(b"Directory created successfully")
        except Exception as e:
            logger.error(e)
            self.send(b"Can't create directory")

    @command
    def handle_remove(self):
        if not self.parser.check_args(1):
            self.send(b"Wrong arguments")
            return
        try:
            self.remove()
            self.send(b"Directory/file removed successfully")
        except Exception as e:
            logger.error(e)
            self.send(b"Can't remove file/directory")

    @command
    def handle_download(self):
        try:
            if not self.parser.check_args(2):
                self.send_raw(StatusCode.err)
                return
            self.send_raw(StatusCode.ok)
            rel_path = self.parser.get_args()['args'][0]
            self.remote_current_file = rel_path
            self.local_current_file = self.parser.get_args()['args'][1]
            rel_path = rel_path.removeprefix('files/')
            abs_path = self.start_path + rel_path
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                logger.info(f'Uploading {abs_path}')
                self.send_raw(StatusCode.ok)
                file = open(abs_path, "rb")
                sz = os.path.getsize(abs_path)
                if self.synchronize_recv() != StatusCode.ok:
                    print("Client didn't reply on ok")
                    return
                self.send(f"{sz}".encode('utf-8'))
                if self.synchronize_recv() != StatusCode.ok:
                    print("Client didn't reply on size")
                    return
                to_send = [i for i in range(math.ceil(sz / self.packet_size))]
                self.is_downloading = DownloadStatus.download
                check = 0
                with alive_bar(len(to_send)) as bar:
                    for _ in to_send:
                        data = file.read(self.packet_size)
                        self.send_raw(data)
                        if self.server_debug_loading:
                            time.sleep(0.001)
                        if self.enable_check:
                            if check % self.packets_per_check == 0:
                                self.synchronize_recv()
                            check += 1
                        bar()
                self.is_downloading = DownloadStatus.none
                file.close()
            else:
                self.send(StatusCode.err)
        except Exception as e:
            logger.error(e)

    @command
    def handle_upload(self):
        if self.sock.recv(1) != StatusCode.ok:
            logger.error("Can't download file: Wrong path")
            self.sock.send(StatusCode.err)
            return
        self.sock.send(StatusCode.ok)
        sz = int(self.sock.recv(self.packet_size).decode('utf-8'))
        file = open(
            f"{self.start_path + self.parser.get_args()['args'][0].removeprefix('/').removeprefix('files/')}", 'wb'
        )
        self.remote_current_file = self.parser.get_args()['args'][0]
        self.local_current_file = self.parser.get_args()['args'][1]
        p_bar = [i for i in range(math.ceil(int(sz) / self.packet_size))]
        self.sock.send(StatusCode.ok)
        self.is_downloading = DownloadStatus.upload
        is_broken = False
        downloaded_bytes = 0
        check = 0
        with alive_bar(len(p_bar)) as bar:
            for i in range(math.ceil(sz / self.packet_size)):
                line = bytes()
                if sz - downloaded_bytes >= self.packet_size:
                    while len(line) < self.packet_size:
                        buff = self.sock.recv(self.packet_size)
                        if not buff:
                            print('exit')
                            return
                        line += buff
                else:
                    while len(line) < sz - downloaded_bytes:
                        buff = self.sock.recv(self.packet_size)
                        if not buff:
                            print('exit')
                            return
                        line += buff
                downloaded_bytes += len(line)
                file.write(line)
                time.sleep(0.001)
                if self.enable_check:
                    if check % self.packets_per_check == 0:
                        self.synchronize_send()
                    check += 1
                bar()
            print('Waiting synchro')
            self.synchronize_recv()
        if not is_broken:
            self.is_downloading = DownloadStatus.none
        file.close()

    """
    # COMMAND UTILS #
    """

    def list_files(self):
        lst = ''
        paths = DisplayablePath.make_tree(Path(self.start_path))
        for path in paths:
            lst += path.displayable() + '\n'
        return lst

    def create_dir(self):
        os.mkdir(
            self.start_path +
            self.data.decode('utf-8').split(' ')[1]
            .removeprefix('/')
            .removeprefix('files/')
        )

    def remove(self):
        abs_path = self.start_path + self.data.decode('utf-8').split(' ')[1].removeprefix('/').removeprefix('files/')
        if os.path.isdir(abs_path):
            os.rmdir(abs_path)
        elif os.path.isfile(abs_path):
            os.remove(abs_path)

    """
    # NETWORK UTILS #
    """

    def send(self, msg: bytes, verbose=False):
        if verbose:
            logger.info("Sent to client:", msg.decode('utf-8'))
        self.sock.send(msg + b'\r\n')

    def send_raw(self, data: bytes, verbose=False):
        if verbose:
            logger.info("Sent to client", data.decode('utf-8'))
        self.sock.send(data)

    def synchronize_recv(self) -> bytes:
        response = StatusCode.none
        try:
            self.sock.settimeout(1)
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

    def clear_buffer(self):
        try:
            self.sock.settimeout(0.1)
            self.sock.recv(self.packet_size)
        except Exception as e:
            pass
        finally:
            self.sock.settimeout(None)

    def get_connection_status(self):
        return self.is_active

    def close(self):
        logger.info("CLOSING CONNECTION")
        self.sock.close()
