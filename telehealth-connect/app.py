from flask import Flask, render_template, request, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
import re
from datetime import datetime
import math

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Needed for flash and session
app.config['SESSION_TYPE'] = 'filesystem'  # Store sessions in filesystem

# Configure MySQL connection
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:#Waridad20#@localhost/telehealth_db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define Patient model


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    appointments = db.relationship('Appointment', backref='patient', lazy=True)

# Define Appointment model


class Appointment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey(
        'patient.id'), nullable=False)
    date_time = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    health_center_id = db.Column(
        db.Integer, db.ForeignKey('health_center.id'), nullable=True)

# Define HealthCenter model


class HealthCenter(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    appointments = db.relationship(
        'Appointment', backref='health_center', lazy=True)

# Simple distance calculation (approximation using string matching for now)


def calculate_distance(user_location, center_location):
    if user_location.lower() in center_location.lower():
        return 0  # Same location
    return 100  # Arbitrary distance for different locations


@app.route('/')
def home():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']

        if not name or len(name.strip()) < 2:
            flash('Name must be at least 2 characters long.')
            return render_template('register.html')
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            flash('Invalid email format.')
            return render_template('register.html')
        if len(password) < 6:
            flash('Password must be at least 6 characters long.')
            return render_template('register.html')
        if Patient.query.filter_by(email=email).first():
            flash('Email already registered.')
            return render_template('register.html')

        new_patient = Patient(name=name, email=email, password=password)
        try:
            db.session.add(new_patient)
            db.session.commit()
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error registering: {str(e)}')
            return render_template('register.html')
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        patient = Patient.query.filter_by(
            email=email, password=password).first()
        if patient:
            session['user_id'] = patient.id
            session['user_name'] = patient.name
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password.')
            return render_template('login.html')
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('home'))


@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login to access the dashboard.')
        return redirect(url_for('login'))
    return render_template('dashboard.html')


@app.route('/book-appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session:
        flash('Please login to book an appointment.')
        return redirect(url_for('login'))
    if request.method == 'POST':
        date_time = datetime.strptime(
            request.form['date_time'], '%Y-%m-%dT%H:%M')
        location = request.form['location']
        patient = Patient.query.get(session['user_id'])
        if not patient:
            flash('User not found. Please log in again.')
            return redirect(url_for('login'))
        health_center = HealthCenter.query.first()
        if not health_center:
            health_center = HealthCenter(
                name="Default Clinic", location="Unknown")
            db.session.add(health_center)
            db.session.commit()
        new_appointment = Appointment(
            patient_id=patient.id, date_time=date_time, location=location, health_center_id=health_center.id)
        try:
            db.session.add(new_appointment)
            db.session.commit()
            flash('Appointment booked successfully!')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking appointment: {str(e)}')
            return render_template('book_appointment.html')
    return render_template('book_appointment.html')


@app.route('/view-appointments')
def view_appointments():
    if 'user_id' not in session:
        flash('Please login to view appointments.')
        return redirect(url_for('login'))
    patient = Patient.query.get(session['user_id'])
    if not patient:
        flash('User not found. Please log in again.')
        return redirect(url_for('login'))
    appointments = Appointment.query.filter_by(
        patient_id=patient.id).order_by(Appointment.date_time).all()
    return render_template('view_appointments.html', appointments=appointments)


@app.route('/find-health-centers', methods=['GET', 'POST'])
def find_health_centers():
    if 'user_id' not in session:
        flash('Please login to find health centers.')
        return redirect(url_for('login'))
    health_centers = HealthCenter.query.all()
    current_datetime = datetime.utcnow().strftime('%Y-%m-%dT%H:%M')
    user_location = None
    if request.method == 'POST':
        user_location = request.form.get('user_location')
        if user_location:
            health_centers = [hc for hc in health_centers if calculate_distance(
                user_location, hc.location) < 50]
    return render_template('find_health_centers.html', health_centers=health_centers, current_datetime=current_datetime, user_location=user_location)


if __name__ == '__main__':
    with app.app_context():
        # Creates all tables (patient, appointment, health_center) if they don’t exist
        db.create_all()
        if not HealthCenter.query.first():  # Add default centers if none exist
            db.session.add_all([
                HealthCenter(name="City Hospital",
                             location="456 Main St, Lagos"),
                HealthCenter(name="Community Clinic",
                             location="789 Side Rd, Abuja"),
                HealthCenter(name="Rural Health Center",
                             location="101 Back Rd, Port Harcourt")
            ])
            db.session.commit()
    app.run(debug=True)
