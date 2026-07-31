import hashlib, secrets

_ITERATIONS = 200_000

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'),
                             bytes.fromhex(salt), _ITERATIONS)
    return dk.hex(), salt

def verify_password(password, salt, expected_hash):
    calc, _ = hash_password(password, salt)
    return secrets.compare_digest(calc, expected_hash)
