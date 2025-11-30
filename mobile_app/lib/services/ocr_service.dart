import 'dart:io';
import 'package:flutter/foundation.dart';
import 'api_service.dart';
import 'logging_service.dart';

/// Confidence levels for OCR results
enum OCRConfidence { low, medium, high }

/// Processing status for OCR operations
enum OCRProcessingStatus { idle, preprocessing, extracting, categorizing, complete, error }

/// Detailed item from OCR extraction
class ReceiptItem {
  final String name;
  final double price;
  final OCRConfidence confidence;
  final String? category;

  const ReceiptItem({
    required this.name,
    required this.price,
    required this.confidence,
    this.category,
  });

  factory ReceiptItem.fromJson(Map<String, dynamic> json) {
    return ReceiptItem(
      name: json['name'] as String? ?? '',
      price: (json['price'] as num?)?.toDouble() ?? 0.0,
      confidence: _parseConfidence(json['confidence']),
      category: json['category'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'name': name,
      'price': price,
      'confidence': confidence.name,
      'category': category,
    };
  }

  static OCRConfidence _parseConfidence(dynamic value) {
    if (value is String) {
      switch (value.toLowerCase()) {
        case 'high':
          return OCRConfidence.high;
        case 'medium':
          return OCRConfidence.medium;
        default:
          return OCRConfidence.low;
      }
    }
    if (value is num) {
      if (value >= 0.8) return OCRConfidence.high;
      if (value >= 0.6) return OCRConfidence.medium;
      return OCRConfidence.low;
    }
    return OCRConfidence.low;
  }
}

/// Comprehensive OCR result with confidence scores and categorization
class OCRResult {
  final String merchant;
  final double total;
  final DateTime date;
  final String category;
  final List<ReceiptItem> items;
  final OCRConfidence merchantConfidence;
  final OCRConfidence totalConfidence;
  final OCRConfidence dateConfidence;
  final OCRConfidence categoryConfidence;
  final String rawText;
  final bool isPremiumProcessing;
  final String? receiptImagePath;
  final Map<String, dynamic>? metadata;

  const OCRResult({
    required this.merchant,
    required this.total,
    required this.date,
    required this.category,
    required this.items,
    required this.merchantConfidence,
    required this.totalConfidence,
    required this.dateConfidence,
    required this.categoryConfidence,
    required this.rawText,
    required this.isPremiumProcessing,
    this.receiptImagePath,
    this.metadata,
  });

  factory OCRResult.fromJson(Map<String, dynamic> json) {
    final itemsJson = json['items'] as List<dynamic>? ?? [];
    final items =
        itemsJson.map((item) => ReceiptItem.fromJson(item as Map<String, dynamic>)).toList();

    return OCRResult(
      merchant: json['merchant'] as String? ?? 'Unknown Merchant',
      total: (json['total'] as num?)?.toDouble() ?? 0.0,
      date: DateTime.tryParse(json['date'] as String? ?? '') ?? DateTime.now(),
      category: json['category'] as String? ?? 'other',
      items: items,
      merchantConfidence: ReceiptItem._parseConfidence(json['merchant_confidence']),
      totalConfidence: ReceiptItem._parseConfidence(json['total_confidence']),
      dateConfidence: ReceiptItem._parseConfidence(json['date_confidence']),
      categoryConfidence: ReceiptItem._parseConfidence(json['category_confidence']),
      rawText: json['raw_text'] as String? ?? '',
      isPremiumProcessing: json['is_premium_processing'] as bool? ?? false,
      receiptImagePath: json['receipt_image_path'] as String?,
      metadata: json['metadata'] as Map<String, dynamic>?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'merchant': merchant,
      'total': total,
      'date': date.toIso8601String(),
      'category': category,
      'items': items.map((item) => item.toJson()).toList(),
      'merchant_confidence': merchantConfidence.name,
      'total_confidence': totalConfidence.name,
      'date_confidence': dateConfidence.name,
      'category_confidence': categoryConfidence.name,
      'raw_text': rawText,
      'is_premium_processing': isPremiumProcessing,
      'receipt_image_path': receiptImagePath,
      'metadata': metadata,
    };
  }

