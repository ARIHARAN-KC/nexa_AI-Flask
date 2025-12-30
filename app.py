from flask import Flask, json, render_template, request, jsonify, send_file, session, redirect, url_for, flash, Response, send_from_directory,stream_with_context
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
from datetime import datetime, UTC
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import json
from urllib.parse import urlparse
import subprocess,sys
from dotenv import load_dotenv
from s3.s3_client import allowed_file, get_profile_pic_url, upload_profile_picture, delete_profile_picture,upload_project_file,list_project_files,delete_project_file,get_project_file_content,save_full_project
import logging

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') 
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
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5 MB

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
        Optional(),
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
    start_date = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    end_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Active')

class PaymentMethod(db.Model):
    __tablename__ = 'payment_methods'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    card_type = db.Column(db.String(50), nullable=False)
    last_four = db.Column(db.String(4), nullable=False)
    expiry_date = db.Column(db.String(5), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))

class BillingHistory(db.Model):
    __tablename__ = 'billing_history'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.now(UTC))
    invoice_id = db.Column(db.String(100), nullable=True)

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    messages = db.Column(db.JSON, nullable=False)
    project_name = db.Column(db.String(100), nullable=True)
    project_plan = db.Column(db.JSON, nullable=True)

class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)

    s3_prefix = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(UTC))
    updated_at = db.Column(
    db.DateTime,
    default=lambda: datetime.now(UTC),
    onupdate=lambda: datetime.now(UTC)
)

    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=True)

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

@app.route("/api/workspace/load_project", methods=["POST"])
@login_required
def load_workspace_project():
    data = request.get_json()
    project_name = data.get("project_name")

    if not project_name:
        return jsonify({"error": "Project name required"}), 400

    files = list_project_files(
        user_id=current_user.id,
        project_id=project_name
    )

    if not files:
        return jsonify({"error": "Project not found"}), 404

    # Store active project in session
    session["active_project"] = project_name
    session.modified = True

    return jsonify({
        "project": project_name,
        "files": files
    })

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

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm()

    if form.validate_on_submit():

        try:
            file = request.files.get("profile_picture")

            if request.form.get("remove_picture") == "1":
                if current_user.profile_picture:
                    delete_profile_picture(current_user.profile_picture)
                    current_user.profile_picture = None

            # UPLOAD PROFILE PICTURE
            elif file and file.filename:
                # Debug size (IMPORTANT)
                file.stream.seek(0, os.SEEK_END)
                size = file.stream.tell()
                file.stream.seek(0)
                print(f"Processing file upload: {file.filename}, size: {size}")

                if size == 0:
                    raise ValueError("Uploaded file is empty")

                filename = upload_profile_picture(file, current_user.id)

                # Delete old pic
                if current_user.profile_picture:
                    delete_profile_picture(current_user.profile_picture)

                current_user.profile_picture = filename

            # Update other fields
            current_user.username = form.username.data
            current_user.email = form.email.data
            current_user.first_name = form.first_name.data
            current_user.last_name = form.last_name.data
            current_user.bio = form.bio.data

            db.session.commit()
            flash("Profile updated successfully", "success")

        except Exception as e:
            print("Upload error:", e)
            flash(str(e), "danger")

        return redirect(url_for("profile"))

    profile_pic_url = get_profile_pic_url(current_user.profile_picture)

    return render_template(
        "profile.html",
        form=form,
        profile_pic_url=profile_pic_url,
    )

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
                    return render_template('account_settings.html', form=form, profile_pic_url=get_profile_pic_url(current_user.profile_picture))
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

    return render_template('account_settings.html', form=form, profile_pic_url=get_profile_pic_url(current_user.profile_picture))

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

    profile_pic_url = (
        get_profile_pic_url(current_user.profile_picture)
        if current_user.profile_picture else None
    )

    selected_model = session['config'].get('model', 'Gemini-Pro')

    last_project = (
        Project.query
        .filter_by(user_id=current_user.id)
        .order_by(Project.updated_at.desc())
        .first()
    )

    if last_project:
        session["active_project"] = last_project.name
        session.modified = True

    return render_template(
        'workspace.html',
        profile_pic_url=profile_pic_url,
        selected_model=selected_model
    )

