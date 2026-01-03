"""Flask application - WSGI compatible version of Trainings Backoffice."""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, g, render_template
from flask_cors import CORS
from sqlalchemy.orm import Session
from collections import defaultdict
import time

# Rate limiting storage
login_attempts = defaultdict(list)  # IP -> list of timestamps
MAX_LOGIN_ATTEMPTS = 5  # Max attempts per window
LOGIN_WINDOW_SECONDS = 300  # 5 minute window
LOCKOUT_SECONDS = 900  # 15 minute lockout after max attempts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Brand, Customer, Trainer, Training, TrainingCatalogEntry, TrainingTask, User, Location, Message, TrainerRegistration
from .models.core import ActivityLog
from .models.core import validate_status_transition, validate_training_type, validate_training_format, TRAINING_STATUSES
from .core.security import create_access_token, get_password_hash, verify_password
from .services.email import (
    send_welcome_email,
    send_trainer_welcome_email,
    send_trainer_application_received,
    send_trainer_application_accepted,
    send_trainer_application_rejected,
    send_training_status_update,
    send_new_application_admin_notification,
    send_trainer_assigned_notification,
    send_training_reminder,
    send_training_application_submitted,
    send_training_application_accepted as send_training_app_accepted,
    send_training_application_rejected as send_training_app_rejected,
    send_training_application_admin_notification
)

# Create tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created/verified successfully")
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")

# Create Flask app with absolute paths
APP_DIR = Path(__file__).parent.absolute()
TEMPLATE_DIR = APP_DIR / 'templates'
STATIC_DIR = APP_DIR / 'static'

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))
app.config['SECRET_KEY'] = settings.secret_key

# Configure CORS
CORS(app, origins=settings.cors_origins, supports_credentials=True)


# Database session management
@app.before_request
def before_request():
    g.db = SessionLocal()


@app.teardown_request
def teardown_request(exception=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()


def get_db():
    return g.db


# Security headers middleware
@app.after_request
def add_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Content Security Policy - restrict script sources to prevent XSS
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    return response


# Authentication decorator
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            from jose import jwt, JWTError
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            username = payload.get('sub')
            if username is None:
                return jsonify({'error': 'Invalid token'}), 401

            user = get_db().query(User).filter(User.username == username).first()
            if user is None:
                return jsonify({'error': 'User not found'}), 401
            if not user.is_active:
                return jsonify({'error': 'User is inactive'}), 403

            g.current_user = user
        except JWTError:
            return jsonify({'error': 'Invalid token'}), 401

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        if g.current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated


# ============== Basic Routes ==============

@app.route('/')
def root():
    """Serve the admin frontend."""
    template_path = TEMPLATE_DIR / 'index.html'
    if not template_path.exists():
        return jsonify({
            "error": "Template not found",
            "template_path": str(template_path),
            "template_dir": str(TEMPLATE_DIR),
            "exists": template_path.exists()
        }), 500
    return render_template('index.html')


@app.route('/login')
def login_page():
    """Serve the login landing page."""
    template_path = TEMPLATE_DIR / 'login.html'
    if not template_path.exists():
        return jsonify({
            "error": "Login template not found",
            "template_path": str(template_path),
            "template_dir": str(TEMPLATE_DIR),
            "exists": template_path.exists()
        }), 500
    return render_template('login.html')


@app.route('/api')
def api_root():
    """API status endpoint."""
    return jsonify({
        "app": settings.app_name,
        "status": "running",
        "version": "1.0.1",
        "docs": "/api-info",
        "health": "/health",
        "template_dir": str(TEMPLATE_DIR),
        "template_exists": (TEMPLATE_DIR / 'index.html').exists()
    })


@app.route('/ping')
def ping():
    return jsonify({
        "ping": "pong",
        "timestamp": datetime.utcnow().isoformat()
    })


@app.route('/health')
def health_check():
    db_health = {"status": "unknown", "connected": False}
    try:
        db = get_db()
        db.execute("SELECT 1")
        db_health = {"status": "healthy", "connected": True}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_health = {"status": "unhealthy", "connected": False, "error": str(e)}

    return jsonify({
        "status": "ok" if db_health.get("connected") else "degraded",
        "app": settings.app_name,
        "timestamp": datetime.utcnow().isoformat(),
        "environment": settings.environment,
        "database": db_health
    })


@app.route('/version')
def version_info():
    return jsonify({
        "version": "1.0.0",
        "app": settings.app_name,
        "environment": settings.environment
    })


@app.route('/api-info')
def api_info():
    """List all available endpoints."""
    return jsonify({
        "endpoints": {
            "auth": {
                "POST /auth/login": "Login with username and password",
                "POST /auth/register": "Register new user (admin only)",
                "GET /auth/me": "Get current user info",
                "PUT /auth/me": "Update current user",
                "GET /auth/users": "List all users (admin only)",
                "DELETE /auth/users/<id>": "Delete user (admin only)"
            },
            "brands": {
                "GET /brands": "List all brands",
                "POST /brands": "Create brand (admin only)",
                "GET /brands/<id>": "Get brand by ID",
                "PUT /brands/<id>": "Update brand (admin only)",
                "DELETE /brands/<id>": "Delete brand (admin only)"
            },
            "customers": {
                "GET /customers": "List all customers",
                "POST /customers": "Create customer",
                "GET /customers/<id>": "Get customer by ID",
                "PUT /customers/<id>": "Update customer",
                "DELETE /customers/<id>": "Delete customer"
            },
            "trainers": {
                "GET /trainers": "List all trainers",
                "POST /trainers": "Create trainer",
                "GET /trainers/<id>": "Get trainer by ID",
                "PUT /trainers/<id>": "Update trainer",
                "DELETE /trainers/<id>": "Delete trainer"
            },
            "trainings": {
                "GET /trainings": "List all trainings",
                "POST /trainings": "Create training",
                "GET /trainings/<id>": "Get training by ID",
                "PUT /trainings/<id>": "Update training",
                "DELETE /trainings/<id>": "Delete training"
            },
            "catalog": {
                "GET /catalog": "List catalog entries",
                "POST /catalog": "Create catalog entry",
                "GET /catalog/<id>": "Get catalog entry by ID",
                "PUT /catalog/<id>": "Update catalog entry",
                "DELETE /catalog/<id>": "Delete catalog entry"
            },
            "tasks": {
                "GET /tasks": "List all tasks",
                "POST /tasks": "Create task",
                "GET /tasks/<id>": "Get task by ID",
                "PUT /tasks/<id>": "Update task",
                "DELETE /tasks/<id>": "Delete task"
            }
        }
    })


# ============== Auth Routes ==============

@app.route('/auth/login', methods=['POST'])
def login():
    # Rate limiting check
    client_ip = request.remote_addr or 'unknown'
    current_time = time.time()

    # Clean up old attempts
    login_attempts[client_ip] = [
        t for t in login_attempts[client_ip]
        if current_time - t < LOCKOUT_SECONDS
    ]

    # Check if locked out
    recent_attempts = [t for t in login_attempts[client_ip] if current_time - t < LOGIN_WINDOW_SECONDS]
    if len(recent_attempts) >= MAX_LOGIN_ATTEMPTS:
        remaining_lockout = int(LOCKOUT_SECONDS - (current_time - login_attempts[client_ip][0]))
        logger.warning(f"Rate limit exceeded for IP {client_ip}")
        return jsonify({
            'error': f'Zu viele Anmeldeversuche. Bitte warten Sie {remaining_lockout // 60} Minuten.'
        }), 429

    if request.content_type == 'application/x-www-form-urlencoded':
        username = request.form.get('username')
        password = request.form.get('password')
    else:
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = get_db().query(User).filter(User.username == username).first()

    if not user or not verify_password(password, user.hashed_password):
        # Record failed attempt
        login_attempts[client_ip].append(current_time)
        attempts_left = MAX_LOGIN_ATTEMPTS - len([t for t in login_attempts[client_ip] if current_time - t < LOGIN_WINDOW_SECONDS])
        if attempts_left > 0:
            return jsonify({'error': f'Incorrect username or password. {attempts_left} Versuche übrig.'}), 401
        else:
            return jsonify({'error': 'Incorrect username or password. Account gesperrt.'}), 401

    if not user.is_active:
        return jsonify({'error': 'User account is inactive'}), 403

    # Clear failed attempts on successful login
    login_attempts[client_ip] = []

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )

    return jsonify({
        "access_token": access_token,
        "token_type": "bearer"
    })