  /// Get overall confidence score (0.0 to 1.0)
  double get overallConfidence {
    final scores = [
      _confidenceToScore(merchantConfidence),
      _confidenceToScore(totalConfidence),
      _confidenceToScore(dateConfidence),
      _confidenceToScore(categoryConfidence),
    ];
    return scores.reduce((a, b) => a + b) / scores.length;
  }

  double _confidenceToScore(OCRConfidence confidence) {
    switch (confidence) {
      case OCRConfidence.high:
        return 1.0;
      case OCRConfidence.medium:
        return 0.7;
      case OCRConfidence.low:
        return 0.4;
    }
  }

  /// Get fields that need manual review based on confidence
  List<String> get fieldsNeedingReview {
    final fields = <String>[];
    if (merchantConfidence == OCRConfidence.low) fields.add('merchant');
    if (totalConfidence == OCRConfidence.low) fields.add('total');
    if (dateConfidence == OCRConfidence.low) fields.add('date');
    if (categoryConfidence == OCRConfidence.low) fields.add('category');
    return fields;
  }
}

/// Batch processing result for multiple receipts
class BatchOCRResult {
  final List<OCRResult> results;
  final List<String> failures;
  final int processed;
  final int total;
  final Duration processingTime;

  const BatchOCRResult({
    required this.results,
    required this.failures,
    required this.processed,
    required this.total,
    required this.processingTime,
  });

  double get successRate => total > 0 ? processed / total : 0.0;
}

/// Service for advanced OCR processing with confidence tracking
class OCRService {
  static final OCRService _instance = OCRService._internal();
  factory OCRService() => _instance;
  OCRService._internal();

  final ApiService _apiService = ApiService();

  /// Current processing status
  final ValueNotifier<OCRProcessingStatus> processingStatus =
      ValueNotifier(OCRProcessingStatus.idle);

  /// Current processing progress (0.0 to 1.0)
  final ValueNotifier<double> processingProgress = ValueNotifier(0.0);

  /// Process a single receipt with enhanced OCR
  Future<OCRResult> processReceipt(
    File receiptFile, {
    bool isPremiumUser = false,
    Map<String, dynamic>? processingOptions,
  }) async {
    processingStatus.value = OCRProcessingStatus.preprocessing;
    processingProgress.value = 0.1;

    try {
      // Step 1: Image preprocessing
      await _simulateProcessingDelay(500);
      processingProgress.value = 0.3;

      // Step 2: OCR extraction - Use advanced processing for premium users
      processingStatus.value = OCRProcessingStatus.extracting;
      final rawResult = isPremiumUser
          ? await _apiService.processReceiptAdvanced(
              receiptFile,
              usePremiumOCR: true,
              processingOptions: processingOptions,
            )
          : await _apiService.uploadReceipt(receiptFile);
      processingProgress.value = 0.7;

      // Step 3: Enhanced categorization and confidence scoring
      processingStatus.value = OCRProcessingStatus.categorizing;
      await _simulateProcessingDelay(300);
      processingProgress.value = 0.9;

      // Step 4: Build enhanced result
      final enhancedResult = _buildEnhancedResult(rawResult, isPremiumUser);

      processingStatus.value = OCRProcessingStatus.complete;
      processingProgress.value = 1.0;

      return enhancedResult;
    } catch (e) {
      processingStatus.value = OCRProcessingStatus.error;
      processingProgress.value = 0.0;
      rethrow;
    } finally {
      // Reset status after a delay
      Future.delayed(const Duration(seconds: 2), () {
        processingStatus.value = OCRProcessingStatus.idle;
        processingProgress.value = 0.0;
      });
    }
  }

