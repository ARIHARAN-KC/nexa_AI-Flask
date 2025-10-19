from flask import Flask, json, render_template, request, jsonify, send_file, session, redirect, url_for, flash, Response, send_from_directory
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField, TextAreaField, FileField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional
from flask_wtf.file import FileAllowed
from src.agents.decision_taker import DecisionTaker
from src.agents.planner import Planner
from src.agents.researcher import Researcher
from src.agents.coder import Coder
from src.agents.project_creator import ProjectCreator
from src.keyword_extractor import SentenceBert
from utils import prepare_coding_files, search_queries
import os
import zipfile
import io
from werkzeug.utils import secure_filename
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import json
from urllib.parse import urlparse

from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') 
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

# PostgreSQL configuration
database_url = os.environ.get('DATABASE_URL')
if database_url:
    # Parse the database URL for Neon.tech
    parsed_url = urlparse(database_url)
    
    # Extract components
    username = parsed_url.username
    password = parsed_url.password
    hostname = parsed_url.hostname
    port = parsed_url.port or 5432
    database = parsed_url.path[1:]  # Remove leading slash
    
    # Construct the SQLAlchemy connection string
    app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{username}:{password}@{hostname}:{port}/{database}?sslmode=require'
else:
    # Fallback to SQLite if DATABASE_URL is not set
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_recycle': 300,
    'pool_pre_ping': True,
}
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024

db = SQLAlchemy(app)
migrate = Migrate(app, db)

# Forms
class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class RegistrationForm(FlaskForm):
    username = StringField('Username', 
                          validators=[DataRequired(), Length(min=2, max=20)])
    email = StringField('Email',
                       validators=[DataRequired(), Email()])
    password = PasswordField('Password', 
                            validators=[DataRequired()])
    confirm_password = PasswordField('Confirm Password',
                                    validators=[DataRequired(), EqualTo('password')])
    accept_terms = BooleanField('I accept the Terms and Conditions', 
                               validators=[DataRequired()])
    submit = SubmitField('Sign Up')

class ConfigurationForm(FlaskForm):
    model = SelectField('AI Model', 
                       choices=[('Gemini-Pro', 'Gemini-Pro'), 
                               ('Cohere', 'Cohere'),
                               ('ChatGPT', 'ChatGPT'),
                               ('DeepSeek', 'DeepSeek')],
                       validators=[DataRequired()])
    api_key = PasswordField('API Key', validators=[DataRequired()])
    project_name = StringField('Project Name', validators=[DataRequired()])
    submit = SubmitField('Save')

class ProfileForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=2, max=20)
    ])
    email = StringField('Email', validators=[
        DataRequired(), 
        Email()
    ])
    first_name = StringField('First Name', validators=[
        Optional(),
        Length(max=50)
    ])
    last_name = StringField('Last Name', validators=[
        Optional(),
        Length(max=50)
    ])
    bio = TextAreaField('Bio', validators=[
        Optional(),
        Length(max=500)
    ])
    profile_picture = FileField('Profile Picture', validators=[
        FileAllowed(['jpg', 'png', 'jpeg', 'gif'], 'Images only!')
    ])

class PaymentMethodForm(FlaskForm):
    card_number = StringField('Card Number', validators=[DataRequired(), Length(min=16, max=16)])
    expiry_date = StringField('Expiry Date (MM/YY)', validators=[DataRequired(), Length(min=5, max=5)])
    cvv = StringField('CVV', validators=[DataRequired(), Length(min=3, max=4)])
    submit = SubmitField('Add Payment Method')

class AccountSettingsForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', validators=[Optional(), EqualTo('new_password')])
    project_updates = BooleanField('Email notifications for project updates')
    security_alerts = BooleanField('Email notifications for security alerts')
    two_factor = BooleanField('Enable Two-Factor Authentication')
    submit = SubmitField('Save Changes')

# Models - Updated for PostgreSQL
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)
    project_updates = db.Column(db.Boolean, default=True)
    security_alerts = db.Column(db.Boolean, default=True)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    api_keys = db.Column(db.JSON, nullable=True, default={})
    
    # Relationships
    subscriptions = db.relationship('Subscription', backref='user', lazy=True, cascade='all, delete-orphan')
    payment_methods = db.relationship('PaymentMethod', backref='user', lazy=True, cascade='all, delete-orphan')
    billing_history = db.relationship('BillingHistory', backref='user', lazy=True, cascade='all, delete-orphan')
    conversations = db.relationship('Conversation', backref='user', lazy=True, cascade='all, delete-orphan')

    def get_id(self):
        return str(self.id)

class Subscription(db.Model):
    __tablename__ = 'subscriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    plan = db.Column(db.String(50), nullable=False, default='Free')
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Active')

