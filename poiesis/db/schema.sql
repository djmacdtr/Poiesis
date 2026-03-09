-- Poiesis Database Schema

CREATE TABLE IF NOT EXISTS books (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    language TEXT NOT NULL DEFAULT 'zh-CN',
    style_preset TEXT NOT NULL DEFAULT 'literary_cn',
    style_prompt TEXT DEFAULT '',
    naming_policy TEXT NOT NULL DEFAULT 'localized_zh',
    is_default INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS characters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL DEFAULT 1,
    name TEXT NOT NULL,
    description TEXT,
    core_motivation TEXT,
    attributes JSON DEFAULT '{}',
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, name),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS world_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL DEFAULT 1,
    rule_key TEXT NOT NULL,
    description TEXT NOT NULL,
    is_immutable INTEGER DEFAULT 0,
    category TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, rule_key),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS timeline (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL DEFAULT 1,
    event_key TEXT NOT NULL UNIQUE,
    chapter_number INTEGER,
    description TEXT NOT NULL,
    characters_involved JSON DEFAULT '[]',
    timestamp_in_world TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS foreshadowing (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL DEFAULT 1,
    hint_key TEXT NOT NULL,
    description TEXT NOT NULL,
    introduced_in_chapter INTEGER,
    resolved_in_chapter INTEGER,
    status TEXT DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, hint_key),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS staging_changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL DEFAULT 1,
    change_type TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    proposed_data JSON NOT NULL,
    status TEXT DEFAULT 'pending',
    source_chapter INTEGER,
    rejection_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL DEFAULT 1,
    chapter_number INTEGER NOT NULL,
    title TEXT,
    content TEXT NOT NULL,
    plan JSON DEFAULT '{}',
    word_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, chapter_number),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS chapter_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL DEFAULT 1,
    chapter_number INTEGER NOT NULL,
    summary TEXT NOT NULL,
    key_events JSON DEFAULT '[]',
    characters_featured JSON DEFAULT '[]',
    new_facts_introduced JSON DEFAULT '[]',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, chapter_number),
    FOREIGN KEY (book_id, chapter_number) REFERENCES chapters(book_id, chapter_number)
);

-- 用户表：管理员与普通用户
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'user',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 系统配置表：存储加密后的 API Key 及其他全局配置
CREATE TABLE IF NOT EXISTS system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