@app.route('/api/process', methods=['POST'])
@login_required
def process_prompt():
    """Processes user prompt for conversation, coding, or project planning in a streaming response."""
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
                    'content': 'Please log in to continue.',
                    'status': 'Error occurred'
                }) + "\n"
                return

            # -------------------------
            # Initialize conversation
            # -------------------------
            conversation = Conversation(
                user_id=user_id,
                messages=[{
                    'role': 'user',
                    'content': prompt,
                    'type': 'conversation'
                }]
            )
            db.session.add(conversation)
            db.session.commit()

            # -------------------------
            # Decision
            # -------------------------
            try:
                decision_taker = DecisionTaker(config['model'], config['api_key'])
                decision_list = decision_taker.execute(prompt)
                decision = decision_list[0] if decision_list else None
            except Exception as e:
                logger.error("DecisionTaker failed: %s", e)
                decision = None

            if not decision:
                decision = {
                    'function': 'ordinary_conversation',
                    'reply': "I couldn't analyze the prompt fully."
                }

            # -------------------------
            # Ordinary conversation
            # -------------------------
            if decision['function'] == 'ordinary_conversation':
                conversation.messages.append({
                    'role': 'assistant',
                    'content': decision['reply'],
                    'type': 'conversation'
                })
                db.session.commit()
                yield json.dumps({
                    'type': 'conversation',
                    'content': decision['reply'],
                    'status': 'Conversation complete'
                }) + "\n"
                return

            # -------------------------
            # Coding/project flow
            # -------------------------
            if decision['function'] == 'coding_project':
                yield json.dumps({'type': 'conversation', 'content': "Starting project planning..."}) + "\n"

                # -------- Planner --------
                try:
                    planner = Planner(config['model'], config['api_key'])
                    model_reply, planner_json = planner.execute(prompt)
                except Exception as e:
                    logger.error("Planner failed: %s", e)
                    planner_json = {}
                    model_reply = "Planner failed"

                yield json.dumps({'type': 'planner', 'plan': planner_json, 'content': "Project plan generated."}) + "\n"

                # -------- Keywords --------
                try:
                    keyword_extractor = SentenceBert()
                    keywords = keyword_extractor.extract_keywords(prompt)
                except Exception as e:
                    logger.error("Keyword extraction failed: %s", e)
                    keywords = []

                yield json.dumps({'type': 'keywords', 'keywords': keywords, 'content': f"Key concepts: {', '.join(keywords)}"}) + "\n"

                # -------- Research --------
                try:
                    researcher = Researcher(config['model'], config['api_key'])
                    researcher_output = researcher.execute(planner_json.get("plans", {}), keywords)
                except Exception as e:
                    logger.error("Researcher failed: %s", e)
                    researcher_output = {"queries": [], "ask_user": ""}

                yield json.dumps({'type': 'researcher', 'research': researcher_output, 'content': "Research completed."}) + "\n"

                # -------- Search --------
                try:
                    queries_result = search_queries(researcher_output.get("queries", []))
                    if not isinstance(queries_result, dict):
                        queries_result = {}
                except Exception as e:
                    logger.error("Search queries failed: %s", e)
                    queries_result = {}

                # -------- Code generation --------
                try:
                    coder = Coder(config['model'], config['api_key'])
                    coder_output = coder.execute(planner_json.get("plans", {}), prompt, queries_result)
                    if not isinstance(coder_output, list):
                        coder_output = []
                except Exception as e:
                    logger.error("Coder failed: %s", e)
                    coder_output = []

                yield json.dumps({'type': 'coder', 'code': coder_output, 'content': "Code generation completed!"}) + "\n"

                # -------- Project creation --------
                try:
                    files = prepare_coding_files(coder_output)
                    project_creator = ProjectCreator(config['model'], config['api_key'])
                    project_output = project_creator.execute(planner_json.get("project", "Untitled Project"), files)
                except Exception as e:
                    logger.error("Project creation failed: %s", e)
                    project_output = {}

                # -------------------------
                # Save project (DB + S3)
                # -------------------------
                try:
                    project_name = planner_json.get("project") or session["config"].get("project_name") or f"project-{conversation.id}"
                    project = Project(user_id=user_id, name=project_name, s3_prefix=f"projects/{user_id}/{project_name}/", conversation_id=conversation.id)
                    db.session.add(project)
                    db.session.commit()

                    for file_path, content in project_output.get("files", {}).items():
                        upload_project_file(user_id=user_id, project_id=project_name, file_path=file_path, content=content)

                    save_full_project(user_id=user_id, project_id=project_name, files={}, metadata={
                        "project_name": project_name,
                        "model": config["model"],
                        "created_at": datetime.now(UTC).isoformat(),
                        "conversation_id": conversation.id
                    })
                    session["active_project"] = project_name
                    session.modified = True
                except Exception as e:
                    logger.error("Saving project failed: %s", e)

                # -------- Final response --------
                yield json.dumps({
                    'type': 'project',
                    'plan': planner_json,
                    'keywords': keywords,
                    'research': researcher_output,
                    'queries_results': queries_result,
                    'code': coder_output,
                    'project': project_output,
                    'content': "Project successfully created!"
                }) + "\n"

                yield json.dumps({'type': 'conversation', 'content': "You can now open this project in the IDE."}) + "\n"

    return Response(stream_with_context(generate()), mimetype='application/json')

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
                file_path = clean_file_path(file_data['file'])
                
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
            start_date=datetime.now(UTC)
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

