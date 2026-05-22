from flask import Blueprint, request, jsonify, session, redirect, url_for, flash, render_template
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
import logging

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            data = request.get_json() if request.is_json else request.form
            username = data.get('username')
            password = data.get('password')
            
            if not username or not password:
                if request.is_json:
                    return jsonify({'error': 'Username and password required'}), 400
                flash('Username and password required')
                return render_template('login.html')
            
            user = User.query.filter_by(username=username).first()
            
            if user and user.check_password(password):
                login_user(user, remember=True)
                logger.info(f"User {username} logged in successfully")
                
                if request.is_json:
                    return jsonify({
                        'success': True,
                        'user': user.to_dict(),
                        'redirect': url_for('main.chat')
                    })
                return redirect(url_for('main.chat'))
            else:
                logger.warning(f"Failed login attempt for username: {username}")
                if request.is_json:
                    return jsonify({'error': 'Invalid username or password'}), 401
                flash('Invalid username or password')
                return render_template('login.html')
                
        except Exception as e:
            logger.error(f"Error during login: {e}")
            if request.is_json:
                return jsonify({'error': 'Login failed'}), 500
            flash('An error occurred during login')
            return render_template('login.html')
    
    return render_template('login.html')

@auth_bp.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            data = request.get_json() if request.is_json else request.form
            username = data.get('username')
            email = data.get('email')
            password = data.get('password')
            confirm_password = data.get('confirm_password')
            language = data.get('language', 'english')
            
            missing_fields = []
            if not username: missing_fields.append('username')
            if not email: missing_fields.append('email')
            if not password: missing_fields.append('password')
            if not confirm_password: missing_fields.append('confirm_password')

            if missing_fields:
                error_msg = f'Required fields missing: {", ".join(missing_fields)}'
                if request.is_json:
                    return jsonify({'error': error_msg}), 400
                flash(error_msg)
                return render_template('signup.html')
            
            if password != confirm_password:
                if request.is_json:
                    return jsonify({'error': 'Passwords do not match'}), 400
                flash('Passwords do not match')
                return render_template('signup.html')
            
            if len(password) < 6:
                if request.is_json:
                    return jsonify({'error': 'Password must be at least 6 characters'}), 400
                flash('Password must be at least 6 characters')
                return render_template('signup.html')
            
            if User.query.filter_by(username=username).first():
                if request.is_json:
                    return jsonify({'error': 'Username already exists'}), 400
                flash('Username already exists')
                return render_template('signup.html')
            
            if User.query.filter_by(email=email).first():
                if request.is_json:
                    return jsonify({'error': 'Email already registered'}), 400
                flash('Email already registered')
                return render_template('signup.html')
            
            user = User(
                username=username,
                email=email,
                preferred_language=language
            )
            user.set_password(password)
            
            db.session.add(user)
            db.session.commit()
            
            login_user(user, remember=True)
            logger.info(f"New user registered: {username}")
            
            if request.is_json:
                return jsonify({
                    'success': True,
                    'user': user.to_dict(),
                    'redirect': url_for('main.chat')
                })
            flash('Account created successfully!')
            return redirect(url_for('main.chat'))
            
        except Exception as e:
            logger.error(f"Error during signup: {e}")
            db.session.rollback()
            if request.is_json:
                return jsonify({'error': 'Registration failed'}), 500
            flash('An error occurred during registration')
            return render_template('signup.html')
    
    return render_template('signup.html')

@auth_bp.route('/logout')
@login_required
def logout():
    username = current_user.username
    logout_user()
    logger.info(f"User {username} logged out")
    flash('You have been logged out')
    return redirect(url_for('main.index'))

@auth_bp.route('/profile')
@login_required
def profile():
    return jsonify(current_user.to_dict())

@auth_bp.route('/update_language', methods=['POST'])
@login_required
def update_language():
    try:
        data = request.get_json()
        language = data.get('language')
        
        if language not in ['english', 'tamil', 'hindi']:
            return jsonify({'error': 'Invalid language'}), 400
        
        current_user.preferred_language = language
        db.session.commit()
        
        return jsonify({'success': True, 'language': language})
    
    except Exception as e:
        logger.error(f"Error updating language: {e}")
        return jsonify({'error': 'Failed to update language'}), 500
