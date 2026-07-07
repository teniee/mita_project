/// Deterministic, offline merchant → category classification.
///
/// Used for instant transaction categorization (manual entry, OCR results)
/// without a network round-trip; the backend/AI can refine later. Keyword
/// tables mirror the app's standard spending categories.
class SmartCategorizationService {
  static final SmartCategorizationService _instance =
      SmartCategorizationService._internal();
  factory SmartCategorizationService() => _instance;
  SmartCategorizationService._internal();

  static const Map<String, List<String>> _keywordsByCategory = {
    'food': [
      'restaurant',
      'cafe',
      'coffee',
      'pizza',
      'burger',
      'sushi',
      'grocery',
      'market',
      'food',
      'bakery',
      'deli',
      'starbucks',
      'mcdonald',
      'chipotle',
      'doordash',
      'ubereats',
      'grubhub',
      'kroger',
      'safeway',
      'wholefoods',
      'trader joe',
      'aldi',
      'diner',
      'kitchen',
      'bbq',
      'taco',
    ],
    'transportation': [
      'uber',
      'lyft',
      'taxi',
      'gas',
      'fuel',
      'shell',
      'chevron',
      'exxon',
      'parking',
      'transit',
      'metro',
      'bus',
      'train',
      'airline',
      'flight',
      'car wash',
      'auto',
      'toll',
    ],
    'entertainment': [
      'cinema',
      'movie',
      'netflix',
      'spotify',
      'hulu',
      'disney',
      'game',
      'steam',
      'playstation',
      'xbox',
      'concert',
      'ticket',
      'theater',
      'bar',
      'club',
      'bowling',
      'arcade',
    ],
    'shopping': [
      'amazon',
      'walmart',
      'target',
      'costco',
      'ebay',
      'etsy',
      'mall',
      'store',
      'shop',
      'clothing',
      'shoes',
      'nike',
      'adidas',
      'apple store',
      'best buy',
      'ikea',
    ],
    'utilities': [
      'electric',
      'power',
      'water',
      'sewer',
      'internet',
      'wifi',
      'comcast',
      'verizon',
      'at&t',
      't-mobile',
      'phone',
      'utility',
      'energy',
      'bill',
    ],
    'health': [
      'pharmacy',
      'cvs',
      'walgreens',
      'doctor',
      'clinic',
      'hospital',
      'dental',
      'medical',
      'gym',
      'fitness',
      'yoga',
      'therapy',
      'vision',
    ],
  };

  /// Classify a transaction into one of the standard categories.
  ///
  /// Deterministic keyword matching on the merchant string; unknown
  /// merchants land in 'other' (never null) so callers always get a
  /// usable category.
  Future<String> categorizeTransaction({
    required String merchant,
    required double amount,
    DateTime? date,
    String? location,
  }) async {
    final normalized = merchant.toLowerCase();
    for (final entry in _keywordsByCategory.entries) {
      for (final keyword in entry.value) {
        if (normalized.contains(keyword)) {
          return entry.key;
        }
      }
    }
    return 'other';
  }
}
