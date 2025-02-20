from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv, find_dotenv
from urllib.parse import quote_plus

# Clear existing environment variables
if 'DATABASE_URL' in os.environ:
    del os.environ['DATABASE_URL']

# Find and load the .env file with override
env_file = find_dotenv()
print(f"\nLoading environment from: {env_file}")
load_dotenv(env_file, override=True)

# Get the actual URL from environment
actual_url = os.environ.get('DATABASE_URL')

print("\nEnvironment Variables:")
print("-" * 50)
print(f"DATABASE_URL: {actual_url}")
print("-" * 50)

try:
    # Create engine with SSL required and connection pooling settings
    engine = create_engine(
        actual_url,
        connect_args={
            "sslmode": "require",
            "application_name": "pickleball_tracker"
        },
        pool_size=5,
        max_overflow=10
    )
    
    # Try to connect using proper SQLAlchemy query syntax
    with engine.connect() as connection:
        result = connection.execute(text("SELECT current_database(), current_user"))
        db, user = result.fetchone()
        print("\nConnection successful!")
        print(f"Connected to database: {db}")
        print(f"Connected as user: {user}")

except Exception as e:
    print("\nConnection failed!")
    print(f"Error: {str(e)}")
    
    # Print debug info
    print("\nDebug Info:")
    print(f"DATABASE_URL being used: {actual_url}") 