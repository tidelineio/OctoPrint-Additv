FROM python:3.12-slim

# Install git and basic dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -ms /bin/bash vscode
USER vscode
WORKDIR /workspaces/OctoPrint-Additv

# Install OctoPrint
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir wheel setuptools octoprint

CMD ["sleep", "infinity"]
