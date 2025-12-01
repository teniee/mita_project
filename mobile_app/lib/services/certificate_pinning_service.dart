import 'dart:io';
import 'package:dio/dio.dart';
import 'package:dio/io.dart';
import 'package:flutter/foundation.dart';
import 'package:crypto/crypto.dart';
import 'logging_service.dart';

/// Apple-Grade Certificate Pinning Service
/// Implements SSL/TLS certificate pinning for MITA backend API
/// Prevents man-in-the-middle attacks and ensures secure communication
///
/// Production Implementation:
/// 1. Generate SHA-256 fingerprint of your SSL certificate
/// 2. Add it to _pinnedCertificates list
/// 3. Update certificates before expiry (typical 90 days)
class CertificatePinningService {
  static final CertificatePinningService _instance =
      CertificatePinningService._internal();
  factory CertificatePinningService() => _instance;
  CertificatePinningService._internal();

  /// Production SSL certificate SHA-256 fingerprints
  /// TODO: Replace with actual certificate fingerprints from mita.finance
  ///
  /// To get certificate fingerprint:
  /// openssl s_client -servername mita.finance -connect mita.finance:443 < /dev/null 2>/dev/null | \
  ///   openssl x509 -fingerprint -sha256 -noout -in /dev/stdin
  static const List<String> _pinnedCertificates = [
    // Primary certificate (mita.finance)
    // 'SHA256_FINGERPRINT_HERE',

    // Backup certificate (in case of renewal)
    // 'SHA256_FINGERPRINT_BACKUP_HERE',

    // Railway deployment certificate (if different)
    // 'SHA256_FINGERPRINT_RAILWAY_HERE',
  ];

  /// Trusted domains for certificate pinning
  static const List<String> _trustedDomains = [
    'mita.finance',
    'api.mita.finance',
    'www.mita.finance',
  ];

  /// Configure Dio client with certificate pinning
  Dio configureDioWithPinning(Dio dio) {
    if (kDebugMode) {
      logWarning(
        'Certificate pinning disabled in debug mode',
        tag: 'CERT_PINNING',
      );
      // In debug mode, allow any certificate for easier testing
      return dio;
    }

    if (_pinnedCertificates.isEmpty) {
      logWarning(
        'No pinned certificates configured - certificate pinning disabled',
        tag: 'CERT_PINNING',
      );
      return dio;
    }

    // Configure certificate validation
    (dio.httpClientAdapter as IOHttpClientAdapter).createHttpClient = () {
      final client = HttpClient();

      client.badCertificateCallback = (cert, host, port) {
        // Validate certificate
        if (!_trustedDomains.contains(host)) {
          logWarning(
            'Untrusted domain: $host',
            tag: 'CERT_PINNING',
          );
          return false;
        }

        // Get certificate SHA-256 fingerprint
        final certificateFingerprint = _getCertificateFingerprint(cert);

        // Check if certificate is pinned
        if (_pinnedCertificates.contains(certificateFingerprint)) {
          logInfo(
            'Certificate validation successful for $host',
            tag: 'CERT_PINNING',
          );
          return true;
        }

        logError(
          'Certificate pinning failed for $host - fingerprint: $certificateFingerprint',
          tag: 'CERT_PINNING',
        );
        return false;
      };

      return client;
    };

    logInfo('Certificate pinning configured successfully', tag: 'CERT_PINNING');
    return dio;
  }

  /// Get SHA-256 fingerprint of certificate
  /// FIXED: X509Certificate doesn't have sha256 property
  /// Using DER bytes and crypto package to calculate SHA-256
  String _getCertificateFingerprint(X509Certificate cert) {
    try {
      // Get certificate DER-encoded bytes
      final certDer = cert.der;

      // Compute SHA-256 hash
      final digest = sha256.convert(certDer);

      // Format as fingerprint (uppercase hex with colons)
      final fingerprint = digest.bytes
          .map((byte) => byte.toRadixString(16).padLeft(2, '0'))
          .join(':')
          .toUpperCase();

      return fingerprint;
    } catch (e) {
      logError('Failed to get certificate fingerprint: $e',
          tag: 'CERT_PINNING');
      return '';
    }
  }

