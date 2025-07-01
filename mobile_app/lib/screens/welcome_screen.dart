import 'package:flutter/material.dart';
import '../services/api_service.dart'; // import API service

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({Key? key}) : super(key: key);

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;
  final ApiService _api = ApiService(); // create API instance

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(seconds: 2),
    )..forward();

    _animation = CurvedAnimation(
      parent: _controller,
      curve: Curves.easeInOut,
    );

    _checkAuth(); // check token and navigate
  }

  Future<void> _checkAuth() async {
    await Future.delayed(const Duration(seconds: 2)); // wait for animation

    final token = await _api.getToken();

    if (token == null) {
      Navigator.pushReplacementNamed(context, '/login'); // if no token
    } else {
      try {
        await _api.getUserProfile(); // try to fetch profile
        Navigator.pushReplacementNamed(context, '/main'); // success -> go to home
      } catch (e) {
        Navigator.pushReplacementNamed(context, '/login'); // error or unauthorized
      }
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF193C57),
      body: Center(
        child: ScaleTransition(
          scale: _animation,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Image.asset(
                'assets/logo/mitalogo.png',
                width: 160,
                height: 160,
              ),
              const SizedBox(height: 30),
              const Text(
                "MITA",
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  fontSize: 40,
                  color: Color(0xFFFFD25F),
                  letterSpacing: 2,
                ),
              ),
              const SizedBox(height: 12),
              const Text(
                "Money Intelligence Task Assistant",
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontWeight: FontWeight.w400,
                  fontSize: 18,
                  color: Colors.white70,
                  letterSpacing: 1,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
