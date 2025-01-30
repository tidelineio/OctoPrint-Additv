from setuptools import setup
import os

# Try to get version from version.py if it exists (release package)
# otherwise use development version
version = "0.0.0-dev"
version_file = os.path.join(os.path.dirname(__file__), "octoprint_additv", "version.py")
if os.path.exists(version_file):
    about = {}
    with open(version_file, "r") as f:
        exec(f.read(), about)
    version = about["__version__"]

setup(
    name="OctoPrint-Additv",
    version=version,
    description="Additv OctoPrint Plugin",
    author="Josh Wright",
    author_email="josh@example.com",
    url="https://github.com/tidelineio/OctoPrint-Additv",
    license="AGPLv3",
    packages=["octoprint_additv"],
    python_requires=">=3.11,<4",
    install_requires=[
        "OctoPrint>=1.10.0,<2.0.0",
        "supabase>=2.12.0,<3.0.0",
        "pyyaml~=6.0",
        "requests>=2.32.0,<3.0.0"
    ],
    entry_points={
        "octoprint.plugin": [
            "additv = octoprint_additv:AdditivPlugin"
        ]
    }
)
