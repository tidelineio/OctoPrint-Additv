FROM python:3.12-slim

# Install git and basic dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -ms /bin/bash vscode

# Switch to non-root user
USER vscode
WORKDIR /workspaces/OctoPrint-Additv

# Install OctoPrint and development dependencies first for better layer caching
RUN pip install --upgrade pip && \
    pip install wheel setuptools debugpy 'OctoPrint>=1.9.0' 'OctoPrint==1.10.2'

# Copy OctoPrint config after installing dependencies
COPY --chown=vscode:vscode .octoprint /home/vscode/.octoprint
