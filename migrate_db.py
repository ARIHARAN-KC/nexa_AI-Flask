# migrate_db.py
import sqlite3
import psycopg2
import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def migrate_sqlite_to_postgres():
    # Get database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    
    if not database_url:
        print("DATABASE_URL environment variable not set")
        print("Please make sure you have a .env file with DATABASE_URL")
        return
    
    print(f"Using database URL: {database_url}")
    
    # SQLite connection
    sqlite_conn = sqlite3.connect('users.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # PostgreSQL connection - use the URL directly
    try:
        pg_conn = psycopg2.connect(database_url)
        pg_cursor = pg_conn.cursor()
        
        print("Connected to PostgreSQL database successfully")
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return
    
    try:
        # First, check if tables exist in PostgreSQL
        print("Checking if tables exist in PostgreSQL...")
        tables_to_check = ['users', 'subscriptions', 'payment_methods', 'billing_history', 'conversations']
        
        for table in tables_to_check:
            try:
                pg_cursor.execute(f"SELECT 1 FROM {table} LIMIT 1")
                print(f"✓ Table {table} exists")
            except Exception as e:
                print(f"✗ Table {table} does not exist: {e}")
                print("Please run 'flask db upgrade' first to create the tables")
                return
        
        # Clear existing data from PostgreSQL tables
        print("Clearing existing data from PostgreSQL tables...")
        for table in tables_to_check:
            try:
                pg_cursor.execute(f"DELETE FROM {table}")
                print(f"Cleared {table} table")
            except Exception as e:
                print(f"Could not clear {table}: {e}")
        
        pg_conn.commit()
        
        # Check what tables exist in SQLite
        print("Checking SQLite tables...")
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        sqlite_tables = [table[0] for table in sqlite_cursor.fetchall()]
        print(f"SQLite tables: {sqlite_tables}")
        
        # Migrate Users table (SQLite table name might be 'user' instead of 'users')
        print("Migrating users table...")
        sqlite_table_name = 'user' if 'user' in sqlite_tables else 'users'
        sqlite_cursor.execute(f"SELECT * FROM {sqlite_table_name}")
        users = sqlite_cursor.fetchall()
        
        for user in users:
            # Handle JSON data conversion
            api_keys = user[11] if len(user) > 11 else None
            if api_keys and isinstance(api_keys, str):
                try:
                    api_keys = json.loads(api_keys)
                except:
                    api_keys = {}
            elif api_keys is None:
                api_keys = {}
            
            pg_cursor.execute("""
                INSERT INTO users (id, username, email, password, first_name, last_name, 
                                 bio, profile_picture, project_updates, security_alerts, 
                                 two_factor_enabled, api_keys)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                user[0], user[1], user[2], user[3], user[4], user[5],
                user[6], user[7], bool(user[8]), bool(user[9]), bool(user[10]), api_keys
            ))
        
        print(f"Migrated {len(users)} users")
        
        # Migrate Subscriptions table
        print("Migrating subscriptions table...")
        sqlite_table_name = 'subscription' if 'subscription' in sqlite_tables else 'subscriptions'
        sqlite_cursor.execute(f"SELECT * FROM {sqlite_table_name}")
        subscriptions = sqlite_cursor.fetchall()
        
        for sub in subscriptions:
            pg_cursor.execute("""
                INSERT INTO subscriptions (id, user_id, plan, start_date, end_date, status)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, sub)
        
        print(f"Migrated {len(subscriptions)} subscriptions")
        
        # Migrate PaymentMethods table
        print("Migrating payment_methods table...")
        sqlite_table_name = 'payment_method' if 'payment_method' in sqlite_tables else 'payment_methods'
        sqlite_cursor.execute(f"SELECT * FROM {sqlite_table_name}")
        payment_methods = sqlite_cursor.fetchall()
        
        for pm in payment_methods:
            pg_cursor.execute("""
                INSERT INTO payment_methods (id, user_id, card_type, last_four, expiry_date, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, pm)
        
        print(f"Migrated {len(payment_methods)} payment methods")
        
        # Migrate BillingHistory table
        print("Migrating billing_history table...")
        sqlite_table_name = 'billing_history'
        sqlite_cursor.execute(f"SELECT * FROM {sqlite_table_name}")
        billing_history = sqlite_cursor.fetchall()
        
        for bh in billing_history:
            pg_cursor.execute("""
                INSERT INTO billing_history (id, user_id, description, amount, date, invoice_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, bh)
        
        print(f"Migrated {len(billing_history)} billing history records")
        
        # Migrate Conversations table
        print("Migrating conversations table...")
        sqlite_table_name = 'conversation' if 'conversation' in sqlite_tables else 'conversations'
        sqlite_cursor.execute(f"SELECT * FROM {sqlite_table_name}")
        conversations = sqlite_cursor.fetchall()
        
        for conv in conversations:
            # Handle JSON data conversion
            messages = conv[3] if len(conv) > 3 else None
            if messages and isinstance(messages, str):
                try:
                    messages = json.loads(messages)
                except:
                    messages = []
            elif messages is None:
                messages = []
            
            project_plan = conv[5] if len(conv) > 5 else None
            if project_plan and isinstance(project_plan, str):
                try:
                    project_plan = json.loads(project_plan)
                except:
                    project_plan = None
            
            pg_cursor.execute("""
                INSERT INTO conversations (id, user_id, timestamp, messages, project_name, project_plan)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                conv[0], conv[1], conv[2], messages, 
                conv[4] if len(conv) > 4 else None, 
                project_plan
            ))
        
        print(f"Migrated {len(conversations)} conversations")
        
        pg_conn.commit()
        print("Migration completed successfully!")
        
    except Exception as e:
        pg_conn.rollback()
        print(f"Error during migration: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        sqlite_conn.close()
        pg_conn.close()

if __name__ == "__main__":
    migrate_sqlite_to_postgres()