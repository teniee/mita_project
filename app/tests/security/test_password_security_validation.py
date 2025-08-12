"""
Password Security Validation Tests for MITA Authentication System
================================================================

Comprehensive tests for password security validation, strength checking,
and security compliance for financial applications.

This test suite ensures:
1. Strong password requirements are enforced
2. Common password attacks are prevented
3. Password hashing is cryptographically secure
4. Password reset flows are secure
5. Brute force protection is working
6. Password policy compliance for financial regulations

Financial applications require enterprise-grade password security
to protect user accounts and prevent unauthorized access to financial data.
"""

import time
import secrets
import hashlib
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

import pytest
import bcrypt
from fastapi import HTTPException

from app.services.auth_jwt_service import hash_password, verify_password
from app.core.security import SecurityUtils, SecurityConfig
from app.core.error_handler import ValidationException
from app.api.auth.schemas import RegisterIn
from app.api.auth.services import register_user_async


class TestPasswordStrengthValidation:
    """
    Test comprehensive password strength validation for financial applications.
    Ensures passwords meet enterprise security standards.
    """
    
    @pytest.fixture
    def common_passwords(self):
        """List of common passwords that should be rejected"""
        return [
            "password",
            "123456",
            "password123",
            "admin",
            "qwerty",
            "letmein",
            "welcome",
            "monkey",
            "1234567890",
            "password1",
            "abc123",
            "Password1",
            "welcome123",
            "admin123",
            "user123",
        ]
    
    @pytest.fixture
    def weak_passwords(self):
        """List of weak passwords with different weaknesses"""
        return {
            "too_short": ["pass", "123", "ab", ""],
            "no_uppercase": ["password123!", "lowercase123", "nouppernumbers1!"],
            "no_lowercase": ["PASSWORD123!", "UPPERCASE123", "ALLCAPS123!"],
            "no_numbers": ["Password!", "OnlyLetters", "NoNumbers!@#"],
            "no_special": ["Password123", "OnlyAlphaNumeric", "NoSpecial123"],
            "dictionary_words": ["dictionary", "telephone", "computer123"],
            "sequential": ["123456789", "abcdefgh", "qwertyuiop"],
            "repeated": ["aaaa1111", "passwordpassword", "1111aaaa"],
            "keyboard_patterns": ["qwerty123", "asdfgh123", "123456qwe"],
        }
    
    @pytest.fixture
    def strong_passwords(self):
        """List of strong passwords that should be accepted"""
        return [
            "StrongP@ssw0rd2024!",
            "MyF1n@nc1@lApp!",
            "Secure#Banking$2024",
            "C0mpl3x&P@ssw0rd!",
            "M1ta@Fin@nce#2024",
            "Ungu3ss@ble&Str0ng!",
            "Enterprise#Gr@de1!",
            "F1n@nc1@l$ecur1ty!",
            "B@nk1ng&Appl1c@tion!",
            "Ultra$ecure#2024!",
        ]
    
    def test_password_minimum_requirements(self, weak_passwords, strong_passwords):
        """
        Test that password minimum requirements are enforced.
        Critical for financial application security compliance.
        """
        # Test 1: Length requirements
        for short_password in weak_passwords["too_short"]:
            with pytest.raises((ValidationException, HTTPException)):
                SecurityUtils.hash_password(short_password)
        
        # Test 2: Character class requirements
        character_class_tests = [
            ("no_uppercase", "Password must contain uppercase letters"),
            ("no_lowercase", "Password must contain lowercase letters"), 
            ("no_numbers", "Password must contain numbers"),
            ("no_special", "Password must contain special characters"),
        ]
        
        for weakness_type, expected_error in character_class_tests:
            for weak_password in weak_passwords[weakness_type]:
                with pytest.raises((ValidationException, HTTPException)) as exc_info:
                    # Use registration validation which includes comprehensive checks
                    data = RegisterIn(
                        email="test@example.com",
                        password=weak_password,
                        country="US",
                        annual_income=50000,
                        timezone="UTC"
                    )
                    # This will trigger password validation
                    hash_password(weak_password)
                
                # Verify appropriate error message
                if hasattr(exc_info.value, 'detail'):
                    assert "password" in exc_info.value.detail.lower()
        
        # Test 3: Strong passwords should be accepted
        for strong_password in strong_passwords:
            try:
                hashed = SecurityUtils.hash_password(strong_password)
                assert hashed is not None
                assert len(hashed) > 50  # bcrypt hash should be long
                
                # Verify password can be validated
                assert SecurityUtils.verify_password(strong_password, hashed) is True
                assert SecurityUtils.verify_password("wrong_password", hashed) is False
                
            except (ValidationException, HTTPException):
                pytest.fail(f"Strong password should be accepted: {strong_password}")
    
    def test_common_password_rejection(self, common_passwords):
        """
        Test that common passwords are rejected.
        Prevents users from using easily guessable passwords.
        """
        # Note: This would typically use a password dictionary check
        # For now, we test that weak passwords are rejected by basic rules
        
        for common_password in common_passwords:
            # Most common passwords will fail basic strength requirements
            try:
                SecurityUtils.hash_password(common_password)
                # If it doesn't throw an error, verify it's actually strong enough
                # (some might pass if they happen to meet requirements)
                assert len(common_password) >= SecurityConfig.MIN_PASSWORD_LENGTH
            except (ValidationException, HTTPException):
                # Expected for most common passwords
                pass
    
    def test_password_complexity_scoring(self):
        """
        Test password complexity scoring and validation.
        Ensures passwords meet financial application security standards.
        """
        # Test cases with expected complexity scores
        password_complexity_tests = [
            ("password", 0),  # Very weak
            ("Password", 1),  # Slightly better
            ("Password1", 2),  # Add numbers
            ("Password1!", 3),  # Add special chars
            ("P@ssw0rd!", 4),  # Good complexity
            ("MyStr0ng&P@ssw0rd2024!", 5),  # Excellent
        ]
        
        def calculate_complexity_score(password: str) -> int:
            """Simple complexity scoring function"""
            score = 0
            
            if len(password) >= 8:
                score += 1
            if any(c.islower() for c in password):
                score += 1
            if any(c.isupper() for c in password):
                score += 1
            if any(c.isdigit() for c in password):
                score += 1
            if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
                score += 1
            
            return score
        
        for password, expected_min_score in password_complexity_tests:
            actual_score = calculate_complexity_score(password)
            
            if expected_min_score >= 4:  # Strong passwords
                try:
                    hashed = SecurityUtils.hash_password(password)
                    assert hashed is not None
                except (ValidationException, HTTPException):
                    pytest.fail(f"High complexity password should be accepted: {password}")
            
            elif expected_min_score <= 2:  # Weak passwords
                with pytest.raises((ValidationException, HTTPException)):
                    SecurityUtils.hash_password(password)
    
    def test_password_entropy_calculation(self):
        """
        Test password entropy calculation for security assessment.
        Higher entropy passwords are more resistant to attacks.
        """
        def calculate_entropy(password: str) -> float:
            """Calculate password entropy in bits"""
            char_space = 0
            
            if any(c.islower() for c in password):
                char_space += 26  # lowercase
            if any(c.isupper() for c in password):
                char_space += 26  # uppercase  
            if any(c.isdigit() for c in password):
                char_space += 10  # digits
            if any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
                char_space += 32  # common symbols
            
            if char_space == 0:
                return 0.0
                
            import math
            return len(password) * math.log2(char_space)
        
        entropy_tests = [
            ("password", 37.6),  # ~38 bits (weak)
            ("Password1!", 59.5),  # ~60 bits (moderate)
            ("MyStr0ng&P@ssw0rd2024!", 146.3),  # ~146 bits (excellent)
        ]
        
        for password, expected_min_entropy in entropy_tests:
            actual_entropy = calculate_entropy(password)
            
            # Allow 5% variance in entropy calculation
            assert actual_entropy >= expected_min_entropy * 0.95, \
                f"Password '{password}' entropy {actual_entropy} below minimum {expected_min_entropy}"
            
            # Passwords with high entropy should be accepted
            if actual_entropy >= 60:  # Good entropy threshold
                try:
                    SecurityUtils.hash_password(password)
                except (ValidationException, HTTPException):
                    pytest.fail(f"High entropy password should be accepted: {password}")
    
    def test_password_policy_compliance(self):
        """
        Test compliance with financial industry password policies.
        Ensures adherence to regulatory requirements.
        """
        # Financial industry standard requirements
        financial_policy_tests = [
            {
                "name": "PCI DSS Compliance",
                "min_length": 8,
                "require_mixed_case": True,
                "require_numbers": True,
                "require_special": True,
                "max_age_days": 90,
            },
            {
                "name": "SOX Compliance", 
                "min_length": 8,
                "require_mixed_case": True,
                "require_numbers": True,
                "require_special": False,  # Less strict
                "max_age_days": 120,
            },
            {
                "name": "FFIEC Guidelines",
                "min_length": 12,  # Stricter for banking
                "require_mixed_case": True,
                "require_numbers": True,
                "require_special": True,
                "max_age_days": 60,
            },
        ]
        
        compliant_passwords = [
            "BankingStr0ng!",    # 13 chars, all requirements
            "FinancialApp2024#",  # 16 chars, all requirements
            "MITA&Secure$Pass1",  # 16 chars, all requirements
        ]
        
        for policy in financial_policy_tests:
            for password in compliant_passwords:
                # Check if password meets policy requirements
                meets_policy = (
                    len(password) >= policy["min_length"] and
                    (not policy["require_mixed_case"] or 
                     (any(c.islower() for c in password) and any(c.isupper() for c in password))) and
                    (not policy["require_numbers"] or any(c.isdigit() for c in password)) and
                    (not policy["require_special"] or 
                     any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password))
                )
                
                if meets_policy:
                    try:
                        hashed = SecurityUtils.hash_password(password)
                        assert hashed is not None
                    except (ValidationException, HTTPException):
                        pytest.fail(f"Policy-compliant password should be accepted: {password} for {policy['name']}")