@app.route('/auth/register', methods=['POST'])
@admin_required
def register():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    role = data.get('role', 'user')
    is_active = data.get('is_active', True)

    if not username or not email or not password:
        return jsonify({'error': 'Username, email and password required'}), 400

    db = get_db()

    if db.query(User).filter(User.username == username).first():
        return jsonify({'error': 'Username already registered'}), 400

    if db.query(User).filter(User.email == email).first():
        return jsonify({'error': 'Email already registered'}), 400

    hashed_password = get_password_hash(password)
    user = User(
        username=username,
        email=email,
        hashed_password=hashed_password,
        role=role,
        is_active=is_active
    )

    db.add(user)
    db.flush()  # Get the user ID before commit

    # Auto-link to trainer if exists with same email
    trainer = db.query(Trainer).filter(Trainer.email == email).first()
    trainer_info = None
    if trainer and trainer.user_id is None:
        trainer.user_id = user.id
        trainer_info = {"trainer_id": trainer.id, "trainer_name": trainer.name}
        logger.info(f"Auto-linked user {user.id} to trainer {trainer.id} by email {email}")

    db.commit()
    db.refresh(user)

    # Send welcome email
    send_welcome_email(user.email, user.username)

    response = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active
    }
    if trainer_info:
        response.update(trainer_info)

    return jsonify(response), 201


@app.route('/auth/me')
@token_required
def get_me():
    user = g.current_user
    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active
    })


@app.route('/auth/users')
@admin_required
def list_users():
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)

    db = get_db()
    users = db.query(User).offset(skip).limit(limit).all()

    # Get trainer info for each user
    result = []
    for u in users:
        trainer = db.query(Trainer).filter(Trainer.user_id == u.id).first()
        result.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "trainer_id": trainer.id if trainer else None,
            "trainer_name": trainer.name if trainer else None
        })

    return jsonify(result)


@app.route('/auth/users/<int:user_id>', methods=['DELETE'])
@admin_required
def delete_user(user_id):
    if user_id == g.current_user.id:
        return jsonify({'error': 'Cannot delete your own account'}), 400

    db = get_db()
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    db.delete(user)
    db.commit()

    return '', 204


@app.route('/auth/logout', methods=['POST'])
@token_required
def logout():
    return jsonify({"message": "Successfully logged out"})


# ============== Brands Routes ==============

@app.route('/brands')
@token_required
def list_brands():
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)

    db = get_db()
    total = db.query(Brand).count()
    brands = db.query(Brand).offset(skip).limit(limit).all()

    return jsonify({
        "items": [{
            "id": b.id,
            "name": b.name,
            "description": b.description
        } for b in brands],
        "total": total,
        "skip": skip,
        "limit": limit
    })


@app.route('/brands', methods=['POST'])
@admin_required
def create_brand():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    try:
        # Generate slug from name
        import re
        name = data.get('name', '')
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

        brand = Brand(
            name=name,
            slug=slug,
            description=data.get('description')
        )

        db = get_db()
        db.add(brand)
        db.commit()
        db.refresh(brand)

        return jsonify({
            "id": brand.id,
            "name": brand.name,
            "description": brand.description
        }), 201
    except Exception as e:
        logger.error(f"Error creating brand: {e}")
        return jsonify({'error': f'Fehler beim Erstellen: {str(e)}'}), 500


@app.route('/brands/<int:brand_id>')
@token_required
def get_brand(brand_id):
    brand = get_db().query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        return jsonify({'error': 'Brand not found'}), 404

    return jsonify({
        "id": brand.id,
        "name": brand.name,
        "description": brand.description
    })


@app.route('/brands/<int:brand_id>', methods=['PUT'])
@admin_required
def update_brand(brand_id):
    db = get_db()
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        return jsonify({'error': 'Brand not found'}), 404

    data = request.get_json()
    if data.get('name'):
        brand.name = data['name']
    if data.get('description') is not None:
        brand.description = data['description']

    db.commit()
    db.refresh(brand)

    return jsonify({
        "id": brand.id,
        "name": brand.name,
        "description": brand.description
    })


@app.route('/brands/<int:brand_id>', methods=['DELETE'])
@admin_required
def delete_brand(brand_id):
    db = get_db()
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        return jsonify({'error': 'Brand not found'}), 404

    db.delete(brand)
    db.commit()

    return jsonify({"status": "deleted"})


# ============== Customers Routes ==============

def customer_to_dict(c):
    """Convert customer model to dictionary."""
    return {
        "id": c.id,
        "name": c.contact_name or c.company_name,
        "company": c.company_name,
        "first_name": c.first_name,
        "last_name": c.last_name,
        "salutation": c.salutation,
        "contact_name": c.contact_name,
        "email": c.contact_email,
        "phone": c.contact_phone,
        "vat_number": c.vat_number,
        "street": c.street,
        "street_number": c.street_number,
        "postal_code": c.postal_code,
        "city": c.city,
        "billing_address": c.billing_address,
        "conditions": c.conditions,
        "comment": c.comment,
        "notes": c.notes,
        "status": c.status,
        "trainings": [{"id": t.id, "title": t.title} for t in c.trainings] if c.trainings else []
    }


@app.route('/customers')
@token_required
def list_customers():
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)

    db = get_db()
    total = db.query(Customer).count()
    customers = db.query(Customer).offset(skip).limit(limit).all()

    return jsonify({
        "items": [customer_to_dict(c) for c in customers],
        "total": total,
        "skip": skip,
        "limit": limit
    })


@app.route('/customers', methods=['POST'])
@token_required
def create_customer():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    try:
        customer = Customer(
            company_name=data.get('company') or data.get('company_name', ''),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            salutation=data.get('salutation'),
            contact_email=data.get('email') or data.get('contact_email'),
            contact_phone=data.get('phone') or data.get('contact_phone'),
            vat_number=data.get('vat_number'),
            street=data.get('street'),
            street_number=data.get('street_number'),
            postal_code=data.get('postal_code'),
            city=data.get('city'),
            conditions=data.get('conditions'),
            comment=data.get('comment'),
            notes=data.get('notes')
        )

        db = get_db()
        db.add(customer)
        db.commit()
        db.refresh(customer)

        return jsonify(customer_to_dict(customer)), 201
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        return jsonify({'error': f'Fehler beim Erstellen: {str(e)}'}), 500


@app.route('/customers/<int:customer_id>')
@token_required
def get_customer(customer_id):
    customer = get_db().query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    return jsonify(customer_to_dict(customer))


@app.route('/customers/<int:customer_id>', methods=['PUT'])
@token_required
def update_customer(customer_id):
    db = get_db()
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    data = request.get_json()

    # Map frontend field names to model field names
    field_mapping = {
        'name': 'contact_name',
        'company': 'company_name',
        'email': 'contact_email',
        'phone': 'contact_phone',
        'notes': 'notes'
    }

    for frontend_key, model_key in field_mapping.items():
        if frontend_key in data:
            setattr(customer, model_key, data[frontend_key])

    db.commit()
    db.refresh(customer)

    return jsonify(customer_to_dict(customer))


@app.route('/customers/<int:customer_id>', methods=['DELETE'])
@token_required
def delete_customer(customer_id):
    db = get_db()
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    db.delete(customer)
    db.commit()

    return jsonify({"status": "deleted"})


# ============== Trainers Routes ==============

def trainer_to_dict(t):
    """Convert trainer model to dictionary."""
    return {
        "id": t.id,
        "user_id": getattr(t, 'user_id', None),
        "first_name": t.first_name,
        "last_name": t.last_name,
        "name": t.name,
        "email": t.email,
        "phone": t.phone,
        "street": getattr(t, 'street', None),
        "house_number": getattr(t, 'house_number', None),
        "postal_code": getattr(t, 'postal_code', None),
        "city": getattr(t, 'city', None),
        "vat_number": getattr(t, 'vat_number', None),
        "bank_account": getattr(t, 'bank_account', None),
        "linkedin_url": getattr(t, 'linkedin_url', None),
        "website": getattr(t, 'website', None),
        "photo_path": getattr(t, 'photo_path', None),
        "specializations": getattr(t, 'specializations', None) or {"selected": [], "custom": []},
        "additional_info": getattr(t, 'additional_info', None),
        "notes": getattr(t, 'notes', None),
        "region": getattr(t, 'region', None),
        "proposed_trainings": json.loads(t.proposed_trainings) if getattr(t, 'proposed_trainings', None) else []
    }


@app.route('/trainers')
@token_required
def list_trainers():
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)

    db = get_db()
    total = db.query(Trainer).count()
    trainers = db.query(Trainer).offset(skip).limit(limit).all()

    return jsonify({
        "items": [trainer_to_dict(t) for t in trainers],
        "total": total,
        "skip": skip,
        "limit": limit
    })


