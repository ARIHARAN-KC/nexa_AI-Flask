import os
from app import app, db

with app.app_context():
    db.create_all()
    print("Database initialized successfully")