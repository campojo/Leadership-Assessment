
CREATE TABLE IF NOT EXISTS assessment_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    question TEXT,
    answer TEXT
);

CREATE TABLE IF NOT EXISTS survey_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    question TEXT,
    answer TEXT
);

CREATE TABLE IF NOT EXISTS summary_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    style TEXT,
    score INTEGER,
    tendency TEXT,
    description TEXT
);
