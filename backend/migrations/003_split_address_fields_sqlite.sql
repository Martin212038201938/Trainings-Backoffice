-- Migration: Split address into separate fields (SQLite version)
-- Date: 2024-11-24

-- Add new columns to trainers table
ALTER TABLE trainers ADD COLUMN street VARCHAR(255);
ALTER TABLE trainers ADD COLUMN house_number VARCHAR(20);
ALTER TABLE trainers ADD COLUMN postal_code VARCHAR(20);
ALTER TABLE trainers ADD COLUMN city VARCHAR(100);
ALTER TABLE trainers ADD COLUMN bank_account VARCHAR(100);
ALTER TABLE trainers ADD COLUMN additional_info TEXT;

-- Add new columns to trainer_registrations table
ALTER TABLE trainer_registrations ADD COLUMN street VARCHAR(255);
ALTER TABLE trainer_registrations ADD COLUMN house_number VARCHAR(20);
ALTER TABLE trainer_registrations ADD COLUMN postal_code VARCHAR(20);
ALTER TABLE trainer_registrations ADD COLUMN city VARCHAR(100);
ALTER TABLE trainer_registrations ADD COLUMN bank_account VARCHAR(100);
ALTER TABLE trainer_registrations ADD COLUMN additional_info TEXT;
ALTER TABLE trainer_registrations ADD COLUMN proposed_trainings TEXT;

-- Migrate existing data
UPDATE trainers SET street = address WHERE address IS NOT NULL AND street IS NULL;
UPDATE trainer_registrations SET street = address WHERE address IS NOT NULL AND street IS NULL;
UPDATE trainers SET additional_info = bio WHERE bio IS NOT NULL AND additional_info IS NULL;
UPDATE trainer_registrations SET additional_info = bio WHERE bio IS NOT NULL AND additional_info IS NULL;
