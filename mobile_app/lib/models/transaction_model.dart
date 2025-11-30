/// Transaction Model
/// Represents a financial transaction with all extended fields
class TransactionModel {
  final String id;
  final String category;
  final double amount;
  final String currency;
  final String? description;
  final String? merchant;
  final String? location;
  final List<String>? tags;
  final bool isRecurring;
  final double? confidenceScore;
  final String? receiptUrl;
  final String? notes;
  final DateTime spentAt;
  final DateTime createdAt;
  final DateTime? updatedAt;

  TransactionModel({
    required this.id,
    required this.category,
    required this.amount,
    this.currency = 'USD',
    this.description,
    this.merchant,
    this.location,
    this.tags,
    this.isRecurring = false,
    this.confidenceScore,
    this.receiptUrl,
    this.notes,
    required this.spentAt,
    required this.createdAt,
    this.updatedAt,
  });

  /// Create from JSON
  factory TransactionModel.fromJson(Map<String, dynamic> json) {
    return TransactionModel(
      id: json['id'] as String,
      category: json['category'] as String,
      amount: (json['amount'] is String)
          ? double.parse(json['amount'] as String)
          : (json['amount'] as num).toDouble(),
      currency: json['currency'] as String? ?? 'USD',
      description: json['description'] as String?,
      merchant: json['merchant'] as String?,
      location: json['location'] as String?,
      tags: json['tags'] != null ? List<String>.from(json['tags'] as List) : null,
      isRecurring: json['is_recurring'] as bool? ?? false,
      confidenceScore:
          json['confidence_score'] != null ? (json['confidence_score'] as num).toDouble() : null,
      receiptUrl: json['receipt_url'] as String?,
      notes: json['notes'] as String?,
      spentAt: DateTime.parse(json['spent_at'] as String),
      createdAt: DateTime.parse(json['created_at'] as String),
      updatedAt: json['updated_at'] != null ? DateTime.parse(json['updated_at'] as String) : null,
    );
  }

  /// Convert to JSON
  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'category': category,
      'amount': amount,
      'currency': currency,
      'description': description,
      'merchant': merchant,
      'location': location,
      'tags': tags,
      'is_recurring': isRecurring,
      'confidence_score': confidenceScore,
      'receipt_url': receiptUrl,
      'notes': notes,
      'spent_at': spentAt.toIso8601String(),
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt?.toIso8601String(),
    };
  }

  /// Create a copy with updated fields
  TransactionModel copyWith({
    String? id,
    String? category,
    double? amount,
    String? currency,
    String? description,
    String? merchant,
    String? location,
    List<String>? tags,
    bool? isRecurring,
    double? confidenceScore,
    String? receiptUrl,
    String? notes,
    DateTime? spentAt,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return TransactionModel(
      id: id ?? this.id,
      category: category ?? this.category,
      amount: amount ?? this.amount,
      currency: currency ?? this.currency,
      description: description ?? this.description,
      merchant: merchant ?? this.merchant,
      location: location ?? this.location,
      tags: tags ?? this.tags,
      isRecurring: isRecurring ?? this.isRecurring,
      confidenceScore: confidenceScore ?? this.confidenceScore,
      receiptUrl: receiptUrl ?? this.receiptUrl,
      notes: notes ?? this.notes,
      spentAt: spentAt ?? this.spentAt,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  @override
  String toString() {
    return 'TransactionModel{id: $id, category: $category, amount: $amount, '
        'merchant: $merchant, spentAt: $spentAt}';
  }
}

/// Transaction Create/Update Input Model
class TransactionInput {
  final double amount;
  final String category;
  final String? description;
  final String? currency;
  final String? merchant;
  final String? location;
  final List<String>? tags;
  final bool? isRecurring;
  final double? confidenceScore;
  final String? receiptUrl;
  final String? notes;
  final DateTime? spentAt;

  TransactionInput({
    required this.amount,
    required this.category,
    this.description,
    this.currency,
    this.merchant,
    this.location,
    this.tags,
    this.isRecurring,
    this.confidenceScore,
    this.receiptUrl,
    this.notes,
    this.spentAt,
  });

  Map<String, dynamic> toJson() {
    final map = <String, dynamic>{
      'amount': amount,
      'category': category,
    };

    if (description != null) map['description'] = description;
    if (currency != null) map['currency'] = currency;
    if (merchant != null) map['merchant'] = merchant;
    if (location != null) map['location'] = location;
    if (tags != null) map['tags'] = tags;
    if (isRecurring != null) map['is_recurring'] = isRecurring;
    if (confidenceScore != null) map['confidence_score'] = confidenceScore;
    if (receiptUrl != null) map['receipt_url'] = receiptUrl;
    if (notes != null) map['notes'] = notes;
    if (spentAt != null) map['spent_at'] = spentAt!.toIso8601String();

    return map;
  }
}

/// Transactions list response
class TransactionsListResponse {
  final List<TransactionModel> transactions;
  final int total;
  final int skip;
  final int limit;

  TransactionsListResponse({
    required this.transactions,
    required this.total,
    this.skip = 0,
    this.limit = 100,
  });

  factory TransactionsListResponse.fromJson(Map<String, dynamic> json) {
    return TransactionsListResponse(
      transactions: (json['transactions'] as List? ?? json['data'] as List? ?? [])
          .map((e) => TransactionModel.fromJson(e as Map<String, dynamic>))
          .toList(),
      total: json['total'] as int? ?? 0,
      skip: json['skip'] as int? ?? 0,
      limit: json['limit'] as int? ?? 100,
    );
  }
}
