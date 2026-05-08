FROM python:3.12-slim

# Install uv.
COPY --from=ghcr.io/astral-sh/uv:0.9.5 /uv /uvx /bin/

WORKDIR /app

# Copy only the dependency files first.
COPY pyproject.toml uv.lock ./

# Install the application dependencies.
# This layer will be cached as long as the dependency files don't change.
RUN uv sync --frozen --no-cache

# Now copy the rest of the application code.
COPY . .

# Create a non-root user and change ownership of the /app directory
RUN useradd -m appuser && chown -R appuser:appuser /app

USER appuser

# Run the application.
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD ["python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"]

CMD ["/app/.venv/bin/uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