  /// Validate SSL certificate manually
  Future<bool> validateCertificate(String host) async {
    if (kDebugMode) {
      return true; // Skip validation in debug mode
    }

    try {
      final socket = await SecureSocket.connect(
        host,
        443,
        timeout: const Duration(seconds: 10),
      );

      final cert = socket.peerCertificate;
      if (cert == null) {
        logError('No certificate found for $host', tag: 'CERT_PINNING');
        await socket.close();
        return false;
      }

      final fingerprint = _getCertificateFingerprint(cert);
      final isValid = _pinnedCertificates.contains(fingerprint);

      await socket.close();

      if (isValid) {
        logInfo('Certificate valid for $host', tag: 'CERT_PINNING');
      } else {
        logError(
          'Certificate invalid for $host - fingerprint: $fingerprint',
          tag: 'CERT_PINNING',
        );
      }

      return isValid;
    } catch (e) {
      logError('Certificate validation error for $host: $e',
          tag: 'CERT_PINNING');
      return false;
    }
  }

  /// Get certificate information for debugging
  /// ENHANCED: Added caching to reduce network overhead
  final Map<String, _CachedCertInfo> _certCache = {};

  Future<Map<String, dynamic>> getCertificateInfo(String host) async {
    // Check cache first
    final cached = _certCache[host];
    if (cached != null && !cached.isExpired) {
      logInfo('Using cached certificate info for $host', tag: 'CERT_PINNING');
      return cached.info;
    }

    try {
      final socket = await SecureSocket.connect(
        host,
        443,
        timeout: const Duration(seconds: 10),
      );

      final cert = socket.peerCertificate;
      if (cert == null) {
        await socket.close();
        return {'error': 'No certificate found'};
      }

      final info = {
        'subject': cert.subject,
        'issuer': cert.issuer,
        'startValidity': cert.startValidity.toIso8601String(),
        'endValidity': cert.endValidity.toIso8601String(),
        'sha256': _getCertificateFingerprint(cert),
        'isExpired': DateTime.now().isAfter(cert.endValidity),
        'daysUntilExpiry': cert.endValidity.difference(DateTime.now()).inDays,
      };

      await socket.close();

      // Cache for 24 hours
      _certCache[host] = _CachedCertInfo(
        info: info,
        fetchedAt: DateTime.now(),
        ttl: const Duration(hours: 24),
      );

      logInfo(
        'Certificate info for $host: ${info['daysUntilExpiry']} days until expiry',
        tag: 'CERT_PINNING',
      );

      return info;
    } catch (e) {
      logError('Failed to get certificate info for $host: $e',
          tag: 'CERT_PINNING');
      return {'error': e.toString()};
    }
  }

  /// Check if certificate is about to expire (< 30 days)
  Future<bool> isCertificateExpiringSoon(String host) async {
    final info = await getCertificateInfo(host);
    if (info.containsKey('error')) {
      return false;
    }

    final daysUntilExpiry = info['daysUntilExpiry'] as int?;
    if (daysUntilExpiry != null && daysUntilExpiry < 30) {
      logWarning(
        'Certificate for $host expires in $daysUntilExpiry days',
        tag: 'CERT_PINNING',
      );
      return true;
    }

    return false;
  }
}

/// Internal cache class for certificate information
class _CachedCertInfo {
  final Map<String, dynamic> info;
  final DateTime fetchedAt;
  final Duration ttl;

  _CachedCertInfo({
    required this.info,
    required this.fetchedAt,
    required this.ttl,
  });

  bool get isExpired => DateTime.now().difference(fetchedAt) > ttl;
}

/// REMOVED MISLEADING EXTENSION - Use CertificatePinningService().configureDioWithPinning(dio) directly
