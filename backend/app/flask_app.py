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
from .models import Brand, Customer, Trainer, Training, TrainingCatalogEntry, TrainingTask, User
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
        "user_id": t.user_id,
        "first_name": t.first_name,
        "last_name": t.last_name,
        "name": t.name,
        "email": t.email,
        "phone": t.phone,
        "address": t.address,
        "vat_number": t.vat_number,
        "linkedin_url": t.linkedin_url,
        "website": t.website,
        "photo_path": t.photo_path,
        "specializations": t.specializations or {"selected": [], "custom": []},
        "bio": t.bio,
        "notes": t.notes,
        "region": t.region,
        "default_day_rate": t.default_day_rate
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

@app.route('/trainings')
@token_required
def list_trainings():
    trainings = get_db().query(Training).all()
    return jsonify([{
        "id": t.id,
        "title": t.title,
        "description": t.description,
        "date": t.date.isoformat() if t.date else None,
        "duration_hours": t.duration_hours,
        "location": t.location,
        "status": t.status,
        "customer_id": t.customer_id,
        "trainer_id": t.trainer_id
    } for t in trainings])


@app.route('/trainings', methods=['POST'])
@token_required
def create_training():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    from datetime import datetime as dt
    training = Training(
        title=data.get('title'),
        description=data.get('description'),
        date=dt.fromisoformat(data['date']) if data.get('date') else None,
        duration_hours=data.get('duration_hours'),
        location=data.get('location'),
        status=data.get('status', 'planned'),
        customer_id=data.get('customer_id'),
        trainer_id=data.get('trainer_id')
    )

    db = get_db()
    db.add(training)
    db.commit()
    db.refresh(training)

    return jsonify({
        "id": training.id,
        "title": training.title,
        "description": training.description,
        "date": training.date.isoformat() if training.date else None,
        "duration_hours": training.duration_hours,
        "location": training.location,
        "status": training.status,
        "customer_id": training.customer_id,
        "trainer_id": training.trainer_id
    }), 201


@app.route('/trainings/<int:training_id>')
@token_required
def get_training(training_id):
    training = get_db().query(Training).filter(Training.id == training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    return jsonify({
        "id": training.id,
        "title": training.title,
        "description": training.description,
        "date": training.date.isoformat() if training.date else None,
        "duration_hours": training.duration_hours,
        "location": training.location,
        "status": training.status,
        "customer_id": training.customer_id,
        "trainer_id": training.trainer_id
    })


@app.route('/trainings/<int:training_id>', methods=['PUT'])
@token_required
def update_training(training_id):
    db = get_db()
    training = db.query(Training).filter(Training.id == training_id).first()
    if not training:
        return jsonify({'error': 'Training not found'}), 404

    data = request.get_json()
    for key in ['title', 'description', 'duration_hours', 'location', 'status', 'customer_id', 'trainer_id']:
        if key in data:
            setattr(training, key, data[key])

    if 'date' in data:
        from datetime import datetime as dt
        training.date = dt.fromisoformat(data['date']) if data['date'] else None

    db.commit()
    db.refresh(training)

    return jsonify({
        "id": training.id,
        "title": training.title,
        "description": training.description,
        "date": training.date.isoformat() if training.date else None,
        "duration_hours": training.duration_hours,
        "location": training.location,
        "status": training.status,
        "customer_id": training.customer_id,
        "trainer_id": training.trainer_id
    })


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


# WSGI application
application = app
