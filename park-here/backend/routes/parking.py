from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import ParkingLocation, Slot, db
from datetime import datetime

parking_bp = Blueprint('parking', __name__)

# Parking Location Endpoints
@parking_bp.route('/locations', methods=['GET'])
def get_parking_locations():
    try:
        # Get query parameters
        city = request.args.get('city')
        available_only = request.args.get('available_only', 'false').lower() == 'true'
        
        # Build query
        query = ParkingLocation.query.filter_by(is_active=True)
        
        if city:
            query = query.filter(ParkingLocation.city.ilike(f'%{city}%'))
        
        if available_only:
            query = query.filter(ParkingLocation.available_slots > 0)
        
        # Execute query
        locations = query.all()
        
        return jsonify([{
            'id': loc.id,
            'name': loc.name,
            'address': loc.address,
            'city': loc.city,
            'total_slots': loc.total_slots,
            'available_slots': loc.available_slots,
            'latitude': loc.latitude,
            'longitude': loc.longitude,
            'created_at': loc.created_at.isoformat()
        } for loc in locations]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parking_bp.route('/locations/<location_id>', methods=['GET'])
def get_parking_location(location_id):
    try:
        location = ParkingLocation.query.get_or_404(location_id)
        
        return jsonify({
            'id': location.id,
            'name': location.name,
            'address': location.address,
            'city': location.city,
            'total_slots': location.total_slots,
            'available_slots': location.available_slots,
            'latitude': location.latitude,
            'longitude': location.longitude,
            'created_at': location.created_at.isoformat(),
            'slots': [{
                'id': slot.id,
                'slot_number': slot.slot_number,
                'type': slot.type,
                'status': slot.status,
                'price_per_hour': slot.price_per_hour
            } for slot in location.slots]
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parking_bp.route('/locations', methods=['POST'])
@jwt_required()
def create_parking_location():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'address', 'city', 'latitude', 'longitude']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Create new parking location
        location = ParkingLocation(
            name=data['name'],
            address=data['address'],
            city=data['city'],
            latitude=float(data['latitude']),
            longitude=float(data['longitude']),
            total_slots=0,
            available_slots=0
        )
        
        db.session.add(location)
        db.session.commit()
        
        return jsonify({
            'message': 'Parking location created successfully',
            'location': {
                'id': location.id,
                'name': location.name,
                'city': location.city,
                'total_slots': location.total_slots,
                'available_slots': location.available_slots
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Slot Management Endpoints
@parking_bp.route('/locations/<location_id>/slots', methods=['GET'])
def get_slots(location_id):
    try:
        location = ParkingLocation.query.get_or_404(location_id)
        
        # Get query parameters
        slot_type = request.args.get('type')
        status = request.args.get('status')
        
        # Build query
        query = Slot.query.filter_by(parking_location_id=location_id)
        
        if slot_type:
            query = query.filter_by(type=slot_type)
            
        if status:
            query = query.filter_by(status=status)
        
        slots = query.all()
        
        return jsonify([{
            'id': slot.id,
            'slot_number': slot.slot_number,
            'type': slot.type,
            'status': slot.status,
            'price_per_hour': slot.price_per_hour,
            'created_at': slot.created_at.isoformat()
        } for slot in slots]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@parking_bp.route('/locations/<location_id>/slots', methods=['POST'])
@jwt_required()
def add_slot(location_id):
    try:
        # Check if location exists
        location = ParkingLocation.query.get_or_404(location_id)
        
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['slot_number', 'type', 'price_per_hour']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if slot number already exists in this location
        if Slot.query.filter_by(
            parking_location_id=location_id,
            slot_number=data['slot_number']
        ).first():
            return jsonify({'error': 'Slot number already exists in this location'}), 400
        
        # Create new slot
        slot = Slot(
            parking_location_id=location_id,
            slot_number=data['slot_number'],
            type=data['type'],
            status='available',
            price_per_hour=float(data['price_per_hour'])
        )
        
        db.session.add(slot)
        
        # Update location slot counts
        location.total_slots += 1
        location.available_slots += 1 if slot.status == 'available' else 0
        
        db.session.commit()
        
        return jsonify({
            'message': 'Slot added successfully',
            'slot': {
                'id': slot.id,
                'slot_number': slot.slot_number,
                'type': slot.type,
                'status': slot.status,
                'price_per_hour': slot.price_per_hour
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@parking_bp.route('/slots/<slot_id>', methods=['PUT'])
@jwt_required()
def update_slot(slot_id):
    try:
        slot = Slot.query.get_or_404(slot_id)
        data = request.get_json()
        
        # Track if status changes from/to available for slot count updates
        old_status = slot.status
        
        # Update slot fields if provided
        if 'status' in data:
            slot.status = data['status']
        
        if 'type' in data:
            slot.type = data['type']
            
        if 'price_per_hour' in data:
            slot.price_per_hour = float(data['price_per_hour'])
        
        # Update location available_slots if status changed
        if 'status' in data and old_status != slot.status:
            location = ParkingLocation.query.get(slot.parking_location_id)
            if old_status == 'available' and slot.status != 'available':
                location.available_slots = max(0, location.available_slots - 1)
            elif old_status != 'available' and slot.status == 'available':
                location.available_slots = min(location.total_slots, location.available_slots + 1)
        
        slot.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Slot updated successfully',
            'slot': {
                'id': slot.id,
                'slot_number': slot.slot_number,
                'type': slot.type,
                'status': slot.status,
                'price_per_hour': slot.price_per_hour
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@parking_bp.route('/slots/<slot_id>', methods=['DELETE'])
@jwt_required()
def delete_slot(slot_id):
    try:
        slot = Slot.query.get_or_404(slot_id)
        location = ParkingLocation.query.get(slot.parking_location_id)
        
        # Update location slot counts
        location.total_slots -= 1
        if slot.status == 'available':
            location.available_slots = max(0, location.available_slots - 1)
        
        # Delete the slot
        db.session.delete(slot)
        db.session.commit()
        
        return jsonify({'message': 'Slot deleted successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