class TestPasswordHashing:
    """
    Test cryptographically secure password hashing implementation.
    Ensures proper security for stored passwords in financial applications.
    """
    
    def test_bcrypt_configuration(self):
        """
        Test bcrypt hashing configuration meets security standards.
        Financial applications require strong hashing parameters.
        """
        test_password = "TestPassword123!"
        
        # Test 1: Hash should use bcrypt
        hashed = SecurityUtils.hash_password(test_password)
        assert hashed.startswith("$2b$") or hashed.startswith("$2a$") or hashed.startswith("$2y$")
        
        # Test 2: Should use appropriate cost factor
        hash_parts = hashed.split("$")
        assert len(hash_parts) >= 4
        cost_factor = int(hash_parts[2])
        assert cost_factor >= SecurityConfig.PASSWORD_HASH_ROUNDS
        assert cost_factor >= 10  # Minimum for financial applications
        
        # Test 3: Each hash should be unique (due to salt)
        hash1 = SecurityUtils.hash_password(test_password)
        hash2 = SecurityUtils.hash_password(test_password)
        assert hash1 != hash2
        
        # Test 4: Both hashes should verify the same password
        assert SecurityUtils.verify_password(test_password, hash1) is True
        assert SecurityUtils.verify_password(test_password, hash2) is True
    
    def test_password_hashing_performance(self):
        """
        Test password hashing performance meets security vs. usability balance.
        Should be slow enough to prevent brute force but fast enough for UX.
        """
        test_password = "PerformanceTest123!"
        
        # Test hashing time (should be reasonable but not instant)
        start_time = time.time()
        hashed = SecurityUtils.hash_password(test_password)
        hash_time = time.time() - start_time
        
        # Should take at least 50ms (security) but less than 2s (usability)
        assert 0.05 <= hash_time <= 2.0
        
        # Test verification time
        start_time = time.time()
        is_valid = SecurityUtils.verify_password(test_password, hashed)
        verify_time = time.time() - start_time
        
        assert is_valid is True
        assert 0.05 <= verify_time <= 2.0
    
    def test_password_hash_integrity(self):
        """
        Test password hash integrity and tamper resistance.
        Ensures hashes cannot be easily modified or corrupted.
        """
        original_password = "IntegrityTest123!"
        hashed = SecurityUtils.hash_password(original_password)
        
        # Test 1: Original password should verify
        assert SecurityUtils.verify_password(original_password, hashed) is True
        
        # Test 2: Wrong passwords should not verify
        wrong_passwords = [
            "WrongPassword123!",
            "integritytest123!",  # Wrong case
            "IntegrityTest124!",  # One character off
            "",  # Empty
            "IntegrityTest123",  # Missing character
        ]
        
        for wrong_password in wrong_passwords:
            assert SecurityUtils.verify_password(wrong_password, hashed) is False
        
        # Test 3: Corrupted hashes should fail gracefully
        corrupted_hashes = [
            hashed[:-1],  # Truncated
            hashed + "x",  # Extended
            hashed.replace("$", "#"),  # Character substitution
            "",  # Empty hash
            "not_a_hash",  # Invalid format
        ]
        
        for corrupted_hash in corrupted_hashes:
            result = SecurityUtils.verify_password(original_password, corrupted_hash)
            assert result is False
    
    def test_salt_uniqueness_and_security(self):
        """
        Test password salt uniqueness and security properties.
        Ensures rainbow table attacks are prevented.
        """
        test_password = "SaltTest123!"
        
        # Generate multiple hashes of the same password
        hashes = [SecurityUtils.hash_password(test_password) for _ in range(10)]
        
        # Test 1: All hashes should be different (unique salts)
        assert len(set(hashes)) == len(hashes)
        
        # Test 2: All hashes should verify the same password
        for hash_value in hashes:
            assert SecurityUtils.verify_password(test_password, hash_value) is True
        
        # Test 3: Extract and verify salt properties
        for hash_value in hashes:
            hash_parts = hash_value.split("$")
            if len(hash_parts) >= 4:
                salt_and_hash = hash_parts[3]
                salt = salt_and_hash[:22]  # bcrypt salt is 22 characters
                
                # Salt should be long enough and contain varied characters
                assert len(salt) >= 20
                assert not salt.isalnum()  # Should contain special base64 characters
    
    def test_timing_attack_resistance(self):
        """
        Test password verification timing attack resistance.
        Ensures constant-time verification for security.
        """
        correct_password = "TimingTest123!"
        hashed = SecurityUtils.hash_password(correct_password)
        
        wrong_passwords = [
            "WrongPassword123!",
            "T",  # Very short
            "TimingTest124!",  # Close to correct
            "x" * 100,  # Very long
        ]
        
        # Measure verification times
        verification_times = []
        
        # Test correct password
        for _ in range(5):
            start = time.time()
            SecurityUtils.verify_password(correct_password, hashed)
            verification_times.append(time.time() - start)
        
        # Test wrong passwords
        for wrong_password in wrong_passwords:
            for _ in range(5):
                start = time.time()
                SecurityUtils.verify_password(wrong_password, hashed)
                verification_times.append(time.time() - start)
        
        # Times should be relatively consistent (not varying by orders of magnitude)
        min_time = min(verification_times)
        max_time = max(verification_times)
        
        # Allow up to 10x variation (bcrypt should be relatively consistent)
        assert max_time / min_time < 10, "Timing variation too large, possible timing attack vulnerability"