class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    card_type = db.Column(db.String(50), nullable=False)
    last_four = db.Column(db.String(4), nullable=False)
    expiry_date = db.Column(db.String(5), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class BillingHistory(db.Model):
    __tablename__ = 'billing_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    invoice_id = db.Column(db.String(100), nullable=True)

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    messages = db.Column(db.JSON, nullable=False)
    project_name = db.Column(db.String(100), nullable=True)
    project_plan = db.Column(db.JSON, nullable=True)

# Initialize login manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))
    except ValueError:
        session.pop('_user_id', None)
        return None

# Utility Functions
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/')
def index():
    return render_template('base.html')

@app.route('/features')
def features():
    return render_template('features.html')

@app.route('/how_its_works')
def how_its_works():
    return render_template('how_its_works.html')

@app.route('/integrations')
def integrations():
    return render_template('integrations.html')

@app.route('/privacy_policy')
def privacy_policy():
    return render_template('privacy_policy.html')

@app.route('/terms_of_service')
def terms_of_service():
    return render_template('terms_of_service.html')

@app.route('/cookie_policy')
def cookie_policy():
    return render_template('cookie_policy.html')

@app.route('/history')
@login_required
def history():
    try:
        conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.timestamp.desc()).all()
        return render_template('history.html', history_items=conversations)
    except Exception as e:
        flash(f'Error loading history: {str(e)}', 'error')
        return render_template('history.html', history_items=[])

@app.route('/examples')
def examples():
    return render_template('examples.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/documentation')
def documentation():
    return render_template('documentation.html')

@app.route('/tutorials')
def tutorials():
    return render_template('tutorials.html')

@app.route('/blog')
def blog():
    return render_template('blog.html')

