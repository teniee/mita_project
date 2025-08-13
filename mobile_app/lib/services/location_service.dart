import 'package:geolocator/geolocator.dart';
import 'package:geocoding/geocoding.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'logging_service.dart';

/// Location service for detecting user's country and region
class LocationService {
  static final LocationService _instance = LocationService._internal();
  factory LocationService() => _instance;
  LocationService._internal();

  static const String _countryCodeKey = 'user_country_code';
  static const String _stateCodeKey = 'user_state_code';
  static const String _locationSetKey = 'location_manually_set';

  /// Check if location permissions are granted
  Future<bool> hasLocationPermission() async {
    LocationPermission permission = await Geolocator.checkPermission();
    return permission == LocationPermission.always || 
           permission == LocationPermission.whileInUse;
  }

  /// Request location permissions
  Future<bool> requestLocationPermission() async {
    LocationPermission permission = await Geolocator.checkPermission();
    
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    
    if (permission == LocationPermission.deniedForever) {
      return false;
    }
    
    return permission == LocationPermission.always || 
           permission == LocationPermission.whileInUse;
  }

  /// Get current location and derive country/state
  Future<Map<String, String?>> detectLocation() async {
    try {
      // Check if location services are enabled
      bool serviceEnabled = await Geolocator.isLocationServiceEnabled();
      if (!serviceEnabled) {
        logWarning('Location services are disabled', tag: 'LOCATION_SERVICE');
        return {'country': null, 'state': null, 'error': 'Location services disabled'};
      }

      // Check/request permissions
      bool hasPermission = await requestLocationPermission();
      if (!hasPermission) {
        logWarning('Location permission denied', tag: 'LOCATION_SERVICE');
        return {'country': null, 'state': null, 'error': 'Location permission denied'};
      }

      // Get current position
      Position position = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.low,
        timeLimit: const Duration(seconds: 10),
      );

      // Reverse geocode to get address
      List<Placemark> placemarks = await placemarkFromCoordinates(
        position.latitude,
        position.longitude,
      );

      if (placemarks.isNotEmpty) {
        final placemark = placemarks.first;
        final countryCode = placemark.isoCountryCode?.toUpperCase();
        final stateCode = placemark.administrativeArea?.toUpperCase();
        
        logInfo('Detected location: Country=$countryCode, State=$stateCode', tag: 'LOCATION_SERVICE');
        
        return {
          'country': countryCode,
          'state': stateCode,
          'error': null,
        };
      }

      return {'country': null, 'state': null, 'error': 'Unable to determine location'};
    } catch (e) {
      logError('Location detection error: $e', tag: 'LOCATION_SERVICE');
      return {'country': null, 'state': null, 'error': e.toString()};
    }
  }

  /// Save user's location to preferences
  Future<void> saveUserLocation(String countryCode, {String? stateCode, bool manuallySet = false}) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_countryCodeKey, countryCode.toUpperCase());
    
    if (stateCode != null) {
      await prefs.setString(_stateCodeKey, stateCode.toUpperCase());
    } else {
      await prefs.remove(_stateCodeKey);
    }
    
    await prefs.setBool(_locationSetKey, manuallySet);
    logInfo('Saved user location: $countryCode, $stateCode (manual: $manuallySet)', tag: 'LOCATION_SERVICE');
  }

  /// Get saved user location from preferences
  Future<Map<String, String?>> getSavedUserLocation() async {
    final prefs = await SharedPreferences.getInstance();
    final countryCode = prefs.getString(_countryCodeKey);
    final stateCode = prefs.getString(_stateCodeKey);
    final manuallySet = prefs.getBool(_locationSetKey) ?? false;
    
    return {
      'country': countryCode,
      'state': stateCode,
      'manually_set': manuallySet.toString(),
    };
  }

  /// Get user's location (saved or detected)
  Future<Map<String, String?>> getUserLocation({bool forceDetection = false}) async {
    // First try to get saved location
    if (!forceDetection) {
      final saved = await getSavedUserLocation();
      if (saved['country'] != null) {
        logInfo('Using saved location: ${saved['country']}, ${saved['state']}', tag: 'LOCATION_SERVICE');
        return saved;
      }
    }

    // Try to detect location
    final detected = await detectLocation();
    if (detected['country'] != null && detected['error'] == null) {
      // Save detected location
      await saveUserLocation(
        detected['country']!,
        stateCode: detected['state'],
        manuallySet: false,
      );
      logInfo('Using detected location: ${detected['country']}, ${detected['state']}', tag: 'LOCATION_SERVICE');
      return detected;
    }

    // Fallback to US if no location can be determined
    logInfo('Using fallback location: US', tag: 'LOCATION_SERVICE');
    return {'country': 'US', 'state': null, 'error': detected['error']};
  }

  /// Clear saved location data
  Future<void> clearSavedLocation() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_countryCodeKey);
    await prefs.remove(_stateCodeKey);
    await prefs.remove(_locationSetKey);
    logInfo('Cleared saved location data', tag: 'LOCATION_SERVICE');
  }

  /// Check if location was manually set by user
  Future<bool> isLocationManuallySet() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getBool(_locationSetKey) ?? false;
  }

  /// Get list of supported countries for manual selection
  List<Map<String, String>> getSupportedCountriesForSelection() {
    return [
      {'code': 'US', 'name': 'United States', 'flag': '🇺🇸'},
    ];
  }

  /// Get US states for selection
  List<Map<String, String>> getUSStatesForSelection() {
    return [
      {'code': 'AL', 'name': 'Alabama'},
      {'code': 'AK', 'name': 'Alaska'},
      {'code': 'AZ', 'name': 'Arizona'},
      {'code': 'AR', 'name': 'Arkansas'},
      {'code': 'CA', 'name': 'California'},
      {'code': 'CO', 'name': 'Colorado'},
      {'code': 'CT', 'name': 'Connecticut'},
      {'code': 'DE', 'name': 'Delaware'},
      {'code': 'FL', 'name': 'Florida'},
      {'code': 'GA', 'name': 'Georgia'},
      {'code': 'HI', 'name': 'Hawaii'},
      {'code': 'ID', 'name': 'Idaho'},
      {'code': 'IL', 'name': 'Illinois'},
      {'code': 'IN', 'name': 'Indiana'},
      {'code': 'IA', 'name': 'Iowa'},
      {'code': 'KS', 'name': 'Kansas'},
      {'code': 'KY', 'name': 'Kentucky'},
      {'code': 'LA', 'name': 'Louisiana'},
      {'code': 'ME', 'name': 'Maine'},
      {'code': 'MD', 'name': 'Maryland'},
      {'code': 'MA', 'name': 'Massachusetts'},
      {'code': 'MI', 'name': 'Michigan'},
      {'code': 'MN', 'name': 'Minnesota'},
      {'code': 'MS', 'name': 'Mississippi'},
      {'code': 'MO', 'name': 'Missouri'},
      {'code': 'MT', 'name': 'Montana'},
      {'code': 'NE', 'name': 'Nebraska'},
      {'code': 'NV', 'name': 'Nevada'},
      {'code': 'NH', 'name': 'New Hampshire'},
      {'code': 'NJ', 'name': 'New Jersey'},
      {'code': 'NM', 'name': 'New Mexico'},
      {'code': 'NY', 'name': 'New York'},
      {'code': 'NC', 'name': 'North Carolina'},
      {'code': 'ND', 'name': 'North Dakota'},
      {'code': 'OH', 'name': 'Ohio'},
      {'code': 'OK', 'name': 'Oklahoma'},
      {'code': 'OR', 'name': 'Oregon'},
      {'code': 'PA', 'name': 'Pennsylvania'},
      {'code': 'RI', 'name': 'Rhode Island'},
      {'code': 'SC', 'name': 'South Carolina'},
      {'code': 'SD', 'name': 'South Dakota'},
      {'code': 'TN', 'name': 'Tennessee'},
      {'code': 'TX', 'name': 'Texas'},
      {'code': 'UT', 'name': 'Utah'},
      {'code': 'VT', 'name': 'Vermont'},
      {'code': 'VA', 'name': 'Virginia'},
      {'code': 'WA', 'name': 'Washington'},
      {'code': 'WV', 'name': 'West Virginia'},
      {'code': 'WI', 'name': 'Wisconsin'},
      {'code': 'WY', 'name': 'Wyoming'},
    ];
  }

  /// Format location for display
  String formatLocationForDisplay(String countryCode, {String? stateCode}) {
    final countries = getSupportedCountriesForSelection();
    final country = countries.firstWhere(
      (c) => c['code'] == countryCode,
      orElse: () => {'name': countryCode, 'flag': ''},
    );
    
    String display = '${country['flag']} ${country['name']}';
    
    if (stateCode != null && countryCode == 'US') {
      final states = getUSStatesForSelection();
      final state = states.firstWhere(
        (s) => s['code'] == stateCode,
        orElse: () => {'name': stateCode},
      );
      display += ', ${state['name']}';
    }
    
    return display;
  }
}