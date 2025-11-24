"""Flask application - WSGI compatible version of Trainings Backoffice."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, g, render_template
from flask_cors import CORS
from sqlalchemy.orm import Session

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger(__name__)

from .config import settings
from .database import Base, SessionLocal, engine
from .models import Brand, Customer, Trainer, Training, TrainingCatalogEntry, TrainingTask, User, Location, Message, TrainerApplication
from .core.security import create_access_token, get_password_hash, verify_password

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
        return jsonify({'error': 'Incorrect username or password'}), 401

    if not user.is_active:
        return jsonify({'error': 'User account is inactive'}), 403

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
    db.commit()
    db.refresh(user)

    return jsonify({
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active
    }), 201


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


@app.route('/auth/users/<int:user_id>/link-trainer', methods=['POST'])
@admin_required
def link_user_to_trainer(user_id):
    """Link a user account to a trainer profile."""
    db = get_db()

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404

    data = request.get_json() or {}
    trainer_id = data.get('trainer_id')

    if trainer_id:
        trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
        if not trainer:
            return jsonify({'error': 'Trainer not found'}), 404

        # Check if trainer is already linked to another user
        existing = db.query(Trainer).filter(
            Trainer.user_id != None,
            Trainer.user_id != user_id,
            Trainer.id == trainer_id
        ).first()
        if existing:
            return jsonify({'error': 'Trainer already linked to another user'}), 400

        # Unlink any existing trainer from this user
        old_trainer = db.query(Trainer).filter(Trainer.user_id == user_id).first()
        if old_trainer:
            old_trainer.user_id = None

        # Link new trainer
        trainer.user_id = user_id
        db.commit()

        return jsonify({
            "message": "Trainer linked successfully",
            "trainer_id": trainer.id,
            "trainer_name": trainer.name
        })
    else:
        # Unlink trainer
        trainer = db.query(Trainer).filter(Trainer.user_id == user_id).first()
        if trainer:
            trainer.user_id = None
            db.commit()

        return jsonify({"message": "Trainer unlinked successfully"})


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
    brands = get_db().query(Brand).all()
    return jsonify([{
        "id": b.id,
        "name": b.name,
        "description": b.description
    } for b in brands])


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
    customers = get_db().query(Customer).all()
    return jsonify([customer_to_dict(c) for c in customers])


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
        "address": t.address,
        "vat_number": getattr(t, 'vat_number', None),
        "linkedin_url": getattr(t, 'linkedin_url', None),
        "website": getattr(t, 'website', None),
        "photo_path": getattr(t, 'photo_path', None),
        "specializations": getattr(t, 'specializations', None) or {"selected": [], "custom": []},
        "bio": getattr(t, 'bio', None),
        "notes": getattr(t, 'notes', None),
        "region": getattr(t, 'region', None),
        "default_day_rate": getattr(t, 'default_day_rate', None)
    }


@app.route('/trainers')
@token_required
def list_trainers():
    trainers = get_db().query(Trainer).all()
    return jsonify([trainer_to_dict(t) for t in trainers])


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

    # Save photo
    import uuid
    from werkzeug.utils import secure_filename

    filename = secure_filename(photo.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else 'jpg'
    new_filename = f"trainer_{trainer_id}_{uuid.uuid4().hex[:8]}.{ext}"

    upload_dir = APP_DIR / 'static' / 'uploads' / 'trainers'
    upload_dir.mkdir(parents=True, exist_ok=True)

    photo_path = upload_dir / new_filename
    photo.save(str(photo_path))

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
    trainings = get_db().query(Training).all()
    return jsonify([training_to_dict(t) for t in trainings])


@app.route('/trainings', methods=['POST'])
@token_required
def create_training():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    from datetime import datetime as dt

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

    db.commit()
    db.refresh(training)

    return jsonify(training_to_dict(training))


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
    locations = get_db().query(Location).all()
    return jsonify([location_to_dict(loc) for loc in locations])


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
    for key in ['first_name', 'last_name', 'email', 'phone', 'address', 'vat_number',
                'linkedin_url', 'website', 'default_day_rate', 'region', 'bio', 'notes',
                'specializations']:
        if key in data:
            setattr(trainer, key, data[key])

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

    return jsonify([{
        "id": t.id,
        "title": t.title,
        "description": t.location_details,
        "start_date": t.start_date.isoformat() if t.start_date else None,
        "end_date": t.end_date.isoformat() if t.end_date else None,
        "duration_days": t.duration_days,
        "location": t.location,
        "status": t.status,
        "already_applied": t.id in my_application_training_ids
    } for t in open_trainings])


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

    application = TrainerApplication(
        training_id=training_id,
        trainer_id=trainer.id,
        message=data.get('message'),
        proposed_rate=data.get('proposed_rate') or trainer.default_day_rate,
        status='pending'
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    return jsonify({
        "id": application.id,
        "status": "pending",
        "message": "Application submitted successfully"
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
    """Delete a message."""
    db = get_db()
    message = db.query(Message).filter(Message.id == message_id).first()

    if not message:
        return jsonify({'error': 'Message not found'}), 404

    # Check access - only sender or recipient can delete
    user = g.current_user
    if message.sender_id != user.id and message.recipient_id != user.id:
        if not (user.role == 'admin' and message.recipient_id is None):
            return jsonify({'error': 'Access denied'}), 403

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
    """Convert trainer application to dictionary."""
    return {
        "id": app.id,
        "email": app.email,
        "first_name": app.first_name,
        "last_name": app.last_name,
        "phone": app.phone,
        "address": app.address,
        "vat_number": app.vat_number,
        "linkedin_url": app.linkedin_url,
        "website": app.website,
        "default_day_rate": app.default_day_rate,
        "region": app.region,
        "bio": app.bio,
        "specializations": app.specializations,
        "photo_url": app.photo_url,
        "status": app.status,
        "created_at": app.created_at.isoformat() if app.created_at else None,
        "reviewed_at": app.reviewed_at.isoformat() if app.reviewed_at else None
    }


@app.route('/trainer/apply', methods=['POST'])
def submit_trainer_application():
    """Submit a trainer application (no auth required)."""
    db = get_db()
    data = request.get_json()

    # Check if email already exists
    existing_app = db.query(TrainerApplication).filter(
        TrainerApplication.email == data.get('email')
    ).first()
    if existing_app:
        return jsonify({"error": "Es gibt bereits eine Bewerbung mit dieser E-Mail-Adresse"}), 400

    existing_user = db.query(User).filter(User.email == data.get('email')).first()
    if existing_user:
        return jsonify({"error": "Ein Benutzer mit dieser E-Mail-Adresse existiert bereits"}), 400

    # Create application
    application = TrainerApplication(
        email=data.get('email'),
        password_hash=get_password_hash(data.get('password')),
        first_name=data.get('first_name'),
        last_name=data.get('last_name'),
        phone=data.get('phone'),
        address=data.get('address'),
        vat_number=data.get('vat_number'),
        linkedin_url=data.get('linkedin_url'),
        website=data.get('website'),
        default_day_rate=data.get('default_day_rate'),
        region=data.get('region'),
        bio=data.get('bio'),
        specializations=data.get('specializations'),
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
        message = Message(
            sender_id=admin.id,  # System message, sender = recipient
            recipient_id=admin.id,
            message_type='trainer_application',
            subject=f"Neue Trainerbewerbung: {application.first_name} {application.last_name}",
            content=f"""Neue Trainerbewerbung eingegangen:

