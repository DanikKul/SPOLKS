# Python socket client-server app

## Installation
 - Open project in PyCharm
 - Go to folder with project `/path/to/SPOLKS`
 - Type `source venv/bin/activate`
 - Type `pip3 install -r requirements.txt`
 - Please run all commands above for each opened terminal (for client and server you need two separate terminals)
 - Go to folders where main scripts stored: `cd server` or `cd client`
 - Setup environment variables in `.env` file in each folder
 - After that you can run server and client scripts `python3 server.py`, `python3 client.py`



## Supported commands
 ```
echo - return argument.                Args: [string...]
time - server time.                    Args: no args
stime - server uptime.                 Args: no args
tree - show files.                     Args: no args
mkdir - create directory.              Args: [dir_path]
rm - remove directory.                 Args: [dir_path]
download - download files from server. Args: [remote_dir_path local_dir_path]
upload - upload files to server.       Args: [remote_dir_path local_dir_path]
logout - disconnect from server.       Args: no args
shutdown - shutdown server.            Args: no args
 ```
Command with options are not supported for now, just list args as it shown above

## Features
 - Server and client use sessions
 - Server has ability to restore broken session
 - Server has ability to restore uploading/downloading files
 - Server have rights to delete session if it's exited correctly or server was relaunched
 - Server won't delete your session if someone connected instead of you