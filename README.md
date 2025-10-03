This project uses `uv`. Make sure you have installed it. https://docs.astral.sh/uv/#installation

### Dev Setup

```bash
uv sync
```

```bash
uv run -m src.main
```

### **How to Use:**

**Start the server with HTTP/2:**

```bash
uv run hypercorn -c hypercorn_config.toml src.main:app
```

**Test with HTTP/2:**

```bash
curl -N --http2 http://localhost:8000/telemetry-events
```

**Test with regular HTTP/1.1:**

```bash
curl -N http://localhost:8000/telemetry-events
```
