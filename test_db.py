from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

def test_connection():
    try:
        database_url = os.getenv('DATABASE_URL')
        print(f"Testing connection with URL: {database_url}")
        
        engine = create_engine(
            database_url,
            connect_args={
                "sslmode": "require"
            }
        )
        
        with engine.connect() as connection:
            result = connection.execute("SELECT version()")
            version = result.scalar()
            print("Successfully connected to the database!")
            print(f"Database version: {version}")
            
    except Exception as e:
        print(f"Error connecting to the database: {e}")
        print("\nPlease verify these settings:")
        print("1. Check if your database password is correct")
        print("2. Verify that your database user has the correct permissions")
        print("3. Make sure your database is accessible from your current location")

if __name__ == "__main__":
    test_connection() 