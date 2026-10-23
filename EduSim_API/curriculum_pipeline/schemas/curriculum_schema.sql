-- EduSim Curriculum Relational Schema DDL
-- Specification for Phase 2 Curriculum Storage
-- NOTE: Declarative DDL only; do NOT auto-execute without migration review.

CREATE TABLE IF NOT EXISTS books (
    book_code VARCHAR(64) PRIMARY KEY,
    board VARCHAR(32) NOT NULL,
    class_level INTEGER NOT NULL,
    subject VARCHAR(64) NOT NULL,
    medium VARCHAR(16) NOT NULL,
    book_title TEXT NOT NULL,
    adapter VARCHAR(64),
    source_sha256 VARCHAR(64),
    chapters_count INTEGER DEFAULT 0,
    pages_total INTEGER DEFAULT 0,
    coverage_status VARCHAR(32) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS curriculum_nodes (
    id VARCHAR(128) PRIMARY KEY,
    book_code VARCHAR(64) NOT NULL REFERENCES books(book_code) ON DELETE CASCADE,
    parent_id VARCHAR(128) REFERENCES curriculum_nodes(id) ON DELETE CASCADE,
    chapter_id VARCHAR(128),
    level VARCHAR(32) NOT NULL, -- chapter, topic, subtopic, activity, subheading
    wrapper VARCHAR(64),         -- Unit, Theme, Lesson wrapper if applicable
    official_number VARCHAR(64),
    official_title TEXT NOT NULL,
    normalized_title TEXT NOT NULL,
    page_start INTEGER NOT NULL,
    page_end INTEGER NOT NULL,
    extraction_type VARCHAR(32) DEFAULT 'explicit',
    evidence TEXT,
    confidence NUMERIC(4, 3) DEFAULT 1.000,
    rule_id VARCHAR(64),
    structure_unresolved BOOLEAN DEFAULT FALSE,
    annotations JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_curriculum_nodes_book ON curriculum_nodes(book_code);
CREATE INDEX IF NOT EXISTS idx_curriculum_nodes_parent ON curriculum_nodes(parent_id);
CREATE INDEX IF NOT EXISTS idx_curriculum_nodes_level ON curriculum_nodes(level);
CREATE INDEX IF NOT EXISTS idx_curriculum_nodes_pages ON curriculum_nodes(page_start, page_end);
