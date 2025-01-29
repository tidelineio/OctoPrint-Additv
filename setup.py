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
    author="Josh",
    author_email="josh@example.com",
    url="https://github.com/you/OctoPrint-Additv",
    license="AGPLv3",
    packages=["octoprint_additv"],
    python_requires=">=3.7,<4",
    install_requires=["OctoPrint>=1.9.0", "supabase"],
    entry_points={
        "octoprint.plugin": [
            "additv = octoprint_additv:AdditivPlugin"
        ]
    }
)
