import sqlite3
import os
import argparse
import sys
from datetime import datetime

# Passlib/bcrypt for password hashing
try:
    from passlib.context import CryptContext
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    has_passlib = True
except ImportError:
    has_passlib = False
    print("Warning: passlib/bcrypt not installed. Password hashing will not be available.")

def get_db_path():
    # If running inside docker backend
    if os.path.exists('/app/data/agent.db'):
        return '/app/data/agent.db'
    # If running locally from root
    if os.path.exists('./data/agent.db'):
        return './data/agent.db'
    # If running locally from scripts
    if os.path.exists('../data/agent.db'):
        return '../data/agent.db'
    return None

def verify_users():
    db_path = get_db_path()
    if not db_path:
        print("Database not found. Please ensure the backend has run at least once.")
        return

    print(f"Connecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    try:
        cur.execute("SELECT id, username, email, role, api_key, is_active FROM users")
        users = cur.fetchall()
        
        print("\n--- Users in Database ---")
        if not users:
            print("No users found in the database.")
        else:
            for u in users:
                print(f"ID: {u[0]} | Username: {u[1]} | Email: {u[2]} | Role: {u[3]} | API Key: {u[4]} | Active: {u[5]}")
        print("-------------------------\n")
    except sqlite3.OperationalError as e:
        print(f"Error querying users table: {e}")
    finally:
        conn.close()

def create_admin(username, password, api_key):
    db_path = get_db_path()
    if not db_path:
        print("Database not found.")
        return

    if not has_passlib:
        print("Error: Cannot create user without passlib to hash the password.")
        sys.exit(1)

    hashed_password = pwd_context.hash(password)
    now = datetime.utcnow().isoformat()

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    
    try:
        cur.execute(
            """
            INSERT INTO users (username, email, hashed_password, role, api_key, is_active, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (username, f"{username}@admin.local", hashed_password, "admin", api_key, True, now, now)
        )
        conn.commit()
        print(f"Successfully created admin user: {username} with API Key: {api_key}")
    except sqlite3.IntegrityError:
        print(f"User {username} already exists. Updating their API key and password...")
        cur.execute(
            "UPDATE users SET api_key = ?, hashed_password = ? WHERE username = ?",
            (api_key, hashed_password, username)
        )
        conn.commit()
        print(f"Updated user {username} with new API Key: {api_key}")
    except Exception as e:
        print(f"Error creating/updating admin: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify or create admin users in the database.")
    parser.add_argument("--create", action="store_true", help="Create or update an admin user")
    parser.add_argument("--username", type=str, default="admin", help="Admin username")
    parser.add_argument("--password", type=str, default="admin", help="Admin password")
    parser.add_argument("--api-key", type=str, default="rudran_86e41d65f9c64383ba471056", help="Admin API Key")
    
    args = parser.parse_args()

    if args.create:
        create_admin(args.username, args.password, args.api_key)
    
    verify_users()
