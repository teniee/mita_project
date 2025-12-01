import 'package:package_info_plus/package_info_plus.dart';

/// Service for retrieving application version information
class AppVersionService {
  static AppVersionService? _instance;
  static AppVersionService get instance =>
      _instance ??= AppVersionService._internal();
  AppVersionService._internal();

  PackageInfo? _packageInfo;

  /// Initialize the service with package information
  Future<void> initialize() async {
    try {
      _packageInfo = await PackageInfo.fromPlatform();
    } catch (e) {
      // Fallback to default values if package info fails
      _packageInfo = null;
    }
  }

  /// Get the current app version
  String get appVersion {
    return _packageInfo?.version ?? '1.0.0';
  }

  /// Get the current build number
  String get buildNumber {
    return _packageInfo?.buildNumber ?? '1';
  }

  /// Get the full version string (version+build)
  String get fullVersion {
    return '$appVersion+$buildNumber';
  }

  /// Get app name
  String get appName {
    return _packageInfo?.appName ?? 'MITA';
  }

  /// Get package name
  String get packageName {
    return _packageInfo?.packageName ?? 'com.mita.app';
  }

  /// Get version data for API requests
  Map<String, String> getVersionData() {
    return {
      'app_version': appVersion,
      'build_number': buildNumber,
      'app_name': appName,
      'package_name': packageName,
    };
  }
}
