import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_cropper/image_cropper.dart';
import 'package:image_picker/image_picker.dart';

import '../services/api_service.dart';

class ReceiptCaptureScreen extends StatefulWidget {
  const ReceiptCaptureScreen({Key? key}) : super(key: key);

  @override
  State<ReceiptCaptureScreen> createState() => _ReceiptCaptureScreenState();
}

class _ReceiptCaptureScreenState extends State<ReceiptCaptureScreen> {
  final ApiService _apiService = ApiService();
  XFile? _image;
  bool _loading = false;
  String? _error;
  Map<String, dynamic>? _result;
  final _merchantController = TextEditingController();
  final _totalController = TextEditingController();
  final List<TextEditingController> _itemNameCtrls = [];
  final List<TextEditingController> _itemPriceCtrls = [];

  @override
  void dispose() {
    _merchantController.dispose();
    _totalController.dispose();
    for (final c in _itemNameCtrls) {
      c.dispose();
    }
    for (final c in _itemPriceCtrls) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _pick(ImageSource source) async {
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(source: source);
      if (picked == null) return;
      final cropped = await ImageCropper().cropImage(sourcePath: picked.path);
      if (cropped == null) return;
      setState(() {
        _image = XFile(cropped.path);
        _result = null;
        _error = null;
      });
    } catch (e) {
      setState(() => _error = 'Image error: $e');
    }
  }

  Future<void> _process() async {
    if (_image == null) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final data = await _apiService.uploadReceipt(File(_image!.path));
      if (!mounted) return;
      setState(() {
        _result = data;
        _merchantController.text = data['merchant']?.toString() ?? '';
        _totalController.text = data['total']?.toString() ?? '';
        _itemNameCtrls.clear();
        _itemPriceCtrls.clear();
        final items = List<Map<String, dynamic>>.from(data['items'] ?? []);
        for (final item in items) {
          _itemNameCtrls.add(TextEditingController(text: item['name']?.toString() ?? ''));
          _itemPriceCtrls.add(TextEditingController(text: item['price']?.toString() ?? ''));
        }
      });
    } catch (e) {
      setState(() => _error = 'Failed: $e');
    } finally {
      setState(() => _loading = false);
    }
  }

  Future<void> _submit() async {
    final payload = {
      'category': _result?['category'] ?? 'other',
      'amount': double.tryParse(_totalController.text) ?? 0.0,
      'spent_at': DateTime.now().toIso8601String(),
    };
    try {
      await _apiService.createTransaction(payload);
      if (!mounted) return;
      Navigator.pop(context);
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to save: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Scan Receipt'),
      ),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            if (_image != null) Image.file(File(_image!.path), height: 200),
            const SizedBox(height: 20),
            if (_result != null)
              Expanded(
                child: SingleChildScrollView(
                  child: Column(
                    children: [
                      TextField(
                        controller: _merchantController,
                        decoration: const InputDecoration(labelText: 'Merchant'),
                      ),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _totalController,
                        keyboardType: TextInputType.number,
                        decoration: const InputDecoration(labelText: 'Total'),
                      ),
                      const SizedBox(height: 10),
                      ListView.builder(
                        shrinkWrap: true,
                        physics: const NeverScrollableScrollPhysics(),
                        itemCount: _itemNameCtrls.length,
                        itemBuilder: (context, i) {
                          return Row(
                            children: [
                              Expanded(
                                child: TextField(
                                  controller: _itemNameCtrls[i],
                                  decoration: const InputDecoration(labelText: 'Item'),
                                ),
                              ),
                              const SizedBox(width: 10),
                              SizedBox(
                                width: 80,
                                child: TextField(
                                  controller: _itemPriceCtrls[i],
                                  keyboardType: TextInputType.number,
                                  decoration: const InputDecoration(labelText: 'Price'),
                                ),
                              ),
                            ],
                          );
                        },
                      ),
                      const SizedBox(height: 10),
                      ElevatedButton(
                        onPressed: _submit,
                        child: const Text('Save Transaction'),
                      ),
                    ],
                  ),
                ),
              ),
            if (_error != null)
              Text(_error!, style: const TextStyle(color: Colors.red)),
            const Spacer(),
            if (_loading)
              const CircularProgressIndicator()
            else ...[
              ElevatedButton(
                onPressed: () => _pick(ImageSource.camera),
                child: const Text('Take Photo'),
              ),
              const SizedBox(height: 10),
              ElevatedButton(
                onPressed: () => _pick(ImageSource.gallery),
                child: const Text('Choose from Gallery'),
              ),
              const SizedBox(height: 10),
              ElevatedButton(
                onPressed: _process,
                child: const Text('Process Receipt'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
