#!/usr/bin/python3
import os
import subprocess
import sys
import tempfile
import platform

def ListContainsRequired(Features, RequiredFeatures):
    return all(Req in Features for Req in RequiredFeatures)

def GetCPUFeaturesVersion():

    # Also LOR but kernel doesn't expose this
    v8_1Mandatory = ["atomics", "asimdrdm", "crc32"]
    v8_2Mandatory = v8_1Mandatory + ["dcpop"]
    v8_3Mandatory = v8_2Mandatory + ["fcma", "jscvt", "lrcpc", "paca", "pacg"]
    v8_4Mandatory = v8_3Mandatory + ["asimddp", "flagm", "ilrcpc", "uscat"]

    with open("/proc/cpuinfo", "r") as File:
        Lines = File.readlines()
    # Minimum spec is ARMv8.0
    _ArchVersion = "8.0"
    for Line in Lines:
        if "Features" in Line:
            Features = Line.split(":")[1].strip().split(" ")

            # We don't care beyond 8.4 right now
            if ListContainsRequired(Features, v8_4Mandatory):
                _ArchVersion = "8.4"
            elif ListContainsRequired(Features, v8_3Mandatory):
                _ArchVersion = "8.3"
            elif ListContainsRequired(Features, v8_2Mandatory):
                _ArchVersion = "8.2"
            elif ListContainsRequired(Features, v8_1Mandatory):
                _ArchVersion = "8.1"
            break;

    return _ArchVersion

def main():
    if (platform.machine() == "aarch64"):
        print(f"ARMv{GetCPUFeaturesVersion()}")
    elif (platform.machine() == "x86_64"):
        print("x64")

    sys.exit(0)

if __name__ == "__main__":
    sys.exit(main())
