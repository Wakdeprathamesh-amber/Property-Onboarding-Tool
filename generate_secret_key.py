#!/usr/bin/env python3
"""
Generate a secure secret key for Flask application
"""

import secrets
import string

def generate_secret_key(length=32):
    """Generate a secure random secret key"""
    # Use a combination of letters, digits, and special characters
    alphabet = string.ascii_letters + string.digits + string.punctuation
    # Remove potentially problematic characters
    alphabet = alphabet.replace("'", "").replace('"', "").replace("\\", "")
    
    # Generate the secret key
    secret_key = ''.join(secrets.choice(alphabet) for _ in range(length))
    return secret_key

def generate_multiple_keys(count=3, length=32):
    """Generate multiple secret keys for different environments"""
    print("🔐 Generating secure secret keys for Flask application...")
    print("=" * 60)
    
    for i in range(count):
        key = generate_secret_key(length)
        print(f"Secret Key {i+1}: {key}")
        print()
    
    print("=" * 60)
    print("📝 Instructions:")
    print("1. Copy one of these keys")
    print("2. Use it as your SECRET_KEY environment variable")
    print("3. Keep it secret and never commit to version control")
    print("4. Use different keys for development, staging, and production")
    print()
    print("⚠️  Security Notes:")
    print("- Each environment should have a unique key")
    print("- Rotate keys periodically in production")
    print("- Store keys securely (environment variables, secret managers)")
    
    return [generate_secret_key(length) for _ in range(count)]

if __name__ == "__main__":
    # Generate 3 different secret keys
    keys = generate_multiple_keys(3, 32)
    
    # Also show a longer key option
    print("\n🔒 For extra security, here's a longer key:")
    long_key = generate_secret_key(64)
    print(f"Long Secret Key (64 chars): {long_key}")
