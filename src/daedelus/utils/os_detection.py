"""
OS Detection and Package Manager Identification.

Detects the operating system and provides appropriate package management commands.

Created by: orpheus497
"""

import logging
import platform
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class OSType(Enum):
    """Operating system types."""
    
    LINUX = "linux"
    MACOS = "macos"
    WINDOWS = "windows"
    BSD = "bsd"
    UNKNOWN = "unknown"


class PackageManager(Enum):
    """Package manager types."""
    
    DNF = "dnf"  # Fedora, RHEL 8+, CentOS 8+
    YUM = "yum"  # RHEL 7, CentOS 7
    APT = "apt"  # Debian, Ubuntu
    PACMAN = "pacman"  # Arch Linux
    ZYPPER = "zypper"  # openSUSE
    BREW = "brew"  # macOS
    PKG = "pkg"  # FreeBSD
    UNKNOWN = "unknown"


@dataclass
class OSInfo:
    """Operating system information."""
    
    os_type: OSType
    distribution: str | None
    version: str | None
    package_manager: PackageManager
    package_manager_cmd: str


class OSDetector:
    """
    Detects operating system and package manager.
    
    Provides accurate OS detection and package manager identification
    for generating appropriate system commands.
    """
    
    def __init__(self) -> None:
        """Initialize OS detector."""
        self._os_info: OSInfo | None = None
        self._detect()
    
    def _detect(self) -> None:
        """Detect operating system and package manager."""
        system = platform.system().lower()
        
        if system == "linux":
            self._os_info = self._detect_linux()
        elif system == "darwin":
            self._os_info = self._detect_macos()
        elif system == "windows":
            self._os_info = self._detect_windows()
        elif "bsd" in system:
            self._os_info = self._detect_bsd()
        else:
            self._os_info = OSInfo(
                os_type=OSType.UNKNOWN,
                distribution=None,
                version=None,
                package_manager=PackageManager.UNKNOWN,
                package_manager_cmd="",
            )
        
        logger.info(
            f"Detected OS: {self._os_info.os_type.value}, "
            f"Package Manager: {self._os_info.package_manager.value}"
        )
    
    def _detect_linux(self) -> OSInfo:
        """Detect Linux distribution and package manager."""
        distribution = None
        version = None
        package_manager = PackageManager.UNKNOWN
        package_manager_cmd = ""
        
        # Try to read /etc/os-release
        os_release_path = Path("/etc/os-release")
        if os_release_path.exists():
            os_release = {}
            with open(os_release_path) as f:
                for line in f:
                    line = line.strip()
                    if "=" in line:
                        key, value = line.split("=", 1)
                        os_release[key] = value.strip('"')
            
            distribution = os_release.get("ID", "").lower()
            version = os_release.get("VERSION_ID", "")
        
        # Detect package manager
        if shutil.which("dnf"):
            package_manager = PackageManager.DNF
            package_manager_cmd = "sudo dnf"
        elif shutil.which("yum"):
            package_manager = PackageManager.YUM
            package_manager_cmd = "sudo yum"
        elif shutil.which("apt"):
            package_manager = PackageManager.APT
            package_manager_cmd = "sudo apt"
        elif shutil.which("pacman"):
            package_manager = PackageManager.PACMAN
            package_manager_cmd = "sudo pacman"
        elif shutil.which("zypper"):
            package_manager = PackageManager.ZYPPER
            package_manager_cmd = "sudo zypper"
        
        return OSInfo(
            os_type=OSType.LINUX,
            distribution=distribution,
            version=version,
            package_manager=package_manager,
            package_manager_cmd=package_manager_cmd,
        )
    
    def _detect_macos(self) -> OSInfo:
        """Detect macOS and package manager."""
        version = platform.mac_ver()[0]
        
        # Check for Homebrew
        package_manager = PackageManager.UNKNOWN
        package_manager_cmd = ""
        
        if shutil.which("brew"):
            package_manager = PackageManager.BREW
            package_manager_cmd = "brew"
        
        return OSInfo(
            os_type=OSType.MACOS,
            distribution="macos",
            version=version,
            package_manager=package_manager,
            package_manager_cmd=package_manager_cmd,
        )
    
    def _detect_windows(self) -> OSInfo:
        """Detect Windows (limited support)."""
        version = platform.win32_ver()[0] if hasattr(platform, "win32_ver") else None
        
        return OSInfo(
            os_type=OSType.WINDOWS,
            distribution="windows",
            version=version,
            package_manager=PackageManager.UNKNOWN,
            package_manager_cmd="",
        )
    
    def _detect_bsd(self) -> OSInfo:
        """Detect BSD and package manager."""
        package_manager = PackageManager.UNKNOWN
        package_manager_cmd = ""
        
        if shutil.which("pkg"):
            package_manager = PackageManager.PKG
            package_manager_cmd = "sudo pkg"
        
        return OSInfo(
            os_type=OSType.BSD,
            distribution="bsd",
            version=None,
            package_manager=package_manager,
            package_manager_cmd=package_manager_cmd,
        )
    
    def get_os_info(self) -> OSInfo:
        """Get detected OS information."""
        return self._os_info
    
    def get_update_command(self) -> str:
        """
        Get the command to update packages on this system.
        
        Returns:
            Complete update command for the current OS
        """
        if self._os_info.package_manager == PackageManager.DNF:
            return "sudo dnf update -y"
        elif self._os_info.package_manager == PackageManager.YUM:
            return "sudo yum update -y"
        elif self._os_info.package_manager == PackageManager.APT:
            return "sudo apt update && sudo apt upgrade -y"
        elif self._os_info.package_manager == PackageManager.PACMAN:
            return "sudo pacman -Syu --noconfirm"
        elif self._os_info.package_manager == PackageManager.ZYPPER:
            return "sudo zypper update -y"
        elif self._os_info.package_manager == PackageManager.BREW:
            return "brew update && brew upgrade"
        elif self._os_info.package_manager == PackageManager.PKG:
            return "sudo pkg update && sudo pkg upgrade -y"
        else:
            return "# Package manager not detected. Please update manually."
    
    def get_install_command(self, package: str) -> str:
        """
        Get the command to install a package on this system.
        
        Args:
            package: Package name to install
            
        Returns:
            Complete install command for the package
        """
        if self._os_info.package_manager == PackageManager.DNF:
            return f"sudo dnf install -y {package}"
        elif self._os_info.package_manager == PackageManager.YUM:
            return f"sudo yum install -y {package}"
        elif self._os_info.package_manager == PackageManager.APT:
            return f"sudo apt install -y {package}"
        elif self._os_info.package_manager == PackageManager.PACMAN:
            return f"sudo pacman -S --noconfirm {package}"
        elif self._os_info.package_manager == PackageManager.ZYPPER:
            return f"sudo zypper install -y {package}"
        elif self._os_info.package_manager == PackageManager.BREW:
            return f"brew install {package}"
        elif self._os_info.package_manager == PackageManager.PKG:
            return f"sudo pkg install -y {package}"
        else:
            return f"# Cannot install {package}: package manager not detected"
    
    def get_search_command(self, package: str) -> str:
        """
        Get the command to search for a package on this system.
        
        Args:
            package: Package name to search for
            
        Returns:
            Complete search command for the package
        """
        if self._os_info.package_manager == PackageManager.DNF:
            return f"dnf search {package}"
        elif self._os_info.package_manager == PackageManager.YUM:
            return f"yum search {package}"
        elif self._os_info.package_manager == PackageManager.APT:
            return f"apt search {package}"
        elif self._os_info.package_manager == PackageManager.PACMAN:
            return f"pacman -Ss {package}"
        elif self._os_info.package_manager == PackageManager.ZYPPER:
            return f"zypper search {package}"
        elif self._os_info.package_manager == PackageManager.BREW:
            return f"brew search {package}"
        elif self._os_info.package_manager == PackageManager.PKG:
            return f"pkg search {package}"
        else:
            return f"# Cannot search for {package}: package manager not detected"


# Global instance
_detector: OSDetector | None = None


def get_os_detector() -> OSDetector:
    """Get the global OS detector instance."""
    global _detector
    if _detector is None:
        _detector = OSDetector()
    return _detector


def get_os_info() -> OSInfo:
    """Get OS information."""
    return get_os_detector().get_os_info()


def get_update_command() -> str:
    """Get system update command."""
    return get_os_detector().get_update_command()


def get_install_command(package: str) -> str:
    """Get package install command."""
    return get_os_detector().get_install_command(package)


def get_search_command(package: str) -> str:
    """Get package search command."""
    return get_os_detector().get_search_command(package)