@app.route('/community')
def community():
    return render_template('community.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            login_user(user, remember=form.remember.data)
            flash('Login successful!', 'success')
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('configure'))
        
        flash('Invalid username or password', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
        elif User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
        else:
            hashed_password = generate_password_hash(password)
            new_user = User(
                username=username,
                email=email,
                password=hashed_password
            )
            db.session.add(new_user)
            db.session.commit()
            new_subscription = Subscription(user_id=new_user.id, plan='Free')
            db.session.add(new_subscription)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    session.pop('config', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    form = ProfileForm()
    
    if request.method == 'GET':
        form.username.data = current_user.username
        form.email.data = current_user.email
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.bio.data = current_user.bio
    
    if form.validate_on_submit():
        try:
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_user and existing_user.id != current_user.id:
                flash('Username already taken', 'error')
                profile_pic_url = url_for('uploaded_file', filename=current_user.profile_picture) if current_user.profile_picture else None
                return render_template('profile.html', form=form, profile_pic_url=profile_pic_url)
            
            existing_email = User.query.filter_by(email=form.email.data).first()
            if existing_email and existing_email.id != current_user.id:
                flash('Email already in use', 'error')
                profile_pic_url = url_for('uploaded_file', filename=current_user.profile_picture) if current_user.profile_picture else None
                return render_template('profile.html', form=form, profile_pic_url=profile_pic_url)

            if 'remove_picture' in request.form and current_user.profile_picture:
                old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_picture)
                if os.path.exists(old_filepath):
                    os.remove(old_filepath)
                current_user.profile_picture = None
            elif form.profile_picture.data:
                file = form.profile_picture.data
                if file and allowed_file(file.filename):
                    if current_user.profile_picture:
                        old_filepath = os.path.join(app.config['UPLOAD_FOLDER'], current_user.profile_picture)
                        if os.path.exists(old_filepath):
                            os.remove(old_filepath)
                    filename = secure_filename(f"{current_user.id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{file.filename.rsplit('.', 1)[1].lower()}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    file.save(filepath)
                    current_user.profile_picture = filename
            
            current_user.username = form.username.data
            current_user.email = form.email.data
            current_user.first_name = form.first_name.data
            current_user.last_name = form.last_name.data
            current_user.bio = form.bio.data
            
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
    
    profile_pic_url = url_for('uploaded_file', filename=current_user.profile_picture) if current_user.profile_picture else None
    return render_template('profile.html', form=form, profile_pic_url=profile_pic_url)

@app.route('/api_key_form', methods=['GET', 'POST'])
@login_required
def api_key_form():
    form = ConfigurationForm()
    
    if form.validate_on_submit():
        model = form.model.data
        api_key = form.api_key.data
        project_name = form.project_name.data
        
        if current_user.api_keys is None:
            current_user.api_keys = {}
        current_user.api_keys[model] = api_key
        db.session.commit()
        
        session['config'] = {
            'model': model,
            'api_key': api_key,
            'project_name': project_name
        }
        
        flash('API key configuration saved successfully!', 'success')
        return redirect(url_for('profile'))
    
    # Populate form with current session config if available
    if session.get('config'):
        form.model.data = session['config'].get('model')
        form.api_key.data = session['config'].get('api_key')
        form.project_name.data = session['config'].get('project_name')
    
    return render_template('api_key_form.html', form=form)

@app.route('/delete_account', methods=['POST'])
@login_required
def delete_account():
    try:
        user = db.session.get(User, current_user.id)
        db.session.delete(user)
        db.session.commit()
        logout_user()
        flash('Your account has been deleted.', 'info')
        return redirect(url_for('index'))
    
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting account: {str(e)}', 'error')
        return redirect(url_for('profile'))

@app.route('/account_settings', methods=['GET', 'POST'])
@login_required
def account_settings():
    form = AccountSettingsForm()
    
    if request.method == 'GET':
        form.project_updates.data = current_user.project_updates
        form.security_alerts.data = current_user.security_alerts
        form.two_factor.data = current_user.two_factor_enabled
    
    if form.validate_on_submit():
        try:
            if form.current_password.data and form.new_password.data:
                if not check_password_hash(current_user.password, form.current_password.data):
                    flash('Current password is incorrect', 'error')
                    profile_pic_url = url_for('uploaded_file', filename=current_user.profile_picture) if current_user.profile_picture else None
                    return render_template('account_settings.html', form=form, profile_pic_url=profile_pic_url)
                current_user.password = generate_password_hash(form.new_password.data)
                flash('Password updated successfully!', 'success')
            
            current_user.project_updates = form.project_updates.data
            current_user.security_alerts = form.security_alerts.data
            current_user.two_factor_enabled = form.two_factor.data
            
            db.session.commit()
            flash('Account settings updated successfully!', 'success')
            return redirect(url_for('account_settings'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating account settings: {str(e)}', 'error')
    
    profile_pic_url = url_for('uploaded_file', filename=current_user.profile_picture) if current_user.profile_picture else None
    return render_template('account_settings.html', form=form, profile_pic_url=profile_pic_url)

@app.route('/configure', methods=['GET', 'POST'])
@login_required
def configure():
    form = ConfigurationForm()
    
    if session.get('config'):
        form.model.data = session['config'].get('model', 'Gemini-Pro')
        form.api_key.data = session['config'].get('api_key', '')
        form.project_name.data = session['config'].get('project_name', 'My-Project')
    
    if form.validate_on_submit():
        model = form.model.data
        api_key = form.api_key.data
        project_name = form.project_name.data
        
        if current_user.api_keys is None:
            current_user.api_keys = {}
        current_user.api_keys[model] = api_key
        db.session.commit()
        
        session['config'] = {
            'model': model,
            'api_key': api_key,
            'project_name': project_name
        }
        
        flash('Configuration saved successfully!', 'success')
        return redirect(url_for('workspace'))
    
    return render_template('configure.html', form=form)

@app.route('/workspace')
@login_required
def workspace():
    if not session.get('config'):
        flash('Please configure your settings first', 'warning')
        return redirect(url_for('configure'))
    profile_pic_url = url_for('uploaded_file', filename=current_user.profile_picture) if current_user.profile_picture else None
    selected_model = session['config'].get('model', 'Gemini-Pro')
    return render_template('workspace.html', profile_pic_url=profile_pic_url, selected_model=selected_model)

@app.route('/api/process', methods=['POST'])
@login_required
def process_prompt():
    if not session.get('config'):
        return jsonify({'error': 'Please configure your settings first'}), 400

    data = request.get_json()
    prompt = data.get('prompt')
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400

    config = session.get('config')
    user_id = current_user.id

    def generate():
        with app.app_context():
            if not user_id:
                yield json.dumps({
                    'type': 'error',
                    'error': 'User not authenticated',
                    'content': 'Sorry, you need to be logged in to process this request.',
                    'status': 'Error occurred'
                }) + "\n"
                return

            conversation = Conversation(
                user_id=user_id,
                messages=[{'role': 'user', 'content': prompt, 'type': 'conversation'}]
            )
            db.session.add(conversation)
            db.session.commit()

            try:
                decision_taker = DecisionTaker(config['model'], config['api_key'])
                decision = decision_taker.execute(prompt)[0]

                conversation.messages = conversation.messages + [{
                    'role': 'assistant',
                    'content': "I'm analyzing your request...",
                    'type': 'conversation'
                }]
                db.session.commit()
                yield json.dumps({
                    'type': 'conversation',
                    'content': "I'm analyzing your request...",
                    'status': 'Starting analysis'
                }) + "\n"

                if decision['function'] == 'ordinary_conversation':
                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': decision['reply'],
                        'type': 'conversation'
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'conversation',
                        'content': decision['reply'],
                        'status': 'Conversation complete'
                    }) + "\n"
                    return

                elif decision['function'] == 'coding_project':
                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Starting project planning...",
                        'type': 'conversation'
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'conversation',
                        'content': "Starting project planning...",
                        'status': 'Planning started'
                    }) + "\n"

                    planner = Planner(config['model'], config['api_key'])
                    generated_plan = planner.execute(prompt)
                    model_reply, planner_json = planner.parse_response(generated_plan)

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Here's the project plan I've created:",
                        'type': 'planner',
                        'data': planner_json
                    }]
                    conversation.project_name = planner_json.get('project', 'Untitled Project')
                    conversation.project_plan = planner_json
                    db.session.commit()
                    yield json.dumps({
                        'type': 'planner',
                        'plan': planner_json,
                        'content': "Here's the project plan I've created:",
                        'status': 'Planning completed'
                    }) + "\n"

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Extracting key concepts for research...",
                        'type': 'conversation'
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'conversation',
                        'content': "Extracting key concepts for research...",
                        'status': 'Extracting keywords'
                    }) + "\n"

                    keyword_extractor = SentenceBert()
                    keywords = keyword_extractor.extract_keywords(prompt)

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': f"Key concepts identified: {', '.join(keywords)}",
                        'type': 'keywords',
                        'data': keywords
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'keywords',
                        'keywords': keywords,
                        'content': f"Key concepts identified: {', '.join(keywords)}",
                        'status': 'Keywords extracted'
                    }) + "\n"

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Researching relevant information...",
                        'type': 'conversation'
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'conversation',
                        'content': "Researching relevant information...",
                        'status': 'Research started'
                    }) + "\n"

                    researcher = Researcher(config['model'], config['api_key'])
                    researcher_output = researcher.execute(
                        generated_plan[generated_plan.index("Plan"):generated_plan.rindex("Summary")],
                        keywords
                    )

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Research completed. Here's what I found:",
                        'type': 'researcher',
                        'data': researcher_output
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'researcher',
                        'keywords': keywords,
                        'research': researcher_output,
                        'content': "Research completed. Here's what I found:",
                        'status': 'Research completed'
                    }) + "\n"

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Gathering detailed information...",
                        'type': 'conversation'
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'conversation',
                        'content': "Gathering detailed information...",
                        'status': 'Executing queries'
                    }) + "\n"

                    queries_result = search_queries(researcher_output["queries"])

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Starting to write the code...",
                        'type': 'conversation'
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'conversation',
                        'content': "Starting to write the code...",
                        'status': 'Coding started'
                    }) + "\n"

                    coder = Coder(config['model'], config['api_key'])
                    coder_output = coder.execute(
                        generated_plan[generated_plan.index("Plan"):generated_plan.rindex("Summary")],
                        prompt,
                        queries_result
                    )

                    print("Coder output:", json.dumps(coder_output, indent=2))

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Code generation completed!",
                        'type': 'coder',
                        'data': coder_output
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'coder',
                        'code': coder_output,
                        'content': "Code generation completed!",
                        'status': 'Coding completed'
                    }) + "\n"

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Finalizing the project...",
                        'type': 'conversation'
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'conversation',
                        'content': "Finalizing the project...",
                        'status': 'Creating project'
                    }) + "\n"

                    files = prepare_coding_files(coder_output)
                    project_creator = ProjectCreator(config['model'], config['api_key'])
                    project_output = project_creator.execute(planner_json["project"], files)

                    print("Project output:", json.dumps(project_output, indent=2))

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "Project successfully created!",
                        'type': 'project',
                        'data': project_output
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'project',
                        'plan': planner_json,
                        'keywords': keywords,
                        'research': researcher_output,
                        'queries_results': queries_result,
                        'code': coder_output,
                        'project': project_output,
                        'content': "Project successfully created!",
                        'status': 'Project completed'
                    }) + "\n"

                    conversation.messages = conversation.messages + [{
                        'role': 'assistant',
                        'content': "You can now download your project files.",
                        'type': 'conversation'
                    }]
                    db.session.commit()
                    yield json.dumps({
                        'type': 'conversation',
                        'content': "You can now download your project files.",
                        'status': 'Ready for download'
                    }) + "\n"

            except Exception as e:
                error_msg = f"Sorry, I encountered an error: {str(e)}"
                print(f"Error in process_prompt: {str(e)}")
                conversation.messages = conversation.messages + [{
                    'role': 'assistant',
                    'content': error_msg,
                    'type': 'error'
                }]
                db.session.commit()
                yield json.dumps({
                    'type': 'error',
                    'error': str(e),
                    'content': error_msg,
                    'status': 'Error occurred'
                }) + "\n"

    return Response(generate(), mimetype='application/json')

