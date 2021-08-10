#!/usr/bin/env python3

import serial
import binascii
import zlib
import os
import sys
import argparse
import math
from tqdm import tqdm

PROMPT_STRING = b'FUSIV-DIALFACE # '

class serialWrapper():

    def __init__(self, port, baudrate):
        self.s = serial.Serial(port, baudrate)

    def readuntil(self, pattern):
        assert isinstance(pattern, bytes), 'readuntil wants bytes'

        line = b''
        while pattern != line[-len(pattern):]:
            print(f'READ: {len(line)} bytes', end='\r')
            line += self.s.read(1)

        return line

    def close(self):
        self.s.close()

    def send(self, line):
        self.s.write(line)

    def sendline(self, line = b''):
        self.send(line + b'\n')

    def readline(self):
        return self.readuntil(b'\n')


def dump(args):
    start = args.start
    size = args.size

    try:
        start = int(start, 16)
    except Exception as e: 
        print(e)
        exit(2)

    try:
        s = serialWrapper(args.port, args.baudrate)
    except serial.serialutil.SerialException:
        print('Resource busy or not connected')
        exit(1)

    s.sendline(b'h')
    response = s.readuntil(PROMPT_STRING)

    command = f'md.b {start:x} {size:x}'
    s.sendline(command.encode())

    print(s.readline().decode())

    with open(args.file, 'wb') as f:
        for _ in tqdm(range(math.ceil(size / 16))):
            line = s.readline()
            line = line.strip()

            hexdump = line[10:57]
            hexdump = hexdump.replace(b' ', b'')

            binary_dump = binascii.unhexlify(hexdump)

            f.write(binary_dump)


def unpack(args):
    class Part:
        def __init__(self, name, offset, size):
            self.name = name
            self.offset = offset
            self.size = size
        
    parts = [
        Part("u-boot_version_string", 0x26D50, 22336),
        Part("CRC32_polynomial_table", 0x2C490, 343044),
        Part("uimage_kernel_1", 0x80094, 2051948),
        Part("cramfs_1", 0x275000, 5812372),
        Part("uimage_kernel_2", 0x800094, 2051948),
        Part("cramfs_2", 0x9F5000, 5812376),
        Part("lzma_1", 0xF80098, 131072),
        Part("lzma_2", 0xFA0098, 131072),
        Part("lzma_3", 0xFC0098, 16777216-0xFC0098),
    ]

    try:
        os.mkdir(args.dir)
    except FileExistsError:
        pass

    with open(args.rom, "rb") as f:
        for part in parts:
            with open(os.path.join(args.dir, part.name), "wb") as outfile:
                f.seek(part.offset, 0)
                data = f.read(part.size)
                outfile.write(data)
                print(f'Wrote {part.name} - {hex(len(data))} bytes')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description = 'AGIF router tool',
        prog = 'AGIF tools'
    )

    parser.add_argument(
        '--port',
        type = str,
        default = '/dev/ttyUSB0',
        help = 'Specify serial port to connect to'
    )

    parser.add_argument(
        '--baudrate',
        type = int,
        default = 57600,
        help = 'Specify serial connection speed'
    )

    # Subparser
    subparser = parser.add_subparsers(help = 'Single utilities')

    # DUMP sub parser
    dump_parser = subparser.add_parser(
        'dump',
        help = 'Dump memory with starting address and size'
    )

    dump_parser.add_argument(
        '--file',
        type = str,
        default = 'dump.bin',
        help = 'Specify output filename'
    )

    dump_parser.add_argument(
        '--start',
        type = str,
        required = True,
        help = 'Dump start address (in hexadecimal)'
    )

    dump_parser.add_argument(
        '--size',
        type = int,
        required = True,
        help = 'Dump size'
    )

    dump_parser.set_defaults(func = dump)

    # UNPACK sub parser
    unpack_parser = subparser.add_parser(
        'unpack',
        help = 'Unpack the AGIF ROM'
    )

    unpack_parser.add_argument(
        '--rom',
        type = str,
        default = 'dump.bin',
        help = 'Specify the rom filename'
    )

    unpack_parser.add_argument(
        '--dir',
        type = str,
        default = 'extracted',
        help = 'Specify the directory to unpack to'
    )

    unpack_parser.set_defaults(func = unpack)

    args = parser.parse_args()

    try:
        args.func(args)
    except AttributeError:
        parser.print_help()

