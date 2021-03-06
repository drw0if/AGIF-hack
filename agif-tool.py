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


class Part:
    def __init__(self, name, offset, size):
        self.name = name
        self.offset = offset
        self.size = size


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


def unpack(args, filename, part_list):
    try:
        os.mkdir(args.dir)
    except FileExistsError:
        pass

    with open(filename, "rb") as f:
        for part in part_list:
            with open(os.path.join(args.dir, part.name), "wb") as outfile:
                f.seek(part.offset, 0)
                data = f.read(part.size)
                outfile.write(data)
                print(f'Wrote {part.name} - {hex(len(data))} bytes')


def unpack_rom(args):      
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

    unpack(args, args.rom, parts)


def unpack_update(args):
    parts = [
        Part("header", 0, 148),
        Part("uimage_header", 0x94, 64),
        Part("lzma", 0xD4, 2051884),
        Part("cramfs", 0x1F5000, 4980736),
    ]

    unpack(args, args.update, parts)


def pack(args):
    parts = [
        Part("header", 0, 148),
        Part("uimage_header", 0x94, 64),
        Part("lzma", 0xD4, 2051884),
        Part("cramfs", 0x1F5000, 4980736),
    ]

    data = bytearray()

    for part in parts:
        with open(os.path.join(args.dir, part.name), "rb") as infile:
            data += infile.read()

    # add size
    size = len(data) - 148
    data[7] = size & 0xFF
    data[6] = (size >> 8) & 0xFF
    data[5] = (size >> 16) & 0xFF
    data[4] = (size >> 24) & 0xFF

    print(f'Size: {size:#x}')

    # add checksum
    data[8] = data[9] = data[10] = data[11] = 0
    checksum = sum(data)

    data[11] = checksum & 0xFF
    data[10] = (checksum >> 8) & 0xFF
    data[9] = (checksum >> 16) & 0xFF
    data[8] = (checksum >> 24) & 0xFF

    print(f'Checksum: {checksum:#x}')

    with open("AGIF_patched.img", "wb") as f:
        f.write(data)
        print(f'Wrote {len(data)} bytes')


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

    parser.add_argument(
        '--dir',
        type = str,
        default = 'extracted',
        help = 'Specify the directory to put the result to'
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

    # UNPACK_ROM sub parser
    unpack_rom_parser = subparser.add_parser(
        'unpack-rom',
        help = 'Unpack the AGIF ROM'
    )

    unpack_rom_parser.add_argument(
        '--rom',
        type = str,
        default = 'dump.bin',
        help = 'Specify the rom filename'
    )

    unpack_rom_parser.set_defaults(func = unpack_rom)

    # UNPACK_UPDATE sub parser
    unpack_update_parser = subparser.add_parser(
        'unpack-update',
        help = 'Unpack the AGIF update'
    )

    unpack_update_parser.add_argument(
        '--update',
        type = str,
        default = 'update.bin',
        help = 'Specify the update filename'
    )

    unpack_update_parser.set_defaults(func = unpack_update)

    # PACK sub parser
    pack_parser = subparser.add_parser(
        'pack',
        help = 'Pack the AGIF update'
    )

    pack_parser.set_defaults(func = pack)

    args = parser.parse_args()

    try:
        args.func(args)
    except AttributeError:
        parser.print_help()

