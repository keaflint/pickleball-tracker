from dotenv import load_dotenv
import os

# Force reload of environment variables
load_dotenv(override=True)

# Print all environment variables
print("\nAll environment variables:")
print("-" * 50)
for key, value in os.environ.items():
    if key in ['DATABASE_URL', 'SECRET_KEY', 'FLASK_APP', 'MAIL_USERNAME', 'MAIL_PASSWORD']:
        print(f"{key}: {value}")
print("-" * 50)

# Verify specific variables
database_url = os.environ.get('DATABASE_URL')
if database_url == 'your-supabase-url':
    print("\nWARNING: DATABASE_URL is still using placeholder value!")
else:
    print("\nDATABASE_URL is properly set")

secret_key = os.environ.get('SECRET_KEY')
if secret_key == 'your-secret-key':
    print("WARNING: SECRET_KEY is still using placeholder value!")
else:
    print("SECRET_KEY is properly set") 