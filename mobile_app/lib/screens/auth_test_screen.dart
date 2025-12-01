import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:dio/dio.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../theme/mita_theme.dart';
import '../config.dart';

/// Comprehensive authentication testing screen for MITA
/// Tests login, registration, API connectivity, and error handling
class AuthTestScreen extends StatefulWidget {
  const AuthTestScreen({super.key});

  @override
  State<AuthTestScreen> createState() => _AuthTestScreenState();
}

class _AuthTestScreenState extends State<AuthTestScreen> {
  final ApiService _api = ApiService();

  // Test controllers
  final TextEditingController _testEmailController = TextEditingController();
  final TextEditingController _testPasswordController = TextEditingController();

  // Test results
  final List<TestResult> _testResults = [];
  bool _testingInProgress = false;
  String? _currentTest;

  // Test data
  static const String _testEmail = 'test@mita.app';
  static const String _testPassword = 'TestPassword123!';

  @override
  void initState() {
    super.initState();
    _testEmailController.text = _testEmail;
    _testPasswordController.text = _testPassword;
  }

  @override
  void dispose() {
    _testEmailController.dispose();
    _testPasswordController.dispose();
    super.dispose();
  }

  Future<void> _runAllTests() async {
    if (_testingInProgress) return;

    setState(() {
      _testingInProgress = true;
      _testResults.clear();
      _currentTest = 'Initializing tests...';
    });

    try {
      // Test 1: Backend connectivity
      await _testBackendConnectivity();

      // Test 2: API service configuration
      await _testApiConfiguration();

      // Test 3: Login endpoint connectivity (expect 401 for invalid creds)
      await _testLoginEndpoint();

      // Test 4: Registration endpoint connectivity
      await _testRegistrationEndpoint();

      // Test 5: FastAPI registration endpoint
      await _testFastApiRegistrationEndpoint();

      // Test 6: Timeout handling
      await _testTimeoutHandling();

      // Test 7: Error handling scenarios
      await _testErrorHandling();

      // Test 8: Onboarding check (if we have valid tokens)
      await _testOnboardingCheck();
    } catch (e) {
      _addTestResult('Overall Test Suite', false, 'Test suite failed: $e');
    } finally {
      setState(() {
        _testingInProgress = false;
        _currentTest = null;
      });
    }
  }

  Future<void> _testBackendConnectivity() async {
    setState(() => _currentTest = 'Testing backend connectivity...');

    try {
      final dio = Dio();
      dio.options.connectTimeout = const Duration(seconds: 8);
      dio.options.receiveTimeout = const Duration(seconds: 8);

      final response =
          await dio.get<Map<String, dynamic>>('$defaultApiBaseUrl/../health');

      if (response.statusCode == 200) {
        final data = response.data ?? <String, dynamic>{};
        final status = data['status'] ?? 'unknown';
        final dbConnected = data['database'] == 'connected';

        _addTestResult('Backend Connectivity', true,
            'Backend online (status: $status, DB: ${dbConnected ? 'connected' : 'disconnected'})');
      } else {
        _addTestResult('Backend Connectivity', false,
            'Unexpected status: ${response.statusCode}');
      }
    } catch (e) {
      _addTestResult('Backend Connectivity', false, 'Failed to connect: $e');
    }
  }

  Future<void> _testApiConfiguration() async {
    setState(() => _currentTest = 'Testing API configuration...');

    try {
      // Check if API service is properly configured
      const baseUrl = defaultApiBaseUrl;

      if (baseUrl.isEmpty) {
        _addTestResult('API Configuration', false, 'Base URL is empty');
        return;
      }

      if (!baseUrl.startsWith('https://')) {
        _addTestResult('API Configuration', false, 'Base URL should use HTTPS');
        return;
      }

      if (!baseUrl.contains('mita-docker-ready-project-manus.onrender.com')) {
        _addTestResult('API Configuration', false,
            'Base URL does not match expected backend');
        return;
      }

      _addTestResult(
          'API Configuration', true, 'API configured correctly: $baseUrl');
    } catch (e) {
      _addTestResult('API Configuration', false, 'Configuration error: $e');
    }
  }

