/// Country profiles service providing income thresholds and financial parameters by country/region
class CountryProfilesService {
  static final CountryProfilesService _instance =
      CountryProfilesService._internal();
  factory CountryProfilesService() => _instance;
  CountryProfilesService._internal();

  /// Country profiles with income thresholds in local currency (annual)
  /// Focused on USA with state-level granularity for accurate income classification
  static const Map<String, Map<String, dynamic>> _countryProfiles = {
    // United States - comprehensive state-level data (USD annual)
    'US': {
      'currency': 'USD',
      'default_behavior': 'balanced',
      'class_thresholds': {
        'low': 40000,
        'lower_middle': 64000,
        'middle': 96000,
        'upper_middle': 160000,
        'high': 216000,
      },
      'states': {
        'AL': {
          'low': 30330,
          'lower_middle': 48528,
          'middle': 72792,
          'upper_middle': 121320,
          'high': 163782
        },
        'AK': {
          'low': 49095,
          'lower_middle': 78552,
          'middle': 117828,
          'upper_middle': 196380,
          'high': 265113
        },
        'AZ': {
          'low': 41330,
          'lower_middle': 66128,
          'middle': 99192,
          'upper_middle': 165320,
          'high': 223182
        },
        'AR': {
          'low': 31625,
          'lower_middle': 50600,
          'middle': 75900,
          'upper_middle': 126500,
          'high': 170775
        },
        'CA': {
          'low': 44935,
          'lower_middle': 71896,
          'middle': 107844,
          'upper_middle': 179740,
          'high': 242649
        },
        'CO': {
          'low': 48320,
          'lower_middle': 77312,
          'middle': 115968,
          'upper_middle': 193280,
          'high': 260928
        },
        'CT': {
          'low': 41885,
          'lower_middle': 67016,
          'middle': 100525,
          'upper_middle': 167542,
          'high': 226181
        },
        'DE': {
          'low': 35545,
          'lower_middle': 56872,
          'middle': 85309,
          'upper_middle': 142182,
          'high': 191945
        },
        'FL': {
          'low': 36655,
          'lower_middle': 58648,
          'middle': 87973,
          'upper_middle': 146622,
          'high': 197939
        },
        'GA': {
          'low': 37316,
          'lower_middle': 59705,
          'middle': 89558,
          'upper_middle': 149264,
          'high': 201506
        },
        'HI': {
          'low': 42428,
          'lower_middle': 67885,
          'middle': 101828,
          'upper_middle': 169714,
          'high': 229113
        },
        'ID': {
          'low': 35000,
          'lower_middle': 56000,
          'middle': 84000,
          'upper_middle': 140000,
          'high': 189000
        },
        'IL': {
          'low': 36102,
          'lower_middle': 57764,
          'middle': 86646,
          'upper_middle': 144410,
          'high': 194953
        },
        'IN': {
          'low': 34000,
          'lower_middle': 54400,
          'middle': 81600,
          'upper_middle': 136000,
          'high': 183600
        },
        'IA': {
          'low': 35000,
          'lower_middle': 56000,
          'middle': 84000,
          'upper_middle': 140000,
          'high': 189000
        },
        'KS': {
          'low': 34500,
          'lower_middle': 55200,
          'middle': 82800,
          'upper_middle': 138000,
          'high': 186300
        },
        'KY': {
          'low': 32500,
          'lower_middle': 52000,
          'middle': 78000,
          'upper_middle': 130000,
          'high': 175500
        },
        'LA': {
          'low': 31000,
          'lower_middle': 49600,
          'middle': 74400,
          'upper_middle': 124000,
          'high': 167400
        },
        'ME': {
          'low': 36866,
          'lower_middle': 58986,
          'middle': 88479,
          'upper_middle': 147466,
          'high': 199079
        },
        'MD': {
          'low': 45101,
          'lower_middle': 72162,
          'middle': 108243,
          'upper_middle': 180406,
          'high': 243548
        },
        'MA': {
          'low': 44822,
          'lower_middle': 71716,
          'middle': 107574,
          'upper_middle': 179290,
          'high': 242041
        },
        'MI': {
          'low': 35000,
          'lower_middle': 56000,
          'middle': 84000,
          'upper_middle': 140000,
          'high': 189000
        },
        'MN': {
          'low': 40000,
          'lower_middle': 64000,
          'middle': 96000,
          'upper_middle': 160000,
          'high': 216000
        },
        'MS': {
          'low': 26000,
          'lower_middle': 41600,
          'middle': 62400,
          'upper_middle': 104000,
          'high': 140400
        },
        'MO': {
          'low': 33500,
          'lower_middle': 53600,
          'middle': 80400,
          'upper_middle': 134000,
          'high': 180900
        },
        'MT': {
          'low': 34500,
          'lower_middle': 55200,
          'middle': 82800,
          'upper_middle': 138000,
          'high': 186300
        },
        'NE': {
          'low': 36000,
          'lower_middle': 57600,
          'middle': 86400,
          'upper_middle': 144000,
          'high': 194400
        },
        'NV': {
          'low': 37500,
          'lower_middle': 60000,
          'middle': 90000,
          'upper_middle': 150000,
          'high': 202500
        },
        'NH': {
          'low': 43000,
          'lower_middle': 68800,
          'middle': 103200,
          'upper_middle': 172000,
          'high': 232200
        },
        'NJ': {
          'low': 45250,
          'lower_middle': 72400,
          'middle': 108600,
          'upper_middle': 181000,
          'high': 244350
        },
        'NM': {
          'low': 30500,
          'lower_middle': 48800,
          'middle': 73200,
          'upper_middle': 122000,
          'high': 164700
        },
        'NY': {
          'low': 39000,
          'lower_middle': 62400,
          'middle': 93600,
          'upper_middle': 156000,
          'high': 210600
        },
        'NC': {
          'low': 35500,
          'lower_middle': 56800,
          'middle': 85200,
          'upper_middle': 142000,
          'high': 191700
        },
        'ND': {
          'low': 36500,
          'lower_middle': 58400,
          'middle': 87600,
          'upper_middle': 146000,
          'high': 197100
        },
        'OH': {
          'low': 34000,
          'lower_middle': 54400,
          'middle': 81600,
          'upper_middle': 136000,
          'high': 183600
        },
        'OK': {
          'low': 32000,
          'lower_middle': 51200,
          'middle': 76800,
          'upper_middle': 128000,
          'high': 172800
        },
        'OR': {
          'low': 37000,
          'lower_middle': 59200,
          'middle': 88800,
          'upper_middle': 148000,
          'high': 199800
        },
        'PA': {
          'low': 35000,
          'lower_middle': 56000,
          'middle': 84000,
          'upper_middle': 140000,
          'high': 189000
        },
        'RI': {
          'low': 39000,
          'lower_middle': 62400,
          'middle': 93600,
          'upper_middle': 156000,
          'high': 210600
        },
        'SC': {
          'low': 34500,
          'lower_middle': 55200,
          'middle': 82800,
          'upper_middle': 138000,
          'high': 186300
        },
        'SD': {
          'low': 35000,
          'lower_middle': 56000,
          'middle': 84000,
          'upper_middle': 140000,
          'high': 189000
        },
        'TN': {
          'low': 34250,
          'lower_middle': 54800,
          'middle': 82200,
          'upper_middle': 137000,
          'high': 184950
        },
        'TX': {
          'low': 37750,
          'lower_middle': 60400,
          'middle': 90600,
          'upper_middle': 151000,
          'high': 203850
        },
        'UT': {
          'low': 41000,
          'lower_middle': 65600,
          'middle': 98400,
          'upper_middle': 164000,
          'high': 221400
        },
        'VT': {
          'low': 38000,
          'lower_middle': 60800,
          'middle': 91200,
          'upper_middle': 152000,
          'high': 205200
        },
        'VA': {
          'low': 41500,
          'lower_middle': 66400,
          'middle': 99600,
          'upper_middle': 166000,
          'high': 224100
        },
        'WA': {
          'low': 44000,
          'lower_middle': 70400,
          'middle': 105600,
          'upper_middle': 176000,
          'high': 237600
        },
        'WV': {
          'low': 29500,
          'lower_middle': 47200,
          'middle': 70800,
          'upper_middle': 118000,
          'high': 159300
        },
        'WI': {
          'low': 36000,
          'lower_middle': 57600,
          'middle': 86400,
          'upper_middle': 144000,
          'high': 194400
        },
        'WY': {
          'low': 36000,
          'lower_middle': 57600,
          'middle': 86400,
          'upper_middle': 144000,
          'high': 194400
        },
      }
    },
  };