  /// Process multiple receipts in batch
  Future<BatchOCRResult> processBatchReceipts(
    List<File> receiptFiles, {
    bool isPremiumUser = false,
    void Function(int processed, int total)? onProgress,
  }) async {
    final stopwatch = Stopwatch()..start();
    final results = <OCRResult>[];
    final failures = <String>[];

    for (int i = 0; i < receiptFiles.length; i++) {
      try {
        final result = await processReceipt(
          receiptFiles[i],
          isPremiumUser: isPremiumUser,
        );
        results.add(result);
        onProgress?.call(i + 1, receiptFiles.length);
      } catch (e) {
        failures.add('Receipt ${i + 1}: ${e.toString()}');
        onProgress?.call(i + 1, receiptFiles.length);
      }
    }

    stopwatch.stop();

    return BatchOCRResult(
      results: results,
      failures: failures,
      processed: results.length,
      total: receiptFiles.length,
      processingTime: stopwatch.elapsed,
    );
  }

  /// Get merchant name suggestions based on OCR input
  Future<List<String>> getMerchantSuggestions(String partialName) async {
    try {
      // Call backend endpoint for merchant suggestions
      if (partialName.trim().isEmpty) return [];

      final suggestions = await _apiService.getMerchantSuggestions(partialName);
      return suggestions;
    } catch (e) {
      logError('Error getting merchant suggestions: $e', tag: 'OCR_SERVICE');

      // Fallback to local suggestions if API fails
      final fallbackSuggestions = [
        'Walmart Supercenter',
        'Target Store',
        'Whole Foods Market',
        'CVS Pharmacy',
        'Starbucks Coffee',
        'McDonald\'s',
        'Home Depot',
        'Best Buy',
        'Amazon',
        'Costco',
      ].where((name) => name.toLowerCase().contains(partialName.toLowerCase())).toList();

      return fallbackSuggestions.take(5).toList();
    }
  }

  /// Get category suggestions based on merchant and amount
  Future<List<Map<String, dynamic>>> getCategorySuggestions({
    required String merchant,
    required double amount,
  }) async {
    try {
      // This would use the AI categorization service
      return await _apiService.getAICategorySuggestions(
        merchant,
        amount: amount,
      );
    } catch (e) {
      logError('Error getting category suggestions: $e', tag: 'OCR_SERVICE');
      return [];
    }
  }

  /// Validate and correct OCR results using AI
  Future<OCRResult> validateAndCorrectOCR(OCRResult result) async {
    try {
      // Call the API service to validate OCR data
      final validatedData = await _apiService.validateOCRResult(result.toJson());

      // Rebuild the result with validated data
      return OCRResult.fromJson(validatedData);
    } catch (e) {
      logError('Error validating OCR result: $e', tag: 'OCR_SERVICE');
      // Return original result if validation fails
      return result;
    }
  }

  /// Enhance OCR data with additional context and corrections
  Future<OCRResult> enhanceOCRData(OCRResult result) async {
    try {
      // Call the API service to enhance OCR data
      final enhancedData = await _apiService.enhanceReceiptData(result.toJson());

      // Rebuild the result with enhanced data
      return OCRResult.fromJson(enhancedData);
    } catch (e) {
      logError('Error enhancing OCR data: $e', tag: 'OCR_SERVICE');
      // Return original result if enhancement fails
      return result;
    }
  }

  /// Check OCR processing status for async operations (using job ID)
  Future<Map<String, dynamic>> checkOCRProcessingStatus(String jobId) async {
    try {
      return await _apiService.getOCRProcessingStatus(jobId);
    } catch (e) {
      logError('Error checking OCR processing status: $e', tag: 'OCR_SERVICE');
      rethrow;
    }
  }

  /// Alternative status check method (direct OCR service endpoint)
  Future<Map<String, dynamic>> checkOCRStatus(String ocrJobId) async {
    try {
      return await _apiService.getOCRStatus(ocrJobId);
    } catch (e) {
      logError('Error checking OCR status: $e', tag: 'OCR_SERVICE');
      rethrow;
    }
  }

