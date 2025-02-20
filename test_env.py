from dotenv import load_dotenv
import os

load_dotenv()

print("DATABASE_URL:", os.environ.get('DATABASE_URL'))
print("FLASK_APP:", os.environ.get('FLASK_APP'))
print("SECRET_KEY:", os.environ.get('SECRET_KEY')) 