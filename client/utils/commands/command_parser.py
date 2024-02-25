from loguru import logger


class Parser:
    def __init__(self):
        self.__cmd: str = ''
        self.__args: dict = {}

    def parse(self, full_cmd: str | bytes, encoding: str = 'utf-8'):
        if isinstance(full_cmd, bytes):
            full_cmd = full_cmd.decode(encoding)
        logger.info(f"Parsing cmd: {full_cmd}")
        cmd_lst = full_cmd.split(' ')
        self.__cmd = cmd_lst[0]
        cmd_lst = cmd_lst[1:]
        for i in range(len(cmd_lst)):
            if cmd_lst[i].startswith('-'):
                if i + 1 != len(cmd_lst):
                    if not cmd_lst[i + 1].startswith('-'):
                        self.__args[cmd_lst[i]] = cmd_lst[i + 1]
                    else:
                        self.__args[cmd_lst[i]] = True
                else:
                    self.__args[cmd_lst[i]] = True

    def get_cmd(self):
        return self.__cmd

    def get_args(self):
        return self.__args

    def get_arg(self, option):
        return self.__args.get(option)


if __name__ == "__main__":
    parser = Parser()
    parser.parse('download -r files/txt/upl_picture.jpg -l files/txt/down_picture.jpg')
    print(parser.get_cmd())
    print(parser.get_args())
    print(parser.get_arg('-r'))
