from flask import Flask, jsonify
from flask_cors import CORS
from datetime import timedelta
import os
from dotenv import load_dotenv

# Initialize extensions
from extensions import db, jwt

def create_app():
    # Load environment variables
    load_dotenv()

    # Initialize Flask app
    app = Flask(__name__)
    CORS(app)

    # Configuration
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///park_here.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-secret-key-here')
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)

    # Initialize extensions with app
    db.init_app(app)
    jwt.init_app(app)

    # Import models (after db initialization)
    from models import User, ParkingLocation, Slot, Booking, Payment

    # Import blueprints from routes
    from routes.auth import auth_bp
    from routes.parking import parking_bp
    from routes.booking import booking_bp
    from routes.payment import payment_bp

    # Register blueprints with consistent URL prefixes
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(parking_bp, url_prefix='/api/parking')
    app.register_blueprint(booking_bp, url_prefix='/api/bookings')
    app.register_blueprint(payment_bp, url_prefix='/api/payments')

    # Create tables
    with app.app_context():
        db.create_all()

    # Health check endpoint
    @app.route('/api/health')
    def health_check():
        return jsonify({'status': 'healthy'}), 200

    # Root endpoint
    @app.route('/')
    def index():
        return jsonify({
            'message': 'Welcome to Park_Here API',
            'version': '1.0.0',
            'endpoints': {
                'auth': '/api/auth',
                'parking': '/api/parking',
                'booking': '/api/bookings',
                'payment': '/api/payments',
                'health': '/api/health'
            }
        }), 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Not found'}), 404

    @app.errorhandler(500)
    def server_error(error):
        return jsonify({'error': 'Internal server error'}), 500

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=5000, debug=True)
