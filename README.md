This project uses `uv`. Make sure you have installed it. https://docs.astral.sh/uv/#installation

### Dev Setup

```bash
uv sync
```

### Database Setup

The database will be automatically created when you start the server. However, you can also initialize it manually:

```bash
uv run python -m src.schema
```

This creates the database at `data/sqlite3.db` with the proper schema (including `raw_bytes` field and nullable columns).

### **How to Use:**

**Start the server (includes UDP socket listener):**

The server automatically:

- Initializes the database connection
- Starts the UDP socket listener on `localhost:1337` to receive packets from the radio interface
- Starts the FastAPI server on port `8000` with SSE endpoint

```bash
uv run hypercorn -c hypercorn_config.toml src.main:app
```

**Test SSE endpoint with HTTP/2:**

```bash
curl -N --http2 http://localhost:1338/telemetry-events
```

**Test SSE endpoint with regular HTTP/1.1:**

```bash
curl -N http://localhost:1338/telemetry-events
```

### Architecture

- **UDP Socket Listener**: Listens on `localhost:1337` for raw bytes from the radio interface
- **Decoder**: Decodes incoming packets using the packet parser
- **Database**: Stores raw bytes and decoded telemetry in SQLite (`data/sqlite3.db`)
- **SSE Server**: Broadcasts decoded telemetry in real-time via Server-Sent Events on port `1338`
