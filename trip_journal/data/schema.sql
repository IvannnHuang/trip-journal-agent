-- ADDED [PROMPT #13]: U1 Foundation schema (domain-entities.md section 2). AI-assisted, Claude Opus 5.5.
-- Times: *_utc columns are ISO 8601 UTC text ("YYYY-MM-DDTHH:MM:SSZ"); local values are
-- naive ISO text in the trip's local time (UTC + utc_offset_minutes).

-- ===== U1 section: imported trip data, settings, place cache =====

CREATE TABLE IF NOT EXISTS trips (
    id            INTEGER PRIMARY KEY,
    source_id     TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    home_timezone TEXT,
    route_summary TEXT,
    imported_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS stops (
    id                 INTEGER PRIMARY KEY,
    trip_id            INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    source_id          TEXT NOT NULL,
    name               TEXT,
    start_utc          TEXT NOT NULL,
    end_utc            TEXT NOT NULL,
    utc_offset_minutes INTEGER NOT NULL,
    local_date         TEXT NOT NULL,
    lat                REAL NOT NULL,
    lon                REAL NOT NULL,
    UNIQUE (trip_id, source_id)
);
CREATE INDEX IF NOT EXISTS idx_stops_trip_day ON stops (trip_id, local_date, start_utc);

CREATE TABLE IF NOT EXISTS notes (
    id                 INTEGER PRIMARY KEY,
    trip_id            INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    stop_id            INTEGER REFERENCES stops(id) ON DELETE CASCADE,
    source_id          TEXT NOT NULL,
    text               TEXT NOT NULL,
    time_utc           TEXT NOT NULL,
    utc_offset_minutes INTEGER NOT NULL,
    local_date         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_notes_trip_day ON notes (trip_id, local_date);

CREATE TABLE IF NOT EXISTS photos (
    id                 INTEGER PRIMARY KEY,
    trip_id            INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    source_id          TEXT NOT NULL,
    time_utc           TEXT NOT NULL,
    utc_offset_minutes INTEGER NOT NULL,
    local_time         TEXT NOT NULL,
    lat                REAL,
    lon                REAL,
    file_name          TEXT
);
CREATE INDEX IF NOT EXISTS idx_photos_trip_time ON photos (trip_id, local_time);

-- Full-text index over notes.text (trigram: substrings of 3+ characters, any language).
CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
    text, content='notes', content_rowid='id', tokenize='trigram'
);
CREATE TRIGGER IF NOT EXISTS notes_ai AFTER INSERT ON notes BEGIN
    INSERT INTO notes_fts (rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS notes_ad AFTER DELETE ON notes BEGIN
    INSERT INTO notes_fts (notes_fts, rowid, text) VALUES ('delete', old.id, old.text);
END;
CREATE TRIGGER IF NOT EXISTS notes_au AFTER UPDATE ON notes BEGIN
    INSERT INTO notes_fts (notes_fts, rowid, text) VALUES ('delete', old.id, old.text);
    INSERT INTO notes_fts (rowid, text) VALUES (new.id, new.text);
END;

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS place_cache (
    lat_key    TEXT NOT NULL,
    lon_key    TEXT NOT NULL,
    name       TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    PRIMARY KEY (lat_key, lon_key)
);

-- ===== end of U1 section (U2/U3 tables are added below by later units) =====
