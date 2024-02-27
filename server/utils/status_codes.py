class StatusCode:
    ok = int.to_bytes(1, length=1, byteorder='big')
    err = int.to_bytes(2, length=1, byteorder='big')
    cmd_start = int.to_bytes(3, length=1, byteorder='big')
    cmd_end = int.to_bytes(4, length=1, byteorder='big')
    not_found = int.to_bytes(5, length=1, byteorder='big')
    unauthorized = int.to_bytes(6, length=1, byteorder='big')
