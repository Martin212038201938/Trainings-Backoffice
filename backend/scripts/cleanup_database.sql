-- Database Cleanup Script for Yellow-Boat Academy
-- This script removes all applications and users except the specified admin
--
-- USAGE:
-- 1. Connect to your PostgreSQL database
-- 2. Review the script first
-- 3. Run: psql -d y-b_trainings_backoffice -f cleanup_database.sql
--
-- WARNING: This will delete data! Make a backup first!

-- Start transaction
BEGIN;

-- Show current state
SELECT 'Current Database State:' as info;
SELECT 'Users:' as table_name, COUNT(*) as count FROM users;
SELECT 'Trainers:' as table_name, COUNT(*) as count FROM trainers;
SELECT 'TrainerRegistrations:' as table_name, COUNT(*) as count FROM trainer_registrations;
SELECT 'TrainerApplications:' as table_name, COUNT(*) as count FROM trainer_applications;
SELECT 'Messages:' as table_name, COUNT(*) as count FROM messages;

-- Show trainer registrations that will be deleted
SELECT 'Trainer Registrations to be deleted:' as info;
SELECT id, email, first_name, last_name, status FROM trainer_registrations;

-- Show users
SELECT 'Users (martin@yellow-boat.com will be kept):' as info;
SELECT id, email, username, role FROM users;

-- Get admin user ID
DO $$
DECLARE
    admin_id INTEGER;
    admin_trainer_id INTEGER;
BEGIN
    SELECT id INTO admin_id FROM users WHERE email = 'martin@yellow-boat.com';

    IF admin_id IS NULL THEN
        RAISE NOTICE 'WARNING: Admin user martin@yellow-boat.com not found!';
    ELSE
        RAISE NOTICE 'Found admin user ID: %', admin_id;

        -- Get admin's trainer profile if exists
        SELECT id INTO admin_trainer_id FROM trainers WHERE user_id = admin_id;
    END IF;

    -- 1. Delete all TrainerApplications (applications for specific trainings)
    DELETE FROM trainer_applications;
    RAISE NOTICE 'Deleted all TrainerApplications';

    -- 2. Delete all TrainerRegistrations (public trainer applications)
    DELETE FROM trainer_registrations;
    RAISE NOTICE 'Deleted all TrainerRegistrations';

    -- 3. Delete messages (keep admin's messages)
    IF admin_id IS NOT NULL THEN
        DELETE FROM messages WHERE sender_id != admin_id AND (recipient_id IS NULL OR recipient_id != admin_id);
    ELSE
        DELETE FROM messages;
    END IF;
    RAISE NOTICE 'Deleted messages';

    -- 4. Delete activity logs
    DELETE FROM activity_logs;
    RAISE NOTICE 'Deleted activity_logs';

    -- 5. Unassign trainers from trainings
    UPDATE trainings SET trainer_id = NULL;
    RAISE NOTICE 'Unassigned trainers from trainings';

    -- 6. Delete trainers (except admin's trainer profile)
    IF admin_trainer_id IS NOT NULL THEN
        DELETE FROM trainers WHERE id != admin_trainer_id;
    ELSE
        DELETE FROM trainers;
    END IF;
    RAISE NOTICE 'Deleted trainers';

    -- 7. Delete users except admin
    IF admin_id IS NOT NULL THEN
        DELETE FROM users WHERE id != admin_id;
    ELSE
        DELETE FROM users;
    END IF;
    RAISE NOTICE 'Deleted users (except admin)';

END $$;

-- Show final state
SELECT 'Final Database State:' as info;
SELECT 'Users:' as table_name, COUNT(*) as count FROM users;
SELECT 'Trainers:' as table_name, COUNT(*) as count FROM trainers;
SELECT 'TrainerRegistrations:' as table_name, COUNT(*) as count FROM trainer_registrations;
SELECT 'TrainerApplications:' as table_name, COUNT(*) as count FROM trainer_applications;
SELECT 'Messages:' as table_name, COUNT(*) as count FROM messages;

-- Verify remaining user
SELECT 'Remaining user:' as info;
SELECT id, email, username, role FROM users;

-- Commit (or ROLLBACK if you want to test first)
COMMIT;
-- ROLLBACK;  -- Uncomment this and comment COMMIT to test without changes
