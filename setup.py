from setuptools import setup
import os

# Get version from version.py
version_file = os.path.join(os.path.dirname(__file__), "octoprint_additv", "version.py")
about = {}
with open(version_file, "r") as f:
    exec(f.read(), about)

setup(
    name="OctoPrint-Additv",
    version=about["__version__"],
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
