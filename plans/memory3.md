# Memory2 Implementation Plan

Source of truth: `plans/memory_2_spec_v_2.md`

## Context

PR #1080 introduced `TimeSeriesStore[T]` with pluggable backends. Paul's review identified it mixes DB lifecycle, connection, and query concerns. `memory.md` describes a system where all sensor data is stored as temporal streams with spatial indexing, cross-stream correlation, and multimodal search. The spec (`memory_2_spec_v_2.md`) defines the full public API. This plan maps the spec to concrete SQLite implementation in `dimos/memory2/`.

## File Structure

```
dimos/memory2/
    __init__.py              # public exports
    _sql.py                  # _validate_identifier(), SQL helpers
    types.py                 # ObservationRef, ObservationMeta, ObservationRow, Lineage, StreamInfo
    db.py                    # DB (Resource lifecycle, SqliteDB)
    session.py               # Session (connection, stream factory, correlate)
    stream.py                # StreamBase, BlobStream, EmbeddingStream, TextStream
    observation_set.py       # ObservationSet (lazy, re-queryable, predicate/ref-table backed)
    query.py                 # Query (filter/search/rank/limit → fetch/fetch_set)
    test_memory2.py          # tests
```

## Implementation Priority (per spec §15)

### Phase 1: Core types + storage

1. **`types.py`** — Data classes

```python

@dataclass(frozen=True)
class ObservationRef:
    stream: str
    rowid: int

@dataclass
class ObservationRow:
    ref: ObservationRef
    ts: float | None = None
    pose: PoseLike | None = None
    scores: dict[str, float] = field(default_factory=dict)
    tags: dict[str, Any] = field(default_factory=dict)

@dataclass
class Lineage:
    parent_ref: ObservationRef | None = None  # single parent via parent_stream + parent_rowid
```

Poses use DimOS's existing `PoseLike` type alias (`Pose | PoseStamped | Point | PointStamped`). Internally, `append()` extracts `(x, y, z, qx, qy, qz, qw)` floats for SQL storage; `load` reconstructs a `dimos.msgs.geometry_msgs.Pose` from stored floats. No custom Pose type.

2. **`_sql.py`** — SQL helpers

```python
def validate_identifier(name: str) -> str: ...  # regex check, length limit
```

3. **`db.py`** — DB + SqliteDB

```python
class DB(Resource, ABC):
    def session(self) -> Session: ...
    def close(self) -> None: ...
    def start(self) -> None: pass
    def stop(self) -> None: self.close()
```

SqliteDB internals:
- Stores file path, creates parent dirs on connect
- `_connect()`: `sqlite3.connect()`, WAL mode, loads sqlite-vec (optional), loads FTS5
- Tracks sessions via `WeakSet` for cleanup
- `:memory:` uses `file::memory:?cache=shared` URI
- Thread safety: each session = one connection, no `check_same_thread=False`

4. **`session.py`** — Session + SqliteSession

```python
@dataclass
class StreamInfo:
    name: str
    payload_type: type
    count: int

class Session(ABC):
    def stream(self, name: str, payload_type: type, *,
               retention: str = "run") -> BlobStream: ...
    def embedding_stream(self, name: str, payload_type: type, *,
                         dim: int, retention: str = "run") -> EmbeddingStream: ...
    def text_stream(self, name: str, payload_type: type, *,
                    tokenizer: str = "unicode61",
                    retention: str = "run") -> TextStream: ...
    def list_streams(self) -> list[StreamInfo]: ...
    def execute(self, sql: str, params=()) -> list: ...
    def close(self) -> None: ...
    def __enter__ / __exit__
```

SqliteSession:
- Holds one `sqlite3.Connection`
- `stream()` / `embedding_stream()` / `text_stream()`: creates tables if needed (see schema below), caches StreamBase instances
- Registers stream metadata in a `_streams` registry table

### Phase 2: Stream + Query + ObservationSet

5. **`stream.py`** — Stream hierarchy (subclassed by data type)

```python
class StreamBase(ABC, Generic[T]):
    """Abstract base: meta + payload + spatial index. No text/vector indexes."""
    # Write
    def append(self, payload: T, **meta: Any) -> ObservationRef: ...
    def append_many(self, payloads, metas) -> list[ObservationRef]: ...

    # Read
    def query(self) -> Query[T]: ...
    def load(self, ref: ObservationRef) -> T: ...
    def load_many(self, refs: list[ObservationRef], *, batch_size=32) -> list[T]: ...
    def iter_meta(self, *, page_size=128) -> Iterator[list[ObservationRow]]: ...
    def count(self) -> int: ...

    # Introspection
    def meta(self, ref: ObservationRef) -> ObservationMeta: ...
    def info(self) -> dict[str, Any]: ...
    def stats(self) -> dict[str, Any]: ...

class BlobStream(StreamBase[T]):
    """Concrete stream for arbitrary LCM-serializable payloads. No special indexes."""

class EmbeddingStream(StreamBase[T]):
    """Stream with a vec0 vector index. append() also inserts into _vec table."""
    def __init__(self, ..., *, dim: int): ...
    def vector(self, ref: ObservationRef) -> list[float] | None: ...
    # search_embedding() on Query is valid only for EmbeddingStream

class TextStream(StreamBase[T]):
    """Stream with an FTS5 index. append() also inserts into _fts table."""
    def __init__(self, ..., *, tokenizer: str = "unicode61"): ...
    # search_text() on Query is valid only for TextStream
```

