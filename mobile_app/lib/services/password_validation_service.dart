import 'dart:math';
import 'logging_service.dart';

/// Enterprise-grade password validation service for financial applications
/// Enforces strong password requirements with comprehensive security checks
class PasswordValidationService {
  static const int _minLength = 8;
  static const int _recommendedMinLength = 12;
  static const double _minEntropy = 40.0;
  static const double _recommendedEntropy = 60.0;

  // Common weak passwords and patterns
  static const Set<String> _commonPasswords = {
    'password',
    '123456',
    '123456789',
    'qwerty',
    'abc123',
    'password123',
    'admin',
    'welcome',
    'monkey',
    'dragon',
    'letmein',
    'trustno1',
    '111111',
    'iloveyou',
    'master',
    'sunshine',
    'ashley',
    'princess',
    'football',
    'michael',
    'ninja',
    'mustang',
    'password1',
    'shadow',
    'baseball',
    'superman',
    'tigger',
    'charlie',
    'robert',
    'jennifer',
    'jordan',
    'hunter',
    'michelle',
    'harley',
    'matthew',
    'daniel',
    'andrew',
    'joshua',
    'anthony',
    'william',
    'david',
    'chris',
  };

  static const Set<String> _keyboardPatterns = {
    'qwerty',
    'qwertyuiop',
    'asdfgh',
    'asdfghjkl',
    'zxcvbn',
    'zxcvbnm',
    '123456',
    '1234567890',
    'abcdef',
    'abcdefg',
    'qwer',
    'asdf',
    'zxcv',
  };

