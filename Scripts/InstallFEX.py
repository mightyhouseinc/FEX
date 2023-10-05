#!/usr/bin/python3
import os
import subprocess
import sys
import tempfile

_Arch = None
def GetArch():
    global _Arch

    if _Arch is None:
        _Arch = subprocess.check_output(['uname', '-m']).decode("utf-8").strip()
    return _Arch

_Distro = None
def GetDistro():
    global _Distro

    # Query files in order
    # /etc/lsb-release
    # /etc/os-release

    if _Distro is None:
        if os.path.exists("/etc/lsb-release"):
            with open("/etc/lsb-release", "r") as File:
                Lines = File.readlines()
            Found = 0
            Distro = ""
            Version = ""
            for Line in Lines:
                Key, Val = Line.split("=", 1)

                if Key == "DISTRIB_ID":
                    Distro = Val.strip().lower()
                    Found+=1
                if Key == "DISTRIB_RELEASE":
                    Version = Val.strip()
                    Found+=1

            if Found == 2:
                _Distro = [Distro, Version]
                return _Distro

        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r") as File:
                Lines = File.readlines()
            Found = 0
            Distro = ""
            Version = ""
            for Line in Lines:
                Key, Val = Line.split("=", 1)

                if Key == "ID":
                    Distro = Val.strip()
                    Found+=1
                if Key == "VERSION_ID":
                    # Strip the double quotes from the version id
                    Version = Val.strip()[1:-1]
                    Found+=1

            if Found == 2:
                _Distro = [Distro, Version]
                return _Distro

        # Unknown
        _Distro = ["Unknown", "0.0"]

    return _Distro

def IsSupportedArch():
    Arch = GetArch()
    return Arch == "aarch64"

def IsSupportedDistro():
    Distro = GetDistro()

    # We only support Ubuntu
    if Distro[0] == "ubuntu":
        # We only support what is available in ppa:fex-emu/fex
        return Distro[1] in ["20.04", "22.04", "22.10"]

    return False

_ArchVersion = None
def ListContainsRequired(Features, RequiredFeatures):
    return all(Req in Features for Req in RequiredFeatures)

def GetCPUFeaturesVersion():
    global _ArchVersion

    # Also LOR but kernel doesn't expose this
    v8_1Mandatory = ["atomics", "asimdrdm", "crc32"]
    v8_2Mandatory = v8_1Mandatory + ["dcpop"]
    v8_3Mandatory = v8_2Mandatory + ["fcma", "jscvt", "lrcpc", "paca", "pacg"]
    v8_4Mandatory = v8_3Mandatory + ["asimddp", "flagm", "ilrcpc", "uscat"]

    #  fphp asimdhp asimddp

    if _ArchVersion is None:
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

_PPAInstalled = None
FEXPPA = "http://ppa.launchpad.net/fex-emu/fex/ubuntu"

def GetPPAStatus():
    global _PPAInstalled

    if _PPAInstalled is None:
        _PPAInstalled = False

        CacheResults = subprocess.check_output(['apt-cache', 'policy']).decode("utf-8")

        for Line in CacheResults.split("\n"):
            if "http" in Line:
                Line = Line.strip()
                LineSplit = Line.split(" ")

                # 'status' 'URL' 'series' 'arch' 'type'
                if LineSplit[1] == FEXPPA:
                    _PPAInstalled = True
                    break

    return _PPAInstalled

def InstallPPA():
    print ("Installing PPA: ppa:fex-emu/fex")
    print ("This bit will ask for your password")

    DidInstall = False
    try:
        CmdResult = subprocess.call(["sudo", "add-apt-repository", "-y", "ppa:fex-emu/fex"])
        DidInstall = CmdResult == 0
    except KeyboardInterrupt:
        DidInstall = False
    if DidInstall:
        print("PPA installed")
    else:
        print("PPA failed to install")

    return DidInstall

ARMVersionToPackage = {
    "8.0": "fex-emu-armv8.0",
    "8.1": "fex-emu-armv8.0",
    "8.2": "fex-emu-armv8.2",
    "8.3": "fex-emu-armv8.2",
    "8.4": "fex-emu-armv8.4",
}

def GetPackagesToInstall():
    return [
        ARMVersionToPackage[GetCPUFeaturesVersion()],
        "fex-emu-binfmt32",
        "fex-emu-binfmt64",
    ]

def UpdatePPA():
    print ("Updating apt sources")
    print ("This bit will ask for your password")

    DidUpdate = False
    try:
        CmdResult = subprocess.call(["sudo", "apt-get", "update"])
        DidUpdate = CmdResult == 0
    except KeyboardInterrupt:
        DidUpdate = False
    if DidUpdate:
        print("PPA installed")
    else:
        print("PPA failed to install")

    return DidUpdate

def CheckAndInstallPackageUpdates():
    PackagesToInstall = GetPackagesToInstall()
    for Package in PackagesToInstall[:]:
        UpgradableStatus = subprocess.check_output(["apt", "list", "--upgradable", Package]).decode("utf-8")
        Found = any(
            Package in Line and "upgradable" in Line
            for Line in UpgradableStatus.split("\n")
        )
        if not Found:
            PackagesToInstall.remove(Package)

    if len(PackagesToInstall) > 0:
        print(f"Found updates for packages: {PackagesToInstall}")
        print ("This bit may ask for your password")

        DidInstall = False
        try:
            CmdResult = subprocess.call(["sudo", "apt-get", "-y", "install"] + PackagesToInstall)
            DidInstall = CmdResult == 0
        except KeyboardInterrupt:
            print ("Keyboard interrupt")
            DidInstall = False
        if DidInstall:
            print("Packages updated")
        else:
            print("Packages failed to update")

        return DidInstall

    return True