`append()` inserts a metadata row (SQLite auto-assigns `rowid`), serializes payload via `lcm_encode()` into `_payload` BLOB, and inserts an R*Tree entry if pose is provided. `EmbeddingStream.append()` also inserts into the `_vec` table; `TextStream.append()` also inserts into the `_fts` table. Returns `ObservationRef(stream, rowid)`. `load()` deserializes via `lcm_decode()` using the stream's `payload_type`.

6. **`query.py`** — Query (chainable, capability-aware)

```python
class Query(Generic[T]):
    # Hard filters
    def filter_time(self, t1: float, t2: float) -> Query[T]: ...
    def filter_before(self, t: float) -> Query[T]: ...
    def filter_after(self, t: float) -> Query[T]: ...
    def filter_near(self, pose: PoseLike, radius: float, *,
                    include_unlocalized: bool = False) -> Query[T]: ...
    def filter_tags(self, **tags: Any) -> Query[T]: ...
    def filter_refs(self, refs: list[ObservationRef]) -> Query[T]: ...
    def at(self, t: float, *, tolerance: float = 1.0) -> Query[T]: ...

    # Candidate generation
    def search_text(self, text: str, *, candidate_k: int | None = None) -> Query[T]: ...
    def search_embedding(self, vector: list[float], *, candidate_k: int) -> Query[T]: ...

    # Ranking + ordering + limit
    def rank(self, **weights: float) -> Query[T]: ...
    def order_by(self, field: str, *, desc: bool = False) -> Query[T]: ...
    def limit(self, k: int) -> Query[T]: ...

    # Terminals
    def fetch(self) -> list[ObservationRow]: ...
    def fetch_set(self) -> ObservationSet[T]: ...
    def count(self) -> int: ...
    def one(self) -> ObservationRow: ...
```

Query internals:
- Accumulates filter predicates, search ops, rank spec, ordering, limit
- `at(t, tolerance)` → sugar for `filter_time(t - tol, t + tol)` + `ORDER BY ABS(ts_start - t) LIMIT 1`
- `order_by(field, desc)` → appends `ORDER BY` clause; valid fields: `ts_start`, `ts_end`
- `fetch()`: generates SQL, executes, returns rows
- `fetch_set()`: creates an ObservationSet (predicate-backed or ref-table-backed)
- search_embedding → sqlite-vec `MATCH`, writes top-k to temp table → ref-table-backed
- search_text → FTS5 `MATCH`
- filter_near → R*Tree range query
- rank → computes composite score from available score columns

7. **`observation_set.py`** — ObservationSet (lazy, re-queryable)

```python
class ObservationSet(Generic[T]):
    # Re-query
    def query(self) -> Query[T]: ...

    # Read
    def load(self, ref: ObservationRef) -> T: ...
    def load_many(self, refs, *, batch_size=32) -> list[T]: ...
    def refs(self, *, limit=None) -> list[ObservationRef]: ...
    def rows(self, *, limit=None) -> list[ObservationRow]: ...
    def one(self) -> ObservationRow: ...
    def fetch_page(self, *, limit=128, offset=0) -> list[ObservationRow]: ...
    def count(self) -> int: ...
    def lineage(self) -> Lineage: ...

    # Cross-stream
    def project_to(self, stream: StreamBase) -> ObservationSet: ...

    # Cleanup (ref-table-backed only; no-op for predicate-backed)
    def close(self) -> None: ...
    def __enter__(self) -> Self: ...
    def __exit__(self, *exc) -> None: ...
    def __del__(self) -> None: ...  # best-effort fallback
```

Internal backing (spec §8):

```python
@dataclass
class PredicateBacking:
    """Lazy: expressible as SQL WHERE over source stream."""
    source_name: str
    query_repr: str  # serialized query filters for replay

@dataclass
class RefTableBacking:
    """Materialized: temp table of refs + scores."""
    table_name: str  # SQLite temp table
    source_streams: list[str]
    ordered: bool = False
```

- `.query()` on predicate-backed → adds more predicates
- `.query()` on ref-table-backed → filters within that temp table
- `project_to()` → joins backing refs via lineage parent_refs to target stream
- `close()` drops the temp table for ref-table-backed sets; no-op for predicate-backed
- Supports context manager (`with`) for deterministic cleanup; `__del__` as fallback
- SQLite connection close is the final safety net for any leaked temp tables

### Phase 3: Later (not in first PR)

