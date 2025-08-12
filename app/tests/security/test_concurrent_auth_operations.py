"""
Concurrent Authentication Operations Tests for MITA
===================================================

Comprehensive tests for concurrent authentication operations, race condition
prevention, and thread safety in financial application authentication systems.

This test suite ensures:
1. Token operations are thread-safe
2. Race conditions in refresh operations are prevented  
3. Concurrent login/logout operations work correctly
4. Rate limiting works under concurrent load
5. Database operations are properly synchronized
6. Redis operations handle concurrency correctly
7. No data corruption occurs under high concurrency

Financial applications must handle concurrent operations safely
to prevent security vulnerabilities and data corruption.
"""

import asyncio
import time
import threading
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from typing import List, Dict, Any, Optional
import queue
import secrets

import pytest

from app.services.auth_jwt_service import (
    create_access_token,
    create_refresh_token,
    verify_token,
    blacklist_token,
    get_token_info
)
from app.core.security import AdvancedRateLimiter, reset_security_instances
from app.core.error_handler import RateLimitException
from app.api.auth.services import authenticate_user_async, register_user_async
from app.api.auth.schemas import LoginIn, RegisterIn


class TestConcurrentTokenOperations:
    """
    Test concurrent token operations for thread safety and race condition prevention.
    Critical for financial applications with high concurrent user activity.
    """
    
    @pytest.fixture
    def user_data(self):
        """Test user data for token operations"""
        return {"sub": "concurrent_test_user", "email": "concurrent@example.com"}
    
    @pytest.fixture
    def blacklist_store(self):
        """Thread-safe blacklist store for testing"""
        import threading
        store = {}
        store_lock = threading.Lock()
        
        def thread_safe_blacklist(jti, ttl):
            with store_lock:
                store[jti] = time.time() + ttl
            return True
            
        def thread_safe_check(jti):
            with store_lock:
                return jti in store and store[jti] > time.time()
        
        return store, thread_safe_blacklist, thread_safe_check
    
    def test_concurrent_token_creation(self, user_data):
        """
        Test concurrent token creation for thread safety.
        Ensures tokens are unique and valid under concurrent load.
        """
        created_tokens = []
        creation_errors = []
        token_lock = threading.Lock()
        
        def create_token_worker():
            try:
                token = create_access_token(user_data)
                with token_lock:
                    created_tokens.append(token)
            except Exception as e:
                with token_lock:
                    creation_errors.append(str(e))
        
        # Test 1: Create tokens concurrently
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(create_token_worker) for _ in range(100)]
            
            # Wait for all tasks to complete
            for future in as_completed(futures):
                future.result()  # This will raise any exceptions
        
        # Test 2: Verify results
        assert len(creation_errors) == 0, f"Token creation errors: {creation_errors}"
        assert len(created_tokens) == 100, "Not all tokens were created"
        
        # Test 3: All tokens should be unique
        assert len(set(created_tokens)) == 100, "Duplicate tokens created under concurrency"
        
        # Test 4: All tokens should be valid
        for token in created_tokens:
            payload = verify_token(token)
            assert payload is not None, "Invalid token created under concurrency"
            assert payload["sub"] == user_data["sub"]
    
    def test_concurrent_token_validation(self, user_data):
        """
        Test concurrent token validation for performance and correctness.
        Ensures validation remains accurate under high load.
        """
        # Create tokens for validation
        valid_tokens = [create_access_token(user_data) for _ in range(50)]
        invalid_tokens = ["invalid_token_" + str(i) for i in range(50)]
        
        validation_results = []
        validation_errors = []
        results_lock = threading.Lock()
        
        def validate_token_worker(token, expected_valid):
            try:
                payload = verify_token(token)
                is_valid = payload is not None
                
                with results_lock:
                    validation_results.append({
                        'token': token[:20] + "...",  # Truncate for readability
                        'expected_valid': expected_valid,
                        'actual_valid': is_valid,
                        'correct': is_valid == expected_valid
                    })
                    
            except Exception as e:
                with results_lock:
                    validation_errors.append(f"Token validation error: {e}")
        
        # Test concurrent validation
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            
            # Submit valid token validation tasks
            for token in valid_tokens:
                futures.append(executor.submit(validate_token_worker, token, True))
            
            # Submit invalid token validation tasks
            for token in invalid_tokens:
                futures.append(executor.submit(validate_token_worker, token, False))
            
            # Wait for completion
            for future in as_completed(futures):
                future.result()
        
        # Verify results
        assert len(validation_errors) == 0, f"Validation errors: {validation_errors}"
        assert len(validation_results) == 100
        
        # All validations should be correct
        incorrect_validations = [r for r in validation_results if not r['correct']]
        assert len(incorrect_validations) == 0, f"Incorrect validations: {incorrect_validations}"
    
    def test_concurrent_token_blacklisting(self, user_data, blacklist_store):
        """
        Test concurrent token blacklisting for race condition prevention.
        Critical for ensuring logout security under concurrent operations.
        """
        store, mock_blacklist, mock_check = blacklist_store
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_check):
            
            # Create tokens for blacklisting
            tokens_to_blacklist = [create_access_token(user_data) for _ in range(50)]
            
            blacklist_results = []
            blacklist_errors = []
            results_lock = threading.Lock()
            
            def blacklist_token_worker(token):
                try:
                    success = blacklist_token(token)
                    with results_lock:
                        blacklist_results.append({'token': token, 'success': success})
                except Exception as e:
                    with results_lock:
                        blacklist_errors.append(f"Blacklist error: {e}")
            
            # Test 1: Concurrent blacklisting
            with ThreadPoolExecutor(max_workers=15) as executor:
                futures = [executor.submit(blacklist_token_worker, token) 
                          for token in tokens_to_blacklist]
                
                for future in as_completed(futures):
                    future.result()
            
            # Test 2: Verify results
            assert len(blacklist_errors) == 0, f"Blacklist errors: {blacklist_errors}"
            assert len(blacklist_results) == 50
            
            successful_blacklists = [r for r in blacklist_results if r['success']]
            assert len(successful_blacklists) == 50, "Not all tokens were blacklisted"
            
            # Test 3: Verify tokens are actually blacklisted
            for result in blacklist_results:
                payload = verify_token(result['token'])
                assert payload is None, "Token should be invalid after blacklisting"
    
    def test_concurrent_refresh_token_rotation(self, user_data, blacklist_store):
        """
        Test concurrent refresh token rotation to prevent race conditions.
        Ensures token rotation security under concurrent refresh attempts.
        """
        store, mock_blacklist, mock_check = blacklist_store
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_check):
            
            # Create initial refresh token
            original_refresh_token = create_refresh_token(user_data)
            
            rotation_results = []
            rotation_errors = []
            results_lock = threading.Lock()
            
            def rotate_token_worker(worker_id):
                try:
                    # Simulate token refresh process
                    # 1. Verify current refresh token
                    payload = verify_token(original_refresh_token, scope="refresh_token")
                    if payload is None:
                        with results_lock:
                            rotation_results.append({
                                'worker_id': worker_id,
                                'success': False,
                                'reason': 'token_invalid'
                            })
                        return
                    
                    # 2. Create new tokens
                    new_access = create_access_token(user_data)
                    new_refresh = create_refresh_token(user_data)
                    
                    # 3. Blacklist old refresh token
                    blacklist_success = blacklist_token(original_refresh_token)
                    
                    with results_lock:
                        rotation_results.append({
                            'worker_id': worker_id,
                            'success': True,
                            'new_access': new_access,
                            'new_refresh': new_refresh,
                            'blacklist_success': blacklist_success
                        })
                        
                except Exception as e:
                    with results_lock:
                        rotation_errors.append(f"Worker {worker_id} error: {e}")
            
            # Test concurrent refresh attempts
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(rotate_token_worker, i) for i in range(20)]
                
                for future in as_completed(futures):
                    future.result()
            
            # Analyze results
            assert len(rotation_errors) == 0, f"Rotation errors: {rotation_errors}"
            
            successful_rotations = [r for r in rotation_results if r['success']]
            failed_rotations = [r for r in rotation_results if not r['success']]
            
            # Only some should succeed due to token invalidation after first use
            assert len(successful_rotations) >= 1, "At least one rotation should succeed"
            
            # Verify original token is blacklisted
            final_payload = verify_token(original_refresh_token, scope="refresh_token")
            assert final_payload is None, "Original refresh token should be invalidated"
    
    def test_race_condition_prevention_login_logout(self, user_data, blacklist_store):
        """
        Test race condition prevention between concurrent login/logout operations.
        Critical for financial application session management security.
        """
        store, mock_blacklist, mock_check = blacklist_store
        
        with patch('app.services.auth_jwt_service.upstash_blacklist_token', mock_blacklist), \
             patch('app.services.auth_jwt_service.is_token_blacklisted', mock_check):
            
            # Shared state for race condition testing
            active_tokens = {}
            operation_log = []
            shared_lock = threading.Lock()
            
            def login_worker(worker_id):
                try:
                    # Create new session tokens
                    access_token = create_access_token(user_data)
                    refresh_token = create_refresh_token(user_data)
                    
                    with shared_lock:
                        active_tokens[worker_id] = {
                            'access': access_token,
                            'refresh': refresh_token,
                            'timestamp': time.time()
                        }
                        operation_log.append(f"LOGIN:{worker_id}")
                        
                except Exception as e:
                    with shared_lock:
                        operation_log.append(f"LOGIN_ERROR:{worker_id}:{e}")
            
            def logout_worker(worker_id):
                try:
                    with shared_lock:
                        if worker_id in active_tokens:
                            tokens = active_tokens[worker_id]
                            del active_tokens[worker_id]
                        else:
                            operation_log.append(f"LOGOUT_NO_SESSION:{worker_id}")
                            return
                    
                    # Blacklist tokens outside of lock
                    blacklist_token(tokens['access'])
                    blacklist_token(tokens['refresh'])
                    
                    with shared_lock:
                        operation_log.append(f"LOGOUT:{worker_id}")
                        
                except Exception as e:
                    with shared_lock:
                        operation_log.append(f"LOGOUT_ERROR:{worker_id}:{e}")
            
            # Test concurrent login/logout operations
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                
                # Submit alternating login/logout operations
                for i in range(100):
                    if i % 2 == 0:
                        futures.append(executor.submit(login_worker, i))
                    else:
                        # Logout previous session
                        futures.append(executor.submit(logout_worker, i - 1))
                
                # Wait for all operations
                for future in as_completed(futures):
                    future.result()
            
            # Analyze operation log
            login_ops = [op for op in operation_log if op.startswith("LOGIN:")]
            logout_ops = [op for op in operation_log if op.startswith("LOGOUT:")]
            errors = [op for op in operation_log if "ERROR" in op]
            
            assert len(errors) == 0, f"Race condition errors: {errors}"
            assert len(login_ops) >= 40, "Not enough login operations completed"
            
            # Verify no tokens are left in inconsistent state
            for session in active_tokens.values():
                access_payload = verify_token(session['access'])
                refresh_payload = verify_token(session['refresh'], scope="refresh_token")
                
                # Active sessions should have valid tokens
                assert access_payload is not None, "Active session has invalid access token"
                assert refresh_payload is not None, "Active session has invalid refresh token"