  /// Poll OCR status until processing is complete
  Future<Map<String, dynamic>> pollOCRStatus(
    String jobId, {
    Duration pollInterval = const Duration(seconds: 2),
    Duration timeout = const Duration(minutes: 5),
  }) async {
    final stopwatch = Stopwatch()..start();

    while (stopwatch.elapsed < timeout) {
      try {
        final status = await checkOCRProcessingStatus(jobId);
        final statusValue = status['status'] as String?;

        if (statusValue == 'complete' || statusValue == 'completed') {
          return status;
        } else if (statusValue == 'failed' || statusValue == 'error') {
          throw Exception('OCR processing failed: ${status['error'] ?? 'Unknown error'}');
        }

        // Update progress if available
        final progress = status['progress'] as num?;
        if (progress != null) {
          processingProgress.value = progress.toDouble();
        }

        // Wait before polling again
        await Future<void>.delayed(pollInterval);
      } catch (e) {
        logError('Error polling OCR status: $e', tag: 'OCR_SERVICE');
        rethrow;
      }
    }

    throw Exception('OCR processing timeout after ${timeout.inSeconds} seconds');
  }

  /// Get receipt image URL for viewing/downloading
  Future<String> getReceiptImageUrl(String receiptId) async {
    try {
      return await _apiService.getReceiptImageUrl(receiptId);
    } catch (e) {
      logError('Error getting receipt image URL: $e', tag: 'OCR_SERVICE');
      rethrow;
    }
  }

  /// Delete receipt image from storage
  Future<void> deleteReceiptImage(String receiptId) async {
    try {
      await _apiService.deleteReceiptImage(receiptId);
    } catch (e) {
      logError('Error deleting receipt image: $e', tag: 'OCR_SERVICE');
      rethrow;
    }
  }

  /// Build enhanced OCR result from raw API response
  OCRResult _buildEnhancedResult(
    Map<String, dynamic> rawResult,
    bool isPremiumUser,
  ) {
    // Simulate confidence scoring based on premium tier
    final baseConfidence = isPremiumUser ? OCRConfidence.high : OCRConfidence.medium;

    return OCRResult(
      merchant: rawResult['merchant'] as String? ?? 'Unknown Merchant',
      total: (rawResult['total'] as num?)?.toDouble() ?? 0.0,
      date: DateTime.tryParse(rawResult['date'] as String? ?? '') ?? DateTime.now(),
      category: rawResult['category'] as String? ?? 'other',
      items: _parseItems(rawResult['items'] as List<dynamic>? ?? []),
      merchantConfidence: _adjustConfidence(baseConfidence, rawResult['merchant']),
      totalConfidence: _adjustConfidence(baseConfidence, rawResult['total']),
      dateConfidence: _adjustConfidence(baseConfidence, rawResult['date']),
      categoryConfidence: _adjustConfidence(baseConfidence, rawResult['category']),
      rawText: rawResult['raw_text'] as String? ?? '',
      isPremiumProcessing: isPremiumUser,
      receiptImagePath: rawResult['receipt_image_path'] as String?,
      metadata: rawResult['metadata'] as Map<String, dynamic>?,
    );
  }

  List<ReceiptItem> _parseItems(List<dynamic> itemsJson) {
    return itemsJson.map((item) => ReceiptItem.fromJson(item as Map<String, dynamic>)).toList();
  }

  OCRConfidence _adjustConfidence(OCRConfidence base, dynamic value) {
    // Adjust confidence based on value quality
    if (value == null || value.toString().trim().isEmpty) {
      return OCRConfidence.low;
    }

    // Additional logic could be added here to analyze the quality
    // of extracted values and adjust confidence accordingly
    return base;
  }

  Future<void> _simulateProcessingDelay(int milliseconds) async {
    await Future<void>.delayed(Duration(milliseconds: milliseconds));
  }

  void dispose() {
    processingStatus.dispose();
    processingProgress.dispose();
  }
}
