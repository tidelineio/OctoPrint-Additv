from setuptools import setup

setup(
    name="OctoPrint-Additv",
    version="0.1.0",
    description="Additv OctoPrint Plugin",
    author="Josh",
    author_email="josh@example.com",
    url="https://github.com/you/OctoPrint-Additv",
    license="AGPLv3",
    packages=["octoprint_additv"],
    python_requires=">=3.7,<4",
    install_requires=["OctoPrint>=1.9.0"],
    entry_points={
        "octoprint.plugin": [
            "additv = octoprint_additv:AdditivPlugin"
        ]
    }
)