@app.route("/history")
@login_required
def history():
    history_items = (
        Conversation.query
        .filter_by(user_id=current_user.id)
        .order_by(Conversation.timestamp.desc())
        .all()
    )

    return render_template(
        "history.html",
        history_items=history_items
    )

@app.route('/api/history/<int:conversation_id>', methods=['GET', 'DELETE'])
@login_required
def manage_conversation(conversation_id):
    conversation = Conversation.query.filter_by(
        id=conversation_id,
        user_id=current_user.id
    ).first_or_404()

    # GET → Load conversation into workspace
    if request.method == 'GET':
        return jsonify({
            'id': conversation.id,
            'timestamp': conversation.timestamp.strftime('%Y-%m-%d %H:%M'),
            'messages': conversation.messages,
            'project_name': conversation.project_name,
            'project_plan': conversation.project_plan
        })

    # DELETE → Delete one conversation
    db.session.delete(conversation)
    db.session.commit()
    return jsonify({'message': 'Conversation deleted'}), 204

@app.route("/api/history", methods=["DELETE"])
@login_required
def clear_history():
    Conversation.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    return jsonify({'message': 'All history cleared'}), 204

@app.route('/ide')
@login_required
def ide():
    profile_pic_url = (
        get_profile_pic_url(current_user.profile_picture)
        if current_user.profile_picture else None
    )

    # Just render IDE — frontend will fetch files from S3
    return render_template('nexaIde.html', profile_pic_url=profile_pic_url)

def load_workspace_project_internal(user_id, project_id):
    """
    Check if user has any project files in S3
    """
    files = list_project_files(user_id, project_id)
    return bool(files)
    
@app.route("/api/ide/save_file", methods=["POST"])
@login_required
def save_ide_file():
    data = request.get_json()

    upload_project_file(
        user_id=current_user.id,
        project_id=session["active_project"],
        file_path=data["file_path"],
        content=data["content"]
    )

    return jsonify({"message": "Saved"})


@app.route('/api/ide/load_files', methods=['GET'])
@login_required
def load_ide_files():
    project_id = session.get("config", {}).get("project_name", "default_project")

    files = list_project_files(
        user_id=current_user.id,
        project_id=project_id
    )

    return jsonify({"files": files})

@app.route('/api/ide/files', methods=['GET', 'POST', 'PUT', 'DELETE'])
@login_required
def manage_ide_files():
    try:
        if request.method == 'GET':
            files = list_project_files(current_user.id)
            return jsonify({
                'files': files,
                'count': len(files)
            })

        elif request.method == 'POST':
            data = request.get_json()
            file_path = data.get('file_path')
            content = data.get('content', '')

            if not file_path:
                return jsonify({'error': 'File path is required'}), 400

            if any(x in file_path for x in ['..', '~']):
                return jsonify({'error': 'Invalid file path'}), 400

            upload_project_file(file_path, content, current_user.id)

            return jsonify({
                'message': 'File created successfully',
                'file_path': file_path,
                'last_modified': datetime.now(UTC).isoformat()
            })

        elif request.method == 'PUT':
            data = request.get_json()
            file_path = data.get('file_path')
            content = data.get('content')

            if not file_path or content is None:
                return jsonify({'error': 'File path and content are required'}), 400

            upload_project_file(file_path, content, current_user.id)

            return jsonify({
                'message': 'File updated successfully',
                'file_path': file_path,
                'last_modified': datetime.now(UTC).isoformat()
            })

        elif request.method == 'DELETE':
            data = request.get_json()
            file_path = data.get('file_path')

            if not file_path:
                return jsonify({'error': 'File path is required'}), 400

            delete_project_file(file_path, current_user.id)

            return jsonify({'message': 'File deleted successfully'})

    except Exception as e:
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
            'last_modified':datetime.now(UTC).isoformat(),
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
    data = request.get_json()
    file_path = data.get("file_path")
    project_id = session.get("active_project")

    delete_project_file(
        current_user.id,
        project_id,
        file_path
    )

    return jsonify({"message": "File deleted"})

