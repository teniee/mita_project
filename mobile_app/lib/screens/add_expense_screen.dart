import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import 'dart:async';
import '../services/offline_queue_service.dart';
import '../services/api_service.dart';
import '../services/expense_state_service.dart';
import 'receipt_capture_screen.dart';
import '../services/logging_service.dart';

class AddExpenseScreen extends StatefulWidget {
  const AddExpenseScreen({Key? key}) : super(key: key);

  @override
  State<AddExpenseScreen> createState() => _AddExpenseScreenState();
}

class _AddExpenseScreenState extends State<AddExpenseScreen> with TickerProviderStateMixin {
  final _formKey = GlobalKey<FormState>();
  final _descriptionController = TextEditingController();
  final OfflineQueueService _queue = OfflineQueueService.instance;
  final ApiService _apiService = ApiService();
  final ExpenseStateService _expenseStateService = ExpenseStateService();
  
  // Animation controllers for feedback
  late AnimationController _submitAnimationController;
  late Animation<double> _submitAnimation;
  late AnimationController _successAnimationController;
  late Animation<double> _successAnimation;
  
  bool _isSubmitting = false;

  double? _amount;
  String? _action;
  String? _description;
  DateTime _selectedDate = DateTime.now();
  List<Map<String, dynamic>> _aiSuggestions = [];
  bool _loadingSuggestions = false;

  final List<Map<String, dynamic>> _categories = [
    {'name': 'Food & Dining', 'icon': Icons.restaurant, 'color': Colors.orange, 'subcategories': ['Restaurants', 'Groceries', 'Fast Food', 'Coffee', 'Delivery']},
    {'name': 'Transportation', 'icon': Icons.directions_car, 'color': Colors.blue, 'subcategories': ['Gas', 'Public Transit', 'Taxi/Uber', 'Parking', 'Car Maintenance']},
    {'name': 'Entertainment', 'icon': Icons.movie, 'color': Colors.purple, 'subcategories': ['Movies', 'Concerts', 'Streaming', 'Gaming', 'Books']},
    {'name': 'Health & Fitness', 'icon': Icons.fitness_center, 'color': Colors.green, 'subcategories': ['Doctor', 'Gym', 'Medicine', 'Supplements', 'Therapy']},
    {'name': 'Shopping', 'icon': Icons.shopping_bag, 'color': Colors.pink, 'subcategories': ['Clothing', 'Electronics', 'Home', 'Beauty', 'Gifts']},
    {'name': 'Bills & Utilities', 'icon': Icons.receipt_long, 'color': Colors.red, 'subcategories': ['Electricity', 'Water', 'Internet', 'Phone', 'Insurance']},
    {'name': 'Education', 'icon': Icons.school, 'color': Colors.indigo, 'subcategories': ['Courses', 'Books', 'Supplies', 'Tuition', 'Certifications']},
    {'name': 'Travel', 'icon': Icons.flight, 'color': Colors.teal, 'subcategories': ['Flights', 'Hotels', 'Food', 'Activities', 'Transport']},
    {'name': 'Personal Care', 'icon': Icons.spa, 'color': Colors.cyan, 'subcategories': ['Haircut', 'Skincare', 'Massage', 'Nails', 'Dental']},
    {'name': 'Other', 'icon': Icons.more_horiz, 'color': Colors.grey, 'subcategories': ['Miscellaneous', 'Fees', 'Donations', 'Pets', 'Hobbies']},
  ];
  
  String? _selectedSubcategory;

  @override
  void initState() {
    super.initState();
    _initializeAnimations();
  }

