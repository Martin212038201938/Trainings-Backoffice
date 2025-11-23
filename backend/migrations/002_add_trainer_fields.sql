-- Migration: Add new trainer fields and trainer applications
-- Date: 2024-11-23

-- Add new columns to trainers table
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(id) UNIQUE;
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS vat_number VARCHAR(100);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS photo_path VARCHAR(500);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS specializations JSON;
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS bio TEXT;

-- Create trainer_applications table
CREATE TABLE IF NOT EXISTS trainer_applications (
    id SERIAL PRIMARY KEY,
    training_id INTEGER NOT NULL REFERENCES trainings(id) ON DELETE CASCADE,
    trainer_id INTEGER NOT NULL REFERENCES trainers(id) ON DELETE CASCADE,
    status VARCHAR(50) DEFAULT 'pending',
    message TEXT,
    proposed_rate FLOAT,
    admin_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(training_id, trainer_id)
);

-- Note: Run this migration on AlwaysData with:
-- psql $DATABASE_URL -f migrations/002_add_trainer_fields.sql
