import 'package:flutter/material.dart';

class LoadingService {
  LoadingService._();
  static final LoadingService instance = LoadingService._();

  final ValueNotifier<int> _counter = ValueNotifier<int>(0);

  ValueNotifier<int> get notifier => _counter;

  void start() => _counter.value++;
  void stop() {
    if (_counter.value > 0) _counter.value--;
  }
}
