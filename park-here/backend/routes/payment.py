from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime
from models import Payment, Booking, User, db
import uuid

payment_bp = Blueprint('payment', __name__)

def generate_transaction_id():
    """Generate a unique transaction ID"""
    return f"TXN{int(datetime.utcnow().timestamp())}{uuid.uuid4().hex[:6].upper()}"

@payment_bp.route('/initiate', methods=['POST'])
@jwt_required()
def initiate_payment():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['booking_id', 'amount', 'payment_method']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Check if booking exists and belongs to the user
        booking = Booking.query.get_or_404(data['booking_id'])
        if booking.user_id != current_user_id:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Check if booking is already paid
        existing_payment = Payment.query.filter_by(booking_id=booking.id, status='completed').first()
        if existing_payment:
            return jsonify({
                'error': 'This booking has already been paid',
                'payment_id': existing_payment.id,
                'status': existing_payment.status
            }), 400
        
        # Validate amount
        if float(data['amount']) != float(booking.total_amount):
            return jsonify({
                'error': f'Amount mismatch. Expected: {booking.total_amount}, Received: {data["amount"]}'
            }), 400
        
        # Create payment record
        payment = Payment(
            booking_id=booking.id,
            user_id=current_user_id,
            amount=float(data['amount']),
            payment_method=data['payment_method'],
            transaction_id=generate_transaction_id(),
            status='pending'
        )
        
        db.session.add(payment)
        
        # In a real application, you would integrate with a payment gateway here
        # For demo purposes, we'll simulate a successful payment
        
        # Simulate payment processing
        payment.status = 'completed'
        booking.payment_status = 'paid'
        
        db.session.commit()
        
        return jsonify({
            'message': 'Payment initiated successfully',
            'payment': {
                'id': payment.id,
                'transaction_id': payment.transaction_id,
                'amount': float(payment.amount),
                'status': payment.status,
                'payment_method': payment.payment_method,
                'created_at': payment.created_at.isoformat()
            }
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@payment_bp.route('/verify', methods=['POST'])
@jwt_required()
def verify_payment():
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['payment_id', 'transaction_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'error': f'{field} is required'}), 400
        
        # Find payment
        payment = Payment.query.filter_by(
            id=data['payment_id'],
            transaction_id=data['transaction_id'],
            user_id=current_user_id
        ).first_or_404()
        
        # In a real application, you would verify the payment with the payment gateway here
        # For demo purposes, we'll return the current status
        
        return jsonify({
            'payment_id': payment.id,
            'transaction_id': payment.transaction_id,
            'amount': float(payment.amount),
            'status': payment.status,
            'payment_method': payment.payment_method,
            'booking_id': payment.booking_id,
            'created_at': payment.created_at.isoformat(),
            'verified': payment.status == 'completed'
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@payment_bp.route('/history', methods=['GET'])
@jwt_required()
def payment_history():
    try:
        current_user_id = get_jwt_identity()
        
        # Get query parameters
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        status = request.args.get('status')
        
        # Build query
        query = Payment.query.filter_by(user_id=current_user_id)
        
        if status:
            query = query.filter_by(status=status)
        
        # Paginate results
        payments = query.order_by(Payment.created_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return jsonify({
            'payments': [{
                'id': payment.id,
                'transaction_id': payment.transaction_id,
                'amount': float(payment.amount),
                'status': payment.status,
                'payment_method': payment.payment_method,
                'booking_id': payment.booking_id,
                'created_at': payment.created_at.isoformat()
            } for payment in payments.items],
            'pagination': {
                'total': payments.total,
                'pages': payments.pages,
                'current_page': payments.page,
                'per_page': payments.per_page,
                'has_next': payments.has_next,
                'has_prev': payments.has_prev
            }
        }), 200
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@payment_bp.route('/refund/<payment_id>', methods=['POST'])
@jwt_required()
def request_refund(payment_id):
    try:
        current_user_id = get_jwt_identity()
        data = request.get_json()
        
        # Find payment
        payment = Payment.query.filter_by(
            id=payment_id,
            user_id=current_user_id
        ).first_or_404()
        
        # Check if payment is eligible for refund
        if payment.status != 'completed':
            return jsonify({'error': 'Only completed payments can be refunded'}), 400
        
        # Check if refund is already requested
        if payment.status == 'refund_requested':
            return jsonify({'error': 'Refund already requested for this payment'}), 400
        
        # Check if refund is already processed
        if payment.status == 'refunded':
            return jsonify({'error': 'This payment has already been refunded'}), 400
        
        # Update payment status to refund requested
        payment.status = 'refund_requested'
        payment.refund_reason = data.get('reason', '')
        payment.updated_at = datetime.utcnow()
        
        # In a real application, you would initiate the refund process with the payment gateway here
        
        db.session.commit()
        
        return jsonify({
            'message': 'Refund requested successfully',
            'payment_id': payment.id,
            'status': payment.status,
            'refund_reason': payment.refund_reason
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Admin-only endpoint to process refunds
@payment_bp.route('/admin/refund/<payment_id>', methods=['POST'])
@jwt_required()
def process_refund(payment_id):
    try:
        current_user = User.query.get(get_jwt_identity())
        
        # Check if user is admin
        if current_user.role != 'admin':
            return jsonify({'error': 'Unauthorized'}), 403
        
        data = request.get_json()
        
        # Find payment
        payment = Payment.query.get_or_404(payment_id)
        
        # Check if payment is eligible for refund
        if payment.status != 'refund_requested':
            return jsonify({
                'error': 'Only payments with status "refund_requested" can be processed',
                'current_status': payment.status
            }), 400
        
        # In a real application, you would process the refund with the payment gateway here
        
        # Update payment status to refunded
        payment.status = 'refunded'
        payment.refund_processed_by = current_user.id
        payment.refund_processed_at = datetime.utcnow()
        payment.updated_at = datetime.utcnow()
        
        # Update booking status if needed
        booking = Booking.query.get(payment.booking_id)
        if booking and booking.status in ['upcoming', 'active']:
            booking.status = 'cancelled'
            
            # Make the slot available again if the booking was upcoming
            if booking.status == 'upcoming' and booking.slot:
                booking.slot.status = 'available'
                
                # Update parking location available slots
                location = ParkingLocation.query.get(booking.slot.parking_location_id)
                if location:
                    location.available_slots = min(location.total_slots, location.available_slots + 1)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Refund processed successfully',
            'payment_id': payment.id,
            'status': payment.status,
            'refund_processed_by': current_user.id,
            'refund_processed_at': payment.refund_processed_at.isoformat()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