- `derive()` with Transform protocol
- `CompositeBacking` (union/intersection/difference)
- `Correlator` / `s.correlate()`
- `retention` enforcement / cleanup
- Full introspection (stats, spatial_bounds)

## SQLite Schema (per stream)

### Metadata table: `{name}_meta`

```sql
CREATE TABLE {name}_meta (
    rowid INTEGER PRIMARY KEY,    -- auto-assigned, used by R*Tree/FTS/vec0
    ts REAL,
    pose_x REAL, pose_y REAL, pose_z REAL,
    pose_qx REAL, pose_qy REAL, pose_qz REAL, pose_qw REAL,
    tags TEXT,                     -- JSON (robot_id, frame_id, etc.)
    parent_stream TEXT,            -- lineage: source stream name
    parent_rowid INTEGER           -- lineage: source observation rowid
);
CREATE INDEX idx_{name}_meta_ts ON {name}_meta(ts);
```

### Payload table: `{name}_payload`

```sql
CREATE TABLE {name}_payload (
    rowid INTEGER PRIMARY KEY,    -- matches _meta.rowid
    data BLOB NOT NULL
);
```

Separate from meta so queries never touch payload BLOBs.

### R*Tree (spatial index): `{name}_rtree`

```sql
CREATE VIRTUAL TABLE {name}_rtree USING rtree(
    rowid,                        -- matches _meta rowid
    min_t, max_t,                 -- both set to ts (point, not range)
    min_x, max_x,                 -- both set to pose_x
    min_y, max_y,                 -- both set to pose_y
    min_z, max_z                  -- both set to pose_z
);
```

Only rows with pose get R*Tree entries (unlocalized != everywhere).
R*Tree `rowid` matches `_meta.rowid` directly — no mapping needed.
Time-only queries use the B-tree index on `_meta.ts` (faster than R*Tree for 1D).
Spatial or spatio-temporal queries use the R*Tree.

### FTS5 (text search): `{name}_fts`

```sql
CREATE VIRTUAL TABLE {name}_fts USING fts5(
    content,
    content={name}_meta,
    content_rowid=rowid
);
```

Created by `TextStream` subclass only.

### Vector index (embedding search): `{name}_vec`

```sql
CREATE VIRTUAL TABLE {name}_vec USING vec0(
    embedding float[{dim}]
);
```

`rowid` matches meta rowid. Created by `EmbeddingStream` subclass only.

## Key Design Decisions

### Pose handling

All pose parameters accept `PoseLike` (`Pose | PoseStamped | Point | PointStamped` from `dimos.msgs.geometry_msgs`). No custom pose type.

```python
from dimos.msgs.geometry_msgs import Pose, Point

images.append(frame, pose=robot_pose)       # Pose object
q.filter_near(Point(1, 2, 3), radius=5.0)   # Point object
```

Internally, `_extract_pose(p: PoseLike) -> tuple[float, ...]` pulls `(x, y, z, qx, qy, qz, qw)` for SQL columns. `ObservationRow.pose` returns a reconstructed `dimos.msgs.geometry_msgs.Pose`.

### Payload serialization

Only LCM message types are storable. `append()` calls `lcm_encode(payload)`, `load()` calls `lcm_decode(blob, payload_type)`. Non-LCM types are rejected at `append()` time with a `TypeError`.

### ObservationRef identity

`id` is a UUID4 string generated on `append()`. Never reuse timestamps as identity.

### Unlocalized observations

Rows without pose are NOT inserted into R*Tree. `filter_near()` excludes them by default. `include_unlocalized=True` bypasses R*Tree and scans meta table.

### Separate payload table

Payload BLOBs live in `{name}_payload`, separate from `{name}_meta`. This ensures queries (which only touch meta + indexes) never page in multi-MB image blobs.

## Existing Code to Reuse

- `dimos/memory/timeseries/sqlite.py:29` — `_validate_identifier()` regex pattern
- `dimos/msgs/geometry_msgs/Pose.py` — DimOS Pose type, `PoseLike` type alias
- `dimos/msgs/geometry_msgs/Point.py` — Point type
- `dimos/core/resource.py` — Resource ABC (start/stop/dispose)
- LCM `lcm_encode()` / `lcm_decode()` — payload serialization

## Verification

1. `uv run pytest dimos/memory2/test_memory2.py -v` — all tests pass
2. `uv run mypy dimos/memory2/` — type checks clean
3. `uv run pytest dimos/memory/timeseries/test_base.py -v` — existing tests untouched

### Test scenarios (map to spec §16 acceptance examples)

- Re-query narrowed data: `filter_time → fetch_set → query → filter_near → fetch_set`
- fetch_set does not load payloads: verify no BLOB reads until explicit `load()`
- Embedding search: `search_embedding → filter_time → limit → fetch_set` → ref-table backed
- Projection: `emb_matches.project_to(images)` → fetch page → load_many
- Paginated preview: `fetch_page(limit=24, offset=0)` returns ObservationRows
- Unlocalized exclusion: rows without pose excluded from `filter_near` by default