def CheckPackageInstallStatus():
    PackagesToInstall = GetPackagesToInstall()
    for Package in PackagesToInstall[:]:
        CmdResult = subprocess.call(["dpkg", "-s", Package], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if CmdResult == 0:
            PackagesToInstall.remove(Package)

    return PackagesToInstall

def InstallPackages(Packages):
    print(f"Installing packages: {Packages}")

    DidInstall = False
    try:
        CmdResult = subprocess.call(["sudo", "apt-get", "-y", "install"] + Packages)
        DidInstall = CmdResult == 0
    except KeyboardInterrupt:
        print ("Keyboard interrupt")
        DidInstall = False
    if DidInstall:
        print("Packages installed")
    else:
        print("Packages failed to install")

    return DidInstall

_RootFSPath = None
def GetRootFSPath():
    global _RootFSPath

    if _RootFSPath is None:
        # Follows the same logic as FEXCore::Config::GetDataDirectory()
        HomeDir = os.getenv("HOME")
        if HomeDir is None:
            HomeDir = os.getenv("PWD")
        if HomeDir is None:
            HomeDir = "."

        Path = HomeDir
        DataXDG = os.getenv("XDG_DATA_HOME")
        if DataXDG != None:
            Path = DataXDG

        DataOverride = os.getenv("FEX_APP_DATA_LOCATION")

        Path = DataOverride if DataOverride != None else f"{Path}/.fex-emu"
        _RootFSPath = f"{Path}/RootFS/"

    return _RootFSPath

def CheckRootFSInstallStatus():
    # Matches what is available on https://rootfs.fex-emu.com/file/fex-rootfs/RootFS_links.json
    UbuntuVersionToRootFS = {
        "20.04": "Ubuntu_20_04.sqsh",
        "20.04": "Ubuntu_20_04.ero",
        "22.04": "Ubuntu_22_04.sqsh",
        "22.04": "Ubuntu_22_04.ero",
        "22.10": "Ubuntu_22_10.sqsh",
        "22.10": "Ubuntu_22_10.ero",
    }

    return os.path.exists(GetRootFSPath() + UbuntuVersionToRootFS[GetDistro()[1]])

def TryInstallRootFS():
    DidInstall = False
    try:
        CmdResult = subprocess.call(["FEXRootFSFetcher"])
        DidInstall = CmdResult == 0
    except KeyboardInterrupt:
        print ("Keyboard interrupt")
        DidInstall = False
    return DidInstall

def TryBasicProgramExecution():
    return subprocess.call(["FEXInterpreter", "/usr/bin/uname", "-a"]) == 0

def ExitWithStatus(Status):
    # Remove the cached credentials
    subprocess.call(["sudo", "-K"])
    sys.exit(Status)

def main():
    # Only run on supported arch
    if not IsSupportedArch():
        print ( "{} is not a supported architecture".format(GetArch()))
        ExitWithStatus(-1)

    if not IsSupportedDistro():
        Distro = GetDistro()
        print ( "'{} {}' is not a supported distro".format(Distro[0], Distro[1]))
        ExitWithStatus(-1)

    if GetDistro()[0] == "ubuntu":
        print ("Getting PPA status: {}".format(("NotInstalled", "Installed")[GetPPAStatus()]))

        if GetPPAStatus():
            if not UpdatePPA():
                print ("apt sources failed to update. Not continuing")
                ExitWithStatus(-1)
            if not CheckAndInstallPackageUpdates():
                print ("apt packages failed to update. Not continuing")
                ExitWithStatus(-1)
        else:
            if not InstallPPA():
                print ("PPA failed to install. Not continuing")
                ExitWithStatus(-1)

        Packages = CheckPackageInstallStatus()
        if len(Packages) > 0:
            if not InstallPackages(Packages):
                print ("Failed to install packages. Not continuing")
                ExitWithStatus(-1)

        if not CheckRootFSInstallStatus():
            print ("RootFS not found. Running FEXRootFSFetcher to get rootfs")
            if not TryInstallRootFS():
                print ("Failed to install RootFS. Not continuing")
                ExitWithStatus(-1)

    print ("FEX is now installed. Trying basic program run")
    if not TryBasicProgramExecution():
        print ("FEXInterpreter failed to run. Not continuing")
        ExitWithStatus(-1)

    print ("")
    print ("===================================================")
    print ("FEX test run executed. You should be set to run FEX")
    print ("===================================================")
    print ("Usage examples:")
    print ("# steam is a bash script. Wrap with FEXBash")
    print ("\tFEXBash steam")
    print ("# Full path execution execution will wrap the application if it exists in the rootfs")
    print ("\tFEXInterpreter /usr/bin/uname")
    print ("# Freestanding x86/x86-64 programs can be executed directly. binfmt_misc will redirect to FEX")
    print ("\t$HOME/PetalCrashOnline.AppImage")
    print ("# If you need a terminal that emulates everything.")
    print ("# Run FEXBash without arguments. Double check uname to see if running under FEX")
    print ("\tFEXBash")

    ExitWithStatus(0)

if __name__ == "__main__":
	sys.exit(main())
