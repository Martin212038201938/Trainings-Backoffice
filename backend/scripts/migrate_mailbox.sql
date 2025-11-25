-- Migration: Add mailbox system tables and user email fields
-- Run this on the production database: y-b_trainings_backoffice

-- 1. Add new columns to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS platform_email VARCHAR(255) UNIQUE;
ALTER TABLE users ADD COLUMN IF NOT EXISTS first_name VARCHAR(100);
ALTER TABLE users ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);

-- 2. Create index on platform_email
CREATE INDEX IF NOT EXISTS ix_users_platform_email ON users(platform_email);

-- 3. Create mailbox_emails table
CREATE TABLE IF NOT EXISTS mailbox_emails (
    id SERIAL PRIMARY KEY,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    message_id VARCHAR(255) UNIQUE,
    in_reply_to VARCHAR(255),
    thread_id VARCHAR(255),
    from_address VARCHAR(255) NOT NULL,
    from_name VARCHAR(255),
    to_addresses TEXT NOT NULL,
    cc_addresses TEXT,
    bcc_addresses TEXT,
    subject VARCHAR(500),
    body_text TEXT,
    body_html TEXT,
    folder VARCHAR(50) DEFAULT 'inbox',
    is_read BOOLEAN DEFAULT FALSE,
    is_starred BOOLEAN DEFAULT FALSE,
    is_draft BOOLEAN DEFAULT FALSE,
    direction VARCHAR(20) DEFAULT 'inbound',
    sent_at TIMESTAMP,
    received_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. Create indexes for mailbox_emails
CREATE INDEX IF NOT EXISTS ix_mailbox_emails_owner_id ON mailbox_emails(owner_id);
CREATE INDEX IF NOT EXISTS ix_mailbox_emails_folder ON mailbox_emails(folder);
CREATE INDEX IF NOT EXISTS ix_mailbox_emails_thread_id ON mailbox_emails(thread_id);
CREATE INDEX IF NOT EXISTS ix_mailbox_emails_in_reply_to ON mailbox_emails(in_reply_to);

-- 5. Create email_attachments table
CREATE TABLE IF NOT EXISTS email_attachments (
    id SERIAL PRIMARY KEY,
    email_id INTEGER NOT NULL REFERENCES mailbox_emails(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    file_size INTEGER,
    file_path VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 6. Create email_notifications table
CREATE TABLE IF NOT EXISTS email_notifications (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    email_id INTEGER NOT NULL REFERENCES mailbox_emails(id) ON DELETE CASCADE,
    notification_sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMP,
    deep_link VARCHAR(500),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Done! Verify with:
-- SELECT column_name FROM information_schema.columns WHERE table_name = 'users';
