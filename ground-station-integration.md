# Ground software integration plan (old-groundstation → src, SSE, NDJSON)

## Goals

- Replace mock DB replay with live decoded telemetry via `/telemetry-events` SSE.
- Keep multiple ingest options: serial, CSV replay, binary log.
- Persist decoded telemetry to NDJSON (rotating files) without blocking SSE.
- Remove Flask/Tkinter; keep only decoding, framing, sorting, and mapping.

## High-level architecture

- `Source` (serial/csv/binlog) → `Framer/Sorter` → `Decoder` → `Mapper` → `asyncio.Queue[Telemetry]`
- Background writer persists each telemetry dict as NDJSON.
- SSE endpoint drains from an async fanout (broadcast) to support multiple clients.

## Files and modules (new)

- `src/ground/__init__.py`
- `src/ground/sources/base.py` (async iterator protocol, backpressure)
- `src/ground/sources/serial_source.py` (pyserial async reader)
- `src/ground/sources/csv_source.py` (time-based replay with speed factor)
- `src/ground/sources/binlog_source.py` (read raw RF/log frames)
- `src/ground/framing/radio_frame.py` (ported from `RadioFrame.py`, pure logic)
- `src/ground/framing/serial_sorter.py` (ported/minified `SerialSorter.py`)
- `src/ground/decoder/packet_decoder.py` (ported `PacketDecoder.py`)
- `src/ground/mapping/telemetry_mapper.py` (map decoded fields → `FlightTelemetry` shape)
- `src/ground/pipeline.py` (wire source→framer→decoder→mapper→broadcast queue)
- `src/ground/persist/ndjson_writer.py` (rotating writer)
- `src/ground/config.py` (ingest config: source type, paths, serial params, replay speed)

## Files (modified)

- `src/main.py`:
- Initialize pipeline on startup; expose broadcast handle to SSE.
- New `/telemetry-events` uses live queue (and reconnect replay per-client).
- Keep `/health-check`.
- `src/config.py`:
- Add NDJSON output dir; environment overrides.

## Porting guidance from old-groundstation

- Copy only computation/IO modules: `RadioFrame.py`, `SerialSorter.py`, `PacketDecoder.py`, any data frame structures used.
- Exclude: `GUI.py`, `GSEFrame.py`, `SimpleDisplay.py`, `ServerInterface.py`, `ServerProcess.py`, Flask/Tkinter, and any code invoking them.
- Replace synchronous loops with async equivalents; remove global state and threads where practical.

## SSE fanout

- Implement a broadcast hub using `asyncio.Queue` per-subscriber or a small pubsub (e.g., `asyncio.Queue` + `weakref` set).
- On client connect: create a queue and consume; on disconnect: cleanup.

## NDJSON persistence

- Write one JSON object per line; filename like `data/out/telemetry-YYYYMMDD.ndjson`.
- Rotate daily or by size (e.g., 50MB). Use non-blocking background task with `asyncio.to_thread` if needed.

## Configuration

- Env vars or `.env` read at startup:
- `GSW_SOURCE={serial|csv|binlog}`
- `GSW_SERIAL_PORT`, `GSW_SERIAL_BAUD`
- `GSW_CSV_PATH`, `GSW_REPLAY_SPEED` (float, 1.0 = real-time)
- `GSW_BINLOG_PATH`
- `GSW_NDJSON_DIR` (default `data/out`)

## Migration path

- Phase 1: Implement CSV replay source to validate mapping and SSE contract.
- Phase 2: Add serial live source (behind flag).
- Phase 3: Add binary log source.

## Testing and validation

- Unit tests for framing/decoder with sample payloads from `old-groundstation`.
- Integration test: start server, stream a short CSV, verify SSE events and NDJSON lines.
- Manual: connect multiple SSE clients; ensure fanout and backpressure work.

## Operational notes

- Clean shutdown on SIGTERM: stop source, drain queues, close NDJSON file.
- Metrics/logging: count frames, decode errors, dropped messages.
- Ruff + type hints across new modules; keep `uv` workflow.
