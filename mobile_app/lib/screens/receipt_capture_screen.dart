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
      });
    } catch (e) {
      setState(() => _error = 'Failed: $e');
    } finally {
      setState(() => _loading = false);
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
                  child: Text(_result.toString()),
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