@app.route('/api/download_project', methods=['POST'])
@login_required
def download_project():
    try:
        data = request.get_json()
        if not data or not data.get('code'):
            return jsonify({'error': 'No project data provided'}), 400

        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            directories = set()
            
            for file_data in data['code']:
                file_path = file_data['file'].strip()
                file_path = file_data['file'].replace('\\', '/').strip('/')
                
                if not file_path:
                    print(f"Skipping empty file path: {file_data['file']}")
                    continue
                
                if any(part in ('..', '~') for part in file_path.split('/')):
                    print(f"Skipping potentially malicious path: {file_path}")
                    continue
                
                current_path = ''
                for part in file_path.split('/')[:-1]:
                    current_path = f"{current_path}{part}/" if current_path else f"{part}/"
                    directories.add(current_path)
                
                zf.writestr(file_path, file_data['code'])
            
            for directory in sorted(directories):
                zf.writestr(directory, '')
        
        memory_file.seek(0)
        project_name = session.get('config', {}).get('project_name', 'nexa_project')
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'{project_name}.zip'
        )
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/billing', methods=['GET'])
@login_required
def billing():
    try:
        subscription = Subscription.query.filter_by(user_id=current_user.id, status='Active').first()
        if not subscription:
            subscription = Subscription(user_id=current_user.id, plan='Free')
            db.session.add(subscription)
            db.session.commit()

        payment_methods = PaymentMethod.query.filter_by(user_id=current_user.id).all()
        billing_history = BillingHistory.query.filter_by(user_id=current_user.id).order_by(BillingHistory.date.desc()).all()

        return render_template(
            'billing.html',
            subscription=subscription,
            payment_methods=payment_methods,
            billing_history=billing_history
        )
    except Exception as e:
        flash(f'Error loading billing page: {str(e)}', 'error')
        return render_template('billing.html', subscription=None, payment_methods=[], billing_history=[])

