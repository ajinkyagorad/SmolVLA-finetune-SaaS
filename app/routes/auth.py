from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from ..models import db, User

# Create Blueprint
auth = Blueprint('auth', __name__)

@auth.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False
        
        user = User.query.filter_by(username=username).first()
        
        # Check if user exists and password is correct
        if not user or not user.verify_password(password):
            flash('Please check your login details and try again.', 'danger')
            return render_template('login.html')
        
        # Log in the user
        login_user(user, remember=remember)
        
        # Redirect to the page the user was trying to access
        next_page = request.args.get('next')
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('main.index')
        
        return redirect(next_page)
    
    return render_template('login.html')


@auth.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration."""
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        hf_token = request.form.get('hf_token')
        wandb_api_key = request.form.get('wandb_api_key')
        
        # Check if username or email already exists
        user_exists = User.query.filter_by(username=username).first()
        email_exists = User.query.filter_by(email=email).first()
        
        if user_exists:
            flash('Username already exists.', 'danger')
            return render_template('register.html')
        
        if email_exists:
            flash('Email already exists.', 'danger')
            return render_template('register.html')
        
        # Create new user
        new_user = User(
            username=username,
            email=email
        )
        new_user.password = password
        
        # Encrypt and store tokens if provided
        cipher = current_app.cipher
        if hf_token:
            new_user.set_hf_token(cipher, hf_token)
        
        if wandb_api_key:
            new_user.set_wandb_api_key(cipher, wandb_api_key)
        
        # Add user to database
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html')


@auth.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.index'))


@auth.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Handle user profile updates."""
    if request.method == 'POST':
        # Update tokens if provided
        hf_token = request.form.get('hf_token')
        wandb_api_key = request.form.get('wandb_api_key')
        
        cipher = current_app.cipher
        
        if hf_token:
            current_user.set_hf_token(cipher, hf_token)
        
        if wandb_api_key:
            current_user.set_wandb_api_key(cipher, wandb_api_key)
        
        # Update email if provided
        email = request.form.get('email')
        if email and email != current_user.email:
            email_exists = User.query.filter_by(email=email).first()
            if email_exists:
                flash('Email already exists.', 'danger')
            else:
                current_user.email = email
        
        # Update password if provided
        password = request.form.get('password')
        if password:
            current_user.password = password
        
        db.session.commit()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('profile.html')