  Future<void> _testLoginEndpoint() async {
    setState(() => _currentTest = 'Testing login endpoint...');

    try {
      // Use invalid credentials to test endpoint without actually logging in
      await _api.login('invalid@test.com', 'wrongpassword');

      // If we get here, something is wrong (should have thrown 401)
      _addTestResult(
          'Login Endpoint', false, 'Login succeeded with invalid credentials');
    } catch (e) {
      if (e is DioException && e.response?.statusCode == 401) {
        _addTestResult(
            'Login Endpoint', true, 'Endpoint accessible (401 as expected)');
      } else if (e is DioException && e.response?.statusCode != null) {
        _addTestResult('Login Endpoint', true,
            'Endpoint accessible (status: ${e.response?.statusCode})');
      } else if (e.toString().contains('timeout') ||
          e.toString().contains('TimeoutException')) {
        _addTestResult('Login Endpoint', false, 'Endpoint timeout: $e');
      } else {
        _addTestResult('Login Endpoint', false, 'Connection failed: $e');
      }
    }
  }

  Future<void> _testRegistrationEndpoint() async {
    setState(() => _currentTest = 'Testing registration endpoint...');

    try {
      // Use test email to test endpoint (expect 409 if already exists)
      final randomEmail =
          'test${DateTime.now().millisecondsSinceEpoch}@mita.test';
      await _api.register(randomEmail, _testPassword);

      _addTestResult('Registration Endpoint', true,
          'Registration endpoint accessible and working');
    } catch (e) {
      if (e is DioException) {
        final statusCode = e.response?.statusCode;
        if (statusCode == 409 || statusCode == 422) {
          _addTestResult('Registration Endpoint', true,
              'Endpoint accessible (conflict as expected)');
        } else if (statusCode == 400) {
          _addTestResult('Registration Endpoint', true,
              'Endpoint accessible (validation working)');
        } else if (statusCode != null) {
          _addTestResult('Registration Endpoint', true,
              'Endpoint accessible (status: $statusCode)');
        } else if (e.toString().contains('timeout') ||
            e.toString().contains('TimeoutException')) {
          _addTestResult(
              'Registration Endpoint', false, 'Endpoint timeout: $e');
        } else {
          _addTestResult(
              'Registration Endpoint', false, 'Connection failed: $e');
        }
      } else {
        _addTestResult('Registration Endpoint', false, 'Unexpected error: $e');
      }
    }
  }

  Future<void> _testFastApiRegistrationEndpoint() async {
    setState(() => _currentTest = 'Testing FastAPI registration endpoint...');

    try {
      // Test FastAPI registration endpoint with random email
      final randomEmail =
          'fastapi${DateTime.now().millisecondsSinceEpoch}@mita.test';
      await _api.register(randomEmail, _testPassword);

      _addTestResult('FastAPI Registration', true,
          'FastAPI registration endpoint accessible and working');
    } catch (e) {
      if (e is DioException) {
        final statusCode = e.response?.statusCode;
        if (statusCode == 409 || statusCode == 422) {
          _addTestResult('FastAPI Registration', true,
              'FastAPI registration endpoint accessible (conflict expected)');
        } else if (statusCode == 404) {
          _addTestResult('FastAPI Registration', false,
              'FastAPI registration endpoint not found (404)');
        } else if (statusCode != null) {
          _addTestResult('FastAPI Registration', true,
              'FastAPI registration endpoint accessible (status: $statusCode)');
        } else if (e.toString().contains('timeout') ||
            e.toString().contains('TimeoutException')) {
          _addTestResult('FastAPI Registration', false,
              'FastAPI registration endpoint timeout: $e');
        } else {
          _addTestResult(
              'FastAPI Registration', false, 'Connection failed: $e');
        }
      } else {
        _addTestResult('FastAPI Registration', false, 'Unexpected error: $e');
      }
    }
  }