@app.route('/api/subscription', methods=['POST'])
@login_required
def update_subscription():
    try:
        data = request.get_json()
        plan = data.get('plan')
        if plan not in ['Free', 'Pro']:
            return jsonify({'error': 'Invalid plan selected'}), 400

        subscription = Subscription.query.filter_by(user_id=current_user.id, status='Active').first()
        if subscription:
            subscription.status = 'Cancelled'
            db.session.add(subscription)
        
        new_subscription = Subscription(
            user_id=current_user.id,
            plan=plan,
            start_date=datetime.utcnow()
        )
        db.session.add(new_subscription)

        if plan == 'Pro':
            billing_entry = BillingHistory(
                user_id=current_user.id,
                description='Pro Plan Subscription',
                amount=29.00,
                invoice_id=f'INV-{current_user.id}-{int(datetime.now().timestamp())}'
            )
            db.session.add(billing_entry)

        db.session.commit()
        flash(f'Successfully updated to {plan} plan!', 'success')
        return jsonify({'message': 'Subscription updated'})
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating subscription: {str(e)}', 'error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/payment_method', methods=['POST'])
@login_required
def add_payment_method():
    form = PaymentMethodForm()
    if form.validate_on_submit():
        try:
            new_payment_method = PaymentMethod(
                user_id=current_user.id,
                card_type='Visa',
                last_four=form.card_number.data[-4:],
                expiry_date=form.expiry_date.data
            )
            db.session.add(new_payment_method)
            db.session.commit()
            flash('Payment method added successfully!', 'success')
            return redirect(url_for('billing'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding payment method: {str(e)}', 'error')
            return redirect(url_for('billing'))
    else:
        flash('Invalid payment method details', 'error')
        return redirect(url_for('billing'))

@app.route('/api/payment_method/<int:id>', methods=['DELETE'])
@login_required
def delete_payment_method(id):
    try:
        payment_method = PaymentMethod.query.filter_by(id=id, user_id=current_user.id).first()
        if not payment_method:
            return jsonify({'error': 'Payment method not found'}), 404
        db.session.delete(payment_method)
        db.session.commit()
        flash('Payment method removed successfully!', 'success')
        return jsonify({'message': 'Payment method deleted'})
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting payment method: {str(e)}', 'error')
        return jsonify({'error': str(e)}), 500

@app.route('/api/billing_history', methods=['GET'])
@login_required
def get_billing_history():
    try:
        billing_history = BillingHistory.query.filter_by(user_id=current_user.id).order_by(BillingHistory.date.desc()).all()
        history_data = [
            {
                'id': item.id,
                'description': item.description,
                'amount': item.amount,
                'date': item.date.strftime('%Y-%m-%d'),
                'invoice_id': item.invoice_id
            }
            for item in billing_history
        ]
        return jsonify(history_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET', 'DELETE'])
@login_required
def manage_history():
    try:
        if request.method == 'GET':
            conversations = Conversation.query.filter_by(user_id=current_user.id).order_by(Conversation.timestamp.desc()).all()
            history_data = [
                {
                    'id': conv.id,
                    'timestamp': conv.timestamp.strftime('%Y-%m-%d %H:%M'),
                    'messages': conv.messages,
                    'project_name': conv.project_name,
                    'project_plan': conv.project_plan
                }
                for conv in conversations
            ]
            return jsonify(history_data)
        elif request.method == 'DELETE':
            Conversation.query.filter_by(user_id=current_user.id).delete()
            db.session.commit()
            return jsonify({'message': 'All history cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history/<int:id>', methods=['GET', 'DELETE'])
@login_required
def manage_conversation(id):
    try:
        conversation = Conversation.query.filter_by(id=id, user_id=current_user.id).first()
        if not conversation:
            return jsonify({'error': 'Conversation not found'}), 404

        if request.method == 'GET':
            return jsonify({
                'id': conversation.id,
                'timestamp': conversation.timestamp.strftime('%Y-%m-%d %H:%M'),
                'messages': conversation.messages,
                'project_name': conversation.project_name,
                'project_plan': conversation.project_plan
            })
        elif request.method == 'DELETE':
            db.session.delete(conversation)
            db.session.commit()
            return jsonify({'message': 'Conversation deleted'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# Add these routes after your existing routes
@app.route('/ide')
@login_required
def ide():
    """Standalone IDE page"""
    profile_pic_url = url_for('uploaded_file', filename=current_user.profile_picture) if current_user.profile_picture else None
    return render_template('nexaIde.html', profile_pic_url=profile_pic_url)

@app.route('/api/ide/save_file', methods=['POST'])
@login_required
def save_ide_file():
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        content = data.get('content')
        
        if not file_path or content is None:
            return jsonify({'error': 'File path and content are required'}), 400
        
        # Store file in user's session or database
        user_files = session.get('user_files', {})
        user_files[file_path] = {
            'content': content,
            'last_modified': datetime.utcnow().isoformat(),
            'user_id': current_user.id
        }
        session['user_files'] = user_files
        
        # In a production environment, you might want to save to database or filesystem
        # For now, we'll use session storage
        
        return jsonify({
            'message': 'File saved successfully', 
            'file_path': file_path,
            'last_modified': user_files[file_path]['last_modified']
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ide/load_files', methods=['GET'])
@login_required
def load_ide_files():
    try:
        # First try to load from session
        user_files = session.get('user_files', {})
        
        print(f"Loaded {len(user_files)} files from session")
        
        # If no files in session, provide empty response
        # The frontend will handle loading workspace project separately
        return jsonify({'files': user_files})
    
    except Exception as e:
        print(f"Error loading IDE files: {str(e)}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/ide/create_file', methods=['POST'])
@login_required
def create_ide_file():
    try:
        data = request.get_json()
        file_name = data.get('file_name')
        content = data.get('content', '')
        
        if not file_name:
            return jsonify({'error': 'File name is required'}), 400
        
        # Validate file name
        if any(char in file_name for char in ['/', '\\', '..']):
            return jsonify({'error': 'Invalid file name'}), 400
        
        user_files = session.get('user_files', {})
        user_files[file_name] = {
            'content': content,
            'last_modified': datetime.utcnow().isoformat(),
            'user_id': current_user.id
        }
        session['user_files'] = user_files
        
        return jsonify({
            'message': 'File created successfully',
            'file_name': file_name
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ide/delete_file', methods=['POST'])
@login_required
def delete_ide_file():
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'error': 'File path is required'}), 400
        
        user_files = session.get('user_files', {})
        if file_path in user_files:
            del user_files[file_path]
            session['user_files'] = user_files
        
        return jsonify({'message': 'File deleted successfully'})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ide/rename_file', methods=['POST'])
@login_required
def rename_ide_file():
    try:
        data = request.get_json()
        old_path = data.get('old_path')
        new_path = data.get('new_path')
        
        if not old_path or not new_path:
            return jsonify({'error': 'Both old and new file paths are required'}), 400
        
        # Validate new file name
        if any(char in new_path for char in ['/', '\\', '..']):
            return jsonify({'error': 'Invalid file name'}), 400
        
        user_files = session.get('user_files', {})
        if old_path in user_files:
            user_files[new_path] = user_files[old_path]
            user_files[new_path]['last_modified'] = datetime.utcnow().isoformat()
            del user_files[old_path]
            session['user_files'] = user_files
        
        return jsonify({
            'message': 'File renamed successfully',
            'new_path': new_path
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ide/download_file', methods=['POST'])
@login_required
def download_ide_file():
    try:
        data = request.get_json()
        file_path = data.get('file_path')
        
        if not file_path:
            return jsonify({'error': 'File path is required'}), 400
        
        user_files = session.get('user_files', {})
        if file_path not in user_files:
            return jsonify({'error': 'File not found'}), 404
        
        content = user_files[file_path]['content']
        
        # Create in-memory file
        output = io.BytesIO()
        output.write(content.encode('utf-8'))
        output.seek(0)
        
        return send_file(
            output,
            mimetype='text/plain',
            as_attachment=True,
            download_name=file_path
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ide/load_workspace_project', methods=['POST'])
@login_required
def load_workspace_project():
    """Load the most recent workspace project into the IDE"""
    try:
        # Get the most recent conversation with project data
        conversation = Conversation.query.filter_by(
            user_id=current_user.id
        ).order_by(Conversation.timestamp.desc()).first()
        
        if not conversation:
            return jsonify({'error': 'No project data found. Please create a project in the workspace first.'}), 404
        
        print(f"Found conversation: {conversation.id}, Project: {conversation.project_name}")
        
        user_files = {}
        files_loaded = 0
        
        # Method 1: Extract from coder data - handle both list and dict formats
        for message in conversation.messages:
            if message.get('type') == 'coder' and message.get('data'):
                coder_data = message['data']
                print(f"Coder data type: {type(coder_data)}")
                print(f"Coder data: {coder_data}")
                
                # Handle list format
                if isinstance(coder_data, list):
                    for file_item in coder_data:
                        if isinstance(file_item, dict):
                            file_path = file_item.get('file')
                            file_code = file_item.get('code')
                            
                            if file_path and file_code is not None:
                                file_path = clean_file_path(file_path)
                                user_files[file_path] = {
                                    'content': file_code,
                                    'last_modified': datetime.utcnow().isoformat(),
                                    'user_id': current_user.id
                                }
                                files_loaded += 1
                                print(f"Loaded from coder list: {file_path}")
                
                # Handle dict format with 'code' key containing list
                elif isinstance(coder_data, dict) and coder_data.get('code'):
                    for file_item in coder_data['code']:
                        if isinstance(file_item, dict):
                            file_path = file_item.get('file')
                            file_code = file_item.get('code')
                            
                            if file_path and file_code is not None:
                                file_path = clean_file_path(file_path)
                                user_files[file_path] = {
                                    'content': file_code,
                                    'last_modified': datetime.utcnow().isoformat(),
                                    'user_id': current_user.id
                                }
                                files_loaded += 1
                                print(f"Loaded from coder dict: {file_path}")
        
        # Method 2: Extract from project data
        if not user_files:
            for message in conversation.messages:
                if message.get('type') == 'project' and message.get('data'):
                    project_data = message['data']
                    if isinstance(project_data, dict) and project_data.get('code'):
                        for file_item in project_data['code']:
                            if isinstance(file_item, dict) and file_item.get('file') and file_item.get('code'):
                                file_path = clean_file_path(file_item['file'])
                                user_files[file_path] = {
                                    'content': file_item['code'],
                                    'last_modified': datetime.utcnow().isoformat(),
                                    'user_id': current_user.id
                                }
                                files_loaded += 1
                                print(f"Loaded from project: {file_path}")
        
        # Method 3: Extract from conversation project_plan
        if not user_files and conversation.project_plan:
            # Create basic project structure from plan
            project_name = conversation.project_name or "workspace_project"
            user_files['README.md'] = {
                'content': f"# {project_name}\n\n## Project Plan\n\n{json.dumps(conversation.project_plan, indent=2)}",
                'last_modified': datetime.utcnow().isoformat(),
                'user_id': current_user.id
            }
            files_loaded += 1
        
        if user_files:
            session['user_files'] = user_files
            session.modified = True
            print(f"Session saved with {len(user_files)} files: {list(user_files.keys())}")  # Debug log
            return jsonify({
                'message': f'Loaded {files_loaded} files from workspace project',
                'files': user_files,
                'count': files_loaded,
                'project_name': conversation.project_name
            })
        else:
            return jsonify({'error': 'No code files found in the workspace project. Create sample files in IDE.'}), 404  # Updated message
            
    except Exception as e:
        print(f"Error loading workspace project: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Failed to load project: {str(e)}'}), 500
    
def clean_file_path(file_path):
    """Clean and normalize file path"""
    if not file_path:
        return "untitled.txt"
    
    # Convert to string and handle the specific format from your logs
    file_path = str(file_path).strip()
    
    # Remove backticks, quotes from both ends
    file_path = file_path.strip('`').strip('"').strip("'")
    
    # Normalize slashes
    file_path = file_path.replace('\\', '/').strip()
    
    # Remove leading/trailing slashes
    file_path = file_path.strip('/')
    
    # Keep src/ prefix for better organization
    if file_path.startswith('src/') and '/' in file_path:
        # Already has src/ prefix, keep it
        pass
    elif not file_path.startswith('src/') and file_path.count('/') > 0:
        # Has subdirectories but no src/, add it
        file_path = f"src/{file_path}"
    
    # Ensure we have a valid filename
    if not file_path or file_path == '.' or file_path == '..':
        return "untitled.txt"
    
    # Add appropriate extension if missing
    if '.' not in file_path.split('/')[-1]:
        # Try to detect file type from common patterns
        if file_path.endswith('/src') or 'src/' in file_path:
            file_path += '/index.html'
        else:
            file_path += '.txt'
    
    return file_path

def extract_files_from_conversation_text(conversation):
    """Alternative method to extract files from conversation text"""
    try:
        user_files = {}
        files_loaded = 0
        
        for message in conversation.messages:
            content = message.get('content', '')
            # Look for code blocks in the content
            if '```' in content:
                lines = content.split('\n')
                current_file = None
                current_content = []
                in_code_block = False
                language = None
                
                for line in lines:
                    line = line.rstrip()
                    if line.strip().startswith('```'):
                        if in_code_block and current_file and current_content:
                            # Save the file
                            file_content = '\n'.join(current_content)
                            user_files[current_file] = {
                                'content': file_content,
                                'last_modified': datetime.utcnow().isoformat(),
                                'user_id': current_user.id
                            }
                            files_loaded += 1
                            print(f"Extracted file from text: {current_file}")
                            current_file = None
                            current_content = []
                        in_code_block = not in_code_block
                        if in_code_block:
                            # Check if line has filename after ```
                            marker = line.strip()[3:].strip()
                            if marker and not marker.startswith('`'):
                                # Use the marker as filename hint
                                current_file = clean_file_path(marker)
                                language = marker.split('.')[-1] if '.' in marker else None
                    elif in_code_block:
                        if not current_file:
                            # Generate a filename based on language or index
                            ext_map = {
                                'python': 'py', 'javascript': 'js', 'html': 'html',
                                'css': 'css', 'java': 'java', 'cpp': 'cpp', 'c': 'c',
                                'php': 'php', 'ruby': 'rb', 'go': 'go', 'rust': 'rs',
                                'sql': 'sql', 'json': 'json', 'xml': 'xml', 'yaml': 'yml',
                                'markdown': 'md', 'txt': 'txt'
                            }
                            ext = ext_map.get(language, 'txt') if language else 'txt'
                            current_file = f"extracted_file_{files_loaded + 1}.{ext}"
                        current_content.append(line)
        
        if user_files:
            session['user_files'] = user_files
            return jsonify({
                'message': f'Extracted {files_loaded} files from conversation text',
                'files': user_files,
                'count': files_loaded
            })
        else:
            # Last resort: create a basic file from the project plan
            return create_fallback_files(conversation)
            
    except Exception as e:
        print(f"Error in alternative extraction: {str(e)}")
        return create_fallback_files(conversation)

def create_fallback_files(conversation):
    """Create fallback files when no code is found"""
    try:
        user_files = {}
        project_name = conversation.project_name or "Untitled Project"
        
        # Create a basic README
        user_files['README.md'] = {
            'content': f"# {project_name}\n\nProject created in Nexa Workspace.\n\n## Description\n\nThis project was automatically generated from your workspace conversation.\n\n## Next Steps\n\n1. Add your code files\n2. Customize this README\n3. Start coding!",
            'last_modified': datetime.utcnow().isoformat(),
            'user_id': current_user.id
        }
        
        # Create a basic Python file
        user_files['main.py'] = {
            'content': f'#!/usr/bin/env python3\n"""\n{project_name}\nGenerated from Nexa Workspace\n"""\n\nprint("Hello from {project_name}!")\n',
            'last_modified': datetime.utcnow().isoformat(),
            'user_id': current_user.id
        }
        
        session['user_files'] = user_files
        
        return jsonify({
            'message': f'Created fallback files for project "{project_name}"',
            'files': user_files,
            'count': len(user_files),
            'fallback': True
        })
        
    except Exception as e:
        print(f"Error creating fallback files: {str(e)}")
        return jsonify({'error': 'No project files could be loaded or created'}), 404
    
@app.route('/api/ide/export_project', methods=['POST'])
@login_required
def export_ide_project():
    try:
        data = request.get_json()
        files = data.get('files', {})
        
        if not files:
            return jsonify({'error': 'No files to export'}), 400
        
        # Create zip file in memory
        memory_file = io.BytesIO()
        with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
            for file_path, file_data in files.items():
                zf.writestr(file_path, file_data.get('content', ''))
        
        memory_file.seek(0)
        
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name='nexa_ide_project.zip'
        )
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
with app.app_context():
    try:
        db.create_all()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating database tables: {e}")
        print("You may need to create the tables manually in your PostgreSQL database")

# Run the application
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)