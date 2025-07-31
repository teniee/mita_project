import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/offline_queue_service.dart';
import '../services/api_service.dart';
import 'receipt_capture_screen.dart';
import '../services/logging_service.dart';

class AddExpenseScreen extends StatefulWidget {
  const AddExpenseScreen({Key? key}) : super(key: key);

  @override
  State<AddExpenseScreen> createState() => _AddExpenseScreenState();
}

class _AddExpenseScreenState extends State<AddExpenseScreen> {
  final _formKey = GlobalKey<FormState>();
  final _descriptionController = TextEditingController();
  final OfflineQueueService _queue = OfflineQueueService.instance;
  final ApiService _apiService = ApiService();

  double? _amount;
  String? _action;
  String? _description;
  DateTime _selectedDate = DateTime.now();
  List<Map<String, dynamic>> _aiSuggestions = [];
  bool _loadingSuggestions = false;

  final List<String> _actions = [
    'Food',
    'Transport',
    'Entertainment',
    'Health',
    'Shopping',
    'Utilities',
    'Education',
    'Other',
  ];

  @override
  void dispose() {
    _descriptionController.dispose();
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
    if (!_formKey.currentState!.validate() || _action == null) return;
    _formKey.currentState!.save();

    final data = {
      'amount': _amount,
      'action': _action,
      'description': _description,
      'date': _selectedDate.toIso8601String(),
    };

    try {
      await _queue.queueExpense(data);
      if (!mounted) return;
      Navigator.pop(context, true); // return result
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to add expense: $e')),
      );
    }
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
                    color: Colors.blue.withOpacity(0.05),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.blue.withOpacity(0.2)),
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
                                      : Colors.blue.withOpacity(0.3),
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
                                          ? Colors.white.withOpacity(0.8)
                                          : Colors.blue.withOpacity(0.7),
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
                            color: Colors.blue.withOpacity(0.8),
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
                items: _actions.map((cat) {
                  return DropdownMenuItem(
                    value: cat,
                    child: Text(cat, style: const TextStyle(fontFamily: 'Manrope')),
                  );
                }).toList(),
                onChanged: (value) => setState(() => _action = value),
                validator: (value) => value == null ? 'Select category' : null,
              ),
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
              ElevatedButton(
                onPressed: _submitExpense,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFFFD25F),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text(
                  'Save Expense',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 16,
                    fontWeight: FontWeight.bold,
                  ),
                ),
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
