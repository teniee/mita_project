import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({Key? key}) : super(key: key);

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final ApiService _api = ApiService();
  bool _loading = false;
  String? _error;
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _passwordController = TextEditingController();

  bool _isValidEmail(String email) {
    return RegExp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$').hasMatch(email);
  }

  bool _isValidPassword(String password) {
    return password.length >= 8;
  }

  String? _validateInputs() {
    final email = _emailController.text.trim();
    final password = _passwordController.text;

    if (email.isEmpty) {
      return 'Please enter your email';
    }
    if (!_isValidEmail(email)) {
      return 'Please enter a valid email address';
    }
    if (password.isEmpty) {
      return 'Please enter a password';
    }
    if (!_isValidPassword(password)) {
      return 'Password must be at least 8 characters long';
    }
    return null;
  }

  Future<void> _register() async {
    // Validate inputs first
    final validationError = _validateInputs();
    if (validationError != null) {
      setState(() {
        _error = validationError;
      });
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final response = await _api.register(
        _emailController.text.trim(),
        _passwordController.text,
      );
      final accessToken = response.data['access_token'];
      final refreshToken = response.data['refresh_token'];
      await _api.saveTokens(accessToken, refreshToken);
      if (!mounted) return;
      
      // Check if user has completed onboarding
      final hasOnboarded = await _api.hasCompletedOnboarding();
      if (hasOnboarded) {
        Navigator.pushReplacementNamed(context, '/main');
      } else {
        Navigator.pushReplacementNamed(context, '/onboarding_region');
      }
    } catch (e) {
      logError('Registration error: $e');
      logError('Error type: ${e.runtimeType}');
      
      String errorMessage = 'Registration failed';
      
      // Extract more specific error message from DioException
      if (e.toString().contains('DioException')) {
        try {
          // Try to extract error from response data
          final dioError = e as dynamic;
          if (dioError.response?.data != null) {
            final data = dioError.response.data;
            logInfo('Response data: $data');
            
            if (data is Map) {
              if (data.containsKey('error') && data['error'] is Map) {
                final errorDetail = data['error']['detail']?.toString() ?? '';
                if (errorDetail.contains('Email already exists')) {
                  errorMessage = 'This email is already registered. Try logging in instead.';
                } else if (errorDetail.isNotEmpty) {
                  errorMessage = errorDetail;
                }
              } else if (data.containsKey('detail')) {
                final detail = data['detail'].toString();
                if (detail.contains('Email already exists')) {
                  errorMessage = 'This email is already registered. Try logging in instead.';
                } else {
                  errorMessage = detail;
                }
              }
            }
          }
        } catch (parseError) {
          logError('Error parsing response: $parseError');
        }
      }
      
      // Fallback error handling
      if (errorMessage == 'Registration failed') {
        if (e.toString().contains('Email already exists')) {
          errorMessage = 'This email is already registered. Try logging in instead.';
        } else if (e.toString().contains('400')) {
          errorMessage = 'Invalid email or password format';
        } else if (e.toString().contains('500')) {
          errorMessage = 'Server error. Please try again later.';
        } else if (e.toString().contains('SocketException') || 
                   e.toString().contains('TimeoutException') ||
                   e.toString().contains('network') ||
                   e.toString().contains('HandshakeException')) {
          errorMessage = 'Network error. Check your internet connection and try again.';
        } else {
          errorMessage = 'Registration failed: ${e.toString()}';
        }
      }
      
      setState(() {
        _loading = false;
        _error = errorMessage;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text('Register'),
        backgroundColor: const Color(0xFFFFF9F0),
        foregroundColor: const Color(0xFF193C57),
        elevation: 0,
      ),
      body: SafeArea(
        child: Center(
          child: Card(
            elevation: 3,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(28),
            ),
            color: Colors.white,
            margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 60),
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 28),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Text(
                    'Create account',
                    style: TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.w700,
                      fontSize: 24,
                      color: Color(0xFF193C57),
                    ),
                  ),
                  const SizedBox(height: 24),
                  TextField(
                    controller: _emailController,
                    decoration: InputDecoration(
                      labelText: 'Email',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _passwordController,
                    obscureText: true,
                    decoration: InputDecoration(
                      labelText: 'Password',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(16),
                      ),
                    ),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Password must be at least 8 characters long',
                    style: TextStyle(
                      fontSize: 12,
                      color: Colors.grey,
                      fontFamily: 'Manrope',
                    ),
                  ),
                  const SizedBox(height: 16),
                  _loading
                      ? const CircularProgressIndicator()
                      : ElevatedButton(
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFFFD25F),
                            foregroundColor: const Color(0xFF193C57),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(18),
                            ),
                            padding: const EdgeInsets.symmetric(
                                vertical: 16, horizontal: 24),
                            textStyle: const TextStyle(
                              fontFamily: 'Sora',
                              fontWeight: FontWeight.w600,
                              fontSize: 16,
                            ),
                          ),
                          onPressed: _register,
                          child: const Text('Register'),
                        ),
                  TextButton(
                    onPressed: () => Navigator.pop(context),
                    child: const Text('Back to login'),
                  ),
                  if (_error != null) ...[
                    const SizedBox(height: 16),
                    Text(
                      _error!,
                      style: const TextStyle(
                        color: Colors.red,
                        fontFamily: 'Manrope',
                      ),
                    ),
                  ]
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

