-- Migration: Split address into separate fields and add new trainer fields
-- Date: 2024-11-24

-- Add new address columns to trainers table
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS street VARCHAR(255);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS house_number VARCHAR(20);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS bank_account VARCHAR(100);
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS additional_info TEXT;
ALTER TABLE trainers ADD COLUMN IF NOT EXISTS proposed_trainings TEXT;

-- Add new address columns to trainer_registrations table
ALTER TABLE trainer_registrations ADD COLUMN IF NOT EXISTS street VARCHAR(255);
ALTER TABLE trainer_registrations ADD COLUMN IF NOT EXISTS house_number VARCHAR(20);
ALTER TABLE trainer_registrations ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20);
ALTER TABLE trainer_registrations ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE trainer_registrations ADD COLUMN IF NOT EXISTS bank_account VARCHAR(100);
ALTER TABLE trainer_registrations ADD COLUMN IF NOT EXISTS additional_info TEXT;
ALTER TABLE trainer_registrations ADD COLUMN IF NOT EXISTS proposed_trainings TEXT;

-- Migrate existing data from address field to new fields (optional - manual review recommended)
-- Note: This is a simple migration that copies the full address to street field
-- Manual cleanup may be needed for proper field separation
UPDATE trainers SET street = address WHERE address IS NOT NULL AND street IS NULL;
UPDATE trainer_registrations SET street = address WHERE address IS NOT NULL AND street IS NULL;

-- Copy bio to additional_info
UPDATE trainers SET additional_info = bio WHERE bio IS NOT NULL AND additional_info IS NULL;
UPDATE trainer_registrations SET additional_info = bio WHERE bio IS NOT NULL AND additional_info IS NULL;

-- Note: Run this migration on AlwaysData with:
-- psql $DATABASE_URL -f migrations/003_split_address_fields.sql