Name: {application.first_name} {application.last_name}
E-Mail: {application.email}
Telefon: {application.phone or 'Nicht angegeben'}
Region: {application.region or 'Nicht angegeben'}

Tagessatz: {application.default_day_rate or 'Nicht angegeben'} EUR
USt-IdNr: {application.vat_number or 'Nicht angegeben'}

Bio:
{application.bio or 'Nicht angegeben'}

Spezialisierungen: {application.specializations or 'Nicht angegeben'}

LinkedIn: {application.linkedin_url or 'Nicht angegeben'}
Website: {application.website or 'Nicht angegeben'}

---
Application ID: {application.id}""",
            status='open',
            is_read=False
        )
        db.add(message)

    db.commit()

    return jsonify({"status": "success", "message": "Bewerbung erfolgreich eingereicht", "id": application.id}), 201


@app.route('/trainer/applications')
@token_required
def list_trainer_applications():
    """List all trainer applications (admin/backoffice only)."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({"error": "Admin access required"}), 403

    db = get_db()
    applications = db.query(TrainerApplication).order_by(
        TrainerApplication.created_at.desc()
    ).all()

    return jsonify([application_to_dict(app) for app in applications])


@app.route('/trainer/applications/<int:app_id>')
@token_required
def get_trainer_application(app_id):
    """Get a single trainer application (admin/backoffice only)."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({"error": "Admin access required"}), 403

    db = get_db()
    application = db.query(TrainerApplication).filter(TrainerApplication.id == app_id).first()
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
    application = db.query(TrainerApplication).filter(TrainerApplication.id == app_id).first()
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
        address=application.address,
        vat_number=application.vat_number,
        linkedin_url=application.linkedin_url,
        website=application.website,
        default_day_rate=application.default_day_rate,
        region=application.region,
        bio=application.bio,
        specializations=specs_json,
        photo_path=application.photo_url
    )
    db.add(trainer)

    # Update application status
    application.status = 'approved'
    application.reviewed_at = datetime.utcnow()
    application.reviewed_by = g.current_user.id

    db.commit()

    return jsonify({
        "status": "success",
        "message": "Trainer erfolgreich angelegt",
        "user_id": user.id,
        "trainer_id": trainer.id
    })


@app.route('/trainer/applications/<int:app_id>/reject', methods=['POST'])
@token_required
def reject_trainer_application(app_id):
    """Reject a trainer application."""
    if g.current_user.role not in ['admin', 'backoffice_user']:
        return jsonify({"error": "Admin access required"}), 403

    db = get_db()
    application = db.query(TrainerApplication).filter(TrainerApplication.id == app_id).first()
    if not application:
        return jsonify({"error": "Application not found"}), 404

    if application.status != 'pending':
        return jsonify({"error": "Application already processed"}), 400

    application.status = 'rejected'
    application.reviewed_at = datetime.utcnow()
    application.reviewed_by = g.current_user.id

    db.commit()

    return jsonify({"status": "success", "message": "Bewerbung abgelehnt"})


# WSGI application
application = app
