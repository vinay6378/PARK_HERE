from app import create_app
from models import db, User, ParkingLocation, Slot, Booking, Payment
from datetime import datetime, timedelta
import uuid

def init_db():
    app = create_app()
    with app.app_context():
        # Create all tables
        print("Creating database tables...")
        db.create_all()
        
        # Check if admin user already exists
        admin = User.query.filter_by(email='admin@parkhere.com').first()
        if not admin:
            print("Creating admin user...")
            admin = User(
                name='Admin User',
                email='admin@parkhere.com',
                phone='9876543210',
                role='admin'
            )
            admin.set_password('admin123')
            db.session.add(admin)
        
        # Create test user if not exists
        user = User.query.filter_by(email='user@example.com').first()
        if not user:
            print("Creating test user...")
            user = User(
                name='Test User',
                email='user@example.com',
                phone='9876543211',
                role='user'
            )
            user.set_password('user123')
            db.session.add(user)
        
        # Create parking locations if not exists
        location = ParkingLocation.query.first()
        if not location:
            print("Creating test parking locations...")
            locations = [
                {
                    'name': 'City Center Parking',
                    'address': '123 Main St, City Center',
                    'city': 'Mumbai',
                    'latitude': 19.0760,
                    'longitude': 72.8777,
                    'total_slots': 50,
                    'available_slots': 30
                },
                {
                    'name': 'Mall Parking',
                    'address': '456 Shopping St, Downtown',
                    'city': 'Delhi',
                    'latitude': 28.6139,
                    'longitude': 77.2090,
                    'total_slots': 100,
                    'available_slots': 45
                },
                {
                    'name': 'Airport Parking',
                    'address': 'Airport Road',
                    'city': 'Bangalore',
                    'latitude': 13.1986,
                    'longitude': 77.7066,
                    'total_slots': 200,
                    'available_slots': 120
                }
            ]
            
            for loc_data in locations:
                location = ParkingLocation(**loc_data)
                db.session.add(location)
                
                # Create some slots for each location
                for i in range(1, 11):
                    slot_type = 'car' if i % 3 != 0 else 'bike'
                    price = 50 if slot_type == 'car' else 30
                    
                    slot = Slot(
                        parking_location=location,
                        slot_number=f"{location.name[:3].upper()}-{i:03d}",
                        type=slot_type,
                        status='available',
                        price_per_hour=price
                    )
                    db.session.add(slot)
        
        # Commit all changes
        db.session.commit()
        print("Database initialized successfully!")

if __name__ == '__main__':
    init_db()
