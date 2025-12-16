import 'package:flutter/material.dart';

/// Minimal debug test screen to verify rendering works
class DebugTestScreen extends StatelessWidget {
  const DebugTestScreen({super.key});

  @override
  Widget build(BuildContext context) {
    print('DEBUG: DebugTestScreen building...');

    return Scaffold(
      backgroundColor: Colors.blue,  // Bright color to see if it renders
      appBar: AppBar(
        title: const Text('DEBUG TEST SCREEN'),
        backgroundColor: Colors.red,
      ),
      body: Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Text(
              'DEBUG TEST',
              style: TextStyle(
                fontSize: 48,
                fontWeight: FontWeight.bold,
                color: Colors.white,
              ),
            ),
            const SizedBox(height: 20),
            const Text(
              'If you see this, rendering works!',
              style: TextStyle(fontSize: 24, color: Colors.white),
            ),
            const SizedBox(height: 40),
            ElevatedButton(
              onPressed: () {
                print('DEBUG: Button pressed!');
              },
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green,
                padding: const EdgeInsets.symmetric(horizontal: 40, vertical: 20),
              ),
              child: const Text(
                'TEST BUTTON',
                style: TextStyle(fontSize: 20, color: Colors.white),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
