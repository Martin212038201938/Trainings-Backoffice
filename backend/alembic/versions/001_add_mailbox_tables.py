"""Add mailbox email tables and user platform email fields

Revision ID: 001_mailbox
Revises:
Create Date: 2025-11-25

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '001_mailbox'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to users table
    op.add_column('users', sa.Column('platform_email', sa.String(255), nullable=True))
    op.add_column('users', sa.Column('first_name', sa.String(100), nullable=True))
    op.add_column('users', sa.Column('last_name', sa.String(100), nullable=True))

    # Create unique index on platform_email
    op.create_index('ix_users_platform_email', 'users', ['platform_email'], unique=True)

    # Create mailbox_emails table
    op.create_table(
        'mailbox_emails',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.String(255), nullable=True),
        sa.Column('in_reply_to', sa.String(255), nullable=True),
        sa.Column('thread_id', sa.String(255), nullable=True),
        sa.Column('from_address', sa.String(255), nullable=False),
        sa.Column('from_name', sa.String(255), nullable=True),
        sa.Column('to_addresses', sa.Text(), nullable=False),
        sa.Column('cc_addresses', sa.Text(), nullable=True),
        sa.Column('bcc_addresses', sa.Text(), nullable=True),
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('body_text', sa.Text(), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('folder', sa.String(50), nullable=True, default='inbox'),
        sa.Column('is_read', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_starred', sa.Boolean(), nullable=True, default=False),
        sa.Column('is_draft', sa.Boolean(), nullable=True, default=False),
        sa.Column('direction', sa.String(20), nullable=True, default='inbound'),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('received_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_mailbox_emails_id', 'mailbox_emails', ['id'], unique=False)
    op.create_index('ix_mailbox_emails_owner_id', 'mailbox_emails', ['owner_id'], unique=False)
    op.create_index('ix_mailbox_emails_message_id', 'mailbox_emails', ['message_id'], unique=True)
    op.create_index('ix_mailbox_emails_in_reply_to', 'mailbox_emails', ['in_reply_to'], unique=False)
    op.create_index('ix_mailbox_emails_thread_id', 'mailbox_emails', ['thread_id'], unique=False)
    op.create_index('ix_mailbox_emails_folder', 'mailbox_emails', ['folder'], unique=False)

    # Create email_attachments table
    op.create_table(
        'email_attachments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('content_type', sa.String(100), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['email_id'], ['mailbox_emails.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_attachments_id', 'email_attachments', ['id'], unique=False)

    # Create email_notifications table
    op.create_table(
        'email_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('email_id', sa.Integer(), nullable=False),
        sa.Column('notification_sent', sa.Boolean(), nullable=True, default=False),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('deep_link', sa.String(500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.ForeignKeyConstraint(['email_id'], ['mailbox_emails.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_email_notifications_id', 'email_notifications', ['id'], unique=False)


def downgrade() -> None:
    # Drop tables
    op.drop_table('email_notifications')
    op.drop_table('email_attachments')
    op.drop_table('mailbox_emails')

    # Remove columns from users table
    op.drop_index('ix_users_platform_email', table_name='users')
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
    op.drop_column('users', 'platform_email')
