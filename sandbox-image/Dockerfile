FROM python:3.12-slim

# Ensure non-root security: create user and group 'sandboxuser' with fixed UID/GID 1000
RUN groupadd -g 1000 sandboxgroup && \
    useradd -u 1000 -g sandboxgroup -m -s /bin/bash sandboxuser

# Install system dependencies if necessary (clean up apt cache immediately)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install locked data-science runtime packages for the sandbox
# Note: Pandas, Polars, DuckDB, NumPy, PyArrow, and Matplotlib are restricted to the sandbox container
RUN pip install --no-cache-dir \
    numpy \
    pandas \
    polars \
    duckdb \
    pyarrow \
    matplotlib

# Create necessary mount points
RUN mkdir -p /data /tmp/output && \
    chown -R sandboxuser:sandboxgroup /tmp/output /data

# Configure environment variables to point all writable temp directories to /tmp/output
ENV HOME=/tmp/output \
    MPLCONFIGDIR=/tmp/output/.matplotlib \
    DUCKDB_TEMP_DIRECTORY=/tmp/output/.duckdb_temp \
    PYTHONUNBUFFERED=1

# Run strictly as non-root user
USER sandboxuser
WORKDIR /tmp/output

# Default entrypoint for script execution
ENTRYPOINT ["python", "-u"]
