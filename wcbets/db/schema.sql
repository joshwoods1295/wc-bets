CREATE TABLE IF NOT EXISTS players (
    player_id   TEXT PRIMARY KEY,   -- FBref player id
    name        TEXT NOT NULL,
    position    TEXT,
    club        TEXT,
    league      TEXT,
    age         INTEGER
);

CREATE TABLE IF NOT EXISTS player_stats (
    player_id       TEXT NOT NULL,
    season          TEXT NOT NULL,
    minutes         REAL DEFAULT 0,
    shots           REAL DEFAULT 0,
    shots_on_target REAL DEFAULT 0,
    goals           REAL DEFAULT 0,
    assists         REAL DEFAULT 0,
    fouls           REAL DEFAULT 0,
    fouls_drawn     REAL DEFAULT 0,
    yellows         REAL DEFAULT 0,
    reds            REAL DEFAULT 0,
    offsides        REAL DEFAULT 0,
    tackles         REAL DEFAULT 0,
    corners_taken   REAL DEFAULT 0,
    saves           REAL DEFAULT 0,
    PRIMARY KEY (player_id, season),
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE TABLE IF NOT EXISTS national_squads (
    player_id   TEXT NOT NULL,
    country     TEXT NOT NULL,
    PRIMARY KEY (player_id, country),
    FOREIGN KEY (player_id) REFERENCES players(player_id)
);

CREATE TABLE IF NOT EXISTS fixtures (
    match_id        TEXT PRIMARY KEY,
    date            TEXT,
    home_country    TEXT NOT NULL,
    away_country    TEXT NOT NULL,
    stage           TEXT
);

CREATE TABLE IF NOT EXISTS backlog (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    notes       TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open',  -- 'open' | 'done'
    created_at  TEXT NOT NULL
);
