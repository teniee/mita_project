import 'package:flutter/material.dart';

class MessageService {
  MessageService._();
  static final MessageService instance = MessageService._();

  final GlobalKey<ScaffoldMessengerState> messengerKey =
      GlobalKey<ScaffoldMessengerState>();

  void showError(String text) {
    messengerKey.currentState?.showSnackBar(
      SnackBar(content: Text(text), backgroundColor: Colors.red),
    );
  }

  void showRateLimit() {
    messengerKey.currentState?.showSnackBar(
      const SnackBar(
        content: Text('Too many requests, please wait a minute.'),
        backgroundColor: Colors.orange,
      ),
    );
  }
}
