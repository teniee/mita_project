import 'package:flutter/material.dart';

enum MessageType { info, warning, error, success }

class MessageService {
  MessageService._();
  static final MessageService instance = MessageService._();

  // Allow creation of instances for specific use cases
  factory MessageService() => instance;

  final GlobalKey<ScaffoldMessengerState> messengerKey = GlobalKey<ScaffoldMessengerState>();

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

  void showMessage(
    String message, {
    MessageType type = MessageType.info,
    Duration duration = const Duration(seconds: 4),
  }) {
    Color backgroundColor;
    switch (type) {
      case MessageType.error:
        backgroundColor = Colors.red;
        break;
      case MessageType.warning:
        backgroundColor = Colors.orange;
        break;
      case MessageType.success:
        backgroundColor = Colors.green;
        break;
      case MessageType.info:
      default:
        backgroundColor = Colors.blue;
        break;
    }

    messengerKey.currentState?.showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: backgroundColor,
        duration: duration,
      ),
    );
  }
}