  /// Get country profile by country code
  Map<String, dynamic>? getCountryProfile(String countryCode) {
    return _countryProfiles[countryCode.toUpperCase()];
  }

  /// Get income thresholds for a specific country/region
  Map<String, double> getIncomeThresholds(String countryCode,
      {String? stateCode}) {
    final profile = getCountryProfile(countryCode);
    if (profile == null) {
      // Fallback to US default thresholds
      return _getDefaultThresholds();
    }

    // Check for state-specific thresholds (e.g., US states)
    if (stateCode != null && profile['states'] != null) {
      final stateThresholds = profile['states'][stateCode.toUpperCase()];
      if (stateThresholds != null) {
        return Map<String, double>.from(stateThresholds
            .map((key, value) => MapEntry(key, value.toDouble())));
      }
    }

    // Return country-level thresholds
    return Map<String, double>.from(profile['class_thresholds']
        .map((key, value) => MapEntry(key, value.toDouble())));
  }

  /// Get default behavior for a country
  String getDefaultBehavior(String countryCode) {
    final profile = getCountryProfile(countryCode);
    return profile?['default_behavior'] ?? 'balanced';
  }

  /// Get currency code for a country
  String getCurrency(String countryCode) {
    final profile = getCountryProfile(countryCode);
    return profile?['currency'] ?? 'USD';
  }

