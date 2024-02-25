from loguru import logger


class Parser:
    def __init__(self):
        self.__cmd: str = ''
        self.__args: dict = {}

    def parse(self, full_cmd: str | bytes, encoding: str = 'utf-8', with_options=False):
        if isinstance(full_cmd, bytes):
            full_cmd = full_cmd.decode(encoding)
        logger.info(f"Parsing cmd: {full_cmd}")
        cmd_lst = full_cmd.split(' ')
        self.__cmd = cmd_lst[0]
        cmd_lst = cmd_lst[1:]
        if with_options:
            for i in range(len(cmd_lst)):
                if cmd_lst[i].startswith('-'):
                    if i + 1 != len(cmd_lst):
                        if not cmd_lst[i + 1].startswith('-'):
                            self.__args[cmd_lst[i]] = cmd_lst[i + 1]
                        else:
                            self.__args[cmd_lst[i]] = True
                    else:
                        self.__args[cmd_lst[i]] = True

        if not with_options:
            self.__args['args'] = []
            for i in range(len(cmd_lst)):
                self.__args['args'].append(cmd_lst[i])

    def check_args(self, amount, with_options=False):
        if not with_options:
            return amount == len(self.__args.get('args'))
        return None

    def get_cmd(self):
        return self.__cmd

    def get_args(self):
        return self.__args

    def get_arg(self, option):
        return self.__args.get(option)


if __name__ == "__main__":
    parser = Parser()
    parser.parse('download files/1 files/2')
    print(parser.get_args()['args'][0])
    print(parser.check_args(0))
