
FROM python:3.14-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install DuckDB CLI, this is good for debugging and local development inside a container to see actual DB data at end
RUN curl -L https://install.duckdb.org | sh

# Add DuckDB CLI to PATH
ENV PATH="/root/.duckdb/cli/latest:${PATH}"

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["bash"]
