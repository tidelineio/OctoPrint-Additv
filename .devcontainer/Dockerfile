FROM python:3.12-slim

# Install git and basic dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -ms /bin/bash vscode

# Set up OctoPrint config
COPY .octoprint /home/vscode/.octoprint
RUN chown -R vscode:vscode /home/vscode/.octoprint

# Switch to non-root user
USER vscode
WORKDIR /workspaces/OctoPrint-Additv

# Install OctoPrint 1.10.2 and debugpy
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir wheel setuptools debugpy 'OctoPrint==1.10.2'
