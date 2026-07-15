import 'package:flutter/material.dart';

enum MessageType { info, warning, error, success }

class MessageService {
  MessageService._();
  static final MessageService instance = MessageService._();

  // Allow creation of instances for specific use cases
  factory MessageService() => instance;

  final GlobalKey<ScaffoldMessengerState> messengerKey =
      GlobalKey<ScaffoldMessengerState>();

  String? _lastErrorText;
  DateTime? _lastErrorShownAt;

  void showError(String text) {
    // One failure — one visible signal. Several requests can fail from the
    // same outage within a frame; queueing an identical red SnackBar per
    // request kept the toast on screen for minutes.
    final now = DateTime.now();
    if (text == _lastErrorText &&
        _lastErrorShownAt != null &&
        now.difference(_lastErrorShownAt!) < const Duration(seconds: 4)) {
      return;
    }
    _lastErrorText = text;
    _lastErrorShownAt = now;
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

  /// Clear all currently displayed messages/snackbars
  /// Call this after successful login to remove any stale error messages
  void clearMessages() {
    messengerKey.currentState?.clearSnackBars();
  }
}
