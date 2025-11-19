import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../providers/transaction_provider.dart';
import '../models/transaction_model.dart';

class EditExpenseScreen extends StatefulWidget {
  final Map<String, dynamic> expense;

  const EditExpenseScreen({super.key, required this.expense});

  @override
  State<EditExpenseScreen> createState() => _EditExpenseScreenState();
}

class _EditExpenseScreenState extends State<EditExpenseScreen> {
  final _formKey = GlobalKey<FormState>();

  late double _amount;
  late String _action;
  late DateTime _selectedDate;

  final List<String> _actions = [
    'Food', 'Transport', 'Entertainment', 'Health',
    'Shopping', 'Utilities', 'Education', 'Other',
  ];

  @override
  void initState() {
    super.initState();
    _amount = widget.expense['amount']?.toDouble() ?? 0.0;
    _action = widget.expense['action'] ?? _actions.first;
    _selectedDate = DateTime.parse(widget.expense['date']);
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    _formKey.currentState!.save();

    final transactionProvider = Provider.of<TransactionProvider>(context, listen: false);

    final input = TransactionInput(
      amount: _amount,
      category: _action,
      spentAt: _selectedDate,
    );

    final result = await transactionProvider.updateTransaction(
      widget.expense['id'],
      input,
    );

    if (!mounted) return;

    if (result != null) {
      Navigator.pop(context, true);
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(transactionProvider.errorMessage ?? 'Failed to update expense')),
      );
    }
  }

  Future<void> _delete() async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('Delete Expense'),
        content: const Text('Are you sure you want to delete this expense?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('Delete')),
        ],
      ),
    );

    if (confirm == true) {
      final transactionProvider = Provider.of<TransactionProvider>(context, listen: false);
      final success = await transactionProvider.deleteTransaction(widget.expense['id']);

      if (!mounted) return;

      if (success) {
        Navigator.pop(context, true);
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(transactionProvider.errorMessage ?? 'Failed to delete expense')),
        );
      }
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
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: Text(
          'Edit Expense',
          style: AppTypography.heading3,
        ),
        backgroundColor: AppColors.background,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        centerTitle: true,
        actions: [
          IconButton(
            icon: const Icon(Icons.delete),
            onPressed: _delete,
          )
        ],
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Form(
          key: _formKey,
          child: ListView(
            children: [
              TextFormField(
                initialValue: _amount.toString(),
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(
                  labelText: 'Amount',
                  prefixIcon: Icon(Icons.attach_money),
                ),
                style: AppTypography.bodyLarge,
                validator: (value) => value == null || value.isEmpty ? 'Enter amount' : null,
                onSaved: (value) => _amount = double.tryParse(value ?? '') ?? 0.0,
              ),
              const SizedBox(height: 20),
              DropdownButtonFormField<String>(
                value: _action,
                decoration: const InputDecoration(
                  labelText: 'Category',
                  prefixIcon: Icon(Icons.category),
                ),
                items: _actions.map((cat) {
                  return DropdownMenuItem(
                    value: cat,
                    child: Text(cat, style: AppTypography.bodyLarge),
                  );
                }).toList(),
                onChanged: (value) => setState(() => _action = value!),
                validator: (value) => value == null ? 'Select category' : null,
              ),
              const SizedBox(height: 20),
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('Date', style: AppTypography.bodyLargeMedium),
                subtitle: Text(DateFormat.yMMMd().format(_selectedDate),
                    style: AppTypography.bodyMedium),
                trailing: IconButton(
                  icon: const Icon(Icons.calendar_today),
                  onPressed: _pickDate,
                ),
              ),
              const SizedBox(height: 30),
              ElevatedButton(
                onPressed: _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppColors.secondary,
                  foregroundColor: AppColors.textPrimary,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: Text(
                  'Save Changes',
                  style: AppTypography.button,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
