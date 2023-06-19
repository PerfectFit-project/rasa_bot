use db;

CREATE TABLE sessiondata(prolific_id TEXT, round_num TEXT, response_type TEXT,
response_value TEXT, time DATETIME);

CREATE TABLE activity_history(prolific_id TEXT, round_num TEXT, activity_index FLOAT, activity_response TEXT, 
time DATETIME);