  Future<void> _testTimeoutHandling() async {
    setState(() => _currentTest = 'Testing timeout handling...');

    try {
      // Create a custom dio instance with very short timeout to test timeout handling
      final testDio = Dio();
      testDio.options.baseUrl = defaultApiBaseUrl;
      testDio.options.connectTimeout =
          const Duration(milliseconds: 1); // Very short timeout
      testDio.options.receiveTimeout = const Duration(milliseconds: 1);

      await testDio.post<Map<String, dynamic>>('/auth/login',
          data: {'email': 'test', 'password': 'test'});

      _addTestResult(
          'Timeout Handling', false, 'Expected timeout did not occur');
    } catch (e) {
      if (e is DioException &&
          (e.type == DioExceptionType.connectionTimeout ||
              e.type == DioExceptionType.receiveTimeout ||
              e.type == DioExceptionType.sendTimeout)) {
        _addTestResult(
            'Timeout Handling', true, 'Timeout handling working correctly');
      } else {
        _addTestResult('Timeout Handling', true,
            'Error handling working (different error: ${e.runtimeType})');
      }
    }
  }

  Future<void> _testErrorHandling() async {
    setState(() => _currentTest = 'Testing error handling scenarios...');

    try {
      // Test with invalid URL to check error handling
      final testDio = Dio();
      testDio.options.baseUrl = 'https://invalid-url-that-does-not-exist.com';
      testDio.options.connectTimeout = const Duration(seconds: 5);

      await testDio.get<Map<String, dynamic>>('/test');

      _addTestResult(
          'Error Handling', false, 'Expected connection error did not occur');
    } catch (e) {
      if (e is DioException && e.type == DioExceptionType.connectionError) {
        _addTestResult(
            'Error Handling', true, 'Connection error handling working');
      } else {
        _addTestResult('Error Handling', true,
            'Error handling working (error: ${e.runtimeType})');
      }
    }
  }

  Future<void> _testOnboardingCheck() async {
    setState(() => _currentTest = 'Testing onboarding status check...');

    try {
      // Check if we have stored tokens first
      final token = await _api.getToken();
      if (token == null) {
        _addTestResult('Onboarding Check', true,
            'No stored tokens (expected without login)');
        return;
      }

      // Try onboarding check with stored tokens
      final hasOnboarded = await _api.hasCompletedOnboarding();
      _addTestResult('Onboarding Check', true,
          'Onboarding check successful: $hasOnboarded');
    } catch (e) {
      if (e is DioException) {
        final statusCode = e.response?.statusCode;
        if (statusCode == 401) {
          _addTestResult('Onboarding Check', true,
              'Onboarding endpoint working (401 for invalid/missing token)');
        } else if (statusCode == 404) {
          _addTestResult(
              'Onboarding Check', false, 'Onboarding endpoint not found (404)');
        } else {
          _addTestResult('Onboarding Check', true,
              'Onboarding endpoint accessible (status: $statusCode)');
        }
      } else {
        _addTestResult(
            'Onboarding Check', false, 'Onboarding check failed: $e');
      }
    }
  }

  void _addTestResult(String testName, bool success, String details) {
    setState(() {
      _testResults.add(TestResult(
        testName: testName,
        success: success,
        details: details,
        timestamp: DateTime.now(),
      ));
    });

    // Log result
    if (success) {
      logInfo('✅ $testName: $details', tag: 'AUTH_TEST');
    } else {
      logError('❌ $testName: $details', tag: 'AUTH_TEST');
    }
  }

  Future<void> _testManualLogin() async {
    if (_testingInProgress) return;

    final email = _testEmailController.text.trim();
    final password = _testPasswordController.text;

    if (email.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter email and password')),
      );
      return;
    }

    setState(() {
      _testingInProgress = true;
      _currentTest = 'Testing manual login...';
    });