@app.route('/api/ide/rename_file', methods=['POST'])
@login_required
def rename_ide_file():
    data = request.get_json()
    old_path = data["old_path"]
    new_path = data["new_path"]
    project_id = session.get("config", {}).get("project_name")

    content = get_project_file_content(
        current_user.id,
        project_id,
        old_path
    )

    upload_project_file(
        current_user.id,
        project_id,
        new_path,
        content
    )

    delete_project_file(
        current_user.id,
        project_id,
        old_path
    )

    return jsonify({"message": "Renamed successfully"})


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

# @app.route('/api/ide/load_workspace_project', methods=['POST'])
# @login_required
# def load_workspace_project():
#     try:
#         files = list_project_files(current_user.id)

#         if files:
#             return jsonify({
#                 'message': f'Loaded {len(files)} files from workspace',
#                 'files': files,
#                 'count': len(files)
#             })

#         return create_sample_project_structure()

#     except Exception as e:
#         return jsonify({'error': str(e)}), 500
    
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
                                'last_modified': datetime.now(UTC).isoformat(),
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
            'last_modified': datetime.now(UTC).isoformat(),
            'user_id': current_user.id
        }
        
        # Create a basic Python file
        user_files['main.py'] = {
            'content': f'#!/usr/bin/env python3\n"""\n{project_name}\nGenerated from Nexa Workspace\n"""\n\nprint("Hello from {project_name}!")\n',
            'last_modified': datetime.now(UTC).isoformat(),
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

def create_sample_project_structure():
    """Create sample project structure when no workspace project exists"""
    try:
        user_files = {
            'README.md': {
                'content': '# Welcome to Nexa IDE\n\n## Getting Started\n\n1. Create new files using the "New File" button\n2. Edit files in the code editor\n3. Save your work using Ctrl+S\n4. Use the terminal for file operations\n\n## Sample Project Structure\n\nThis is a sample project created for you to get started.',
                'last_modified': datetime.now(UTC).isoformat(),
                'user_id': current_user.id
            },
            'main.py': {
                'content': '#!/usr/bin/env python3\n"""\nMain application file\nCreated in Nexa IDE\n"""\n\nprint("Hello from Nexa IDE!")\n\nclass Project:\n    def __init__(self, name):\n        self.name = name\n    \n    def run(self):\n        print(f"Running {self.name}...")\n        return "Success!"\n\nif __name__ == "__main__":\n    project = Project("Nexa IDE Demo")\n    result = project.run()\n    print(f"Result: {result}")',
                'last_modified': datetime.now(UTC).isoformat(),
                'user_id': current_user.id
            },
            'styles.css': {
                'content': '/* Main stylesheet */\nbody {\n    font-family: Arial, sans-serif;\n    margin: 0;\n    padding: 20px;\n    background-color: #f5f5f5;\n}\n\n.container {\n    max-width: 1200px;\n    margin: 0 auto;\n    background: white;\n    padding: 20px;\n    border-radius: 8px;\n    box-shadow: 0 2px 4px rgba(0,0,0,0.1);\n}',
                'last_modified': datetime.now(UTC).isoformat(),
                'user_id': current_user.id
            }
        }
        
        session['user_files'] = user_files
        session.modified = True
        
        return jsonify({
            'message': 'Created sample project structure',
            'files': user_files,
            'count': len(user_files),
            'sample': True
        })
        
    except Exception as e:
        return jsonify({'error': f'Failed to create sample project: {str(e)}'}), 500
    
@app.route('/api/ide/export_project', methods=['POST'])
@login_required
def export_ide_project():
    project_id = session.get("config", {}).get("project_name")

    files = list_project_files(
        current_user.id,
        project_id
    )

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for path, data in files.items():
            zf.writestr(path, data["content"])

    memory_file.seek(0)

    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{project_id}.zip"
    )

# Initialize database
with app.app_context():
    try:
        db.create_all()
        print("Database tables created successfully")
    except Exception as e:
        print(f"Error creating database tables: {e}")
        print("You may need to create the tables manually in your PostgreSQL database")

#S3 setup
def run_s3_setup():
    try:
        print("Running S3 setup...")
        subprocess.run(
            ["yarn", "init:s3"],
            check=True,
            shell=True
        )
        print("S3 initialized")
    except subprocess.CalledProcessError as e:
        print("S3 setup failed")
        sys.exit(1)

# Run the application
if __name__ == "__main__":
    run_s3_setup() #s3 setup
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