  /// Comprehensive password validation result
  static PasswordValidationResult validatePassword(String password) {
    try {
      final issues = <String>[];
      final warnings = <String>[];
      double strength = 0.0;
      bool isStrong = true;

      logDebug('Starting comprehensive password validation',
          tag: 'PASSWORD_VALIDATION');

      // Basic length check
      if (password.length < _minLength) {
        issues.add('Password must be at least $_minLength characters long');
        isStrong = false;
      } else if (password.length < _recommendedMinLength) {
        warnings.add(
            'Consider using at least $_recommendedMinLength characters for better security');
      }

      // Character variety requirements
      bool hasLower = password.contains(RegExp(r'[a-z]'));
      bool hasUpper = password.contains(RegExp(r'[A-Z]'));
      bool hasDigits = password.contains(RegExp(r'\d'));
      bool hasSpecial =
          password.contains(RegExp(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]'));

      if (!hasLower) {
        issues.add('Password must contain at least one lowercase letter');
        isStrong = false;
      }

      if (!hasUpper) {
        issues.add('Password must contain at least one uppercase letter');
        isStrong = false;
      }

      if (!hasDigits) {
        issues.add('Password must contain at least one number');
        isStrong = false;
      }

      if (!hasSpecial) {
        issues.add(
            'Password must contain at least one special character (!@#\$%^&*...)');
        isStrong = false;
      }

      // Check for common weak passwords
      final lowerPassword = password.toLowerCase();
      if (_commonPasswords.contains(lowerPassword)) {
        issues.add(
            'This is a commonly used password. Choose something more unique');
        isStrong = false;
      }

      // Check for keyboard patterns
      for (final pattern in _keyboardPatterns) {
        if (lowerPassword.contains(pattern) && pattern.length >= 4) {
          issues.add('Avoid keyboard patterns like "$pattern"');
          isStrong = false;
          break;
        }
      }

      // Check for repeated characters
      final repeatedPattern = _checkRepeatedCharacters(password);
      if (repeatedPattern.isNotEmpty) {
        issues.add('Avoid repeated characters or patterns: $repeatedPattern');
        isStrong = false;
      }

      // Check for sequential patterns
      final sequentialIssues = _checkSequentialPatterns(password);
      if (sequentialIssues.isNotEmpty) {
        issues.addAll(sequentialIssues);
        isStrong = false;
      }

      // Check for personal information patterns
      final personalInfoIssues = _checkPersonalInformationPatterns(password);
      if (personalInfoIssues.isNotEmpty) {
        warnings.addAll(personalInfoIssues);
      }

      // Calculate entropy and strength
      final entropy = _calculateEntropy(password);
      strength = _calculatePasswordStrength(password, entropy);

      if (entropy < _minEntropy) {
        issues.add(
            'Password complexity is too low (entropy: ${entropy.toStringAsFixed(1)}/${_minEntropy.toStringAsFixed(1)})');
        isStrong = false;
      } else if (entropy < _recommendedEntropy) {
        warnings.add(
            'Consider increasing password complexity for maximum security (entropy: ${entropy.toStringAsFixed(1)}/${_recommendedEntropy.toStringAsFixed(1)})');
      }

      // Check for dictionary words
      final dictionaryWarnings = _checkDictionaryWords(password);
      if (dictionaryWarnings.isNotEmpty) {
        warnings.addAll(dictionaryWarnings);
      }

      // Generate security score
      final securityScore =
          _calculateSecurityScore(password, entropy, issues.isEmpty);

      final result = PasswordValidationResult(
        isValid: issues.isEmpty,
        isStrong: isStrong && issues.isEmpty,
        strength: strength,
        entropy: entropy,
        securityScore: securityScore,
        issues: issues,
        warnings: warnings,
        suggestions: _generateSuggestions(password, issues),
      );

      logInfo('Password validation completed',
          tag: 'PASSWORD_VALIDATION',
          extra: {
            'is_valid': result.isValid,
            'is_strong': result.isStrong,
            'entropy': entropy,
            'security_score': securityScore,
            'issues_count': issues.length,
            'warnings_count': warnings.length,
          });

      return result;
    } catch (e, stackTrace) {
      logError('Password validation failed: $e',
          tag: 'PASSWORD_VALIDATION', error: e, stackTrace: stackTrace);

      return const PasswordValidationResult(
        isValid: false,
        isStrong: false,
        strength: 0.0,
        entropy: 0.0,
        securityScore: 0,
        issues: ['Password validation error occurred'],
        warnings: [],
        suggestions: ['Please try again or contact support'],
      );
    }
  }

  /// Calculate password entropy (bits of randomness)
  static double _calculateEntropy(String password) {
    if (password.isEmpty) return 0.0;

    int charsetSize = 0;

    // Count character set size
    bool hasLower = password.contains(RegExp(r'[a-z]'));
    bool hasUpper = password.contains(RegExp(r'[A-Z]'));
    bool hasDigits = password.contains(RegExp(r'\d'));
    bool hasSpecial =
        password.contains(RegExp(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]'));

    if (hasLower) charsetSize += 26;
    if (hasUpper) charsetSize += 26;
    if (hasDigits) charsetSize += 10;
    if (hasSpecial) charsetSize += 32; // Common special characters

    if (charsetSize == 0) return 0.0;

    // Calculate entropy: log2(charset^length)
    return password.length * log(charsetSize) / ln2;
  }

  /// Calculate overall password strength (0.0 to 1.0)
  static double _calculatePasswordStrength(String password, double entropy) {
    double strength = 0.0;

    // Length contribution (40%)
    final lengthScore = min(password.length / 16.0, 1.0);
    strength += lengthScore * 0.4;

    // Entropy contribution (40%)
    final entropyScore = min(entropy / 80.0, 1.0);
    strength += entropyScore * 0.4;

    // Character variety contribution (20%)
    int varietyCount = 0;
    if (password.contains(RegExp(r'[a-z]'))) varietyCount++;
    if (password.contains(RegExp(r'[A-Z]'))) varietyCount++;
    if (password.contains(RegExp(r'\d'))) varietyCount++;
    if (password.contains(RegExp(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]')))
      varietyCount++;

    final varietyScore = varietyCount / 4.0;
    strength += varietyScore * 0.2;

    return min(strength, 1.0);
  }

  /// Calculate security score (0-100)
  static int _calculateSecurityScore(
      String password, double entropy, bool hasNoIssues) {
    double score = 0.0;

    // Base score from entropy
    score += min(entropy / _recommendedEntropy, 1.0) * 60;

    // Length bonus
    if (password.length >= _recommendedMinLength) {
      score += 15;
    } else if (password.length >= _minLength) score += 10;

    // Character variety bonus
    int varietyBonus = 0;
    if (password.contains(RegExp(r'[a-z]'))) varietyBonus += 2;
    if (password.contains(RegExp(r'[A-Z]'))) varietyBonus += 2;
    if (password.contains(RegExp(r'\d'))) varietyBonus += 3;
    if (password.contains(RegExp(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]')))
      varietyBonus += 5;
    score += varietyBonus;

    // Penalty for issues
    if (!hasNoIssues) score *= 0.5;

    // Bonus for avoiding common patterns
    if (!_hasCommonPatterns(password)) score += 10;

    return min(score.round(), 100);
  }

  /// Check for repeated characters and patterns
  static String _checkRepeatedCharacters(String password) {
    // Check for 3+ repeated characters
    final repeatedChars = RegExp(r'(.)\1{2,}');
    final match = repeatedChars.firstMatch(password);
    if (match != null) {
      return match.group(0)!;
    }

    // Check for repeated short patterns
    for (int patternLength = 2; patternLength <= 3; patternLength++) {
      for (int i = 0; i <= password.length - patternLength * 3; i++) {
        final pattern = password.substring(i, i + patternLength);
        final nextOccurrence = password.indexOf(pattern, i + patternLength);
        if (nextOccurrence == i + patternLength) {
          final thirdOccurrence =
              password.indexOf(pattern, nextOccurrence + patternLength);
          if (thirdOccurrence == nextOccurrence + patternLength) {
            return pattern * 3;
          }
        }
      }
    }

    return '';
  }

  /// Check for sequential patterns (123, abc, etc.)
  static List<String> _checkSequentialPatterns(String password) {
    final issues = <String>[];
    final lowerPassword = password.toLowerCase();

    // Check for ascending sequences
    for (int i = 0; i <= lowerPassword.length - 3; i++) {
      bool isSequential = true;
      for (int j = i + 1; j < i + 3 && j < lowerPassword.length; j++) {
        if (lowerPassword.codeUnitAt(j) !=
            lowerPassword.codeUnitAt(j - 1) + 1) {
          isSequential = false;
          break;
        }
      }
      if (isSequential) {
        issues.add(
            'Avoid sequential characters like "${lowerPassword.substring(i, i + 3)}"');
        break;
      }
    }

    // Check for descending sequences
    for (int i = 0; i <= lowerPassword.length - 3; i++) {
      bool isSequential = true;
      for (int j = i + 1; j < i + 3 && j < lowerPassword.length; j++) {
        if (lowerPassword.codeUnitAt(j) !=
            lowerPassword.codeUnitAt(j - 1) - 1) {
          isSequential = false;
          break;
        }
      }
      if (isSequential) {
        issues.add(
            'Avoid reverse sequential characters like "${lowerPassword.substring(i, i + 3)}"');
        break;
      }
    }

    return issues;
  }

  /// Check for potential personal information patterns
  static List<String> _checkPersonalInformationPatterns(String password) {
    final warnings = <String>[];

    // Check for years
    final yearPattern = RegExp(r'(19|20)\d{2}');
    if (yearPattern.hasMatch(password)) {
      warnings.add('Avoid using birth years or significant dates');
    }

    // Check for months
    final monthNames = [
      'january',
      'february',
      'march',
      'april',
      'may',
      'june',
      'july',
      'august',
      'september',
      'october',
      'november',
      'december'
    ];
    final lowerPassword = password.toLowerCase();
    for (final month in monthNames) {
      if (lowerPassword.contains(month.substring(0, 3)) ||
          lowerPassword.contains(month)) {
        warnings.add('Avoid using month names in passwords');
        break;
      }
    }

    // Check for common names (basic check)
    final commonNames = [
      'john',
      'mary',
      'james',
      'patricia',
      'robert',
      'jennifer',
      'michael',
      'linda',
      'william',
      'elizabeth',
      'david',
      'barbara'
    ];
    for (final name in commonNames) {
      if (lowerPassword.contains(name)) {
        warnings.add('Avoid using common names in passwords');
        break;
      }
    }

    return warnings;
  }

  /// Check for dictionary words (basic implementation)
  static List<String> _checkDictionaryWords(String password) {
    final warnings = <String>[];
    final lowerPassword = password.toLowerCase();

    // Basic dictionary words check (simplified)
    final commonWords = [
      'love',
      'life',
      'work',
      'home',
      'family',
      'money',
      'happy',
      'secure',
      'strong',
      'safe',
      'trust',
      'peace',
      'hope'
    ];

    for (final word in commonWords) {
      if (lowerPassword.contains(word) && word.length >= 4) {
        warnings.add('Consider avoiding dictionary words like "$word"');
        break;
      }
    }

    return warnings;
  }

  /// Check if password has common patterns
  static bool _hasCommonPatterns(String password) {
    final lowerPassword = password.toLowerCase();

    // Check keyboard patterns
    for (final pattern in _keyboardPatterns) {
      if (lowerPassword.contains(pattern) && pattern.length >= 3) {
        return true;
      }
    }

    // Check repeated characters
    if (_checkRepeatedCharacters(password).isNotEmpty) {
      return true;
    }

    // Check sequential patterns
    if (_checkSequentialPatterns(password).isNotEmpty) {
      return true;
    }

    return false;
  }

  /// Generate improvement suggestions
  static List<String> _generateSuggestions(
      String password, List<String> issues) {
    final suggestions = <String>[];

    if (password.length < _recommendedMinLength) {
      suggestions.add(
          'Use at least $_recommendedMinLength characters for better security');
    }

    if (!password.contains(RegExp(r'[A-Z]')) ||
        !password.contains(RegExp(r'[a-z]'))) {
      suggestions.add('Mix uppercase and lowercase letters');
    }

    if (!password.contains(RegExp(r'\d'))) {
      suggestions.add('Include numbers for added complexity');
    }

    if (!password.contains(RegExp(r'[!@#$%^&*()_+\-=\[\]{};:"\\|,.<>\/?]'))) {
      suggestions.add(
          'Add special characters (!@#\$%^&*...) to strengthen your password');
    }

    if (issues.any(
        (issue) => issue.contains('common') || issue.contains('pattern'))) {
      suggestions.add('Avoid predictable patterns and common passwords');
      suggestions.add('Consider using a passphrase with random words instead');
    }

    if (suggestions.isEmpty) {
      suggestions.add(
          'Your password meets basic requirements. Consider making it longer for maximum security.');
    }

    return suggestions;
  }

  /// Get password strength description
  static String getStrengthDescription(double strength) {
    if (strength >= 0.8) return 'Very Strong';
    if (strength >= 0.6) return 'Strong';
    if (strength >= 0.4) return 'Moderate';
    if (strength >= 0.2) return 'Weak';
    return 'Very Weak';
  }

  /// Get security score description
  static String getSecurityScoreDescription(int score) {
    if (score >= 90) return 'Excellent';
    if (score >= 80) return 'Very Good';
    if (score >= 70) return 'Good';
    if (score >= 60) return 'Fair';
    if (score >= 50) return 'Poor';
    return 'Very Poor';
  }

  /// Validate password strength (public method for tests)
  static double validatePasswordStrength(String password) {
    final result = validatePassword(password);
    return result.strength;
  }
}

/// Result of comprehensive password validation
class PasswordValidationResult {
  final bool isValid;
  final bool isStrong;
  final double strength; // 0.0 to 1.0
  final double entropy; // bits
  final int securityScore; // 0 to 100
  final List<String> issues;
  final List<String> warnings;
  final List<String> suggestions;

  const PasswordValidationResult({
    required this.isValid,
    required this.isStrong,
    required this.strength,
    required this.entropy,
    required this.securityScore,
    required this.issues,
    required this.warnings,
    required this.suggestions,
  });

  String get strengthDescription =>
      PasswordValidationService.getStrengthDescription(strength);
  String get securityScoreDescription =>
      PasswordValidationService.getSecurityScoreDescription(securityScore);

  @override
  String toString() {
    return 'PasswordValidationResult(valid: $isValid, strong: $isStrong, '
        'strength: ${strength.toStringAsFixed(2)}, entropy: ${entropy.toStringAsFixed(1)}, '
        'score: $securityScore, issues: ${issues.length}, warnings: ${warnings.length})';
  }
}