class TestConcurrentRateLimiting:
    """
    Test concurrent rate limiting operations for accuracy and performance.
    Ensures rate limiting works correctly under high concurrent load.
    """
    
    @pytest.fixture
    def mock_redis_client(self):
        """Thread-safe mock Redis client"""
        import threading
        
        mock_client = Mock()
        mock_client.ping.return_value = True
        
        # Thread-safe counters
        counters = {}
        counter_lock = threading.Lock()
        
        def thread_safe_execute():
            with counter_lock:
                # Simulate rate limit counting
                key = "test_rate_limit"
                if key not in counters:
                    counters[key] = 0
                counters[key] += 1
                
                # Return realistic rate limit data
                return [counters[key], 300, 1, 300]  # IP count, IP TTL, Email count, Email TTL
        
        mock_client.pipeline.return_value = mock_client
        mock_client.execute.side_effect = thread_safe_execute
        mock_client.zremrangebyscore.return_value = 0
        mock_client.zadd.return_value = 1
        mock_client.zcard.side_effect = lambda key: counters.get("test_rate_limit", 0)
        mock_client.expire.return_value = True
        mock_client.get.return_value = "0"  # No penalties initially
        mock_client.incr.return_value = 1
        mock_client.setex.return_value = True
        
        return mock_client
    
    def test_concurrent_rate_limit_accuracy(self, mock_redis_client):
        """
        Test rate limiting accuracy under concurrent load.
        Ensures financial application maintains security under stress.
        """
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis_client):
            rate_limiter = AdvancedRateLimiter()
            
            # Track results
            rate_limit_results = []
            rate_limit_errors = []
            results_lock = threading.Lock()
            
            def rate_limit_worker(worker_id):
                try:
                    mock_request = Mock()
                    mock_request.client.host = f"192.168.1.{worker_id % 255}"
                    mock_request.headers = {'User-Agent': f'ConcurrentTest/{worker_id}'}
                    mock_request.url.path = "/auth/login"
                    mock_request.method = "POST"
                    
                    email = f"concurrent_{worker_id}@example.com"
                    
                    try:
                        rate_limiter.check_auth_rate_limit(mock_request, email, "login")
                        with results_lock:
                            rate_limit_results.append({'worker_id': worker_id, 'allowed': True})
                    except RateLimitException:
                        with results_lock:
                            rate_limit_results.append({'worker_id': worker_id, 'allowed': False})
                            
                except Exception as e:
                    with results_lock:
                        rate_limit_errors.append(f"Worker {worker_id}: {e}")
            
            # Test concurrent rate limiting
            with ThreadPoolExecutor(max_workers=50) as executor:
                futures = [executor.submit(rate_limit_worker, i) for i in range(200)]
                
                for future in as_completed(futures):
                    future.result()
            
            # Analyze results
            assert len(rate_limit_errors) == 0, f"Rate limit errors: {rate_limit_errors}"
            assert len(rate_limit_results) == 200
            
            allowed_requests = [r for r in rate_limit_results if r['allowed']]
            blocked_requests = [r for r in rate_limit_results if not r['allowed']]
            
            # Should have both allowed and blocked requests (rate limiting working)
            assert len(allowed_requests) > 0, "Some requests should be allowed"
            assert len(blocked_requests) > 0, "Some requests should be blocked"
            
            # Total should be consistent
            assert len(allowed_requests) + len(blocked_requests) == 200
    
    def test_concurrent_progressive_penalties(self, mock_redis_client):
        """
        Test progressive penalty system under concurrent operations.
        Ensures penalty calculations remain consistent under load.
        """
        reset_security_instances()
        
        with patch('app.core.security.redis_client', mock_redis_client):
            rate_limiter = AdvancedRateLimiter()
            
            penalty_results = []
            penalty_errors = []
            results_lock = threading.Lock()
            
            def penalty_worker(violation_count):
                try:
                    # Mock Redis to return specific violation count
                    with patch.object(mock_redis_client, 'get', return_value=str(violation_count)):
                        client_id = f"penalty_test_client_{violation_count}"
                        penalty = rate_limiter._check_progressive_penalties(client_id, "login")
                        
                        with results_lock:
                            penalty_results.append({
                                'violation_count': violation_count,
                                'penalty_multiplier': penalty
                            })
                            
                except Exception as e:
                    with results_lock:
                        penalty_errors.append(f"Violation count {violation_count}: {e}")
            
            # Test concurrent penalty calculations
            violation_counts = list(range(0, 20)) * 10  # Test same counts multiple times
            
            with ThreadPoolExecutor(max_workers=20) as executor:
                futures = [executor.submit(penalty_worker, count) for count in violation_counts]
                
                for future in as_completed(futures):
                    future.result()
            
            # Analyze results
            assert len(penalty_errors) == 0, f"Penalty calculation errors: {penalty_errors}"
            assert len(penalty_results) == len(violation_counts)
            
            # Group results by violation count
            penalty_by_count = {}
            for result in penalty_results:
                count = result['violation_count']
                penalty = result['penalty_multiplier']
                
                if count not in penalty_by_count:
                    penalty_by_count[count] = []
                penalty_by_count[count].append(penalty)
            
            # Verify consistency - same violation count should always give same penalty
            for count, penalties in penalty_by_count.items():
                unique_penalties = set(penalties)
                assert len(unique_penalties) == 1, \
                    f"Inconsistent penalties for count {count}: {unique_penalties}"
    
    @pytest.mark.asyncio
    async def test_concurrent_database_operations(self):
        """
        Test concurrent database operations for authentication.
        Ensures database consistency under concurrent auth operations.
        """
        # Mock database session
        mock_db_sessions = []
        session_lock = threading.Lock()
        
        def create_mock_session():
            session = AsyncMock()
            session.execute = AsyncMock()
            session.add = Mock()
            session.commit = AsyncMock()
            session.refresh = AsyncMock()
            
            with session_lock:
                mock_db_sessions.append(session)
            
            return session
        
        auth_results = []
        auth_errors = []
        results_lock = threading.Lock()
        
        async def auth_worker(worker_id):
            try:
                mock_session = create_mock_session()
                
                # Mock user query result
                mock_result = Mock()
                mock_result.scalars.return_value.first.return_value = None  # No existing user
                mock_session.execute.return_value = mock_result
                
                # Test registration
                registration_data = RegisterIn(
                    email=f"concurrent_{worker_id}@example.com",
                    password=f"ConcurrentPass{worker_id}!",
                    country="US",
                    annual_income=50000,
                    timezone="UTC"
                )
                
                result = await register_user_async(registration_data, mock_session)
                
                with results_lock:
                    auth_results.append({
                        'worker_id': worker_id,
                        'success': True,
                        'token_present': result.access_token is not None
                    })
                    
            except Exception as e:
                with results_lock:
                    auth_errors.append(f"Worker {worker_id}: {e}")
        
        # Run concurrent authentication operations
        tasks = [auth_worker(i) for i in range(20)]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        assert len(auth_errors) == 0, f"Auth errors: {auth_errors}"
        assert len(auth_results) == 20
        
        successful_auths = [r for r in auth_results if r['success'] and r['token_present']]
        assert len(successful_auths) == 20, "All concurrent authentications should succeed"
        
        # Verify database operations were called correctly
        assert len(mock_db_sessions) == 20, "Should have 20 database sessions"
        
        for session in mock_db_sessions:
            session.add.assert_called_once()  # User should be added
            session.commit.assert_called_once()  # Transaction should be committed
            session.refresh.assert_called_once()  # User should be refreshed
    
    def test_memory_consistency_under_concurrency(self):
        """
        Test memory consistency and data integrity under concurrent operations.
        Ensures no memory corruption or data races occur.
        """
        # Shared data structure for testing
        shared_token_store = {}
        store_lock = threading.Lock()
        
        consistency_errors = []
        
        def token_management_worker(worker_id):
            try:
                user_data = {"sub": f"consistency_user_{worker_id}"}
                
                # Create token
                token = create_access_token(user_data)
                
                # Store token with thread safety
                with store_lock:
                    shared_token_store[worker_id] = token
                
                # Verify token multiple times
                for _ in range(10):
                    payload = verify_token(token)
                    if payload is None or payload["sub"] != user_data["sub"]:
                        consistency_errors.append(f"Worker {worker_id}: Token validation failed")
                        break
                    
                    time.sleep(0.001)  # Small delay to increase chance of race conditions
                
                # Clean up
                with store_lock:
                    if worker_id in shared_token_store:
                        del shared_token_store[worker_id]
                        
            except Exception as e:
                consistency_errors.append(f"Worker {worker_id}: {e}")
        
        # Run concurrent operations
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(token_management_worker, i) for i in range(100)]
            
            for future in as_completed(futures):
                future.result()
        
        # Check for consistency errors
        assert len(consistency_errors) == 0, f"Consistency errors: {consistency_errors}"
        
        # Verify shared store is clean
        assert len(shared_token_store) == 0, "Memory leak: tokens not cleaned up"


if __name__ == "__main__":
    # Run concurrent operation tests
    pytest.main([__file__, "-v", "-s"])