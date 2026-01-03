from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from models import Booking, Slot, ParkingLocation, User, db
from sqlalchemy import or_

booking_bp = Blueprint('booking', __name__)

@booking_bp.route('', methods=['POST'])
@jwt_required()
def create_booking():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['slot_id', 'vehicle_number', 'start_time', 'end_time']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Parse datetime strings
        try:
            start_time = datetime.fromisoformat(data['start_time'].replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(data['end_time'].replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({'error': 'Invalid date format. Use ISO 8601 format'}), 400
        
        # Validate time range
        if start_time >= end_time:
            return jsonify({'error': 'End time must be after start time'}), 400
        
        if start_time < datetime.utcnow():
            return jsonify({'error': 'Start time cannot be in the past'}), 400
        
        # Check if slot exists and is available
        slot = Slot.query.get(data['slot_id'])
        if not slot:
            return jsonify({'error': 'Slot not found'}), 404
        
        if slot.status != 'available':
            return jsonify({'error': 'This slot is not available for booking'}), 400
        
        # Check for overlapping bookings
        overlapping_booking = Booking.query.filter(
            Booking.slot_id == data['slot_id'],
            Booking.status.in_(['upcoming', 'active']),
            or_(
                # New booking starts during an existing booking
                (start_time >= Booking.start_time) & (start_time < Booking.end_time),
                # New booking ends during an existing booking
                (end_time > Booking.start_time) & (end_time <= Booking.end_time),
                # New booking completely contains an existing booking
                (start_time <= Booking.start_time) & (end_time >= Booking.end_time)
            )
        ).first()
        
        if overlapping_booking:
            return jsonify({
                'error': 'This slot is already booked for the selected time period',
                'conflicting_booking_id': overlapping_booking.id
            }), 400
        
        # Calculate duration and amount
        duration_hours = (end_time - start_time).total_seconds() / 3600
        amount = round(duration_hours * slot.price_per_hour, 2)
        
        # Create booking
        booking = Booking(
            user_id=current_user_id,
            slot_id=data['slot_id'],
            vehicle_number=data['vehicle_number'],
            start_time=start_time,
            end_time=end_time,
            total_amount=amount,
            status='upcoming'
        )
        
        # Update slot status
        slot.status = 'booked'
        
        # Update parking location available slots
        location = ParkingLocation.query.get(slot.parking_location_id)
        if location and slot.status == 'available':
            location.available_slots = max(0, location.available_slots - 1)
        
        db.session.add(booking)
        db.session.commit()
        
        return jsonify({
            'message': 'Booking created successfully',
            'booking': {
                'id': booking.id,
                'slot_id': booking.slot_id,
                'vehicle_number': booking.vehicle_number,
                'start_time': booking.start_time.isoformat(),
                'end_time': booking.end_time.isoformat(),
                'total_amount': booking.total_amount,
                'status': booking.status,
                'created_at': booking.created_at.isoformat()
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@booking_bp.route('', methods=['GET'])
@jwt_required()
def get_user_bookings():
    try:
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        status = request.args.get('status')
        upcoming = request.args.get('upcoming', 'false').lower() == 'true'
        
        # Build query
        query = Booking.query.filter_by(user_id=current_user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        if upcoming:
            now = datetime.utcnow()
            query = query.filter(Booking.start_time > now)
        
        # Order by start time (newest first)
        query = query.order_by(Booking.start_time.desc())
        
        bookings = query.all()
        
        return jsonify([{
            'id': booking.id,
            'slot_id': booking.slot_id,
            'slot_number': booking.slot.slot_number if booking.slot else None,
            'location_name': booking.slot.parking_location.name if booking.slot and booking.slot.parking_location else None,
            'vehicle_number': booking.vehicle_number,
            'start_time': booking.start_time.isoformat(),
            'end_time': booking.end_time.isoformat(),
            'actual_end_time': booking.actual_end_time.isoformat() if booking.actual_end_time else None,
            'total_amount': float(booking.total_amount) if booking.total_amount else 0.0,
            'status': booking.status,
            'created_at': booking.created_at.isoformat(),
            'payment_status': booking.payments[0].status if booking.payments else 'unpaid'
        } for booking in bookings]), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@booking_bp.route('/<booking_id>', methods=['GET'])
@jwt_required()
def get_booking(booking_id):
    try:
        current_user_id = get_jwt_identity()
        
        booking = Booking.query.get_or_404(booking_id)
        
        # Check if the current user is the owner of the booking
        if booking.user_id != current_user_id and not User.query.get(current_user_id).role == 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        return jsonify({
            'id': booking.id,
            'slot_id': booking.slot_id,
            'slot_number': booking.slot.slot_number if booking.slot else None,
            'slot_type': booking.slot.type if booking.slot else None,
            'location_id': booking.slot.parking_location_id if booking.slot else None,
            'location_name': booking.slot.parking_location.name if booking.slot and booking.slot.parking_location else None,
            'address': booking.slot.parking_location.address if booking.slot and booking.slot.parking_location else None,
            'vehicle_number': booking.vehicle_number,
            'start_time': booking.start_time.isoformat(),
            'end_time': booking.end_time.isoformat(),
            'actual_end_time': booking.actual_end_time.isoformat() if booking.actual_end_time else None,
            'total_amount': float(booking.total_amount) if booking.total_amount else 0.0,
            'status': booking.status,
            'created_at': booking.created_at.isoformat(),
            'payment': {
                'status': booking.payments[0].status if booking.payments else 'unpaid',
                'payment_method': booking.payments[0].payment_method if booking.payments else None,
                'transaction_id': booking.payments[0].transaction_id if booking.payments else None,
                'paid_at': booking.payments[0].created_at.isoformat() if booking.payments else None
            } if booking.payments else None
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@booking_bp.route('/<booking_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_booking(booking_id):
    try:
        current_user_id = get_jwt_identity()
        booking = Booking.query.get_or_404(booking_id)
        
        # Check if the current user is the owner of the booking or an admin
        if booking.user_id != current_user_id and not User.query.get(current_user_id).role == 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if booking can be cancelled
        if booking.status not in ['upcoming', 'active']:
            return jsonify({'error': 'This booking cannot be cancelled'}), 400
        
        # Update booking status
        booking.status = 'cancelled'
        booking.updated_at = datetime.utcnow()
        
        # Update slot status if the booking is upcoming
        if booking.status == 'upcoming' and booking.slot:
            booking.slot.status = 'available'
            
            # Update parking location available slots
            location = ParkingLocation.query.get(booking.slot.parking_location_id)
            if location:
                location.available_slots = min(location.total_slots, location.available_slots + 1)
        
        db.session.commit()
        
        # TODO: Process refund if payment was made
        
        return jsonify({
            'message': 'Booking cancelled successfully',
            'booking_id': booking.id,
            'status': booking.status
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@booking_bp.route('/<booking_id>/extend', methods=['POST'])
@jwt_required()
def extend_booking(booking_id):
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        if 'additional_hours' not in data or not data['additional_hours']:
            return jsonify({'error': 'additional_hours is required'}), 400
        
        additional_hours = float(data['additional_hours'])
        if additional_hours <= 0:
            return jsonify({'error': 'additional_hours must be greater than 0'}), 400
        
        booking = Booking.query.get_or_404(booking_id)
        
        # Check if the current user is the owner of the booking
        if booking.user_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if booking can be extended
        if booking.status != 'active':
            return jsonify({'error': 'Only active bookings can be extended'}), 400
        
        # Calculate new end time and additional amount
        new_end_time = booking.end_time + timedelta(hours=additional_hours)
        additional_amount = round(additional_hours * booking.slot.price_per_hour, 2)
        
        # Check for overlapping bookings
        overlapping_booking = Booking.query.filter(
            Booking.slot_id == booking.slot_id,
            Booking.id != booking.id,
            Booking.status.in_(['upcoming', 'active']),
            or_(
                # New end time overlaps with an existing booking
                (new_end_time > Booking.start_time) & (new_end_time <= Booking.end_time),
                # New end time is after an existing booking that starts at our new end time
                (new_end_time == Booking.start_time)
            )
        ).first()
        
        if overlapping_booking:
            return jsonify({
                'error': 'Cannot extend booking as it would overlap with another booking',
                'conflicting_booking_id': overlapping_booking.id,
                'max_additional_hours': (overlapping_booking.start_time - booking.end_time).total_seconds() / 3600
            }), 400
        
        # Update booking
        booking.end_time = new_end_time
        booking.total_amount += additional_amount
        booking.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Booking extended successfully',
            'booking_id': booking.id,
            'new_end_time': booking.end_time.isoformat(),
            'additional_amount': additional_amount,
            'new_total_amount': float(booking.total_amount)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