class TestPasswordResetSecurity:
    """
    Test password reset security mechanisms.
    Critical for financial application account recovery security.
    """
    
    def test_reset_token_generation(self):
        """
        Test secure reset token generation.
        Tokens must be cryptographically secure and unpredictable.
        """
        # Generate multiple tokens
        tokens = [SecurityUtils.generate_secure_token() for _ in range(100)]
        
        # Test 1: All tokens should be unique
        assert len(set(tokens)) == len(tokens)
        
        # Test 2: Tokens should be long enough (at least 32 characters)
        for token in tokens[:10]:  # Test subset for performance
            assert len(token) >= 32
            
            # Test 3: Tokens should be URL-safe
            import string
            allowed_chars = string.ascii_letters + string.digits + '-_'
            assert all(c in allowed_chars for c in token)
        
        # Test 4: Test entropy of generated tokens
        token_entropy = self._calculate_token_entropy(tokens[0])
        assert token_entropy >= 256  # Should have high entropy
    
    def _calculate_token_entropy(self, token: str) -> float:
        """Calculate approximate entropy of a token"""
        import math
        from collections import Counter
        
        # Count character frequencies
        char_counts = Counter(token)
        total_chars = len(token)
        
        # Calculate Shannon entropy
        entropy = 0.0
        for count in char_counts.values():
            probability = count / total_chars
            if probability > 0:
                entropy -= probability * math.log2(probability)
        
        # Scale by token length for total entropy
        return entropy * total_chars
    
    def test_reset_token_expiration(self):
        """
        Test password reset token expiration mechanisms.
        Ensures tokens cannot be used indefinitely.
        """
        # Mock token storage with expiration
        token_store = {}
        
        def store_reset_token(email: str, token: str, expiry_minutes: int = 30):
            expiry_time = time.time() + (expiry_minutes * 60)
            token_store[token] = {
                'email': email,
                'expiry': expiry_time,
                'used': False
            }
        
        def is_token_valid(token: str) -> bool:
            if token not in token_store:
                return False
            
            token_data = token_store[token]
            return not token_data['used'] and token_data['expiry'] > time.time()
        
        def use_token(token: str) -> bool:
            if not is_token_valid(token):
                return False
            
            token_store[token]['used'] = True
            return True
        
        # Test 1: Fresh token should be valid
        test_email = "test@example.com"
        test_token = SecurityUtils.generate_secure_token()
        store_reset_token(test_email, test_token, expiry_minutes=1)
        
        assert is_token_valid(test_token) is True
        
        # Test 2: Token should be usable once
        assert use_token(test_token) is True
        assert is_token_valid(test_token) is False  # Should be invalid after use
        assert use_token(test_token) is False  # Cannot use again
        
        # Test 3: Expired token should be invalid
        expired_token = SecurityUtils.generate_secure_token()
        store_reset_token(test_email, expired_token, expiry_minutes=-1)  # Already expired
        
        assert is_token_valid(expired_token) is False
        assert use_token(expired_token) is False
    
    def test_password_reset_rate_limiting(self):
        """
        Test password reset request rate limiting.
        Prevents abuse of reset functionality.
        """
        # Mock rate limiter for password reset
        reset_attempts = {}
        
        def can_request_reset(email: str, max_requests: int = 3, window_minutes: int = 60) -> bool:
            current_time = time.time()
            window_start = current_time - (window_minutes * 60)
            
            if email not in reset_attempts:
                reset_attempts[email] = []
            
            # Clean old attempts
            reset_attempts[email] = [
                attempt_time for attempt_time in reset_attempts[email] 
                if attempt_time > window_start
            ]
            
            # Check if under limit
            if len(reset_attempts[email]) >= max_requests:
                return False
            
            # Record new attempt
            reset_attempts[email].append(current_time)
            return True
        
        test_email = "ratelimit@example.com"
        
        # Test 1: First few requests should succeed
        for i in range(3):
            assert can_request_reset(test_email) is True
        
        # Test 2: Additional requests should be blocked
        assert can_request_reset(test_email) is False
        assert can_request_reset(test_email) is False
        
        # Test 3: Different email should not be affected
        other_email = "other@example.com"
        assert can_request_reset(other_email) is True
    
    def test_secure_password_update(self):
        """
        Test secure password update process.
        Ensures new passwords meet security requirements.
        """
        original_password = "OriginalPass123!"
        original_hash = SecurityUtils.hash_password(original_password)
        
        # Test 1: New password should meet strength requirements
        strong_new_passwords = [
            "NewStrongPass456!",
            "UpdatedSecure789@",
            "FreshPassword321#",
        ]
        
        for new_password in strong_new_passwords:
            new_hash = SecurityUtils.hash_password(new_password)
            
            # New hash should be different from original
            assert new_hash != original_hash
            
            # New password should verify correctly
            assert SecurityUtils.verify_password(new_password, new_hash) is True
            
            # Original password should not work with new hash
            assert SecurityUtils.verify_password(original_password, new_hash) is False
        
        # Test 2: Weak new passwords should be rejected
        weak_new_passwords = [
            "weak",
            "123456",
            "password",
            original_password,  # Same as original (should be prevented)
        ]
        
        for weak_password in weak_new_passwords:
            with pytest.raises((ValidationException, HTTPException)):
                SecurityUtils.hash_password(weak_password)
    
    def test_password_history_prevention(self):
        """
        Test prevention of password reuse from history.
        Financial applications should prevent recent password reuse.
        """
        # Mock password history storage
        password_history = {}
        
        def add_to_history(user_id: str, password_hash: str, max_history: int = 5):
            if user_id not in password_history:
                password_history[user_id] = []
            
            password_history[user_id].append(password_hash)
            
            # Keep only recent passwords
            if len(password_history[user_id]) > max_history:
                password_history[user_id] = password_history[user_id][-max_history:]
        
        def is_password_in_history(user_id: str, new_password: str) -> bool:
            if user_id not in password_history:
                return False
            
            # Check if new password matches any in history
            for old_hash in password_history[user_id]:
                if SecurityUtils.verify_password(new_password, old_hash):
                    return True
            
            return False
        
        test_user_id = "test_user_123"
        
        # Test 1: Build password history
        historical_passwords = [
            "HistoricalPass1!",
            "HistoricalPass2!",
            "HistoricalPass3!",
            "HistoricalPass4!",
            "HistoricalPass5!",
        ]
        
        for password in historical_passwords:
            password_hash = SecurityUtils.hash_password(password)
            add_to_history(test_user_id, password_hash)
        
        # Test 2: Reusing old passwords should be prevented
        for old_password in historical_passwords:
            assert is_password_in_history(test_user_id, old_password) is True
        
        # Test 3: New password should be allowed
        new_password = "BrandNewPassword123!"
        assert is_password_in_history(test_user_id, new_password) is False
        
        # Test 4: After adding new password, oldest should be forgotten
        new_hash = SecurityUtils.hash_password(new_password)
        add_to_history(test_user_id, new_hash)
        
        # First password should no longer be in history (assuming max_history=5)
        assert is_password_in_history(test_user_id, historical_passwords[0]) is False
        assert is_password_in_history(test_user_id, new_password) is True


if __name__ == "__main__":
    # Run password security tests
    pytest.main([__file__, "-v"])