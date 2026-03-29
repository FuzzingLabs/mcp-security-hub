"""
Shared pytest configuration and fixtures for all MCP server tests.
"""

import subprocess
import sys
from pathlib import Path

import pytest

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (may require external resources)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "docker: mark test as requiring Docker (build + run containers)"
    )


@pytest.fixture(scope="session")
def docker_available():
    """Check if Docker is available."""
    try:
        subprocess.run(
            ["docker", "version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.fixture(scope="session")
def nuclei_available():
    """Check if Nuclei binary is available."""
    try:
        subprocess.run(
            ["nuclei", "-version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


@pytest.fixture(scope="session")
def nmap_available():
    """Check if Nmap binary is available."""
    try:
        subprocess.run(
            ["nmap", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False
