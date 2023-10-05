#!/usr/bin/python3
import re
import sys
import subprocess
from pkg_resources import parse_version

# Order this list from oldest to newest
# try not to list something newer than our minimum compiler supported version
BigCoreIDs = {
    (0x41, 0xD07): "cortex-a57",
    (0x41, 0xD08): "cortex-a72",
    (0x41, 0xD09): "cortex-a73",
    (0x41, 0xD0A): "cortex-a75",
    (0x41, 0xD0B): "cortex-a76",
    (0x41, 0xD0D): "cortex-a77",
    (0x41, 0xD41): "cortex-a78",
    (0x41, 0xD44): "cortex-x1",
    (0x41, 0xD47): [
        ["cortex-a78", "0.0"],
        ["cortex-a710", "14.0"],
    ],
    (0x41, 0xD48): [
        ["cortex-x1", "0.0"],
        ["cortex-x2", "14.0"],
    ],
    (0x41, 0xD0C): "neoverse-n1",
    (0x41, 0xD49): "neoverse-n2",
    (0x4E, 0x004): "carmel",
    (0x51, 0x800): "cortex-a73",
    (0x51, 0x802): "cortex-a75",
    (0x51, 0x804): "cortex-a76",
    (0x41, 0x0): [
        ["apple-a13", "0.0"],  # If we aren't on 12.0+
        ["apple-a14", "12.0"],  # Only exists in 12.0+
    ],
}

LittleCoreIDs = {
    (0x41, 0xD04): "cortex-a35",
    (0x41, 0xD03): "cortex-a53",
    (0x41, 0xD05): "cortex-a55",
    (0x41, 0xD46): [
        ["cortex-a55", "0.0"],
        ["cortex-a510", "14.0"],
    ],
    (0x51, 0x801): "cortex-a53",
    (0x51, 0x803): "cortex-a55",
    (0x51, 0x805): "cortex-a55",
}

# Args: </proc/cpuinfo file> <clang version>
if (len(sys.argv) < 3):
    sys.exit()

clang_version = sys.argv[2]
cpuinfo = []
with open(sys.argv[1]) as cpuinfo_file:
    current_implementer = 0
    current_part = 0
    for line in cpuinfo_file:
        line = line.strip()
        if "CPU implementer" in line:
            current_implementer = int(re.findall(r'0x[0-9A-F]+', line, re.I)[0], 16)
        if "CPU part" in line:
            current_part = int(re.findall(r'0x[0-9A-F]+', line, re.I)[0], 16)
            cpuinfo += {(current_implementer, current_part)}

largest_big = "cortex-a57"
largest_little = "cortex-a53"

for core in cpuinfo:
    if BigCoreIDs.get(core):
        IDList = BigCoreIDs.get(core)
        if type(IDList) is list:
            for ID in IDList:
                if parse_version(clang_version) >= parse_version(ID[1]):
                    largest_big = ID[0]
        else:
            largest_big = BigCoreIDs.get(core)

    if LittleCoreIDs.get(core):
        largest_little = LittleCoreIDs.get(core)

# We only want the big core output
print(largest_big)
# print(largest_little)
