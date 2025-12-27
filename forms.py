from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SelectField, SubmitField, TextAreaField, FileField
from wtforms.validators import DataRequired, Length, Email, EqualTo, Optional
from flask_wtf.file import FileAllowed

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')
    submit = SubmitField('Login')

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
    submit = SubmitField('Update Profile')

class PaymentMethodForm(FlaskForm):
    card_number = StringField('Card Number', validators=[DataRequired(), Length(min=16, max=16)])
    expiry_date = StringField('Expiry Date (MM/YY)', validators=[DataRequired(), Length(min=5, max=5)])
    cvv = StringField('CVV', validators=[DataRequired(), Length(min=3, max=4)])
    submit = SubmitField('Add Payment Method')

class AccountSettingsForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[Optional()])
    new_password = PasswordField('New Password', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirm New Password', 
                                    validators=[Optional(), EqualTo('new_password')])
    project_updates = BooleanField('Email notifications for project updates')
    security_alerts = BooleanField('Email notifications for security alerts')
    two_factor = BooleanField('Enable Two-Factor Authentication')
    submit = SubmitField('Save Changes')