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

-- ===== U3 section: organizer suggestions and review decisions =====
-- ADDED [PROMPT #25]: U3 table note_suggestions (U3 domain-entities.md section 2, IC-8).
-- One row per note (FA-1). s_* = the model's values; f_* = final values, set only when edited.

CREATE TABLE IF NOT EXISTS note_suggestions (
    id             INTEGER PRIMARY KEY,
    trip_id        INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    note_id        INTEGER NOT NULL UNIQUE REFERENCES notes(id) ON DELETE CASCADE,
    status         TEXT NOT NULL CHECK (status IN ('pending', 'accepted', 'edited', 'rejected')),
    s_category     TEXT NOT NULL,
    s_stop_id      INTEGER REFERENCES stops(id) ON DELETE CASCADE,
    s_dish         TEXT,
    s_rating       INTEGER CHECK (s_rating BETWEEN 1 AND 5),
    s_tip          TEXT,
    f_category     TEXT,
    f_stop_id      INTEGER REFERENCES stops(id) ON DELETE CASCADE,
    f_dish         TEXT,
    f_rating       INTEGER CHECK (f_rating BETWEEN 1 AND 5),
    f_tip          TEXT,
    prompt_version TEXT NOT NULL,
    model_name     TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    decided_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_suggestions_trip ON note_suggestions (trip_id);

-- ADDED [PROMPT #36]: daily journals and ordered paragraphs.
CREATE TABLE IF NOT EXISTS journals (
    trip_id        INTEGER NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    day            TEXT    NOT NULL,              -- local date YYYY-MM-DD
    tone           TEXT    NOT NULL CHECK (tone IN ('casual', 'concise', 'detailed')),
    prompt_version TEXT    NOT NULL,
    model_name     TEXT    NOT NULL,
    trace_json     TEXT    NOT NULL,
    generated_at   TEXT    NOT NULL,
    updated_at     TEXT    NOT NULL,
    PRIMARY KEY (trip_id, day)
);

CREATE TABLE IF NOT EXISTS journal_paragraphs (
    trip_id  INTEGER NOT NULL,
    day      TEXT    NOT NULL,
    slot     TEXT    NOT NULL,                   -- 'summary' or 'stop:<id>'
    position INTEGER NOT NULL,
    text     TEXT    NOT NULL,
    owner    TEXT    NOT NULL CHECK (owner IN ('generated', 'user')),
    PRIMARY KEY (trip_id, day, slot),
    FOREIGN KEY (trip_id, day) REFERENCES journals(trip_id, day) ON DELETE CASCADE
);
