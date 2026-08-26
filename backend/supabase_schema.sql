-- SmartNVO Supabase Schema
-- Run this in Supabase SQL Editor: https://supabase.com/dashboard/project/roihhmabpkjwzrgnssrh/sql/new

CREATE TABLE IF NOT EXISTS grades (
    id SERIAL PRIMARY KEY,
    grade_number INTEGER NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS topics (
    id SERIAL PRIMARY KEY,
    grade_id INTEGER NOT NULL REFERENCES grades(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS lessons (
    id SERIAL PRIMARY KEY,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    content TEXT
);

CREATE TABLE IF NOT EXISTS exercises (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    solution TEXT,
    difficulty TEXT CHECK (difficulty IN ('easy','medium','hard')) DEFAULT 'medium',
    exercise_type TEXT CHECK (exercise_type IN ('multiple_choice','numeric','algebra')) DEFAULT 'numeric'
);

CREATE TABLE IF NOT EXISTS generated_lesson_content (
    id SERIAL PRIMARY KEY,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    detail_level TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT uq_generated_lesson_content_lesson_level UNIQUE (lesson_id, detail_level)
);

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    -- Nullable: a guest user (is_guest = true) has neither. Postgres treats
    -- NULLs as distinct in a UNIQUE index, so any number of guest rows can
    -- coexist under these constraints.
    google_sub TEXT UNIQUE,
    email TEXT UNIQUE,
    name TEXT,
    picture TEXT,
    plan TEXT NOT NULL DEFAULT 'free',
    is_admin INTEGER NOT NULL DEFAULT 0,
    is_guest BOOLEAN NOT NULL DEFAULT FALSE,
    upgraded_at TIMESTAMP,
    ai_exercises_today INTEGER NOT NULL DEFAULT 0,
    ai_chat_today INTEGER NOT NULL DEFAULT 0,
    ai_theory_today INTEGER NOT NULL DEFAULT 0,
    nvo_exams_today INTEGER NOT NULL DEFAULT 0,
    image_scans_today INTEGER NOT NULL DEFAULT 0,
    usage_reset_date DATE,
    last_ai_chat_at TIMESTAMP,
    last_ai_theory_at TIMESTAMP,
    last_login_ip TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS exercise_attempts (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id) ON DELETE CASCADE,
    submitted_answer TEXT NOT NULL,
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    topic_id INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    completed_exercises INTEGER,
    total_exercises INTEGER,
    accuracy_percentage FLOAT,
    last_updated TIMESTAMP
);

CREATE TABLE IF NOT EXISTS lesson_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    lesson_id INTEGER NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    completed_exercises INTEGER,
    total_exercises INTEGER,
    completed BOOLEAN,
    last_updated TIMESTAMP
);

CREATE TABLE IF NOT EXISTS user_xp_profiles (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL UNIQUE,
    total_xp INTEGER NOT NULL DEFAULT 0,
    streak_days INTEGER NOT NULL DEFAULT 0,
    streak_multiplier FLOAT NOT NULL DEFAULT 1.0,
    today_xp INTEGER NOT NULL DEFAULT 0,
    last_activity_date DATE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS xp_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id INTEGER,
    xp_amount INTEGER NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_badges (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    badge_key TEXT NOT NULL,
    unlocked_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_daily_missions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    mission_date DATE NOT NULL,
    mission_key TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    topic_id INTEGER REFERENCES topics(id),
    lesson_id INTEGER NOT NULL REFERENCES lessons(id),
    required_difficulty TEXT NOT NULL,
    target_count INTEGER NOT NULL,
    completed_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    xp_base INTEGER NOT NULL,
    xp_bonus INTEGER NOT NULL DEFAULT 0,
    route TEXT NOT NULL,
    mission_order INTEGER NOT NULL,
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    xp_awarded BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_user_daily_mission UNIQUE (user_id, mission_date, mission_key)
);

CREATE TABLE IF NOT EXISTS user_mission_exercises (
    id SERIAL PRIMARY KEY,
    mission_id INTEGER NOT NULL REFERENCES user_daily_missions(id) ON DELETE CASCADE,
    exercise_id INTEGER NOT NULL REFERENCES exercises(id),
    is_correct BOOLEAN NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_mission_exercise UNIQUE (mission_id, exercise_id)
);

-- Disposable cache entries (explicit expires_at), not long-lived user data.
-- See app/services/nvo_exam_store.py for the read/write/purge path.
CREATE TABLE IF NOT EXISTS generated_exams (
    exam_id TEXT PRIMARY KEY,
    questions_json TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS nvo_generation_jobs (
    job_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    progress INTEGER NOT NULL DEFAULT 0,
    message TEXT NOT NULL DEFAULT '',
    exam_id TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS companion_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    pairing_code TEXT NOT NULL,
    exam_id TEXT,
    question_ids JSONB NOT NULL DEFAULT '[]',
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    pairing_expires_at TIMESTAMP NOT NULL,
    session_expires_at TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS companion_devices (
    id SERIAL PRIMARY KEY,
    device_id TEXT UNIQUE NOT NULL,
    session_fk INTEGER NOT NULL REFERENCES companion_sessions(id) ON DELETE CASCADE,
    device_label TEXT,
    paired_at TIMESTAMP NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_users_google_sub ON users(google_sub);
CREATE INDEX IF NOT EXISTS ix_users_email ON users(email);
-- Serves both the per-IP guest-flood cap and the stale-guest reaper.
CREATE INDEX IF NOT EXISTS ix_users_guest_ip_created ON users(is_guest, last_login_ip, created_at);
CREATE INDEX IF NOT EXISTS ix_exercises_lesson_id ON exercises(lesson_id);
CREATE INDEX IF NOT EXISTS ix_exercise_attempts_user_id ON exercise_attempts(user_id);
CREATE INDEX IF NOT EXISTS ix_user_progress_user_id ON user_progress(user_id);
CREATE INDEX IF NOT EXISTS ix_lesson_progress_user_id ON lesson_progress(user_id);
CREATE INDEX IF NOT EXISTS ix_xp_events_user_id ON xp_events(user_id);
CREATE INDEX IF NOT EXISTS ix_generated_lesson_content_lesson_id ON generated_lesson_content(lesson_id);
CREATE INDEX IF NOT EXISTS ix_generated_exams_expires_at ON generated_exams(expires_at);
CREATE INDEX IF NOT EXISTS ix_nvo_generation_jobs_expires_at ON nvo_generation_jobs(expires_at);
CREATE INDEX IF NOT EXISTS ix_companion_sessions_pairing_code ON companion_sessions(pairing_code);
CREATE INDEX IF NOT EXISTS ix_companion_devices_session_fk ON companion_devices(session_fk);

-- Enable Row Level Security on all application tables
ALTER TABLE grades ENABLE ROW LEVEL SECURITY;
ALTER TABLE topics ENABLE ROW LEVEL SECURITY;
ALTER TABLE lessons ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_lesson_content ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE exercise_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE lesson_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_xp_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE xp_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_badges ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_daily_missions ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_mission_exercises ENABLE ROW LEVEL SECURITY;
ALTER TABLE generated_exams ENABLE ROW LEVEL SECURITY;
ALTER TABLE nvo_generation_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE companion_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE companion_devices ENABLE ROW LEVEL SECURITY;

-- Locked-down default policies: only service_role can access via Supabase API
-- Non-destructive pattern: create policy only when missing.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'grades' AND policyname = 'grades_service_role_all') THEN
        CREATE POLICY grades_service_role_all ON grades FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'topics' AND policyname = 'topics_service_role_all') THEN
        CREATE POLICY topics_service_role_all ON topics FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'lessons' AND policyname = 'lessons_service_role_all') THEN
        CREATE POLICY lessons_service_role_all ON lessons FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'exercises' AND policyname = 'exercises_service_role_all') THEN
        CREATE POLICY exercises_service_role_all ON exercises FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'generated_lesson_content' AND policyname = 'generated_lesson_content_service_role_all') THEN
        CREATE POLICY generated_lesson_content_service_role_all ON generated_lesson_content FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'users' AND policyname = 'users_service_role_all') THEN
        CREATE POLICY users_service_role_all ON users FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'exercise_attempts' AND policyname = 'exercise_attempts_service_role_all') THEN
        CREATE POLICY exercise_attempts_service_role_all ON exercise_attempts FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'user_progress' AND policyname = 'user_progress_service_role_all') THEN
        CREATE POLICY user_progress_service_role_all ON user_progress FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'lesson_progress' AND policyname = 'lesson_progress_service_role_all') THEN
        CREATE POLICY lesson_progress_service_role_all ON lesson_progress FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'user_xp_profiles' AND policyname = 'user_xp_profiles_service_role_all') THEN
        CREATE POLICY user_xp_profiles_service_role_all ON user_xp_profiles FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'xp_events' AND policyname = 'xp_events_service_role_all') THEN
        CREATE POLICY xp_events_service_role_all ON xp_events FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'user_badges' AND policyname = 'user_badges_service_role_all') THEN
        CREATE POLICY user_badges_service_role_all ON user_badges FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'user_daily_missions' AND policyname = 'user_daily_missions_service_role_all') THEN
        CREATE POLICY user_daily_missions_service_role_all ON user_daily_missions FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'user_mission_exercises' AND policyname = 'user_mission_exercises_service_role_all') THEN
        CREATE POLICY user_mission_exercises_service_role_all ON user_mission_exercises FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'generated_exams' AND policyname = 'generated_exams_service_role_all') THEN
        CREATE POLICY generated_exams_service_role_all ON generated_exams FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'nvo_generation_jobs' AND policyname = 'nvo_generation_jobs_service_role_all') THEN
        CREATE POLICY nvo_generation_jobs_service_role_all ON nvo_generation_jobs FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'companion_sessions' AND policyname = 'companion_sessions_service_role_all') THEN
        CREATE POLICY companion_sessions_service_role_all ON companion_sessions FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public' AND tablename = 'companion_devices' AND policyname = 'companion_devices_service_role_all') THEN
        CREATE POLICY companion_devices_service_role_all ON companion_devices FOR ALL TO service_role USING (true) WITH CHECK (true);
    END IF;
END $$;
