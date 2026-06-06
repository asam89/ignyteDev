FROM python:3.12-slim

# Install git and GitHub CLI
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
       -o /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] \n       https://cli.github.com/packages stable main" \
       > /etc/apt/sources.list.d/github-cli.list \
    && apt-get update && apt-get install -y gh \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/
COPY dashboard/ ./dashboard/

# Create directories
RUN mkdir -p /app/data /app/uploads /repos

# Git identity for the bot
RUN git config --global user.email "bot@ignyteconsulting.com" \
    && git config --global user.name "IgnyteDev Bot"

EXPOSE 8080

CMD ["python", "bot/worker_node.py"]
