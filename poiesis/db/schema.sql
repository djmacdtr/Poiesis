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

CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL UNIQUE,
    book_id INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'running',
    config_snapshot JSON DEFAULT '{}',
    llm_snapshot JSON DEFAULT '{}',
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS run_chapters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    planner_output_json JSON DEFAULT '{}',
    retrieval_pack_json JSON DEFAULT '{}',
    draft_text TEXT DEFAULT '',
    final_content TEXT DEFAULT '',
    changeset_json JSON DEFAULT '{}',
    verifier_issues_json JSON DEFAULT '[]',
    editor_rewrites_json JSON DEFAULT '[]',
    merge_result_json JSON DEFAULT '{}',
    summary_json JSON DEFAULT '{}',
    metrics_json JSON DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, chapter_number),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS run_scenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    scene_plan_json JSON DEFAULT '{}',
    draft_json JSON DEFAULT '{}',
    final_text TEXT DEFAULT '',
    changeset_json JSON DEFAULT '{}',
    verifier_issues_json JSON DEFAULT '[]',
    review_required INTEGER NOT NULL DEFAULT 0,
    review_reason TEXT DEFAULT '',
    review_status TEXT DEFAULT 'auto_approved',
    metrics_json JSON DEFAULT '{}',
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(run_id, chapter_number, scene_number),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS story_state_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    snapshot_json JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, chapter_number),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS loops (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    loop_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    introduced_in_scene TEXT DEFAULT '',
    due_start_chapter INTEGER,
    due_end_chapter INTEGER,
    due_window TEXT DEFAULT '',
    priority INTEGER NOT NULL DEFAULT 1,
    related_characters JSON DEFAULT '[]',
    resolution_requirements JSON DEFAULT '[]',
    last_updated_scene TEXT DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, loop_id),
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS loop_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    loop_id TEXT NOT NULL,
    chapter_number INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (book_id) REFERENCES books(id)
);

CREATE TABLE IF NOT EXISTS scene_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    action TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL DEFAULT 'pending',
    reason TEXT DEFAULT '',
    patch_text TEXT DEFAULT '',
    resolved_scene_status TEXT DEFAULT '',
    result_summary TEXT DEFAULT '',
    closed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS scene_review_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    operator TEXT DEFAULT '',
    input_payload_json JSON DEFAULT '{}',
    result_payload_json JSON DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES scene_reviews(id)
);

CREATE TABLE IF NOT EXISTS scene_patches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    scene_number INTEGER NOT NULL,
    patch_text TEXT NOT NULL,
    before_text TEXT DEFAULT '',
    after_text TEXT DEFAULT '',
    verifier_issues_json JSON DEFAULT '[]',
    applied_successfully INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES runs(id)
);

CREATE TABLE IF NOT EXISTS chapter_outputs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    book_id INTEGER NOT NULL,
    run_id INTEGER NOT NULL,
    chapter_number INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    summary_json JSON DEFAULT '{}',
    scene_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(book_id, chapter_number),
    FOREIGN KEY (book_id) REFERENCES books(id),
    FOREIGN KEY (run_id) REFERENCES runs(id)
);