  void _initializeAnimations() {
    _submitAnimationController = AnimationController(
      duration: const Duration(milliseconds: 600),
      vsync: this,
    );
    _submitAnimation = Tween<double>(begin: 1.0, end: 0.0).animate(
      CurvedAnimation(parent: _submitAnimationController, curve: Curves.easeInOut),
    );
    
    _successAnimationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );
    _successAnimation = Tween<double>(begin: 0.0, end: 1.0).animate(
      CurvedAnimation(parent: _successAnimationController, curve: Curves.elasticOut),
    );
  }

  List<String> _getSelectedCategorySubcategories() {
    if (_action == null) return [];
    
    final selectedCategory = _categories.firstWhere(
      (cat) => cat['name'] == _action,
      orElse: () => {'subcategories': <String>[]},
    );
    
    return List<String>.from(selectedCategory['subcategories'] ?? []);
  }

  @override
  void dispose() {
    _descriptionController.dispose();
    _submitAnimationController.dispose();
    _successAnimationController.dispose();
    super.dispose();
  }

  Future<void> _getAISuggestions(String description) async {
    if (description.trim().isEmpty) {
      setState(() {
        _aiSuggestions = [];
        _loadingSuggestions = false;
      });
      return;
    }

    setState(() {
      _loadingSuggestions = true;
    });

    try {
      final suggestions = await _apiService.getAICategorySuggestions(
        description,
        amount: _amount,
      );
      
      if (mounted) {
        setState(() {
          _aiSuggestions = suggestions;
          _loadingSuggestions = false;
        });
      }
    } catch (e) {
      logError('Error getting AI suggestions: $e');
      if (mounted) {
        setState(() {
          _loadingSuggestions = false;
        });
      }
    }
  }

  void _selectAISuggestion(Map<String, dynamic> suggestion) {
    setState(() {
      _action = suggestion['category'] as String?;
      if (suggestion['confidence'] != null) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.psychology, color: Colors.white),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'AI suggestion applied with ${(suggestion['confidence'] * 100).toInt()}% confidence',
                  ),
                ),
              ],
            ),
            backgroundColor: Colors.green,
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 2),
          ),
        );
      }
    });
  }

  Future<void> _submitExpense() async {
    if (!_formKey.currentState!.validate() || _action == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.warning, color: Colors.white),
              const SizedBox(width: 8),
              const Expanded(
                child: Text(
                  'Please fill in all required fields',
                  style: TextStyle(fontFamily: 'Manrope'),
                ),
              ),
            ],
          ),
          backgroundColor: Colors.orange,
          behavior: SnackBarBehavior.floating,
          duration: const Duration(seconds: 2),
        ),
      );
      return;
    }
    
    if (_isSubmitting) return; // Prevent double submission
    
    _formKey.currentState!.save();
    setState(() => _isSubmitting = true);
    
    // Start submit animation
    _submitAnimationController.forward();

    final selectedCategory = _categories.firstWhere(
      (cat) => cat['name'] == _action,
      orElse: () => _categories.last,
    );

    final data = {
      'amount': _amount,
      'category': _action,
      'subcategory': _selectedSubcategory ?? 'General',
      'description': _description,
      'date': _selectedDate.toIso8601String(),
      'color': selectedCategory['color']?.value?.toString(),
      'icon': selectedCategory['icon']?.codePoint?.toString(),
      'timestamp': DateTime.now().millisecondsSinceEpoch,
      'offline_created': true, // Mark as created offline-first
    };

    // Store previous calendar state for potential rollback
    final previousCalendarData = List<dynamic>.from(_expenseStateService.calendarData);
    
    try {
      // 1. Add expense optimistically to state service
      _expenseStateService.addExpenseOptimistically(data);
      
      // 2. Show immediate success feedback with animation
      await _showSuccessFeedback();
      
      // 3. Queue the expense for API submission
      await _queue.queueExpense(data);
      
      // 4. Try to submit to API immediately if online
      try {
        await _apiService.createExpense(data).timeout(
          Duration(seconds: 8),
          onTimeout: () => throw TimeoutException('API submission timeout', Duration(seconds: 8))
        );
        logInfo('Expense submitted to API successfully', tag: 'ADD_EXPENSE');
      } catch (apiError) {
        // API submission failed, but expense is queued for offline sync
        logWarning('API submission failed, expense queued for offline sync', tag: 'ADD_EXPENSE', extra: {
          'error': apiError.toString(),
        });
        
        // Show offline mode notification
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Row(
                children: [
                  const Icon(Icons.cloud_off, color: Colors.white),
                  const SizedBox(width: 8),
                  const Expanded(
                    child: Text(
                      'Expense saved offline and will sync when online',
                      style: TextStyle(fontFamily: 'Manrope'),
                    ),
                  ),
                ],
              ),
              backgroundColor: Colors.blue,
              behavior: SnackBarBehavior.floating,
              duration: const Duration(seconds: 2),
            ),
          );
        }
      }
      
      // 5. Navigate back with success result
      if (mounted) {
        // Wait a bit for animations to complete
        await Future.delayed(const Duration(milliseconds: 500));
        Navigator.pop(context, {
          'success': true,
          'expense_data': data,
          'amount': _amount,
          'category': _action,
        });
      }
      
    } catch (e, stackTrace) {
      // Rollback optimistic changes
      _expenseStateService.rollbackOptimisticChanges(previousCalendarData);
      
      logError('Failed to submit expense', tag: 'ADD_EXPENSE', error: e, extra: {
        'stackTrace': stackTrace.toString(),
        'expenseData': data,
      });
      
      if (mounted) {
        // Reset animations
        _submitAnimationController.reset();
        _successAnimationController.reset();
        
        // Show error message
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Row(
              children: [
                const Icon(Icons.error, color: Colors.white),
                const SizedBox(width: 8),
                const Expanded(
                  child: Text(
                    'Failed to add expense. Please try again.',
                    style: TextStyle(fontFamily: 'Manrope'),
                  ),
                ),
              ],
            ),
            backgroundColor: Colors.red,
            behavior: SnackBarBehavior.floating,
            duration: const Duration(seconds: 3),
            action: SnackBarAction(
              label: 'RETRY',
              textColor: Colors.white,
              onPressed: () => _submitExpense(),
            ),
          ),
        );
      }
    } finally {
      if (mounted) {
        setState(() => _isSubmitting = false);
      }
    }
  }
  
  Future<void> _showSuccessFeedback() async {
    // Start success animation
    _successAnimationController.forward();
    
    // Show animated success message
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: AnimatedBuilder(
            animation: _successAnimation,
            builder: (context, child) {
              return Transform.scale(
                scale: _successAnimation.value,
                child: Row(
                  children: [
                    Icon(
                      Icons.check_circle,
                      color: Colors.white,
                      size: 20 + (4 * _successAnimation.value),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Expense added successfully! \$${_amount?.toStringAsFixed(2)} for $_action',
                        style: const TextStyle(
                          fontFamily: 'Manrope',
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
          backgroundColor: Colors.green,
          duration: const Duration(seconds: 2),
          behavior: SnackBarBehavior.floating,
          margin: const EdgeInsets.all(16),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
          ),
        ),
      );
    }
    
    // Wait for animation to complete
    await Future.delayed(const Duration(milliseconds: 400));
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _selectedDate,
      firstDate: DateTime(2023),
      lastDate: DateTime(2100),
    );
    if (picked != null && picked != _selectedDate) {
      setState(() => _selectedDate = picked);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Add Expense',
          style: TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.bold,
            color: Color(0xFF193C57),
          ),
        ),
        backgroundColor: const Color(0xFFFFF9F0),
        elevation: 0,
        iconTheme: const IconThemeData(color: Color(0xFF193C57)),
        centerTitle: true,
      ),
      body: LayoutBuilder(
        builder: (context, constraints) {
          final isWide = constraints.maxWidth > 600;
          final form = Form(
            key: _formKey,
            child: ListView(
              shrinkWrap: true,
              children: [
              TextFormField(
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Amount',
                  prefixIcon: Icon(Icons.attach_money),
                ),
                style: const TextStyle(fontFamily: 'Manrope'),
                validator: (value) =>
                    value == null || value.isEmpty ? 'Enter amount' : null,
                onSaved: (value) => _amount = double.tryParse(value ?? ''),
                onChanged: (value) {
                  _amount = double.tryParse(value);
                  if (_descriptionController.text.isNotEmpty) {
                    _getAISuggestions(_descriptionController.text);
                  }
                },
              ),
              const SizedBox(height: 20),
              TextFormField(
                controller: _descriptionController,
                decoration: InputDecoration(
                  labelText: 'Description',
                  prefixIcon: const Icon(Icons.description),
                  suffixIcon: _loadingSuggestions
                      ? const SizedBox(
                          width: 20,
                          height: 20,
                          child: Padding(
                            padding: EdgeInsets.all(12),
                            child: CircularProgressIndicator(strokeWidth: 2),
                          ),
                        )
                      : const Icon(Icons.psychology, color: Colors.blue),
                  helperText: 'Describe your expense for AI suggestions',
                ),
                style: const TextStyle(fontFamily: 'Manrope'),
                onChanged: (value) {
                  _description = value;
                  if (value.length > 3) {
                    // Debounce AI suggestions
                    Future.delayed(const Duration(milliseconds: 500), () {
                      if (_descriptionController.text == value) {
                        _getAISuggestions(value);
                      }
                    });
                  }
                },
                onSaved: (value) => _description = value,
              ),
              const SizedBox(height: 16),
              
              // AI Suggestions Section
              if (_aiSuggestions.isNotEmpty) ...[
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.blue.withValues(alpha: 0.05),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.blue.withValues(alpha: 0.2)),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Icon(Icons.psychology, color: Colors.blue, size: 20),
                          const SizedBox(width: 8),
                          const Text(
                            'AI Category Suggestions',
                            style: TextStyle(
                              fontFamily: 'Sora',
                              fontWeight: FontWeight.w600,
                              fontSize: 14,
                              color: Colors.blue,
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: _aiSuggestions.map((suggestion) {
                          final category = suggestion['category'] as String;
                          final confidence = suggestion['confidence'] as double? ?? 0.0;
                          final reason = suggestion['reason'] as String? ?? '';
                          
                          return GestureDetector(
                            onTap: () => _selectAISuggestion(suggestion),
                            child: Container(
                              padding: const EdgeInsets.symmetric(
                                horizontal: 12,
                                vertical: 8,
                              ),
                              decoration: BoxDecoration(
                                color: _action == category
                                    ? Colors.blue
                                    : Colors.white,
                                borderRadius: BorderRadius.circular(20),
                                border: Border.all(
                                  color: _action == category
                                      ? Colors.blue
                                      : Colors.blue.withValues(alpha: 0.3),
                                ),
                              ),
                              child: Row(
                                mainAxisSize: MainAxisSize.min,
                                children: [
                                  Text(
                                    category,
                                    style: TextStyle(
                                      fontFamily: 'Manrope',
                                      fontSize: 12,
                                      fontWeight: FontWeight.w500,
                                      color: _action == category
                                          ? Colors.white
                                          : Colors.blue,
                                    ),
                                  ),
                                  const SizedBox(width: 4),
                                  Text(
                                    '${(confidence * 100).toInt()}%',
                                    style: TextStyle(
                                      fontFamily: 'Manrope',
                                      fontSize: 10,
                                      color: _action == category
                                          ? Colors.white.withValues(alpha: 0.8)
                                          : Colors.blue.withValues(alpha: 0.7),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          );
                        }).toList(),
                      ),
                      if (_aiSuggestions.isNotEmpty && _aiSuggestions.first['reason'] != null) ...[
                        const SizedBox(height: 8),
                        Text(
                          _aiSuggestions.first['reason'] as String,
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 11,
                            color: Colors.blue.withValues(alpha: 0.8),
                            fontStyle: FontStyle.italic,
                          ),
                        ),
                      ],
                    ],
                  ),
                ),
                const SizedBox(height: 16),
              ],
              
              DropdownButtonFormField<String>(
                value: _action,
                decoration: const InputDecoration(
                  labelText: 'Category',
                  prefixIcon: Icon(Icons.category),
                ),
                items: _categories.map((cat) {
                  return DropdownMenuItem(
                    value: cat['name'] as String,
                    child: Row(
                      children: [
                        Icon(cat['icon'] as IconData, color: cat['color'] as Color, size: 20),
                        const SizedBox(width: 8),
                        Text(cat['name'] as String, style: const TextStyle(fontFamily: 'Manrope')),
                      ],
                    ),
                  );
                }).toList(),
                onChanged: (value) => setState(() => _action = value),
                validator: (value) => value == null ? 'Select category' : null,
              ),
              
              // Subcategory dropdown if a category is selected
              if (_action != null) ...[
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  value: _selectedSubcategory,
                  decoration: const InputDecoration(
                    labelText: 'Subcategory',
                    prefixIcon: Icon(Icons.category_outlined),
                  ),
                  items: _getSelectedCategorySubcategories().map((subcat) {
                    return DropdownMenuItem(
                      value: subcat,
                      child: Text(subcat, style: const TextStyle(fontFamily: 'Manrope')),
                    );
                  }).toList(),
                  onChanged: (value) => setState(() => _selectedSubcategory = value),
                ),
              ],
              const SizedBox(height: 20),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('Date', style: TextStyle(fontFamily: 'Manrope')),
                subtitle: Text(
                  DateFormat.yMMMd().format(_selectedDate),
                  style: const TextStyle(fontFamily: 'Manrope'),
                ),
                trailing: IconButton(
                  icon: const Icon(Icons.calendar_today),
                  onPressed: _pickDate,
                ),
              ),
              const SizedBox(height: 30),
              ElevatedButton(
                onPressed: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const ReceiptCaptureScreen(),
                    ),
                  );
                },
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFE0E0E0),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 12),
                ),
                child: const Text('Scan Receipt'),
              ),
              const SizedBox(height: 20),
              AnimatedBuilder(
                animation: _submitAnimation,
                builder: (context, child) {
                  return Transform.scale(
                    scale: 1.0 - (_submitAnimation.value * 0.1),
                    child: ElevatedButton(
                      onPressed: _isSubmitting ? null : _submitExpense,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _isSubmitting 
                            ? Colors.grey.shade300 
                            : const Color(0xFFFFD25F),
                        foregroundColor: _isSubmitting 
                            ? Colors.grey.shade600 
                            : Colors.black,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        elevation: _isSubmitting ? 1 : 4,
                      ),
                      child: AnimatedSwitcher(
                        duration: const Duration(milliseconds: 300),
                        child: _isSubmitting
                            ? Row(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  SizedBox(
                                    width: 20,
                                    height: 20,
                                    child: CircularProgressIndicator(
                                      strokeWidth: 2,
                                      valueColor: AlwaysStoppedAnimation<Color>(
                                        Colors.grey.shade600,
                                      ),
                                    ),
                                  ),
                                  const SizedBox(width: 8),
                                  const Text(
                                    'Adding...',
                                    style: TextStyle(
                                      fontFamily: 'Sora',
                                      fontSize: 16,
                                      fontWeight: FontWeight.bold,
                                    ),
                                  ),
                                ],
                              )
                            : const Text(
                                'Save Expense',
                                style: TextStyle(
                                  fontFamily: 'Sora',
                                  fontSize: 16,
                                  fontWeight: FontWeight.bold,
                                ),
                              ),
                      ),
                    ),
                  );
                },
              ),
            ],
          ),
        );

          return Padding(
            padding: const EdgeInsets.all(20),
            child: isWide
                ? Row(
                    children: [
                      Expanded(child: form),
                      const SizedBox(width: 20),
                      Expanded(
                        child: Center(
                          child: Icon(Icons.receipt_long,
                              size: 120, color: Colors.grey[400]),
                        ),
                      ),
                    ],
                  )
                : form,
          );
        },
      ),
    );
  }
}
