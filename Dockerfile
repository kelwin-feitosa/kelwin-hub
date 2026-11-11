FROM python:3.12-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY pyproject.toml ./
COPY hub ./hub
COPY scripts ./scripts
RUN pip install --no-cache-dir '.[backup]' && useradd -u 10001 -m hub && mkdir -p /app/data && chown -R hub:hub /app/data
USER hub
EXPOSE 8000
CMD ["uvicorn", "hub.server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "127.0.0.1"]
