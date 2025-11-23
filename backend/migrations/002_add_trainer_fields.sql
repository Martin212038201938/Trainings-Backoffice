-- Migration: Add new trainer fields
-- Date: 2024-11-23

-- Add new columns to trainers table
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS address TEXT;
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS vat_number VARCHAR(100);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS photo_path VARCHAR(500);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS specializations JSON;
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS bio TEXT;

-- Note: Run this migration on AlwaysData with:
-- psql $DATABASE_URL -f migrations/002_add_trainer_fields.sql
