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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '958932d67f8decd00598e34a9064b63b5c22e0f8a36e595c014490a6e388eb01')
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static/uploads')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
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

# Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    first_name = db.Column(db.String(50), nullable=True)
    last_name = db.Column(db.String(50), nullable=True)
    bio = db.Column(db.String(500), nullable=True)
    profile_picture = db.Column(db.String(255), nullable=True)
    project_updates = db.Column(db.Boolean, default=True)
    security_alerts = db.Column(db.Boolean, default=True)
    two_factor_enabled = db.Column(db.Boolean, default=False)
    api_keys = db.Column(db.JSON, nullable=True, default={})
    subscriptions = db.relationship('Subscription', backref='user', lazy=True)
    payment_methods = db.relationship('PaymentMethod', backref='user', lazy=True)
    billing_history = db.relationship('BillingHistory', backref='user', lazy=True)
    conversations = db.relationship('Conversation', backref='user', lazy=True)

    def get_id(self):
        return str(self.id)

class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    plan = db.Column(db.String(50), nullable=False, default='Free')
    start_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    end_date = db.Column(db.DateTime, nullable=True)
    status = db.Column(db.String(20), nullable=False, default='Active')

class PaymentMethod(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    card_type = db.Column(db.String(50), nullable=False)
    last_four = db.Column(db.String(4), nullable=False)
    expiry_date = db.Column(db.String(5), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

class BillingHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    description = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    invoice_id = db.Column(db.String(100), nullable=True)

class Conversation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
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

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)