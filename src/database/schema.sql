CREATE TABLE topics (
    topic_id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL,
    category VARCHAR NOT NULL, provenance VARCHAR NOT NULL
);
CREATE TABLE sources (
    source_id VARCHAR PRIMARY KEY, name VARCHAR NOT NULL, unit VARCHAR NOT NULL
);
CREATE TABLE observations (
    observation_id BIGINT PRIMARY KEY,
    topic_id VARCHAR REFERENCES topics(topic_id),
    source_id VARCHAR REFERENCES sources(source_id),
    timestamp TIMESTAMP NOT NULL, attention DOUBLE CHECK(attention >= 0),
    is_synthetic BOOLEAN NOT NULL,
    UNIQUE(topic_id, source_id, timestamp)
);
CREATE TABLE engagement (
    observation_id BIGINT PRIMARY KEY REFERENCES observations(observation_id),
    engagements DOUBLE CHECK(engagements >= 0)
);
CREATE TABLE sentiment (
    observation_id BIGINT PRIMARY KEY REFERENCES observations(observation_id),
    sentiment DOUBLE CHECK(sentiment BETWEEN -1 AND 1)
);