  /// Convert annual income to monthly
  double annualToMonthly(double annualIncome) {
    return annualIncome / 12;
  }

  /// Convert monthly income to annual
  double monthlyToAnnual(double monthlyIncome) {
    return monthlyIncome * 12;
  }

  /// Get all supported countries
  List<String> getSupportedCountries() {
    return _countryProfiles.keys.toList();
  }

  /// Get country name from country code
  String getCountryName(String countryCode) {
    switch (countryCode.toUpperCase()) {
      case 'US':
        return 'United States';
      default:
        return countryCode;
    }
  }

  /// Check if a country has state/province level data
  bool hasSubregions(String countryCode) {
    final profile = getCountryProfile(countryCode);
    return profile?['states'] != null;
  }

  /// Get subregions (states/provinces) for a country
  List<String> getSubregions(String countryCode) {
    final profile = getCountryProfile(countryCode);
    if (profile?['states'] != null) {
      return (profile!['states'] as Map<String, dynamic>).keys.toList();
    }
    return [];
  }

  /// Get default thresholds (fallback)
  Map<String, double> _getDefaultThresholds() {
    return {
      'low': 36000.0,
      'lower_middle': 57600.0,
      'middle': 86400.0,
      'upper_middle': 144000.0,
      'high': 194400.0,
    };
  }

  /// Classify income tier based on monthly income and location
  String classifyIncomeByLocation(double monthlyIncome, String countryCode,
      {String? stateCode}) {
    final thresholds = getIncomeThresholds(countryCode, stateCode: stateCode);
    final annualIncome = monthlyToAnnual(monthlyIncome);

    if (annualIncome <= thresholds['low']!) {
      return 'low';
    } else if (annualIncome <= thresholds['lower_middle']!) {
      return 'lowerMiddle';
    } else if (annualIncome <= thresholds['middle']!) {
      return 'middle';
    } else if (annualIncome <= thresholds['upper_middle']!) {
      return 'upperMiddle';
    } else {
      return 'high';
    }
  }

  /// Get localized income tier description
  String getLocalizedTierName(String tier, String countryCode) {
    final currency = getCurrency(countryCode);
    final thresholds = getIncomeThresholds(countryCode);

    switch (tier) {
      case 'low':
        return 'Essential Earner (< ${_formatCurrency(thresholds['low']!, currency)}/year)';
      case 'lowerMiddle':
        return 'Rising Saver (${_formatCurrency(thresholds['low']!, currency)} - ${_formatCurrency(thresholds['lower_middle']!, currency)}/year)';
      case 'middle':
        return 'Growing Professional (${_formatCurrency(thresholds['lower_middle']!, currency)} - ${_formatCurrency(thresholds['middle']!, currency)}/year)';
      case 'upperMiddle':
        return 'Established Professional (${_formatCurrency(thresholds['middle']!, currency)} - ${_formatCurrency(thresholds['upper_middle']!, currency)}/year)';
      case 'high':
        return 'High Achiever (> ${_formatCurrency(thresholds['upper_middle']!, currency)}/year)';
      default:
        return tier;
    }
  }

  /// Format currency for display
  String _formatCurrency(double amount, String currency) {
    final formattedAmount = amount >= 1000
        ? '${(amount / 1000).toStringAsFixed(0)}K'
        : amount.toStringAsFixed(0);

    switch (currency) {
      case 'USD':
        return '\$$formattedAmount';
      case 'CAD':
        return 'C\$$formattedAmount';
      case 'GBP':
        return '£$formattedAmount';
      case 'EUR':
        return '€$formattedAmount';
      case 'BGN':
        return '$formattedAmount лв';
      case 'JPY':
        return '¥$formattedAmount';
      default:
        return '$formattedAmount $currency';
    }
  }
}