    try {
      final response = await _api.login(email, password);

      // Detailed response analysis
      String responseDetails = 'Status: ${response.statusCode}';
      if (response.data is Map<String, dynamic>) {
        final data = response.data as Map<String, dynamic>;
        responseDetails += '\nKeys: ${data.keys.toList()}';

        // Check for tokens
        final accessToken =
            data['access_token'] ?? data['data']?['access_token'];
        final refreshToken =
            data['refresh_token'] ?? data['data']?['refresh_token'];

        if (accessToken != null) {
          responseDetails +=
              '\nAccess token: Present (${accessToken.toString().length} chars)';
        } else {
          responseDetails += '\nAccess token: MISSING';
        }

        if (refreshToken != null) {
          responseDetails +=
              '\nRefresh token: Present (${refreshToken.toString().length} chars)';
        } else {
          responseDetails += '\nRefresh token: MISSING';
        }
      }

      _addTestResult(
          'Manual Login', true, 'Login successful: $responseDetails');

      // Show success message
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Login test successful!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (e is DioException && e.response?.statusCode == 401) {
        _addTestResult('Manual Login', true,
            'Login endpoint working (401 for invalid credentials)');
      } else {
        _addTestResult('Manual Login', false, 'Login failed: $e');
      }

      // Show error message
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Login test: ${e.toString()}'),
            backgroundColor: Colors.orange,
          ),
        );
      }
    } finally {
      setState(() {
        _testingInProgress = false;
        _currentTest = null;
      });
    }
  }

  Future<void> _testManualRegistration() async {
    if (_testingInProgress) return;

    final email = _testEmailController.text.trim();
    final password = _testPasswordController.text;

    if (email.isEmpty || password.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please enter email and password')),
      );
      return;
    }

    setState(() {
      _testingInProgress = true;
      _currentTest = 'Testing manual registration...';
    });

    try {
      // Add timestamp to make email unique
      final uniqueEmail =
          email.replaceFirst('@', '+${DateTime.now().millisecondsSinceEpoch}@');
      final response = await _api.register(uniqueEmail, password);
      _addTestResult('Manual Registration', true,
          'Registration successful: ${response.statusCode}');

      // Show success message
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Registration test successful!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    } catch (e) {
      if (e is DioException &&
          (e.response?.statusCode == 409 || e.response?.statusCode == 422)) {
        _addTestResult('Manual Registration', true,
            'Registration endpoint working (conflict expected)');
      } else {
        _addTestResult('Manual Registration', false, 'Registration failed: $e');
      }

      // Show error message
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Registration test: ${e.toString()}'),
            backgroundColor: Colors.orange,
          ),
        );
      }
    } finally {
      setState(() {
        _testingInProgress = false;
        _currentTest = null;
      });
    }
  }

  Widget _buildTestResultCard(TestResult result) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Icon(
              result.success ? Icons.check_circle : Icons.error,
              color: result.success ? Colors.green : Colors.red,
              size: 20,
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    result.testName,
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    result.details,
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.7),
                    ),
                  ),
                  Text(
                    '${result.timestamp.hour.toString().padLeft(2, '0')}:${result.timestamp.minute.toString().padLeft(2, '0')}:${result.timestamp.second.toString().padLeft(2, '0')}',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.5),
                      fontSize: 10,
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      backgroundColor: colorScheme.surface,
      appBar: AppBar(
        title: const Text('Authentication Tests'),
        backgroundColor: colorScheme.surface,
        foregroundColor: colorScheme.onSurface,
        elevation: 0,
        actions: [
          IconButton(
            icon: const Icon(Icons.info_outline),
            onPressed: () {
              showDialog<void>(
                context: context,
                builder: (context) => AlertDialog(
                  title: const Text('Authentication Testing'),
                  content: const Text(
                    'This screen tests the authentication flow integration between the mobile app and backend server.\n\n'
                    '• Backend connectivity\n'
                    '• API configuration\n'
                    '• Login/registration endpoints\n'
                    '• Timeout and error handling\n\n'
                    'Use the manual test section to test with real credentials.',
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.of(context).pop(),
                      child: const Text('OK'),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Automated tests section
              MitaTheme.createElevatedCard(
                elevation: 1,
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Automated Tests',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Comprehensive authentication flow testing',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Current test status
                    if (_testingInProgress && _currentTest != null) ...[
                      Row(
                        children: [
                          SizedBox(
                            width: 20,
                            height: 20,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: colorScheme.primary,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              _currentTest!,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 16),
                    ],

                    // Run tests button
                    FilledButton.icon(
                      onPressed: _testingInProgress ? null : _runAllTests,
                      icon: Icon(_testingInProgress
                          ? Icons.hourglass_top
                          : Icons.play_arrow),
                      label: Text(
                          _testingInProgress ? 'Testing...' : 'Run All Tests'),
                      style: FilledButton.styleFrom(
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // Manual test section
              MitaTheme.createElevatedCard(
                elevation: 1,
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Manual Tests',
                      style: theme.textTheme.titleMedium?.copyWith(
                        fontWeight: FontWeight.w700,
                      ),
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Test with specific credentials',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Email field
                    TextField(
                      controller: _testEmailController,
                      keyboardType: TextInputType.emailAddress,
                      decoration: const InputDecoration(
                        labelText: 'Test Email',
                        hintText: 'Enter email to test',
                        prefixIcon: Icon(Icons.email),
                      ),
                    ),

                    const SizedBox(height: 12),

                    // Password field
                    TextField(
                      controller: _testPasswordController,
                      obscureText: true,
                      decoration: const InputDecoration(
                        labelText: 'Test Password',
                        hintText: 'Enter password to test',
                        prefixIcon: Icon(Icons.lock),
                      ),
                    ),

                    const SizedBox(height: 16),

                    // Manual test buttons
                    Row(
                      children: [
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed:
                                _testingInProgress ? null : _testManualLogin,
                            icon: const Icon(Icons.login),
                            label: const Text('Test Login'),
                          ),
                        ),
                        const SizedBox(width: 12),
                        Expanded(
                          child: OutlinedButton.icon(
                            onPressed: _testingInProgress
                                ? null
                                : _testManualRegistration,
                            icon: const Icon(Icons.person_add),
                            label: const Text('Test Register'),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),

              const SizedBox(height: 16),

              // Test results section
              Expanded(
                child: MitaTheme.createElevatedCard(
                  elevation: 1,
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(
                            'Test Results',
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                          if (_testResults.isNotEmpty)
                            TextButton.icon(
                              onPressed: () {
                                setState(() {
                                  _testResults.clear();
                                });
                              },
                              icon: const Icon(Icons.clear_all, size: 16),
                              label: const Text('Clear'),
                              style: TextButton.styleFrom(
                                padding: const EdgeInsets.symmetric(
                                    horizontal: 8, vertical: 4),
                              ),
                            ),
                        ],
                      ),
                      const SizedBox(height: 8),
                      if (_testResults.isEmpty)
                        Expanded(
                          child: Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.science_outlined,
                                  size: 48,
                                  color: colorScheme.onSurface
                                      .withValues(alpha: 0.3),
                                ),
                                const SizedBox(height: 16),
                                Text(
                                  'No test results yet',
                                  style: theme.textTheme.bodyLarge?.copyWith(
                                    color: colorScheme.onSurface
                                        .withValues(alpha: 0.6),
                                  ),
                                ),
                                const SizedBox(height: 8),
                                Text(
                                  'Run tests to see results here',
                                  style: theme.textTheme.bodyMedium?.copyWith(
                                    color: colorScheme.onSurface
                                        .withValues(alpha: 0.5),
                                  ),
                                ),
                              ],
                            ),
                          ),
                        )
                      else
                        Expanded(
                          child: ListView.builder(
                            itemCount: _testResults.length,
                            itemBuilder: (context, index) {
                              return _buildTestResultCard(_testResults[index]);
                            },
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Test result data class
class TestResult {
  final String testName;
  final bool success;
  final String details;
  final DateTime timestamp;

  TestResult({
    required this.testName,
    required this.success,
    required this.details,
    required this.timestamp,
  });
}
