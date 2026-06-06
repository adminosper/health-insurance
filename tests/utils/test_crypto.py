"""Unit tests for the Field-Level Encryption utility."""

from src.utils.crypto import cipher


def test_encrypt_decrypt_list():
    """Test that a list of diagnosis codes is encrypted and decrypted properly."""
    original_data = ["I21", "E11.9", "J45.909"]
    
    # Encrypt
    encrypted_token = cipher.encrypt_list(original_data)
    
    # Ensure it's not plaintext
    assert isinstance(encrypted_token, str)
    assert encrypted_token != str(original_data)
    assert "I21" not in encrypted_token
    
    # Decrypt
    decrypted_data = cipher.decrypt_to_list(encrypted_token)
    
    # Ensure accurate recovery
    assert decrypted_data == original_data


def test_encrypt_empty_list():
    """Test encryption and decryption of an empty list."""
    original_data = []
    
    encrypted_token = cipher.encrypt_list(original_data)
    decrypted_data = cipher.decrypt_to_list(encrypted_token)
    
    assert decrypted_data == original_data
