import 'package:flutter/material.dart';
import '../services/ocr_service.dart';

/// Material 3 confidence indicator chip
class ConfidenceIndicator extends StatelessWidget {
  final OCRConfidence confidence;
  final String label;
  final bool showLabel;
  final double size;

  const ConfidenceIndicator({
    super.key,
    required this.confidence,
    required this.label,
    this.showLabel = true,
    this.size = 16.0,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    
    Color getColor() {
      switch (confidence) {
        case OCRConfidence.high:
          return colorScheme.primary;
        case OCRConfidence.medium:
          return colorScheme.tertiary;
        case OCRConfidence.low:
          return colorScheme.error;
      }
    }

    IconData getIcon() {
      switch (confidence) {
        case OCRConfidence.high:
          return Icons.check_circle;
        case OCRConfidence.medium:
          return Icons.help_outline;
        case OCRConfidence.low:
          return Icons.warning_outlined;
      }
    }

    final color = getColor();
    
    if (!showLabel) {
      return Icon(
        getIcon(),
        color: color,
        size: size,
      );
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8.0, vertical: 4.0),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(16.0),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            getIcon(),
            color: color,
            size: size,
          ),
          if (showLabel) ...[
            const SizedBox(width: 4.0),
            Text(
              label,
              style: theme.textTheme.labelSmall?.copyWith(
                color: color,
                fontWeight: FontWeight.w500,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

/// OCR processing status indicator with animations
class OCRProcessingIndicator extends StatelessWidget {
  final OCRProcessingStatus status;
  final double progress;
  final String? customMessage;

  const OCRProcessingIndicator({
    super.key,
    required this.status,
    this.progress = 0.0,
    this.customMessage,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    String getMessage() {
      if (customMessage != null) return customMessage!;
      
      switch (status) {
        case OCRProcessingStatus.idle:
          return 'Ready to scan';
        case OCRProcessingStatus.preprocessing:
          return 'Preparing image...';
        case OCRProcessingStatus.extracting:
          return 'Extracting text...';
        case OCRProcessingStatus.categorizing:
          return 'Categorizing expenses...';
        case OCRProcessingStatus.complete:
          return 'Processing complete!';
        case OCRProcessingStatus.error:
          return 'Processing failed';
      }
    }

    Widget getIcon() {
      switch (status) {
        case OCRProcessingStatus.idle:
          return Icon(
            Icons.receipt_outlined,
            color: colorScheme.onSurfaceVariant,
            size: 32.0,
          );
        case OCRProcessingStatus.preprocessing:
        case OCRProcessingStatus.extracting:
        case OCRProcessingStatus.categorizing:
          return SizedBox(
            width: 32.0,
            height: 32.0,
            child: CircularProgressIndicator(
              value: progress > 0 ? progress : null,
              strokeWidth: 3.0,
              color: colorScheme.primary,
            ),
          );
        case OCRProcessingStatus.complete:
          return Icon(
            Icons.check_circle,
            color: colorScheme.primary,
            size: 32.0,
          );
        case OCRProcessingStatus.error:
          return Icon(
            Icons.error_outline,
            color: colorScheme.error,
            size: 32.0,
          );
      }
    }

    return Card(
      elevation: 2.0,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            getIcon(),
            const SizedBox(height: 12.0),
            Text(
              getMessage(),
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurfaceVariant,
                fontWeight: FontWeight.w500,
              ),
              textAlign: TextAlign.center,
            ),
            if (progress > 0 && progress < 1) ...[
              const SizedBox(height: 8.0),
              Text(
                '${(progress * 100).toInt()}%',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Enhanced receipt data field with confidence and editing
class OCRDataField extends StatefulWidget {
  final String label;
  final String value;
  final OCRConfidence confidence;
  final TextInputType? keyboardType;
  final List<String>? suggestions;
  final Function(String) onChanged;
  final String? helperText;
  final IconData? prefixIcon;

  const OCRDataField({
    super.key,
    required this.label,
    required this.value,
    required this.confidence,
    required this.onChanged,
    this.keyboardType,
    this.suggestions,
    this.helperText,
    this.prefixIcon,
  });

  @override
  State<OCRDataField> createState() => _OCRDataFieldState();
}

class _OCRDataFieldState extends State<OCRDataField> {
  late TextEditingController _controller;
  bool _showSuggestions = false;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(text: widget.value);
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        TextField(
          controller: _controller,
          keyboardType: widget.keyboardType,
          onChanged: (value) {
            widget.onChanged(value);
            if (widget.suggestions != null && value.isNotEmpty) {
              setState(() {
                _showSuggestions = true;
              });
            } else {
              setState(() {
                _showSuggestions = false;
              });
            }
          },
          decoration: InputDecoration(
            labelText: widget.label,
            helperText: widget.helperText,
            prefixIcon: widget.prefixIcon != null 
                ? Icon(widget.prefixIcon) 
                : null,
            suffixIcon: ConfidenceIndicator(
              confidence: widget.confidence,
              label: widget.confidence.name,
              showLabel: false,
            ),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(12.0),
            ),
            filled: widget.confidence == OCRConfidence.low,
            fillColor: widget.confidence == OCRConfidence.low
                ? colorScheme.errorContainer.withValues(alpha: 0.1)
                : null,
          ),
        ),
        if (_showSuggestions && widget.suggestions != null && widget.suggestions!.isNotEmpty)
          Container(
            margin: const EdgeInsets.only(top: 4.0),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(8.0),
              border: Border.all(color: colorScheme.outline.withValues(alpha: 0.3)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: widget.suggestions!
                  .where((suggestion) => suggestion
                      .toLowerCase()
                      .contains(_controller.text.toLowerCase()))
                  .take(5)
                  .map((suggestion) => InkWell(
                        onTap: () {
                          _controller.text = suggestion;
                          widget.onChanged(suggestion);
                          setState(() {
                            _showSuggestions = false;
                          });
                        },
                        child: Container(
                          width: double.infinity,
                          padding: const EdgeInsets.symmetric(
                            horizontal: 12.0,
                            vertical: 8.0,
                          ),
                          child: Text(
                            suggestion,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurfaceVariant,
                            ),
                          ),
                        ),
                      ))
                  .toList(),
            ),
          ),
      ],
    );
  }
}

/// Receipt scanning overlay with guidance
class ReceiptScanOverlay extends StatelessWidget {
  final bool isScanning;
  final String? guidanceText;
  final VoidCallback? onRetake;

  const ReceiptScanOverlay({
    super.key,
    this.isScanning = false,
    this.guidanceText,
    this.onRetake,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final size = MediaQuery.of(context).size;

    return Container(
      width: size.width,
      height: size.height,
      color: Colors.black.withValues(alpha: 0.8),
      child: Stack(
        children: [
          // Scanning frame
          Center(
            child: Container(
              width: size.width * 0.8,
              height: size.height * 0.6,
              decoration: BoxDecoration(
                border: Border.all(
                  color: isScanning ? colorScheme.primary : Colors.white,
                  width: 2.0,
                ),
                borderRadius: BorderRadius.circular(12.0),
              ),
              child: isScanning
                  ? Container(
                      decoration: BoxDecoration(
                        color: colorScheme.primary.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10.0),
                      ),
                      child: Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            CircularProgressIndicator(
                              color: colorScheme.primary,
                            ),
                            const SizedBox(height: 16.0),
                            Text(
                              'Scanning receipt...',
                              style: theme.textTheme.bodyLarge?.copyWith(
                                color: Colors.white,
                                fontWeight: FontWeight.w500,
                              ),
                            ),
                          ],
                        ),
                      ),
                    )
                  : null,
            ),
          ),
          
          // Corner guides
          if (!isScanning) ..._buildCornerGuides(context),
          
          // Guidance text
          Positioned(
            bottom: 120.0,
            left: 20.0,
            right: 20.0,
            child: Container(
              padding: const EdgeInsets.all(16.0),
              decoration: BoxDecoration(
                color: colorScheme.surface,
                borderRadius: BorderRadius.circular(12.0),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.2),
                    blurRadius: 8.0,
                    offset: const Offset(0, 4),
                  ),
                ],
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(
                    Icons.receipt_outlined,
                    color: colorScheme.primary,
                    size: 32.0,
                  ),
                  const SizedBox(height: 8.0),
                  Text(
                    guidanceText ?? 'Position receipt within the frame',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurface,
                      fontWeight: FontWeight.w500,
                    ),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 8.0),
                  Text(
                    'Ensure good lighting and focus',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurfaceVariant,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
          
          // Action buttons
          if (onRetake != null)
            Positioned(
              bottom: 40.0,
              left: 20.0,
              right: 20.0,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                children: [
                  FloatingActionButton(
                    heroTag: "ocr_retake_fab",
                    onPressed: onRetake,
                    backgroundColor: colorScheme.surfaceContainerHighest,
                    foregroundColor: colorScheme.onSurfaceVariant,
                    child: const Icon(Icons.refresh),
                  ),
                  FloatingActionButton.extended(
                    heroTag: "ocr_confirm_fab",
                    onPressed: () => Navigator.of(context).pop(),
                    backgroundColor: colorScheme.primary,
                    foregroundColor: colorScheme.onPrimary,
                    icon: const Icon(Icons.check),
                    label: Text(isScanning ? 'Processing...' : 'Capture'),
                  ),
                ],
              ),
            ),
        ],
      ),
    );
  }

  List<Widget> _buildCornerGuides(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final size = MediaQuery.of(context).size;
    final frameWidth = size.width * 0.8;
    final frameHeight = size.height * 0.6;
    final centerX = size.width / 2;
    final centerY = size.height / 2;
    
    const guideLength = 30.0;
    const guideWidth = 3.0;
    
    return [
      // Top-left corner
      Positioned(
        left: centerX - frameWidth / 2,
        top: centerY - frameHeight / 2,
        child: _buildCornerGuide(colorScheme.primary, guideLength, guideWidth, true, true),
      ),
      // Top-right corner
      Positioned(
        right: centerX - frameWidth / 2,
        top: centerY - frameHeight / 2,
        child: _buildCornerGuide(colorScheme.primary, guideLength, guideWidth, false, true),
      ),
      // Bottom-left corner
      Positioned(
        left: centerX - frameWidth / 2,
        bottom: centerY - frameHeight / 2,
        child: _buildCornerGuide(colorScheme.primary, guideLength, guideWidth, true, false),
      ),
      // Bottom-right corner
      Positioned(
        right: centerX - frameWidth / 2,
        bottom: centerY - frameHeight / 2,
        child: _buildCornerGuide(colorScheme.primary, guideLength, guideWidth, false, false),
      ),
    ];
  }

  Widget _buildCornerGuide(Color color, double length, double width, bool isLeft, bool isTop) {
    return SizedBox(
      width: length,
      height: length,
      child: Stack(
        children: [
          // Horizontal line
          Positioned(
            left: isLeft ? 0 : null,
            right: isLeft ? null : 0,
            top: isTop ? 0 : null,
            bottom: isTop ? null : 0,
            child: Container(
              width: length,
              height: width,
              color: color,
            ),
          ),
          // Vertical line
          Positioned(
            left: isLeft ? 0 : null,
            right: isLeft ? null : 0,
            top: isTop ? 0 : null,
            bottom: isTop ? null : 0,
            child: Container(
              width: width,
              height: length,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
}

/// Receipt item list with confidence indicators
class OCRReceiptItemsList extends StatelessWidget {
  final List<ReceiptItem> items;
  final Function(int, ReceiptItem) onItemChanged;
  final VoidCallback? onAddItem;

  const OCRReceiptItemsList({
    super.key,
    required this.items,
    required this.onItemChanged,
    this.onAddItem,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              'Receipt Items',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const Spacer(),
            if (onAddItem != null)
              TextButton.icon(
                onPressed: onAddItem,
                icon: const Icon(Icons.add),
                label: const Text('Add Item'),
              ),
          ],
        ),
        const SizedBox(height: 8.0),
        if (items.isEmpty)
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(24.0),
            decoration: BoxDecoration(
              color: colorScheme.surfaceContainerHighest.withValues(alpha: 0.3),
              borderRadius: BorderRadius.circular(12.0),
              border: Border.all(
                color: colorScheme.outline.withValues(alpha: 0.3),
                style: BorderStyle.solid,
              ),
            ),
            child: Column(
              children: [
                Icon(
                  Icons.receipt_outlined,
                  color: colorScheme.onSurfaceVariant,
                  size: 48.0,
                ),
                const SizedBox(height: 8.0),
                Text(
                  'No items detected',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          )
        else
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: items.length,
            separatorBuilder: (context, index) => const SizedBox(height: 8.0),
            itemBuilder: (context, index) {
              final item = items[index];
              return _buildItemCard(context, index, item);
            },
          ),
      ],
    );
  }

  Widget _buildItemCard(BuildContext context, int index, ReceiptItem item) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      elevation: 1.0,
      child: Padding(
        padding: const EdgeInsets.all(12.0),
        child: Row(
          children: [
            Expanded(
              flex: 3,
              child: OCRDataField(
                label: 'Item Name',
                value: item.name,
                confidence: item.confidence,
                onChanged: (value) {
                  final updatedItem = ReceiptItem(
                    name: value,
                    price: item.price,
                    confidence: item.confidence,
                    category: item.category,
                  );
                  onItemChanged(index, updatedItem);
                },
                prefixIcon: Icons.shopping_cart_outlined,
              ),
            ),
            const SizedBox(width: 12.0),
            Expanded(
              flex: 2,
              child: OCRDataField(
                label: 'Price',
                value: item.price.toStringAsFixed(2),
                confidence: item.confidence,
                keyboardType: const TextInputType.numberWithOptions(decimal: true),
                onChanged: (value) {
                  final price = double.tryParse(value) ?? item.price;
                  final updatedItem = ReceiptItem(
                    name: item.name,
                    price: price,
                    confidence: item.confidence,
                    category: item.category,
                  );
                  onItemChanged(index, updatedItem);
                },
                prefixIcon: Icons.attach_money,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Batch processing progress indicator
class BatchProcessingIndicator extends StatelessWidget {
  final int processed;
  final int total;
  final int failed;
  final Duration? estimatedTimeRemaining;

  const BatchProcessingIndicator({
    super.key,
    required this.processed,
    required this.total,
    this.failed = 0,
    this.estimatedTimeRemaining,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final progress = total > 0 ? processed / total : 0.0;

    return Card(
      elevation: 2.0,
      child: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.receipt_long,
                  color: colorScheme.primary,
                ),
                const SizedBox(width: 8.0),
                Text(
                  'Processing Receipts',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16.0),
            LinearProgressIndicator(
              value: progress,
              backgroundColor: colorScheme.surfaceContainerHighest,
              valueColor: AlwaysStoppedAnimation(colorScheme.primary),
            ),
            const SizedBox(height: 12.0),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(
                  '$processed of $total receipts',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                  ),
                ),
                Text(
                  '${(progress * 100).toInt()}%',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurfaceVariant,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
            if (failed > 0) ...[
              const SizedBox(height: 8.0),
              Row(
                children: [
                  Icon(
                    Icons.warning_outlined,
                    color: colorScheme.error,
                    size: 16.0,
                  ),
                  const SizedBox(width: 4.0),
                  Text(
                    '$failed failed',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.error,
                    ),
                  ),
                ],
              ),
            ],
            if (estimatedTimeRemaining != null) ...[
              const SizedBox(height: 8.0),
              Text(
                'Est. ${_formatDuration(estimatedTimeRemaining!)} remaining',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  String _formatDuration(Duration duration) {
    if (duration.inMinutes > 0) {
      return '${duration.inMinutes}m ${duration.inSeconds % 60}s';
    }
    return '${duration.inSeconds}s';
  }
}