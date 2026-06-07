import base64
import hashlib
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.backends import default_backend
from app.config import settings

def get_aes_key() -> bytes:
    """Derive a 256-bit AES key from the configured AES_KEY string."""
    return hashlib.sha256(settings.AES_KEY.encode('utf-8')).digest()

def encrypt_field(plain_text: str) -> str:
    """Encrypt a string using AES-256-CBC. Returns base64-encoded ciphertext."""
    if not plain_text:
        return ""
    key = get_aes_key()
    iv = hashlib.md5(settings.AES_KEY.encode()).digest()[:16]
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plain_text.encode('utf-8')) + padder.finalize()
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()
    
    return base64.b64encode(ciphertext).decode('utf-8')

def decrypt_field(cipher_text: str) -> str:
    """Decrypt a base64-encoded AES-256-CBC ciphertext."""
    if not cipher_text:
        return ""
    key = get_aes_key()
    iv = hashlib.md5(settings.AES_KEY.encode()).digest()[:16]
    
    ciphertext = base64.b64decode(cipher_text.encode('utf-8'))
    
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    decryptor = cipher.decryptor()
    padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
    
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded_plaintext) + unpadder.finalize()
    
    return plaintext.decode('utf-8')

def mask_phone(phone: str) -> str:
    """Mask phone number: 138****0000"""
    if not phone or len(phone) < 7:
        return phone
    return phone[:3] + "****" + phone[-4:]

def mask_id_card(id_card: str) -> str:
    """Mask ID card: 11***********1234"""
    if not id_card or len(id_card) < 8:
        return id_card
    return id_card[:2] + "*" * (len(id_card) - 6) + id_card[-4:]

def mask_name(name: str) -> str:
    """Mask name: 张**"""
    if not name:
        return name
    if len(name) <= 1:
        return name
    return name[0] + "*" * (len(name) - 1)
