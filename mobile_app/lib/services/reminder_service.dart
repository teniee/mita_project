import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class ReminderService {
  static final FlutterLocalNotificationsPlugin _plugin = FlutterLocalNotificationsPlugin();

  static Future<void> scheduleDailyReminder() async {
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const ios = DarwinInitializationSettings();
    await _plugin.initialize(
      const InitializationSettings(android: android, iOS: ios),
    );
    await _plugin.show(
      0,
      'Mood Check',
      'Remember to log your mood today!',
      const NotificationDetails(
        android: AndroidNotificationDetails('mood', 'Mood'),
        iOS: DarwinNotificationDetails(),
      ),
    );
  }
}
