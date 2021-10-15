## Description 
roms:
    full_mtdblock0 -> Flash memory content

updates:
    .img -> non signed
    .rmt -> signed from telecom

### agif-tool.py
- dump: Dump flash memory through UART command, it is very slow
- unpack-rom: Unpack the memory flash dump 
- unpack-update: Unpack update file
  - eg. `python3 agif-tool.py unpack-update --update updates/AGIF_1.2.0d.img && 7z x cramfs`
- pack: Pack update file

### Findings
- The board has a UART exposed, you can activate debug mode which open telnet on the linux