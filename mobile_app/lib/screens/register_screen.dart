import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../services/password_validation_service.dart';
import '../services/timeout_manager_service.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

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

  PasswordValidationResult _validatePassword(String password) {
    return PasswordValidationService.validatePassword(password);
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
    
    final passwordValidation = _validatePassword(password);
    if (!passwordValidation.isValid) {
      return passwordValidation.issues.first;
    }
    if (!passwordValidation.isStrong) {
      return 'Password does not meet security requirements. ${passwordValidation.issues.join('; ')}';
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
      // 🚨 EMERGENCY: Try emergency registration first for faster signup
      logInfo('🚨 ATTEMPTING EMERGENCY REGISTRATION for better performance', tag: 'REGISTER');
      
      final response = await _api.emergencyRegister(
        _emailController.text.trim(),
        _passwordController.text,
      );
      
      final accessToken = response.data['access_token'] as String;
      final refreshToken = response.data['refresh_token'] as String?; // May be null for emergency endpoint
      
      // Save tokens (emergency endpoint may not provide refresh token)
      await _api.saveTokens(accessToken, refreshToken ?? '');
      
      if (!mounted) return;
      
      logInfo('🚨 EMERGENCY REGISTRATION SUCCESS - proceeding to onboarding', tag: 'REGISTER');
      
      // For emergency registration, always go to onboarding since it's a new account
      Navigator.pushReplacementNamed(context, '/onboarding_region');
      
    } catch (emergencyError) {
      logError('🚨 EMERGENCY REGISTRATION FAILED, trying regular registration', tag: 'REGISTER', error: emergencyError);
      
      // Fallback to regular registration
      try {
        final response = await _api.register(
          _emailController.text.trim(),
          _passwordController.text,
        );
        final accessToken = response.data['access_token'] as String;
        final refreshToken = response.data['refresh_token'] as String;
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
              final data = dioError.response?.data;
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
        
        // Enhanced error handling with proper timeout detection
        if (errorMessage == 'Registration failed') {
          if (e is DioException) {
            switch (e.type) {
              case DioExceptionType.receiveTimeout:
                errorMessage = 'Registration is taking longer than expected. Our servers may be busy. Please try again in a moment.';
                break;
              case DioExceptionType.sendTimeout:
                errorMessage = 'Upload timeout. Please check your internet connection and try again.';
                break;
              case DioExceptionType.connectionTimeout:
                errorMessage = 'Connection timeout. Please check your internet connection and try again.';
                break;
              case DioExceptionType.connectionError:
                errorMessage = 'Connection error. Please check your internet connection and try again.';
                break;
              case DioExceptionType.badResponse:
                final statusCode = e.response?.statusCode;
                if (statusCode == 400) {
                  errorMessage = 'Invalid email or password format';
                } else if (statusCode == 409 || statusCode == 422) {
                  errorMessage = 'This email is already registered. Try logging in instead.';
                } else if (statusCode != null && statusCode >= 500) {
                  errorMessage = 'Server error. Please try again later.';
                } else {
                  errorMessage = 'Registration failed. Please try again.';
                }
                break;
              default:
                errorMessage = 'Registration failed. Please try again.';
            }
          } else if (e is TimeoutException) {
            errorMessage = 'Registration timeout. Our servers may be busy. Please try again in a moment.';
          } else if (e.toString().contains('Email already exists')) {
            errorMessage = 'This email is already registered. Try logging in instead.';
          } else if (e.toString().contains('SocketException') || 
                     e.toString().contains('network') ||
                     e.toString().contains('HandshakeException')) {
            errorMessage = 'Network error. Check your internet connection and try again.';
          } else {
            errorMessage = 'Registration failed. Please try again.';
          }
        }
        
        setState(() {
          _loading = false;
          _error = errorMessage;
        });
      }
    } finally {
      if (mounted) {
        setState(() {
          _loading = false;
        });
      }
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

