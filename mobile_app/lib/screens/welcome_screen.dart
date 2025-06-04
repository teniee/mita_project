import 'package:flutter/material.dart';
import '../services/api_service.dart'; // Импорт сервиса

class WelcomeScreen extends StatefulWidget {
  const WelcomeScreen({Key? key}) : super(key: key);

  @override
  State<WelcomeScreen> createState() => _WelcomeScreenState();
}

class _WelcomeScreenState extends State<WelcomeScreen> with SingleTickerProviderStateMixin {
  late AnimationController _controller;
  late Animation<double> _animation;
  final ApiService _api = ApiService(); // Создание экземпляра API

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

    _checkAuth(); // Проверка токена и переход
  }

  Future<void> _checkAuth() async {
    await Future.delayed(const Duration(seconds: 2)); // Подождать анимацию

    final token = await _api.getToken();

    if (token == null) {
      Navigator.pushReplacementNamed(context, '/login'); // Если токена нет
    } else {
      try {
        await _api.getUserProfile(); // Попробовать получить профиль
        Navigator.pushReplacementNamed(context, '/main'); // Успех — перейти на главный экран
      } catch (e) {
        Navigator.pushReplacementNamed(context, '/login'); // Ошибка — на логин
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
