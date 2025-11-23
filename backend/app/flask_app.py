"""Flask application - WSGI compatible version of Trainings Backoffice."""
from __future__ import annotations

import logging
import sys
from datetime import datetime, timedelta
from functools import wraps

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

# Create Flask app
app = Flask(__name__, template_folder='templates', static_folder='static')
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
    return render_template('index.html')


@app.route('/api')
def api_root():
    """API status endpoint."""
    return jsonify({
        "app": settings.app_name,
        "status": "running",
        "version": "1.0.0",
        "docs": "/api-info",
        "health": "/health"
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

    users = get_db().query(User).offset(skip).limit(limit).all()

    return jsonify([{
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "role": u.role,
        "is_active": u.is_active
    } for u in users])


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

    brand = Brand(
        name=data.get('name'),
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

@app.route('/customers')
@token_required
def list_customers():
    customers = get_db().query(Customer).all()
    return jsonify([{
        "id": c.id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "company": c.company,
        "notes": c.notes
    } for c in customers])


@app.route('/customers', methods=['POST'])
@token_required
def create_customer():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    customer = Customer(
        name=data.get('name'),
        email=data.get('email'),
        phone=data.get('phone'),
        company=data.get('company'),
        notes=data.get('notes')
    )

    db = get_db()
    db.add(customer)
    db.commit()
    db.refresh(customer)

    return jsonify({
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "company": customer.company,
        "notes": customer.notes
    }), 201


@app.route('/customers/<int:customer_id>')
@token_required
def get_customer(customer_id):
    customer = get_db().query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    return jsonify({
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "company": customer.company,
        "notes": customer.notes
    })


@app.route('/customers/<int:customer_id>', methods=['PUT'])
@token_required
def update_customer(customer_id):
    db = get_db()
    customer = db.query(Customer).filter(Customer.id == customer_id).first()
    if not customer:
        return jsonify({'error': 'Customer not found'}), 404

    data = request.get_json()
    for key in ['name', 'email', 'phone', 'company', 'notes']:
        if key in data:
            setattr(customer, key, data[key])

    db.commit()
    db.refresh(customer)

    return jsonify({
        "id": customer.id,
        "name": customer.name,
        "email": customer.email,
        "phone": customer.phone,
        "company": customer.company,
        "notes": customer.notes
    })


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

@app.route('/trainers')
@token_required
def list_trainers():
    trainers = get_db().query(Trainer).all()
    return jsonify([{
        "id": t.id,
        "name": t.name,
        "email": t.email,
        "phone": t.phone,
        "specialization": t.specialization,
        "bio": t.bio
    } for t in trainers])


@app.route('/trainers', methods=['POST'])
@token_required
def create_trainer():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'Invalid JSON'}), 400

    trainer = Trainer(
        name=data.get('name'),
        email=data.get('email'),
        phone=data.get('phone'),
        specialization=data.get('specialization'),
        bio=data.get('bio')
    )

    db = get_db()
    db.add(trainer)
    db.commit()
    db.refresh(trainer)

    return jsonify({
        "id": trainer.id,
        "name": trainer.name,
        "email": trainer.email,
        "phone": trainer.phone,
        "specialization": trainer.specialization,
        "bio": trainer.bio
    }), 201


@app.route('/trainers/<int:trainer_id>')
@token_required
def get_trainer(trainer_id):
    trainer = get_db().query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404

    return jsonify({
        "id": trainer.id,
        "name": trainer.name,
        "email": trainer.email,
        "phone": trainer.phone,
        "specialization": trainer.specialization,
        "bio": trainer.bio
    })


@app.route('/trainers/<int:trainer_id>', methods=['PUT'])
@token_required
def update_trainer(trainer_id):
    db = get_db()
    trainer = db.query(Trainer).filter(Trainer.id == trainer_id).first()
    if not trainer:
        return jsonify({'error': 'Trainer not found'}), 404

    data = request.get_json()
    for key in ['name', 'email', 'phone', 'specialization', 'bio']:
        if key in data:
            setattr(trainer, key, data[key])

    db.commit()
    db.refresh(trainer)

    return jsonify({
        "id": trainer.id,
        "name": trainer.name,
        "email": trainer.email,
        "phone": trainer.phone,
        "specialization": trainer.specialization,
        "bio": trainer.bio
    })


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


# WSGI application
application = app
