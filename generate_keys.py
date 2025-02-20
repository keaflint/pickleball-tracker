import secrets

# Generate SECRET_KEY
secret_key = secrets.token_hex(32)
print(f"SECRET_KEY: {secret_key}")

# Generate WTF_CSRF_SECRET_KEY
csrf_key = secrets.token_hex(32)
print(f"WTF_CSRF_SECRET_KEY: {csrf_key}") 