@app.route('/trainers', methods=['POST'])
@token_required
def create_trainer():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    try:
        # Handle name split if only 'name' is provided
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        if not first_name and not last_name and data.get('name'):
            parts = data.get('name', '').split(' ', 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ''

        trainer = Trainer(
            first_name=first_name,
            last_name=last_name,
            email=data.get('email', ''),
            phone=data.get('phone'),
            address=data.get('address'),
            vat_number=data.get('vat_number'),
            linkedin_url=data.get('linkedin_url'),
            website=data.get('website'),
            specializations=data.get('specializations'),
            bio=data.get('bio'),
            notes=data.get('notes'),
            region=data.get('region'),
            default_day_rate=data.get('default_day_rate')
        )

        db = get_db()

        # Auto-link to user if exists with same email
        if trainer.email:
            user = db.query(User).filter(User.email == trainer.email).first()
            if user and not db.query(Trainer).filter(Trainer.user_id == user.id).first():
                trainer.user_id = user.id
                logger.info(f"Auto-linked trainer to user {user.id} by email {trainer.email}")

        db.add(trainer)
        db.commit()
        db.refresh(trainer)

        return jsonify(trainer_to_dict(trainer)), 201
    except Exception as e:
        logger.error(f"Error creating trainer: {e}")
        return jsonify({'error': f'Fehler beim Erstellen: {str(e)}'}), 500


@app.route('/trainers/<int:trainer_id>')
@token_required
def get_trainer(trainer_id):
    trainer = get_db().query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404

    return jsonify(trainer_to_dict(trainer))


@app.route('/trainers/<int:trainer_id>', methods=['PUT'])
@token_required
def update_trainer(trainer_id):
    db = get_db()
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404

    data = request.get_json()

    # Handle name split if only 'name' is provided
    if 'name' in data and 'first_name' not in data:
        parts = data.get('name', '').split(' ', 1)
        data['first_name'] = parts[0]
        data['last_name'] = parts[1] if len(parts) > 1 else ''

    for key in ['first_name', 'last_name', 'email', 'phone', 'address', 'vat_number',
                'linkedin_url', 'specializations', 'bio', 'notes', 'region', 'default_day_rate']:
        if key in data:
            setattr(trainer, key, data[key])

    db.commit()
    db.refresh(trainer)

    return jsonify(trainer_to_dict(trainer))


@app.route('/trainers/<int:trainer_id>/photo', methods=['POST'])
@token_required
def upload_trainer_photo(trainer_id):
    db = get_db()
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404

    if 'photo' not in request.files:
        return jsonify({'error': 'No photo file provided'}), 400

    photo = request.files['photo']
    if photo.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    import uuid
    from werkzeug.utils import secure_filename

    # Validate file type
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    filename = secure_filename(photo.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if ext not in ALLOWED_EXTENSIONS:
        return jsonify({
            'error': f'Ungültiger Dateityp: {ext}. Erlaubt: {", ".join(ALLOWED_EXTENSIONS)}'
        }), 400

    # Validate file size (max 5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    photo.seek(0, 2)  # Seek to end
    file_size = photo.tell()
    photo.seek(0)  # Seek back to start

    if file_size > MAX_FILE_SIZE:
        return jsonify({
            'error': f'Datei zu groß: {file_size / 1024 / 1024:.1f}MB. Maximum: 5MB'
        }), 400

    # Generate new filename
    new_filename = f"trainer_{trainer_id}_{uuid.uuid4().hex[:8]}.{ext}"

    upload_dir = APP_DIR / 'static' / 'uploads' / 'trainers'
    upload_dir.mkdir(parents=True, exist_ok=True)

    photo_path = upload_dir / new_filename

    # Try to optimize image if PIL is available
    try:
        from PIL import Image
        import io

        # Open and process image
        img = Image.open(photo)

        # Convert RGBA to RGB if necessary (for JPEG)
        if img.mode == 'RGBA' and ext in ['jpg', 'jpeg']:
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background

        # Resize if too large (max 800x800)
        max_size = (800, 800)
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save with optimization
        if ext in ['jpg', 'jpeg']:
            img.save(str(photo_path), 'JPEG', quality=85, optimize=True)
        elif ext == 'png':
            img.save(str(photo_path), 'PNG', optimize=True)
        else:
            img.save(str(photo_path))

        logger.info(f"Optimized and saved trainer photo: {new_filename}")
    except ImportError:
        # PIL not available, save directly
        photo.save(str(photo_path))
        logger.info(f"Saved trainer photo without optimization (PIL not available): {new_filename}")
    except Exception as e:
        # If image processing fails, save directly
        photo.seek(0)
        photo.save(str(photo_path))
        logger.warning(f"Image optimization failed, saved directly: {e}")

    trainer.photo_path = f"/static/uploads/trainers/{new_filename}"
    db.commit()

    return jsonify({"photo_path": trainer.photo_path})


@app.route('/trainers/<int:trainer_id>', methods=['DELETE'])
@token_required
def delete_trainer(trainer_id):
    db = get_db()
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404

    db.delete(trainer)
    db.commit()

    return jsonify({"status": "deleted"})


# ============== Trainings Routes ==============

def training_to_dict(t):
    """Convert training model to dictionary."""
    start_date = getattr(t, 'start_date', None)
    end_date = getattr(t, 'end_date', None)
    return {
        "id": t.id,
        "title": t.title,
        "brand_id": getattr(t, 'brand_id', None),
        "customer_id": getattr(t, 'customer_id', None),
        "trainer_id": getattr(t, 'trainer_id', None),
        "status": getattr(t, 'status', None),
        "start_date": start_date.isoformat() if start_date else None,
        "end_date": end_date.isoformat() if end_date else None,
        "date": start_date.isoformat() if start_date else None,  # Legacy field
        "duration_days": getattr(t, 'duration_days', None),
        "duration_hours": getattr(t, 'duration_hours', None),
        "duration_type": getattr(t, 'duration_type', 'days'),
        "zeitraum": getattr(t, 'zeitraum', None),
        "training_type": getattr(t, 'training_type', None),
        "training_format": getattr(t, 'training_format', None),
        "location": getattr(t, 'location', None),
        "location_details": getattr(t, 'location_details', None),
        "location_cost": getattr(t, 'location_cost', None),
        "location_by_customer": getattr(t, 'location_by_customer', False),
        "catering_cost": getattr(t, 'catering_cost', None),
        "catering_by_customer": getattr(t, 'catering_by_customer', False),
        "provision": getattr(t, 'provision', None),
        "other_costs": getattr(t, 'other_costs', None),
        "online_link": getattr(t, 'online_link', None),
        "max_participants": getattr(t, 'max_participants', None),
        "language": getattr(t, 'language', None),
        "tagessatz": getattr(t, 'tagessatz', None),
        "price_external": getattr(t, 'price_external', None),
        "price_internal": getattr(t, 'price_internal', None),
        "margin": getattr(t, 'margin', None),
        "internal_notes": getattr(t, 'internal_notes', None),
        "logistics_notes": getattr(t, 'logistics_notes', None),
        "communication_notes": getattr(t, 'communication_notes', None),
        "finance_notes": getattr(t, 'finance_notes', None),
        "location_booking": getattr(t, 'location_booking', None),
        "catering_booking": getattr(t, 'catering_booking', None),
        "price_per_participant": getattr(t, 'price_per_participant', None)
    }


@app.route('/trainings')
@token_required
def list_trainings():
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)

    db = get_db()
    total = db.query(Training).count()
    trainings = db.query(Training).offset(skip).limit(limit).all()

    return jsonify({
        "items": [training_to_dict(t) for t in trainings],
        "total": total,
        "skip": skip,
        "limit": limit
    })


@app.route('/trainings', methods=['POST'])
@token_required
def create_training():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    from datetime import datetime as dt

    # Validate status
    status = data.get('status', 'lead')
    if status not in TRAINING_STATUSES:
        return jsonify({'error': f"Ungültiger Status: {status}. Erlaubt: {', '.join(TRAINING_STATUSES)}"}), 400

    # Validate training_type
    if data.get('training_type'):
        is_valid, error_msg = validate_training_type(data['training_type'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400

    # Validate training_format
    if data.get('training_format'):
        is_valid, error_msg = validate_training_format(data['training_format'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400

    try:
        training = Training(
            title=data.get('title'),
            brand_id=data.get('brand_id'),
            customer_id=data.get('customer_id'),
            trainer_id=data.get('trainer_id'),
            status=data.get('status', 'lead'),
            start_date=dt.fromisoformat(data['start_date']).date() if data.get('start_date') else None,
            end_date=dt.fromisoformat(data['end_date']).date() if data.get('end_date') else None,
            duration_days=data.get('duration_days', 1),
            training_type=data.get('training_type'),
            training_format=data.get('training_format'),
            location=data.get('location'),
            max_participants=data.get('max_participants'),
            tagessatz=data.get('tagessatz'),
            price_external=data.get('price_external'),
            price_internal=data.get('price_internal'),
            internal_notes=data.get('internal_notes')
        )

        # Set additional fields if model supports them
        for field in ['duration_hours', 'duration_type', 'zeitraum', 'location_cost',
                      'location_by_customer', 'catering_cost', 'catering_by_customer',
                      'provision', 'other_costs', 'location_booking', 'catering_booking',
                      'price_per_participant', 'language', 'online_link', 'location_details',
                      'logistics_notes', 'communication_notes', 'finance_notes']:
            if field in data and hasattr(training, field):
                setattr(training, field, data[field])

        db = get_db()
        db.add(training)
        db.commit()
        db.refresh(training)

        return jsonify(training_to_dict(training)), 201
    except Exception as e:
        logger.error(f"Error creating training: {e}")
        return jsonify({'error': f'Fehler beim Erstellen: {str(e)}'}), 500


@app.route('/trainings/<int:training_id>')
@token_required
def get_training(training_id):
    training = get_db().query(Training).filter(Training.id == training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    return jsonify(training_to_dict(training))


@app.route('/trainings/<int:training_id>', methods=['PUT'])
@token_required
def update_training(training_id):
    db = get_db()
    training = db.query(Training).filter(Training.id == training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    data = request.get_json()
    from datetime import datetime as dt

    # Validate status transition if status is being changed
    if 'status' in data and data['status'] != training.status:
        is_valid, error_msg = validate_status_transition(training.status, data['status'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400

    # Validate training_type if provided
    if 'training_type' in data:
        is_valid, error_msg = validate_training_type(data['training_type'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400

    # Validate training_format if provided
    if 'training_format' in data:
        is_valid, error_msg = validate_training_format(data['training_format'])
        if not is_valid:
            return jsonify({'error': error_msg}), 400

    # Track status change for activity log
    old_status = training.status
    new_status = data.get('status', old_status)

    # Update simple fields
    for key in ['title', 'location', 'status', 'customer_id', 'trainer_id', 'brand_id',
                'duration_days', 'duration_hours', 'duration_type', 'zeitraum',
                'training_type', 'training_format', 'max_participants',
                'tagessatz', 'location_cost', 'location_by_customer',
                'catering_cost', 'catering_by_customer', 'provision', 'other_costs',
                'price_external', 'price_internal', 'internal_notes',
                'logistics_notes', 'communication_notes', 'finance_notes',
                'location_booking', 'catering_booking', 'price_per_participant',
                'language', 'online_link', 'location_details']:
        if key in data and hasattr(training, key):
            setattr(training, key, data[key])

    # Update date fields
    if 'start_date' in data:
        training.start_date = dt.fromisoformat(data['start_date']).date() if data['start_date'] else None
    if 'end_date' in data:
        training.end_date = dt.fromisoformat(data['end_date']).date() if data['end_date'] else None

    # Track trainer assignment change
    old_trainer_id = training.trainer_id
    new_trainer_id = data.get('trainer_id', old_trainer_id)

    # Create activity log for status change
    if old_status != new_status:
        log = ActivityLog(
            training_id=training_id,
            message=f"Status geändert: {old_status} → {new_status}",
            created_by=g.current_user.username
        )
        db.add(log)

    db.commit()
    db.refresh(training)

    # Send email notifications for status change
    if old_status != new_status:
        # Notify trainer if assigned
        if training.trainer and training.trainer.email:
            trainer = training.trainer
            send_training_status_update(
                trainer.email,
                f"{trainer.first_name} {trainer.last_name}",
                training.title or f"Training {training_id}",
                old_status,
                new_status,
                training_id
            )

    # Send notification if trainer was newly assigned
    if new_trainer_id and new_trainer_id != old_trainer_id:
        new_trainer = db.query(Trainer).filter(Trainer.id == new_trainer_id).first()
        if new_trainer and new_trainer.email:
            customer_name = training.customer.company_name if training.customer else "Unbekannt"
            training_date = training.start_date.strftime("%d.%m.%Y") if training.start_date else "Noch nicht festgelegt"
            send_trainer_assigned_notification(
                new_trainer.email,
                f"{new_trainer.first_name} {new_trainer.last_name}",
                training.title or f"Training {training_id}",
                training_date,
                customer_name
            )

    return jsonify(training_to_dict(training))


@app.route('/trainings/<int:training_id>/activity-logs')
@token_required
def get_training_activity_logs(training_id):
    """Get activity logs for a training."""
    db = get_db()

    training = db.query(Training).filter(Training.id == training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    logs = db.query(ActivityLog).filter(
        ActivityLog.training_id == training_id
    ).order_by(ActivityLog.created_at.desc()).all()

    return jsonify([{
        "id": log.id,
        "message": log.message,
        "created_by": log.created_by,
        "created_at": log.created_at.isoformat() if log.created_at else None
    } for log in logs])


@app.route('/trainings/<int:training_id>/activity-logs', methods=['POST'])
@token_required
def add_training_activity_log(training_id):
    """Add an activity log entry to a training."""
    db = get_db()

    training = db.query(Training).filter(Training.id == training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({'error': 'Message required'}), 400

    log = ActivityLog(
        training_id=training_id,
        message=data['message'],
        created_by=g.current_user.username
    )

    db.add(log)
    db.commit()
    db.refresh(log)

    return jsonify({
        "id": log.id,
        "message": log.message,
        "created_by": log.created_by,
        "created_at": log.created_at.isoformat() if log.created_at else None
    }), 201


@app.route('/trainings/<int:training_id>', methods=['DELETE'])
@token_required
def delete_training(training_id):
    db = get_db()
    training = db.query(Training).filter(Training.id == training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    db.delete(training)
    db.commit()

    return jsonify({"status": "deleted"})


# ============== Locations Routes ==============

def location_to_dict(loc):
    """Convert location model to dictionary."""
    return {
        "id": loc.id,
        "name": loc.name,
        # Address
        "city": loc.city,
        "street": loc.street,
        "street_number": loc.street_number,
        "postal_code": loc.postal_code,
        # Billing address
        "billing_street": loc.billing_street,
        "billing_street_number": loc.billing_street_number,
        "billing_postal_code": loc.billing_postal_code,
        "billing_city": loc.billing_city,
        "billing_vat": loc.billing_vat,
        # Contact
        "contact_first_name": loc.contact_first_name,
        "contact_last_name": loc.contact_last_name,
        "contact_email": loc.contact_email,
        "contact_phone": loc.contact_phone,
        "contact_notes": loc.contact_notes,
        # Details
        "description": loc.description,
        "max_participants": loc.max_participants,
        "features": loc.features,
        "website_link": loc.website_link,
        "catering_available": loc.catering_available,
        "rental_cost": loc.rental_cost,
        "rental_cost_type": loc.rental_cost_type,
        "parking": loc.parking,
        "directions": loc.directions,
        "participant_info": loc.participant_info
    }


@app.route('/locations')
@token_required
def list_locations():
    skip = request.args.get('skip', 0, type=int)
    limit = request.args.get('limit', 100, type=int)

    db = get_db()
    total = db.query(Location).count()
    locations = db.query(Location).offset(skip).limit(limit).all()

    return jsonify({
        "items": [location_to_dict(loc) for loc in locations],
        "total": total,
        "skip": skip,
        "limit": limit
    })


@app.route('/locations', methods=['POST'])
@token_required
def create_location():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    try:
        location = Location(
            name=data.get('name', ''),
            city=data.get('city'),
            street=data.get('street'),
            street_number=data.get('street_number'),
            postal_code=data.get('postal_code'),
            billing_street=data.get('billing_street'),
            billing_street_number=data.get('billing_street_number'),
            billing_postal_code=data.get('billing_postal_code'),
            billing_city=data.get('billing_city'),
            billing_vat=data.get('billing_vat'),
            contact_first_name=data.get('contact_first_name'),
            contact_last_name=data.get('contact_last_name'),
            contact_email=data.get('contact_email'),
            contact_phone=data.get('contact_phone'),
            contact_notes=data.get('contact_notes'),
            description=data.get('description'),
            max_participants=data.get('max_participants'),
            features=data.get('features'),
            website_link=data.get('website_link'),
            catering_available=data.get('catering_available', 'no'),
            rental_cost=data.get('rental_cost'),
            rental_cost_type=data.get('rental_cost_type', 'day'),
            parking=data.get('parking'),
            directions=data.get('directions'),
            participant_info=data.get('participant_info')
        )

        db = get_db()
        db.add(location)
        db.commit()
        db.refresh(location)

        return jsonify(location_to_dict(location)), 201
    except Exception as e:
        logger.error(f"Error creating location: {e}")
        return jsonify({'error': f'Fehler beim Erstellen: {str(e)}'}), 500


@app.route('/locations/<int:location_id>')
@token_required
def get_location(location_id):
    location = get_db().query(Location).filter(Location.id == location_id).first()
    if not location:
        return jsonify({'error': 'Location not found'}), 404

    return jsonify(location_to_dict(location))


@app.route('/locations/<int:location_id>', methods=['PUT'])
@token_required
def update_location(location_id):
    db = get_db()
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        return jsonify({'error': 'Location not found'}), 404

    data = request.get_json()

    for key in ['name', 'city', 'street', 'street_number', 'postal_code',
                'billing_street', 'billing_street_number', 'billing_postal_code',
                'billing_city', 'billing_vat', 'contact_first_name', 'contact_last_name',
                'contact_email', 'contact_phone', 'contact_notes', 'description',
                'max_participants', 'features', 'website_link', 'catering_available',
                'rental_cost', 'rental_cost_type', 'parking', 'directions', 'participant_info']:
        if key in data:
            setattr(location, key, data[key])

    db.commit()
    db.refresh(location)

    return jsonify(location_to_dict(location))


@app.route('/locations/<int:location_id>', methods=['DELETE'])
@token_required
def delete_location(location_id):
    db = get_db()
    location = db.query(Location).filter(Location.id == location_id).first()
    if not location:
        return jsonify({'error': 'Location not found'}), 404

    db.delete(location)
    db.commit()

    return jsonify({"status": "deleted"})


# ============== Trainer Portal Routes ==============

@app.route('/trainer/dashboard')
@token_required
def trainer_dashboard():
    """Get trainer dashboard data - only for trainers."""
    if g.current_user.role != 'trainer':
        return jsonify({'error': 'Trainer access required'}), 403

    db = get_db()

    # Find trainer linked to this user
    trainer = db.query(Trainer).filter(Trainer.user_id == g.current_user.id).first()

    # If not found by user_id, try to find by email and auto-link
    if not trainer:
        trainer = db.query(Trainer).filter(Trainer.email == g.current_user.email).first()
        if trainer:
            # Auto-link trainer to user
            trainer.user_id = g.current_user.id
            db.commit()
            logger.info(f"Auto-linked trainer {trainer.id} to user {g.current_user.id}")

    if not trainer:
        return jsonify({'error': 'No trainer profile linked to this account. Please contact admin.'}), 404

    # Get trainer's trainings
    my_trainings = db.query(Training).filter(Training.trainer_id == trainer.id).all()

    # Calculate statistics
    total_trainings = len(my_trainings)
    completed_trainings = len([t for t in my_trainings if t.status in ['delivered', 'invoiced']])
    total_earnings = sum(t.tagessatz or 0 for t in my_trainings if t.status == 'invoiced')

    # Get my applications
    from .models import TrainerApplication
    my_applications = db.query(TrainerApplication).filter(
        TrainerApplication.trainer_id == trainer.id
    ).all()

    return jsonify({
        "trainer": trainer_to_dict(trainer),
        "stats": {
            "total_trainings": total_trainings,
            "completed_trainings": completed_trainings,
            "total_earnings": total_earnings,
            "pending_applications": len([a for a in my_applications if a.status == 'pending']),
            "accepted_applications": len([a for a in my_applications if a.status == 'accepted'])
        },
        "recent_trainings": [{
            "id": t.id,
            "title": t.title,
            "date": t.start_date.isoformat() if t.start_date else None,
            "status": t.status,
            "earnings": t.tagessatz
        } for t in my_trainings[:5]],
        "applications": [{
            "id": a.id,
            "training_id": a.training_id,
            "status": a.status,
            "proposed_rate": a.proposed_rate,
            "message": a.message,
            "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in my_applications]
    })


@app.route('/trainer/profile', methods=['PUT'])
@token_required
def update_trainer_profile():
    """Update trainer's own profile."""
    if g.current_user.role != 'trainer':
        return jsonify({'error': 'Trainer access required'}), 403

    db = get_db()

    # Find trainer linked to this user
    trainer = db.query(Trainer).filter(Trainer.user_id == g.current_user.id).first()
    if not trainer:
        trainer = db.query(Trainer).filter(Trainer.email == g.current_user.email).first()
        if trainer:
            trainer.user_id = g.current_user.id
            db.commit()

    if not trainer:
        return jsonify({'error': 'No trainer profile linked to this account'}), 404

    data = request.get_json()

    # Update allowed fields (excluding customer feedback which trainers shouldn't edit)
    for key in ['first_name', 'last_name', 'email', 'phone', 'street', 'house_number',
                'postal_code', 'city', 'vat_number', 'bank_account',
                'linkedin_url', 'website', 'region', 'additional_info', 'notes',
                'specializations']:
        if key in data:
            setattr(trainer, key, data[key])

    # Handle proposed_trainings separately (needs JSON serialization)
    if 'proposed_trainings' in data:
        trainer.proposed_trainings = json.dumps(data['proposed_trainings']) if data['proposed_trainings'] else None

    db.commit()
    db.refresh(trainer)

    return jsonify(trainer_to_dict(trainer))


@app.route('/trainer/open-trainings')
@token_required
def get_open_trainings():
    """Get trainings that trainers can apply for."""
    if g.current_user.role != 'trainer':
        return jsonify({'error': 'Trainer access required'}), 403

    db = get_db()

    # Find trainer linked to this user (with auto-link by email)
    trainer = db.query(Trainer).filter(Trainer.user_id == g.current_user.id).first()
    if not trainer:
        trainer = db.query(Trainer).filter(Trainer.email == g.current_user.email).first()
        if trainer:
            trainer.user_id = g.current_user.id
            db.commit()

    if not trainer:
        return jsonify({'error': 'No trainer profile linked'}), 404

    # Get trainings without assigned trainer (open for applications)
    from .models import TrainerApplication
    open_trainings = db.query(Training).filter(
        Training.trainer_id == None,
        Training.status.in_(['lead', 'trainer_outreach', 'planning'])
    ).all()

    # Check which ones the trainer already applied for
    my_application_training_ids = [a.training_id for a in db.query(TrainerApplication).filter(
        TrainerApplication.trainer_id == trainer.id
    ).all()]

    result = []
    for t in open_trainings:
        # Calculate hourly rate (assuming 8 hours per day)
        tagessatz = t.tagessatz
        stundensatz = round(tagessatz / 8, 2) if tagessatz else None

        result.append({
            "id": t.id,
            "title": t.title,
            "description": t.location_details,
            "start_date": t.start_date.isoformat() if t.start_date else None,
            "end_date": t.end_date.isoformat() if t.end_date else None,
            "duration_days": t.duration_days,
            "location": t.location,
            "status": t.status,
            "tagessatz": tagessatz,
            "stundensatz": stundensatz,
            "already_applied": t.id in my_application_training_ids
        })

    return jsonify(result)


@app.route('/trainer/my-trainings')
@token_required
def get_my_trainings():
    """Get trainer's assigned trainings with full details (excluding costs)."""
    if g.current_user.role != 'trainer':
        return jsonify({'error': 'Trainer access required'}), 403

    db = get_db()

    trainer = db.query(Trainer).filter(Trainer.user_id == g.current_user.id).first()
    if not trainer:
        trainer = db.query(Trainer).filter(Trainer.email == g.current_user.email).first()
        if trainer:
            trainer.user_id = g.current_user.id
            db.commit()

    if not trainer:
        return jsonify({'error': 'No trainer profile linked'}), 404

    # Get trainer's assigned trainings
    my_trainings = db.query(Training).filter(Training.trainer_id == trainer.id).all()

    result = []
    for t in my_trainings:
        # Get location details if linked
        location_info = None
        if hasattr(t, 'location_id') and t.location_id:
            loc = db.query(Location).filter(Location.id == t.location_id).first()
            if loc:
                # Include all location info EXCEPT costs
                location_info = {
                    "id": loc.id,
                    "name": loc.name,
                    "city": loc.city,
                    "street": loc.street,
                    "street_number": loc.street_number,
                    "postal_code": loc.postal_code,
                    "description": loc.description,
                    "max_participants": loc.max_participants,
                    "features": loc.features,
                    "website_link": loc.website_link,
                    "catering_available": loc.catering_available,
                    "parking": loc.parking,
                    "directions": loc.directions,
                    "participant_info": loc.participant_info
                    # Note: rental_cost excluded
                }

        training_data = {
            "id": t.id,
            "title": t.title,
            "status": getattr(t, 'status', None),
            "start_date": t.start_date.isoformat() if t.start_date else None,
            "end_date": t.end_date.isoformat() if t.end_date else None,
            "duration_days": getattr(t, 'duration_days', None),
            "duration_hours": getattr(t, 'duration_hours', None),
            "duration_type": getattr(t, 'duration_type', 'days'),
            "zeitraum": getattr(t, 'zeitraum', None),
            "training_type": getattr(t, 'training_type', None),
            "training_format": getattr(t, 'training_format', None),
            "location": getattr(t, 'location', None),
            "location_details": getattr(t, 'location_details', None),
            "online_link": getattr(t, 'online_link', None),
            "max_participants": getattr(t, 'max_participants', None),
            "language": getattr(t, 'language', None),
            # Comment fields (excluding finance)
            "internal_notes": getattr(t, 'internal_notes', None),
            "logistics_notes": getattr(t, 'logistics_notes', None),
            "communication_notes": getattr(t, 'communication_notes', None),
            # Location booking info
            "location_booking": getattr(t, 'location_booking', None),
            "catering_booking": getattr(t, 'catering_booking', None),
            # Location details from linked location
            "location_info": location_info
            # Note: costs (tagessatz, price_external, price_internal, etc.) excluded
        }
        result.append(training_data)

    return jsonify(result)


@app.route('/trainer/apply/<int:training_id>', methods=['POST'])
@token_required
def apply_for_training(training_id):
    """Apply for a training as a trainer."""
    if g.current_user.role != 'trainer':
        return jsonify({'error': 'Trainer access required'}), 403

    db = get_db()

    trainer = db.query(Trainer).filter(Trainer.user_id == g.current_user.id).first()
    if not trainer:
        return jsonify({'error': 'No trainer profile linked'}), 404

    training = db.query(Training).filter(Training.id == training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    # Check if already applied
    from .models import TrainerApplication
    existing = db.query(TrainerApplication).filter(
        TrainerApplication.training_id == training_id,
        TrainerApplication.trainer_id == trainer.id
    ).first()

    if existing:
        return jsonify({'error': 'Already applied for this training'}), 400

    data = request.get_json() or {}

    # Use the training's tagessatz - trainer does not propose their own rate
    application = TrainerApplication(
        training_id=training_id,
        trainer_id=trainer.id,
        message=data.get('message'),
        proposed_rate=training.tagessatz,  # Always use training's rate
        status='pending'
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    # Send confirmation email to trainer
    trainer_name = f"{trainer.first_name} {trainer.last_name}" if trainer.first_name else trainer.name
    training_title = training.title or f"Training {training_id}"
    if trainer.email:
        send_training_application_submitted(
            trainer.email,
            trainer_name,
            training_title,
            training_id
        )

    # Send notification to admins
    admin_users = db.query(User).filter(User.role.in_(['admin', 'backoffice_user'])).all()
    for admin in admin_users:
        if admin.email:
            send_training_application_admin_notification(
                admin.email,
                trainer_name,
                training_title,
                training_id,
                application.id
            )

    # Calculate hourly rate (assuming 8 hours per day)
    tagessatz = training.tagessatz
    stundensatz = round(tagessatz / 8, 2) if tagessatz else None

    return jsonify({
        "id": application.id,
        "status": "pending",
        "message": "Application submitted successfully",
        "tagessatz": tagessatz,
        "stundensatz": stundensatz
    }), 201


@app.route('/trainer/applications/<int:application_id>', methods=['DELETE'])
@token_required
def withdraw_application(application_id):
    """Withdraw a training application."""
    if g.current_user.role != 'trainer':
        return jsonify({'error': 'Trainer access required'}), 403

    db = get_db()

    trainer = db.query(Trainer).filter(Trainer.user_id == g.current_user.id).first()
    if not trainer:
        return jsonify({'error': 'No trainer profile linked'}), 404

    from .models import TrainerApplication
    application = db.query(TrainerApplication).filter(
        TrainerApplication.id == application_id,
        TrainerApplication.trainer_id == trainer.id
    ).first()

    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if application.status != 'pending':
        return jsonify({'error': 'Can only withdraw pending applications'}), 400

    db.delete(application)
    db.commit()

    return jsonify({"status": "withdrawn"})


# ============== Debug/Config Check Routes ==============

@app.route('/admin/debug/config')
@token_required
def debug_config():
    """Debug endpoint to check configuration (admin only)."""
    if g.current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from .config import settings
    import os

    # Check .env file location
    env_file_path = str(settings.model_config.get('env_file', 'not set'))

    return jsonify({
        "env_file_path": env_file_path,
        "env_file_exists": os.path.exists(env_file_path) if env_file_path != 'not set' else False,
        "alwaysdata": {
            "api_key_set": bool(settings.alwaysdata_api_key),
            "api_key_length": len(settings.alwaysdata_api_key) if settings.alwaysdata_api_key else 0,
            "account": settings.alwaysdata_account,
            "domain_id": settings.alwaysdata_domain_id,
            "domain_id_configured": settings.alwaysdata_domain_id != 0
        },
        "smtp": {
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "username": settings.smtp_username,
            "password_set": bool(settings.smtp_password),
            "password_length": len(settings.smtp_password) if settings.smtp_password else 0,
            "use_tls": settings.smtp_use_tls,
            "from_email": settings.smtp_from_email,
            "email_enabled": settings.email_enabled
        },
        "platform": {
            "email_domain": settings.platform_email_domain
        }
    })


@app.route('/admin/debug/test-alwaysdata')
@token_required
def test_alwaysdata_connection():
    """Test AlwaysData API connection (admin only)."""
    if g.current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from .config import settings

    if not settings.alwaysdata_api_key:
        return jsonify({"success": False, "error": "API key not configured"})

    if not settings.alwaysdata_domain_id:
        return jsonify({"success": False, "error": "Domain ID not configured (is 0)"})

    try:
        import requests
        from .services.alwaysdata import get_api_auth, ALWAYSDATA_API_URL

        # Test: List existing mailboxes
        response = requests.get(
            f"{ALWAYSDATA_API_URL}/mailbox/",
            auth=get_api_auth(),
            timeout=30
        )

        return jsonify({
            "success": response.status_code == 200,
            "status_code": response.status_code,
            "mailbox_count": len(response.json()) if response.status_code == 200 else 0,
            "response_preview": str(response.text)[:500] if response.status_code != 200 else "OK"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route('/admin/debug/test-smtp')
@token_required
def test_smtp_connection():
    """Test SMTP connection (admin only)."""
    if g.current_user.role != 'admin':
        return jsonify({'error': 'Admin access required'}), 403

    from .config import settings
    import smtplib

    if not settings.smtp_host:
        return jsonify({"success": False, "error": "SMTP host not configured"})

    if not settings.smtp_username or not settings.smtp_password:
        return jsonify({"success": False, "error": "SMTP credentials not configured"})

    try:
        # Try to connect and authenticate
        if settings.smtp_use_tls:
            server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            server.starttls()
        else:
            server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30)

        server.login(settings.smtp_username, settings.smtp_password)
        server.quit()

        return jsonify({
            "success": True,
            "message": "SMTP connection and authentication successful",
            "host": settings.smtp_host,
            "port": settings.smtp_port,
            "username": settings.smtp_username
        })
    except smtplib.SMTPAuthenticationError as e:
        return jsonify({
            "success": False,
            "error": f"Authentication failed: {e}",
            "host": settings.smtp_host,
            "username": settings.smtp_username,
            "hint": "Check that SMTP_USERNAME is the full email address and SMTP_PASSWORD is correct"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ============== Admin Training Applications Routes ==============

@app.route('/admin/training-applications')
@token_required
def list_training_applications():
    """List all training applications (admin/backoffice only)."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({'error': 'Admin access required'}), 403

    db = get_db()
    from .models import TrainerApplication

    applications = db.query(TrainerApplication).order_by(
        TrainerApplication.created_at.desc()
    ).all()

    result = []
    for app in applications:
        trainer = db.query(Trainer).filter(Trainer.id == app.trainer_id).first()
        training = db.query(Training).filter(Training.id == app.training_id).first()
        result.append({
            "id": app.id,
            "trainer_id": app.trainer_id,
            "trainer_name": trainer.name if trainer else "Unbekannt",
            "trainer_email": trainer.email if trainer else None,
            "training_id": app.training_id,
            "training_title": training.title if training else "Unbekannt",
            "proposed_rate": app.proposed_rate,
            "message": app.message,
            "status": app.status,
            "created_at": app.created_at.isoformat() if app.created_at else None
        })

    return jsonify(result)


@app.route('/admin/training-applications/<int:app_id>/accept', methods=['POST'])
@token_required
def accept_training_application(app_id):
    """Accept a training application and assign trainer to training."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({'error': 'Admin access required'}), 403

    db = get_db()
    from .models import TrainerApplication

    application = db.query(TrainerApplication).filter(TrainerApplication.id == app_id).first()
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if application.status != 'pending':
        return jsonify({'error': 'Application already processed'}), 400

    # Get the training and assign the trainer
    training = db.query(Training).filter(Training.id == application.training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    # Check if training already has a trainer
    if training.trainer_id:
        return jsonify({'error': 'Training already has a trainer assigned'}), 400

    # Assign trainer to training
    training.trainer_id = application.trainer_id

    # Update application status
    application.status = 'accepted'

    # Reject all other pending applications for this training
    other_apps = db.query(TrainerApplication).filter(
        TrainerApplication.training_id == application.training_id,
        TrainerApplication.id != app_id,
        TrainerApplication.status == 'pending'
    ).all()
    rejected_trainer_ids = [other_app.trainer_id for other_app in other_apps]
    for other_app in other_apps:
        other_app.status = 'rejected'

    db.commit()

    # Get trainer info for emails
    trainer = db.query(Trainer).filter(Trainer.id == application.trainer_id).first()
    training_title = training.title or f"Training {training.id}"
    training_date = training.start_date.strftime("%d.%m.%Y") if training.start_date else None
    customer_name = training.customer.company_name if training.customer else None

    # Send acceptance email to the accepted trainer
    if trainer and trainer.email:
        trainer_name = f"{trainer.first_name} {trainer.last_name}" if trainer.first_name else trainer.name
        send_training_app_accepted(
            trainer.email,
            trainer_name,
            training_title,
            training_date,
            customer_name
        )

    # Send rejection emails to other applicants
    for rejected_trainer_id in rejected_trainer_ids:
        rejected_trainer = db.query(Trainer).filter(Trainer.id == rejected_trainer_id).first()
        if rejected_trainer and rejected_trainer.email:
            rejected_name = f"{rejected_trainer.first_name} {rejected_trainer.last_name}" if rejected_trainer.first_name else rejected_trainer.name
            send_training_app_rejected(
                rejected_trainer.email,
                rejected_name,
                training_title,
                "Das Training wurde einem anderen Trainer zugewiesen."
            )

    return jsonify({
        "status": "success",
        "message": f"Trainer {trainer.name if trainer else 'Unbekannt'} wurde dem Training zugewiesen",
        "trainer_id": application.trainer_id,
        "training_id": application.training_id
    })


@app.route('/admin/training-applications/<int:app_id>/reject', methods=['POST'])
@token_required
def reject_training_application(app_id):
    """Reject a training application."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({'error': 'Admin access required'}), 403

    db = get_db()
    from .models import TrainerApplication

    application = db.query(TrainerApplication).filter(TrainerApplication.id == app_id).first()
    if not application:
        return jsonify({'error': 'Application not found'}), 404

    if application.status != 'pending':
        return jsonify({'error': 'Application already processed'}), 400

    # Get trainer and training info before updating
    trainer = db.query(Trainer).filter(Trainer.id == application.trainer_id).first()
    training = db.query(Training).filter(Training.id == application.training_id).first()

    # Get optional rejection reason from request body
    data = request.get_json() or {}
    reason = data.get('reason')

    application.status = 'rejected'
    db.commit()

    # Send rejection email to trainer
    if trainer and trainer.email and training:
        trainer_name = f"{trainer.first_name} {trainer.last_name}" if trainer.first_name else trainer.name
        training_title = training.title or f"Training {training.id}"
        send_training_app_rejected(
            trainer.email,
            trainer_name,
            training_title,
            reason
        )

    return jsonify({"status": "success", "message": "Bewerbung abgelehnt"})


# ============== Messages Routes ==============

def message_to_dict(m):
    """Convert message model to dictionary."""
    return {
        "id": m.id,
        "sender_id": m.sender_id,
        "sender_name": m.sender.username if m.sender else None,
        "recipient_id": m.recipient_id,
        "recipient_name": m.recipient.username if m.recipient else "Alle Admins",
        "parent_id": m.parent_id,
        "message_type": m.message_type,
        "subject": m.subject,
        "content": m.content,
        "page_url": m.page_url,
        "error_details": m.error_details,
        "status": m.status,
        "is_read": m.is_read,
        "read_at": m.read_at.isoformat() if m.read_at else None,
        "created_at": m.created_at.isoformat() if m.created_at else None
    }


@app.route('/messages')
@token_required
def list_messages():
    """Get messages for current user."""
    db = get_db()
    user = g.current_user

    # Get messages where user is recipient or sender
    # For admins, also include messages sent to all admins (recipient_id = NULL)
    if user.role == 'admin':
        messages = db.query(Message).filter(
            (Message.recipient_id == user.id) |
            (Message.sender_id == user.id) |
            ((Message.recipient_id == None) & (Message.message_type == 'error_report'))
        ).order_by(Message.created_at.desc()).all()
    else:
        messages = db.query(Message).filter(
            (Message.recipient_id == user.id) |
            (Message.sender_id == user.id)
        ).order_by(Message.created_at.desc()).all()

    return jsonify([message_to_dict(m) for m in messages])


@app.route('/messages/unread-count')
@token_required
def get_unread_count():
    """Get count of unread messages for current user."""
    db = get_db()
    user = g.current_user

    if user.role == 'admin':
        count = db.query(Message).filter(
            ((Message.recipient_id == user.id) |
             ((Message.recipient_id == None) & (Message.message_type == 'error_report'))) &
            (Message.is_read == False) &
            (Message.sender_id != user.id)
        ).count()
    else:
        count = db.query(Message).filter(
            (Message.recipient_id == user.id) &
            (Message.is_read == False)
        ).count()

    return jsonify({"unread_count": count})


@app.route('/messages', methods=['POST'])
@token_required
def create_message():
    """Create a new message or error report."""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    db = get_db()

    message = Message(
        sender_id=g.current_user.id,
        recipient_id=data.get('recipient_id'),  # NULL for error reports to all admins
        parent_id=data.get('parent_id'),
        message_type=data.get('message_type', 'message'),
        subject=data.get('subject'),
        content=data.get('content'),
        page_url=data.get('page_url'),
        error_details=data.get('error_details'),
        status='open' if data.get('message_type') == 'error_report' else None
    )

    db.add(message)
    db.commit()
    db.refresh(message)

    return jsonify(message_to_dict(message)), 201


@app.route('/messages/<int:message_id>')
@token_required
def get_message(message_id):
    """Get a specific message and mark as read."""
    db = get_db()
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        return jsonify({'error': 'Message not found'}), 404

    # Check access
    user = g.current_user
    has_access = (
        message.sender_id == user.id or
        message.recipient_id == user.id or
        (user.role == 'admin' and message.recipient_id is None)
    )

    if not has_access:
        return jsonify({'error': 'Access denied'}), 403

    # Mark as read if recipient
    if message.recipient_id == user.id or (user.role == 'admin' and message.recipient_id is None):
        if not message.is_read and message.sender_id != user.id:
            message.is_read = True
            message.read_at = datetime.utcnow()
            db.commit()

    return jsonify(message_to_dict(message))


@app.route('/messages/<int:message_id>', methods=['PUT'])
@token_required
def update_message(message_id):
    """Update message status (admin only for error reports)."""
    db = get_db()
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        return jsonify({'error': 'Message not found'}), 404

    data = request.get_json()

    # Only admins can update error report status
    if 'status' in data:
        if g.current_user.role != 'admin':
            return jsonify({'error': 'Admin access required'}), 403
        message.status = data['status']

    db.commit()
    db.refresh(message)

    return jsonify(message_to_dict(message))


@app.route('/messages/<int:message_id>', methods=['DELETE'])
@token_required
def delete_message(message_id):
    """Delete a message. Any authenticated user can delete any message."""
    db = get_db()
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        return jsonify({'error': 'Message not found'}), 404

    db.delete(message)
    db.commit()

    return jsonify({"status": "deleted"})


@app.route('/users/list')
@token_required
def list_users_for_messaging():
    """Get list of users for messaging."""
    db = get_db()
    user = g.current_user

    if user.role in ['admin', 'backoffice_user']:
        # Admins and backoffice users can message all users
        users = db.query(User).filter(
            User.id != user.id,
            User.is_active == True
        ).all()
    elif user.role == 'trainer':
        # Trainers can only message admins and backoffice users
        users = db.query(User).filter(
            User.role.in_(['admin', 'backoffice_user']),
            User.is_active == True
        ).all()
    else:
        users = []

    return jsonify([{
        "id": u.id,
        "username": u.username,
        "role": u.role
    } for u in users])


# ========== TRAINER APPLICATION ROUTES ==========

def application_to_dict(app):
    """Convert trainer registration/application to dictionary."""
    return {
        "id": app.id,
        "email": app.email,
        "first_name": app.first_name,
        "last_name": app.last_name,
        "phone": app.phone,
        "street": app.street,
        "house_number": app.house_number,
        "postal_code": app.postal_code,
        "city": app.city,
        "vat_number": app.vat_number,
        "bank_account": app.bank_account,
        "linkedin_url": app.linkedin_url,
        "website": app.website,
        "region": app.region,
        "additional_info": app.additional_info,
        "specializations": app.specializations,
        "proposed_trainings": app.proposed_trainings,
        "photo_url": app.photo_url,
        "status": app.status,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None
    }


@app.route('/trainer/apply', methods=['POST'])
def submit_trainer_application():
    """Submit a trainer application (no auth required)."""
    try:
        db = get_db()
        data = request.get_json()

        # Check if email already exists
        existing_app = db.query(TrainerRegistration).filter(
            TrainerRegistration.email == data.get('email')
        ).first()
        if existing_app:
            return jsonify({"error": "Es gibt bereits eine Bewerbung mit dieser E-Mail-Adresse"}), 400

        existing_user = db.query(User).filter(User.email == data.get('email')).first()
        if existing_user:
            return jsonify({"error": "Ein Benutzer mit dieser E-Mail-Adresse existiert bereits"}), 400

        # Create application
        proposed_trainings = data.get('proposed_trainings', [])

        application = TrainerRegistration(
            email=data.get('email'),
            password_hash=get_password_hash(data.get('password')),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            phone=data.get('phone'),
            street=data.get('street'),
            house_number=data.get('house_number'),
            postal_code=data.get('postal_code'),
            city=data.get('city'),
            vat_number=data.get('vat_number'),
            bank_account=data.get('bank_account'),
            linkedin_url=data.get('linkedin_url'),
            website=data.get('website'),
            region=data.get('region'),
            additional_info=data.get('additional_info'),
            specializations=data.get('specializations'),
            proposed_trainings=json.dumps(proposed_trainings) if proposed_trainings else None,
            status='pending'
        )

        db.add(application)
        db.commit()
        db.refresh(application)

        # Create notification message for all admins and backoffice users
        admin_users = db.query(User).filter(
            User.role.in_(['admin', 'backoffice_user']),
            User.is_active == True
        ).all()

        # Create a system message for each admin/backoffice user
        for admin in admin_users:
            # Format address
            address_parts = [p for p in [application.street, application.house_number] if p]
            address_line1 = ' '.join(address_parts) if address_parts else ''
            address_parts2 = [p for p in [application.postal_code, application.city] if p]
            address_line2 = ' '.join(address_parts2) if address_parts2 else ''
            full_address = f"{address_line1}, {address_line2}" if address_line1 and address_line2 else (address_line1 or address_line2 or 'Nicht angegeben')

            # Format trainings
            trainings_text = 'Keine Trainings angegeben'
            if application.proposed_trainings:
                trainings = json.loads(application.proposed_trainings)
                if trainings:
                    trainings_list = []
                    for i, t in enumerate(trainings, 1):
                        duration_text = f"{t.get('duration', '')} {t.get('duration_unit', '')}"
                        materials = "Ja" if t.get('materials_available') else "Nein"
                        trainings_list.append(f"{i}. {t.get('title', 'Ohne Titel')}\n   - Beschreibung: {t.get('description', '-')}\n   - Dauer: {duration_text}\n   - Materialien vorhanden: {materials}\n   - Zielgruppe: {t.get('target_audience', '-')}\n   - Angebotspreis: {t.get('price', '-')} EUR")
                    trainings_text = '\n'.join(trainings_list)

            message = Message(
                sender_id=admin.id,  # System message, sender = recipient
                recipient_id=admin.id,
                message_type='trainer_application',
                subject=f"Neue Trainerbewerbung: {application.first_name} {application.last_name}",
                content=f"""Neue Trainerbewerbung eingegangen:

Name: {application.first_name} {application.last_name}
E-Mail: {application.email}
Telefon: {application.phone or 'Nicht angegeben'}
Adresse: {full_address}
Region: {application.region or 'Nicht angegeben'}

USt-IdNr: {application.vat_number or 'Nicht angegeben'}
Kontonummer: {application.bank_account or 'Nicht angegeben'}

Weitere Informationen:
{application.additional_info or 'Nicht angegeben'}

Spezialisierungen: {application.specializations or 'Nicht angegeben'}

LinkedIn: {application.linkedin_url or 'Nicht angegeben'}
Website: {application.website or 'Nicht angegeben'}

--- Meine bisherigen Trainings ---
{trainings_text}

---
Application ID: {application.id}""",
                status='open',
                is_read=False
            )
            db.add(message)

        db.commit()

        # Send confirmation email to trainer
        trainer_name = f"{application.first_name} {application.last_name}"
        send_trainer_application_received(application.email, trainer_name)

        # Send notification email to admins
        for admin in admin_users:
            if admin.email:
                send_new_application_admin_notification(
                    admin.email,
                    trainer_name,
                    application.email,
                    application.id
                )

        return jsonify({"status": "success", "message": "Bewerbung erfolgreich eingereicht", "id": application.id}), 201

    except Exception as e:
        logging.error(f"Error submitting trainer application: {str(e)}", exc_info=True)
        return jsonify({"error": f"Fehler beim Einreichen der Bewerbung: {str(e)}"}), 500


@app.route('/trainer/applications')
@token_required
def list_trainer_applications():
    """List all trainer applications (admin/backoffice only)."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({"error": "Admin access required"}), 403

    db = get_db()
    applications = db.query(TrainerRegistration).order_by(
        TrainerRegistration.created_at.desc()
    ).all()

    return jsonify([application_to_dict(app) for app in applications])


@app.route('/trainer/applications/<int:app_id>')
@token_required
def get_trainer_application(app_id):
    """Get a single trainer application (admin/backoffice only)."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({"error": "Admin access required"}), 403

    db = get_db()
    application = db.query(TrainerRegistration).filter(TrainerRegistration.id == app_id).first()
    if not application:
        return jsonify({"error": "Application not found"}), 404

    return jsonify(application_to_dict(application))


@app.route('/trainer/applications/<int:app_id>/approve', methods=['POST'])
@token_required
def approve_trainer_application(app_id):
    """Approve trainer application and create trainer + user accounts."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({"error": "Admin access required"}), 403

    db = get_db()
    application = db.query(TrainerRegistration).filter(TrainerRegistration.id == app_id).first()
    if not application:
        return jsonify({"error": "Application not found"}), 404

    if application.status != 'pending':
        return jsonify({"error": "Application already processed"}), 400

    # Create user account
    user = User(
        username=application.email,  # Email as username
        email=application.email,
        hashed_password=application.password_hash,
        role='trainer',
        is_active=True
    )
    db.add(user)
    db.flush()  # Get the user ID

    # Create trainer profile
    # Convert specializations text to JSON format if provided
    specs_json = None
    if application.specializations:
        specs_list = [s.strip() for s in application.specializations.split(',') if s.strip()]
        specs_json = {"selected": [], "custom": specs_list}

    trainer = Trainer(
        user_id=user.id,
        first_name=application.first_name,
        last_name=application.last_name,
        email=application.email,
        phone=application.phone,
        street=application.street,
        house_number=application.house_number,
        postal_code=application.postal_code,
        city=application.city,
        vat_number=application.vat_number,
        bank_account=application.bank_account,
        linkedin_url=application.linkedin_url,
        website=application.website,
        region=application.region,
        additional_info=application.additional_info,
        specializations=specs_json,
        proposed_trainings=application.proposed_trainings,
        photo_path=application.photo_url
    )
    db.add(trainer)

    # Update application status
    application.status = 'approved'
    application.reviewed_at = datetime.utcnow()
    application.reviewed_by = g.current_user.id

    # Try to create platform email via AlwaysData API
    platform_email = None
    email_password = None
    try:
        from .services.alwaysdata import create_user_mailbox, send_credentials_email

        # Get list of existing platform emails to avoid duplicates
        existing_emails = [u.platform_email for u in db.query(User).filter(User.platform_email.isnot(None)).all()]

        success, platform_email, email_password = create_user_mailbox(
            application.last_name,
            existing_emails=existing_emails
        )

        if success and platform_email:
            user.platform_email = platform_email
            user.first_name = application.first_name
            user.last_name = application.last_name
            logging.info(f"Created platform email {platform_email} for user {user.username}")
    except Exception as e:
        logging.warning(f"Could not create platform email: {e}")

    db.commit()

    # Send acceptance email to trainer
    trainer_name = f"{application.first_name} {application.last_name}"
    send_trainer_application_accepted(application.email, trainer_name)

    # Send welcome email from Martin with important information
    send_trainer_welcome_email(application.email, trainer_name)

    # If platform email was created, send credentials
    if platform_email and email_password:
        try:
            from .services.alwaysdata import send_credentials_email
            send_credentials_email(application.email, platform_email, email_password, trainer_name)
        except Exception as e:
            logging.warning(f"Could not send credentials email: {e}")

    return jsonify({
        "status": "success",
        "message": "Trainer erfolgreich angelegt" + (f" mit E-Mail {platform_email}" if platform_email else ""),
        "user_id": user.id,
        "trainer_id": trainer.id,
        "platform_email": platform_email
    })


@app.route('/trainer/applications/<int:app_id>/reject', methods=['POST'])
@token_required
def reject_trainer_application(app_id):
    """Reject a trainer application."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({"error": "Admin access required"}), 403

    db = get_db()
    application = db.query(TrainerRegistration).filter(TrainerRegistration.id == app_id).first()
    if not application:
        return jsonify({"error": "Application not found"}), 404

    if application.status != 'pending':
        return jsonify({"error": "Application already processed"}), 400

    # Get optional rejection reason
    data = request.get_json() or {}
    reason = data.get('reason')

    application.status = 'rejected'
    application.reviewed_at = datetime.utcnow()
    application.reviewed_by = g.current_user.id

    db.commit()

    # Send rejection email to trainer
    trainer_name = f"{application.first_name} {application.last_name}"
    send_trainer_application_rejected(application.email, trainer_name, reason)

    return jsonify({"status": "success", "message": "Bewerbung abgelehnt"})


# ============== Scheduled Tasks ==============

@app.route('/cron/send-training-reminders', methods=['POST'])
def send_training_reminders():
    """
    Send reminder emails for trainings happening tomorrow.
    This endpoint should be called by a cron job daily at 12:00.

    Security: Uses a simple API key for authentication.
    """
    # Simple API key authentication for cron jobs
    api_key = request.headers.get('X-Cron-Key')
    expected_key = os.environ.get('CRON_API_KEY', 'change-this-key')

    if api_key != expected_key:
        return jsonify({"error": "Unauthorized"}), 401

    db = get_db()
    tomorrow = (datetime.utcnow() + timedelta(days=1)).date()

    # Find all trainings starting tomorrow with assigned trainers
    trainings = db.query(Training).filter(
        Training.start_date == tomorrow,
        Training.trainer_id.isnot(None),
        Training.status.in_(['trainer_confirmed', 'planning'])
    ).all()

    sent_count = 0
    for training in trainings:
        trainer = training.trainer
        if trainer and trainer.email:
            customer_name = training.customer.company_name if training.customer else "Unbekannt"
            location = training.location or training.location_details or "Siehe Backoffice"
            training_date = training.start_date.strftime("%d.%m.%Y")
            training_time = "Siehe Backoffice"  # Could be enhanced with actual time field

            success = send_training_reminder(
                trainer.email,
                f"{trainer.first_name} {trainer.last_name}",
                training.title or f"Training {training.id}",
                training_date,
                training_time,
                location,
                customer_name
            )

            if success:
                sent_count += 1
                logger.info(f"Sent reminder for training {training.id} to {trainer.email}")

    return jsonify({
        "status": "success",
        "trainings_found": len(trainings),
        "reminders_sent": sent_count
    })


# WSGI application
application = app
