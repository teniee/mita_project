import 'dart:io';

import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:image_cropper/image_cropper.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';

import '../models/transaction_model.dart';
import '../providers/transaction_provider.dart';
import '../services/api_service.dart';
import '../services/ocr_service.dart';
import '../widgets/ocr_widgets.dart';

class ReceiptCaptureScreen extends StatefulWidget {
  final bool enableBatchProcessing;
  final List<File>? initialImages;

  const ReceiptCaptureScreen({
    super.key,
    this.enableBatchProcessing = false,
    this.initialImages,
  });

  @override
  State<ReceiptCaptureScreen> createState() => _ReceiptCaptureScreenState();
}

class _ReceiptCaptureScreenState extends State<ReceiptCaptureScreen>
    with TickerProviderStateMixin {
  final OCRService _ocrService = OCRService();
  final ApiService _apiService = ApiService();

  // State management
  OCRResult? _ocrResult;
  List<File> _selectedImages = [];
  BatchOCRResult? _batchResult;
  String? _error;
  bool _isPremiumUser = false;
  List<String> _merchantSuggestions = [];
  bool _isValidating = false;
  bool _isEnhancing = false;

  // Animation controllers
  late AnimationController _slideController;
  late AnimationController _fadeController;
  late Animation<double> _fadeAnimation;

  // Page controller for step navigation
  late PageController _pageController;
  int _currentStep = 0;

  @override
  void initState() {
    super.initState();

    // Initialize animations
    _slideController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _fadeController = AnimationController(
      duration: const Duration(milliseconds: 200),
      vsync: this,
    );

    _fadeAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeInOut,
    ));

    _pageController = PageController();

    // Load initial images if provided
    if (widget.initialImages != null) {
      _selectedImages = List.from(widget.initialImages!);
    }

    _checkPremiumStatus();
    _fadeController.forward();
  }

  @override
  void dispose() {
    _slideController.dispose();
    _fadeController.dispose();
    _pageController.dispose();
    _ocrService.dispose();
    super.dispose();
  }

  Future<void> _checkPremiumStatus() async {
    // Check if user has premium subscription
    // This would integrate with your IAP service
    try {
      final profile = await _apiService.getUserProfile();
      setState(() {
        _isPremiumUser = profile['is_premium'] as bool? ?? false;
      });
    } catch (e) {
      debugPrint('Error checking premium status: $e');
    }
  }

  Future<void> _pickImage(ImageSource source) async {
    try {
      final picker = ImagePicker();

      if (widget.enableBatchProcessing && source == ImageSource.gallery) {
        // Multi-select for batch processing
        final images = await picker.pickMultiImage(
          maxHeight: 2048,
          maxWidth: 2048,
          imageQuality: 80,
        );

        if (images.isNotEmpty) {
          final files = images.map((image) => File(image.path)).toList();
          setState(() {
            _selectedImages.addAll(files);
            _error = null;
          });
          _navigateToStep(1);
        }
      } else {
        // Single image selection
        final picked = await picker.pickImage(
          source: source,
          maxHeight: 2048,
          maxWidth: 2048,
          imageQuality: 80,
        );

        if (picked != null) {
          // Crop the image for better OCR results
          final cropped = await _cropImage(picked.path);
          if (cropped != null) {
            setState(() {
              _selectedImages = [File(cropped.path)];
              _error = null;
            });
            _navigateToStep(1);
          }
        }
      }
    } catch (e) {
      setState(() {
        _error = 'Image selection error: $e';
      });
    }
  }

  Future<CroppedFile?> _cropImage(String imagePath) async {
    return await ImageCropper().cropImage(
      sourcePath: imagePath,
      uiSettings: [
        AndroidUiSettings(
          toolbarTitle: 'Crop Receipt',
          toolbarColor: Theme.of(context).colorScheme.primary,
          toolbarWidgetColor: Theme.of(context).colorScheme.onPrimary,
          aspectRatioPresets: [
            CropAspectRatioPreset.original,
            CropAspectRatioPreset.ratio3x2,
            CropAspectRatioPreset.ratio4x3,
          ],
        ),
        IOSUiSettings(
          title: 'Crop Receipt',
          aspectRatioPresets: [
            CropAspectRatioPreset.original,
            CropAspectRatioPreset.ratio3x2,
            CropAspectRatioPreset.ratio4x3,
          ],
        ),
      ],
    );
  }

  Future<void> _processReceipts() async {
    if (_selectedImages.isEmpty) return;

    setState(() {
      _error = null;
    });

    try {
      if (_selectedImages.length == 1) {
        // Single receipt processing
        final result = await _ocrService.processReceipt(
          _selectedImages.first,
          isPremiumUser: _isPremiumUser,
        );

        if (!mounted) return;
        setState(() {
          _ocrResult = result;
        });

        // Load merchant suggestions
        _loadMerchantSuggestions(result.merchant);

        _navigateToStep(2);
      } else {
        // Batch processing
        final batchResult = await _ocrService.processBatchReceipts(
          _selectedImages,
          isPremiumUser: _isPremiumUser,
          onProgress: (processed, total) {
            // Update progress in real-time
            if (mounted) setState(() {});
          },
        );

        if (!mounted) return;
        setState(() {
          _batchResult = batchResult;
        });

        _navigateToStep(3);
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = 'OCR processing failed: $e';
      });
    }
  }

  Future<void> _loadMerchantSuggestions(String merchantName) async {
    try {
      final suggestions =
          await _ocrService.getMerchantSuggestions(merchantName);
      if (!mounted) return;
      setState(() {
        _merchantSuggestions = suggestions;
      });
    } catch (e) {
      debugPrint('Error loading merchant suggestions: $e');
    }
  }

  Future<void> _validateOCRResult() async {
    if (_ocrResult == null) return;

    setState(() {
      _isValidating = true;
      _error = null;
    });

    try {
      final validatedResult =
          await _ocrService.validateAndCorrectOCR(_ocrResult!);

      if (!mounted) return;
      setState(() {
        _ocrResult = validatedResult;
        _isValidating = false;
      });

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                Icon(
                  Icons.check_circle,
                  color: Theme.of(context).colorScheme.onInverseSurface,
                ),
                const SizedBox(width: 8.0),
                const Text('OCR data validated successfully'),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.inverseSurface,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isValidating = false;
        _error = 'Validation failed: $e';
      });
    }
  }

  Future<void> _enhanceOCRResult() async {
    if (_ocrResult == null) return;

    setState(() {
      _isEnhancing = true;
      _error = null;
    });

    try {
      final enhancedResult = await _ocrService.enhanceOCRData(_ocrResult!);

      if (!mounted) return;
      setState(() {
        _ocrResult = enhancedResult;
        _isEnhancing = false;
      });

      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              Icon(
                Icons.auto_awesome,
                color: Theme.of(context).colorScheme.onInverseSurface,
              ),
              const SizedBox(width: 8.0),
              const Text('Receipt data enhanced with AI'),
            ],
          ),
          backgroundColor: Theme.of(context).colorScheme.inverseSurface,
          behavior: SnackBarBehavior.floating,
        ),
      );
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _isEnhancing = false;
        _error = 'Enhancement failed: $e';
      });
    }
  }

  void _navigateToStep(int step) {
    setState(() {
      _currentStep = step;
    });

    _slideController.forward().then((_) {
      _pageController.animateToPage(
        step,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOutCubic,
      );
      _slideController.reset();
    });
  }

  Future<void> _saveTransaction() async {
    if (_ocrResult == null) return;

    try {
      final transactionProvider =
          Provider.of<TransactionProvider>(context, listen: false);

      final input = TransactionInput(
        amount: _ocrResult!.total,
        category: _ocrResult!.category,
        merchant: _ocrResult!.merchant,
        spentAt: _ocrResult!.date,
        confidenceScore: _ocrResult!.overallConfidence,
        notes: 'Source: OCR Receipt',
      );

      final result = await transactionProvider.createTransaction(input);

      if (result == null) {
        throw Exception(
            transactionProvider.errorMessage ?? 'Failed to create transaction');
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                Icon(
                  Icons.check_circle,
                  color: Theme.of(context).colorScheme.onInverseSurface,
                ),
                const SizedBox(width: 8.0),
                const Text('Transaction saved successfully!'),
              ],
            ),
            backgroundColor: Theme.of(context).colorScheme.inverseSurface,
            behavior: SnackBarBehavior.floating,
          ),
        );
        Navigator.pop(context, _ocrResult);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save transaction: $e'),
            backgroundColor: Theme.of(context).colorScheme.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  Future<void> _saveBatchTransactions() async {
    if (_batchResult == null || _batchResult!.results.isEmpty) return;

    try {
      final transactionProvider =
          Provider.of<TransactionProvider>(context, listen: false);
      int successCount = 0;

      for (final result in _batchResult!.results) {
        final input = TransactionInput(
          amount: result.total,
          category: result.category,
          merchant: result.merchant,
          spentAt: result.date,
          confidenceScore: result.overallConfidence,
          notes: 'Source: OCR Batch',
        );

        final transaction = await transactionProvider.createTransaction(input);
        if (transaction != null) {
          successCount++;
        }
      }

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
              '$successCount transactions saved successfully!',
            ),
            backgroundColor: Theme.of(context).colorScheme.inverseSurface,
            behavior: SnackBarBehavior.floating,
          ),
        );
        Navigator.pop(context, _batchResult);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Failed to save transactions: $e'),
            backgroundColor: Theme.of(context).colorScheme.error,
            behavior: SnackBarBehavior.floating,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(widget.enableBatchProcessing
            ? 'Batch Receipt Scan'
            : 'Scan Receipt'),
        backgroundColor: colorScheme.surface,
        elevation: 0,
        actions: [
          if (_isPremiumUser)
            Container(
              margin: const EdgeInsets.only(right: 16.0),
              child: Chip(
                label: const Text('Premium'),
                backgroundColor: colorScheme.primaryContainer,
                labelStyle: TextStyle(
                  color: colorScheme.onPrimaryContainer,
                  fontSize: 12.0,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
        ],
      ),
      body: Stack(
        children: [
          FadeTransition(
            opacity: _fadeAnimation,
            child: PageView(
              controller: _pageController,
              physics: const NeverScrollableScrollPhysics(),
              children: [
                _buildImageSelectionStep(),
                _buildProcessingStep(),
                _buildResultStep(),
                _buildBatchResultStep(),
              ],
            ),
          ),

          // Progress indicator
          Positioned(
            top: 0,
            left: 0,
            right: 0,
            child: LinearProgressIndicator(
              value: (_currentStep + 1) / 4,
              backgroundColor: colorScheme.surfaceContainerHighest,
              valueColor: AlwaysStoppedAnimation(colorScheme.primary),
            ),
          ),

          // Error overlay
          if (_error != null)
            Positioned(
              bottom: 100,
              left: 16,
              right: 16,
              child: Card(
                color: colorScheme.errorContainer,
                child: Padding(
                  padding: const EdgeInsets.all(16.0),
                  child: Row(
                    children: [
                      Icon(
                        Icons.error_outline,
                        color: colorScheme.onErrorContainer,
                      ),
                      const SizedBox(width: 8.0),
                      Expanded(
                        child: Text(
                          _error!,
                          style: TextStyle(color: colorScheme.onErrorContainer),
                        ),
                      ),
                      IconButton(
                        onPressed: () => setState(() => _error = null),
                        icon: Icon(
                          Icons.close,
                          color: colorScheme.onErrorContainer,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildImageSelectionStep() {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24.0),

          // Header
          Text(
            widget.enableBatchProcessing
                ? 'Select Receipts'
                : 'Capture Receipt',
            style: theme.textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.bold,
              color: colorScheme.onSurface,
            ),
          ),
          const SizedBox(height: 8.0),
          Text(
            widget.enableBatchProcessing
                ? 'Select multiple receipt images for batch processing'
                : 'Take a photo or select an image of your receipt',
            style: theme.textTheme.bodyLarge?.copyWith(
              color: colorScheme.onSurfaceVariant,
            ),
          ),

          const SizedBox(height: 32.0),

          // Selected images preview
          if (_selectedImages.isNotEmpty) ...[
            Text(
              '${_selectedImages.length} image${_selectedImages.length > 1 ? 's' : ''} selected',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 16.0),
            SizedBox(
              height: 120.0,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                itemCount: _selectedImages.length,
                itemBuilder: (context, index) {
                  return Container(
                    width: 90.0,
                    margin: const EdgeInsets.only(right: 12.0),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(12.0),
                      border: Border.all(color: colorScheme.outline),
                    ),
                    child: ClipRRect(
                      borderRadius: BorderRadius.circular(12.0),
                      child: Stack(
                        children: [
                          Image.file(
                            _selectedImages[index],
                            fit: BoxFit.cover,
                            width: double.infinity,
                            height: double.infinity,
                          ),
                          Positioned(
                            top: 4,
                            right: 4,
                            child: GestureDetector(
                              onTap: () {
                                setState(() {
                                  _selectedImages.removeAt(index);
                                });
                              },
                              child: Container(
                                decoration: BoxDecoration(
                                  color: colorScheme.error,
                                  shape: BoxShape.circle,
                                ),
                                padding: const EdgeInsets.all(4.0),
                                child: Icon(
                                  Icons.close,
                                  color: colorScheme.onError,
                                  size: 16.0,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 24.0),
          ],

          const Spacer(),

          // Action buttons
          Column(
            children: [
              // Camera button
              SizedBox(
                width: double.infinity,
                height: 56.0,
                child: FilledButton.icon(
                  onPressed: () => _pickImage(ImageSource.camera),
                  icon: const Icon(Icons.camera_alt),
                  label: const Text('Take Photo'),
                  style: FilledButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16.0),
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 12.0),

              // Gallery button
              SizedBox(
                width: double.infinity,
                height: 56.0,
                child: OutlinedButton.icon(
                  onPressed: () => _pickImage(ImageSource.gallery),
                  icon: const Icon(Icons.photo_library),
                  label: Text(widget.enableBatchProcessing
                      ? 'Select from Gallery'
                      : 'Choose from Gallery'),
                  style: OutlinedButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16.0),
                    ),
                  ),
                ),
              ),

              if (_selectedImages.isNotEmpty) ...[
                const SizedBox(height: 12.0),
                SizedBox(
                  width: double.infinity,
                  height: 56.0,
                  child: FilledButton.icon(
                    onPressed: _processReceipts,
                    icon: const Icon(Icons.auto_awesome),
                    label: Text(_selectedImages.length > 1
                        ? 'Process ${_selectedImages.length} Receipts'
                        : 'Process Receipt'),
                    style: FilledButton.styleFrom(
                      backgroundColor: colorScheme.secondary,
                      foregroundColor: colorScheme.onSecondary,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(16.0),
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),

          const SizedBox(height: 24.0),
        ],
      ),
    );
  }

  Widget _buildProcessingStep() {
    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          ValueListenableBuilder<OCRProcessingStatus>(
            valueListenable: _ocrService.processingStatus,
            builder: (context, status, child) {
              return ValueListenableBuilder<double>(
                valueListenable: _ocrService.processingProgress,
                builder: (context, progress, child) {
                  return OCRProcessingIndicator(
                    status: status,
                    progress: progress,
                  );
                },
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildResultStep() {
    if (_ocrResult == null) {
      return const Center(child: Text('No OCR result available'));
    }

    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24.0),

          // Header
          Row(
            children: [
              Text(
                'Review Receipt Data',
                style: theme.textTheme.headlineSmall?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Spacer(),
              ConfidenceIndicator(
                confidence:
                    _getOverallConfidence(_ocrResult!.overallConfidence),
                label: 'Overall',
              ),
            ],
          ),

          const SizedBox(height: 16.0),

          // Action buttons for validation and enhancement
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _isValidating ? null : _validateOCRResult,
                  icon: _isValidating
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.verified),
                  label: const Text('Validate'),
                  style: OutlinedButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12.0),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 12.0),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _isEnhancing ? null : _enhanceOCRResult,
                  icon: _isEnhancing
                      ? const SizedBox(
                          width: 16,
                          height: 16,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.auto_awesome),
                  label: const Text('Enhance'),
                  style: OutlinedButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12.0),
                    ),
                  ),
                ),
              ),
            ],
          ),

          const SizedBox(height: 24.0),

          Expanded(
            child: SingleChildScrollView(
              child: Column(
                children: [
                  // Merchant field
                  OCRDataField(
                    label: 'Merchant',
                    value: _ocrResult!.merchant,
                    confidence: _ocrResult!.merchantConfidence,
                    suggestions: _merchantSuggestions,
                    onChanged: (value) {
                      _ocrResult = OCRResult(
                        merchant: value,
                        total: _ocrResult!.total,
                        date: _ocrResult!.date,
                        category: _ocrResult!.category,
                        items: _ocrResult!.items,
                        merchantConfidence: _ocrResult!.merchantConfidence,
                        totalConfidence: _ocrResult!.totalConfidence,
                        dateConfidence: _ocrResult!.dateConfidence,
                        categoryConfidence: _ocrResult!.categoryConfidence,
                        rawText: _ocrResult!.rawText,
                        isPremiumProcessing: _ocrResult!.isPremiumProcessing,
                      );
                    },
                    prefixIcon: Icons.store,
                  ),

                  const SizedBox(height: 16.0),

                  // Total field
                  OCRDataField(
                    label: 'Total Amount',
                    value: _ocrResult!.total.toStringAsFixed(2),
                    confidence: _ocrResult!.totalConfidence,
                    keyboardType:
                        const TextInputType.numberWithOptions(decimal: true),
                    onChanged: (value) {
                      final total = double.tryParse(value) ?? _ocrResult!.total;
                      _ocrResult = OCRResult(
                        merchant: _ocrResult!.merchant,
                        total: total,
                        date: _ocrResult!.date,
                        category: _ocrResult!.category,
                        items: _ocrResult!.items,
                        merchantConfidence: _ocrResult!.merchantConfidence,
                        totalConfidence: _ocrResult!.totalConfidence,
                        dateConfidence: _ocrResult!.dateConfidence,
                        categoryConfidence: _ocrResult!.categoryConfidence,
                        rawText: _ocrResult!.rawText,
                        isPremiumProcessing: _ocrResult!.isPremiumProcessing,
                      );
                    },
                    prefixIcon: Icons.attach_money,
                  ),

                  const SizedBox(height: 16.0),

                  // Date field
                  OCRDataField(
                    label: 'Date',
                    value: _ocrResult!.date.toString().split(' ')[0],
                    confidence: _ocrResult!.dateConfidence,
                    onChanged: (value) {
                      final date = DateTime.tryParse(value) ?? _ocrResult!.date;
                      _ocrResult = OCRResult(
                        merchant: _ocrResult!.merchant,
                        total: _ocrResult!.total,
                        date: date,
                        category: _ocrResult!.category,
                        items: _ocrResult!.items,
                        merchantConfidence: _ocrResult!.merchantConfidence,
                        totalConfidence: _ocrResult!.totalConfidence,
                        dateConfidence: _ocrResult!.dateConfidence,
                        categoryConfidence: _ocrResult!.categoryConfidence,
                        rawText: _ocrResult!.rawText,
                        isPremiumProcessing: _ocrResult!.isPremiumProcessing,
                      );
                    },
                    prefixIcon: Icons.calendar_today,
                  ),

                  const SizedBox(height: 16.0),

                  // Category field
                  OCRDataField(
                    label: 'Category',
                    value: _ocrResult!.category,
                    confidence: _ocrResult!.categoryConfidence,
                    onChanged: (value) {
                      _ocrResult = OCRResult(
                        merchant: _ocrResult!.merchant,
                        total: _ocrResult!.total,
                        date: _ocrResult!.date,
                        category: value,
                        items: _ocrResult!.items,
                        merchantConfidence: _ocrResult!.merchantConfidence,
                        totalConfidence: _ocrResult!.totalConfidence,
                        dateConfidence: _ocrResult!.dateConfidence,
                        categoryConfidence: _ocrResult!.categoryConfidence,
                        rawText: _ocrResult!.rawText,
                        isPremiumProcessing: _ocrResult!.isPremiumProcessing,
                      );
                    },
                    prefixIcon: Icons.category,
                  ),

                  const SizedBox(height: 24.0),

                  // Receipt items
                  if (_ocrResult!.items.isNotEmpty)
                    OCRReceiptItemsList(
                      items: _ocrResult!.items,
                      onItemChanged: (index, item) {
                        final updatedItems =
                            List<ReceiptItem>.from(_ocrResult!.items);
                        updatedItems[index] = item;
                        _ocrResult = OCRResult(
                          merchant: _ocrResult!.merchant,
                          total: _ocrResult!.total,
                          date: _ocrResult!.date,
                          category: _ocrResult!.category,
                          items: updatedItems,
                          merchantConfidence: _ocrResult!.merchantConfidence,
                          totalConfidence: _ocrResult!.totalConfidence,
                          dateConfidence: _ocrResult!.dateConfidence,
                          categoryConfidence: _ocrResult!.categoryConfidence,
                          rawText: _ocrResult!.rawText,
                          isPremiumProcessing: _ocrResult!.isPremiumProcessing,
                        );
                      },
                    ),
                ],
              ),
            ),
          ),

          const SizedBox(height: 16.0),

          // Save button
          SizedBox(
            width: double.infinity,
            height: 56.0,
            child: FilledButton.icon(
              onPressed: _saveTransaction,
              icon: const Icon(Icons.save),
              label: const Text('Save Transaction'),
              style: FilledButton.styleFrom(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16.0),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBatchResultStep() {
    if (_batchResult == null) {
      return const Center(child: Text('No batch result available'));
    }

    final theme = Theme.of(context);

    return Padding(
      padding: const EdgeInsets.all(24.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const SizedBox(height: 24.0),
          Text(
            'Batch Processing Complete',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 16.0),
          BatchProcessingIndicator(
            processed: _batchResult!.processed,
            total: _batchResult!.total,
            failed: _batchResult!.failures.length,
          ),
          const SizedBox(height: 24.0),
          Expanded(
            child: ListView.builder(
              itemCount: _batchResult!.results.length,
              itemBuilder: (context, index) {
                final result = _batchResult!.results[index];
                return Card(
                  margin: const EdgeInsets.only(bottom: 8.0),
                  child: ListTile(
                    leading: CircleAvatar(
                      backgroundColor:
                          Theme.of(context).colorScheme.primaryContainer,
                      child: Text('${index + 1}'),
                    ),
                    title: Text(result.merchant),
                    subtitle: Text(
                        '\$${result.total.toStringAsFixed(2)} • ${result.category}'),
                    trailing: ConfidenceIndicator(
                      confidence:
                          _getOverallConfidence(result.overallConfidence),
                      label: 'Confidence',
                      showLabel: false,
                    ),
                  ),
                );
              },
            ),
          ),
          const SizedBox(height: 16.0),
          SizedBox(
            width: double.infinity,
            height: 56.0,
            child: FilledButton.icon(
              onPressed: _saveBatchTransactions,
              icon: const Icon(Icons.save),
              label: Text('Save ${_batchResult!.results.length} Transactions'),
              style: FilledButton.styleFrom(
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(16.0),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  OCRConfidence _getOverallConfidence(double score) {
    if (score >= 0.8) return OCRConfidence.high;
    if (score >= 0.6) return OCRConfidence.medium;
    return OCRConfidence.low;
  }
}
