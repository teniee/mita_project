import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';
import '../services/api_service.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({Key? key}) : super(key: key);

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final ApiService _api = ApiService();
  bool _loading = false;
  String? _error;

  Future<void> _handleGoogleSignIn() async {
    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final googleUser = await GoogleSignIn().signIn();
      if (googleUser == null) {
        setState(() {
          _loading = false;
          _error = 'Sign-in cancelled';
        });
        return;
      }

      final googleAuth = await googleUser.authentication;
      final idToken = googleAuth.idToken;

      if (idToken == null) {
        setState(() {
          _loading = false;
          _error = 'Missing Google ID token';
        });
        return;
      }

      final response = await _api.loginWithGoogle(idToken);
      final accessToken = response.data['access_token'];
      final refreshToken = response.data['refresh_token'];
      final userId = response.data['user_id'];
      await _api.saveTokens(accessToken, refreshToken);
      await _api.saveUserId(userId);

      if (!mounted) return;
      Navigator.pushReplacementNamed(context, '/main');
    } catch (e) {
      setState(() {
        _loading = false;
        _error = 'Login failed: $e';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
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
                    "Sign in to MITA",
                    style: TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.w700,
                      fontSize: 24,
                      color: Color(0xFF193C57),
                    ),
                  ),
                  const SizedBox(height: 24),
                  _loading
                      ? const CircularProgressIndicator()
                      : ElevatedButton.icon(
                          icon: Image.asset(
                            'assets/logo/mitalogo.png',
                            width: 24,
                            height: 24,
                          ),
                          label: const Text("Sign in with Google"),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFFFFD25F),
                            foregroundColor: const Color(0xFF193C57),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(18),
                            ),
                            padding: const EdgeInsets.symmetric(vertical: 16, horizontal: 24),
                            textStyle: const TextStyle(
                              fontFamily: 'Sora',
                              fontWeight: FontWeight.w600,
                              fontSize: 16,
                            ),
                          ),
                          onPressed: _handleGoogleSignIn,
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
