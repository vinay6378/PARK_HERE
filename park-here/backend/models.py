from datetime import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'user', 'admin', 'parking_owner'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = db.relationship('Booking', backref='user', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ParkingLocation(db.Model):
    __tablename__ = 'parking_locations'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(50), nullable=False)
    total_slots = db.Column(db.Integer, default=0)
    available_slots = db.Column(db.Integer, default=0)
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    slots = db.relationship('Slot', backref='parking_location', lazy=True)
    
    def update_available_slots(self):
        self.available_slots = Slot.query.filter_by(
            parking_location_id=self.id, 
            status='available'
        ).count()
        db.session.commit()

class Slot(db.Model):
    __tablename__ = 'slots'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    parking_location_id = db.Column(db.String(36), db.ForeignKey('parking_locations.id'), nullable=False)
    slot_number = db.Column(db.String(10), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # 'car', 'bike', 'handicap', 'ev'
    status = db.Column(db.String(20), default='available')  # 'available', 'booked', 'maintenance'
    price_per_hour = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = db.relationship('Booking', backref='slot', lazy=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'slot_number': self.slot_number,
            'type': self.type,
            'status': self.status,
            'price_per_hour': self.price_per_hour
        }

class Booking(db.Model):
    __tablename__ = 'bookings'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    slot_id = db.Column(db.String(36), db.ForeignKey('slots.id'), nullable=False)
    vehicle_number = db.Column(db.String(20), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime)
    actual_end_time = db.Column(db.DateTime)
    total_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default='upcoming')  # 'upcoming', 'active', 'completed', 'cancelled'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    payments = db.relationship('Payment', backref='booking', lazy=True)
    
    def calculate_amount(self):
        if not self.end_time or not self.start_time:
            return 0.0
        
        duration_hours = (self.end_time - self.start_time).total_seconds() / 3600
        return round(duration_hours * self.slot.price_per_hour, 2)

class Payment(db.Model):
    __tablename__ = 'payments'
    
    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    booking_id = db.Column(db.String(36), db.ForeignKey('bookings.id'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_method = db.Column(db.String(50), nullable=False)  # 'upi', 'card', 'wallet', 'cash'
    transaction_id = db.Column(db.String(100), unique=True)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'completed', 'failed', 'refunded'
    payment_details = db.Column(db.JSON)  # Store additional payment details
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
