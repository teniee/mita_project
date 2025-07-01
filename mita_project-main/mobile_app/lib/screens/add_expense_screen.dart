import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/offline_queue_service.dart';
import 'receipt_capture_screen.dart';

class AddExpenseScreen extends StatefulWidget {
  const AddExpenseScreen({Key? key}) : super(key: key);

  @override
  State<AddExpenseScreen> createState() => _AddExpenseScreenState();
}

class _AddExpenseScreenState extends State<AddExpenseScreen> {
  final _formKey = GlobalKey<FormState>();
  final OfflineQueueService _queue = OfflineQueueService.instance;

  double? _amount;
  String? _action;
  DateTime _selectedDate = DateTime.now();

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

  Future<void> _submitExpense() async {
    if (!_formKey.currentState!.validate() || _action == null) return;
    _formKey.currentState!.save();

    final data = {
      'amount': _amount,
      'action': _action,
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
              ),
              const SizedBox(height: 20),
              DropdownButtonFormField<String>(
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
