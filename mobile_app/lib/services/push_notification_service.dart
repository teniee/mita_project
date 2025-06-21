import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/material.dart';
import '../screens/advice_history_screen.dart';

Future<void> firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  // Handle background message if needed.
}

class PushNotificationService {
  static Future<void> initialize(GlobalKey<NavigatorState> navigatorKey) async {
    FirebaseMessaging.onBackgroundMessage(firebaseMessagingBackgroundHandler);
    FirebaseMessaging.onMessageOpenedApp.listen((RemoteMessage message) {
      final link = message.data['deeplink'] as String?;
      if (link != null && link.isNotEmpty) {
        navigatorKey.currentState?.pushNamed(link);
      } else {
        navigatorKey.currentState?.push(
          MaterialPageRoute(builder: (_) => const AdviceHistoryScreen()),
        );
      }
    });
  }
}
