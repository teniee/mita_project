#!/usr/bin/env dart

/// Script to replace print() statements with proper logging
/// Usage: dart run scripts/replace_print_statements.dart

import 'dart:io';

void main() async {
  final libDir = Directory('mobile_app/lib');
  
  if (!libDir.existsSync()) {
    print('❌ mobile_app/lib directory not found');
    exit(1);
  }

  print('🔍 Finding Dart files with print statements...');
  
  final dartFiles = <File>[];
  await for (final entity in libDir.list(recursive: true)) {
    if (entity is File && entity.path.endsWith('.dart')) {
      final content = await entity.readAsString();
      if (content.contains('print(')) {
        dartFiles.add(entity);
      }
    }
  }

  print('📝 Found ${dartFiles.length} files with print statements');

  for (final file in dartFiles) {
    print('🔧 Processing ${file.path}...');
    await _replacePrintStatements(file);
  }

  print('✅ Completed replacing print statements with structured logging');
}

Future<void> _replacePrintStatements(File file) async {
  var content = await file.readAsString();
  bool modified = false;

  // Check if logging service is already imported
  if (!content.contains("import 'logging_service.dart'") && 
      !content.contains('import \'logging_service.dart\'')) {
    
    // Find the last import and add logging service import
    final lines = content.split('\n');
    int lastImportIndex = -1;
    
    for (int i = 0; i < lines.length; i++) {
      if (lines[i].startsWith('import ')) {
        lastImportIndex = i;
      }
    }
    
    if (lastImportIndex != -1) {
      // Determine the correct import path
      final depth = file.path.split('/').length - 3; // Adjust for mobile_app/lib
      final importPath = '../' * (depth - 2) + 'services/logging_service.dart';
      lines.insert(lastImportIndex + 1, "import '$importPath';");
      content = lines.join('\n');
      modified = true;
    }
  }

  // Replace common print patterns
  final replacements = [
    // Debug prints
    RegExp(r"print\('🚀 ([^']+)'\);?"),
    RegExp(r"print\('✅ ([^']+)'\);?"),
    RegExp(r"print\('❌ ([^']+)'\);?"),
    RegExp(r"print\('⚠️ ([^']+)'\);?"),
    RegExp(r"print\('📤 ([^']+)'\);?"),
    RegExp(r"print\('📥 ([^']+)'\);?"),
    RegExp(r"print\('🐛 ([^']+)'\);?"),
    
    // General prints
    RegExp(r"print\('([^']+)'\);?"),
    RegExp(r'print\("([^"]+)"\);?'),
    
    // Error prints with variables
    RegExp(r"print\('Error: ([^']+): \$([^']+)'\);?"),
  ];

  // Simple replacements for common patterns
  final simpleReplacements = {
    r"print('DEBUG: ": "logDebug('",
    r"print('INFO: ": "logInfo('",
    r"print('WARNING: ": "logWarning('",
    r"print('ERROR: ": "logError('",
    r"print('🚀 ": "logDebug('",
    r"print('✅ ": "logInfo('",
    r"print('❌ ": "logError('",
    r"print('⚠️ ": "logWarning('",
    r"print('📤 ": "logDebug('",
    r"print('📥 ": "logDebug('",
    r"print('🐛 ": "logDebug('",
  };

  for (final entry in simpleReplacements.entries) {
    if (content.contains(entry.key)) {
      content = content.replaceAll(entry.key, entry.value);
      modified = true;
    }
  }

  // Replace remaining print statements with appropriate log levels
  final printRegex = RegExp(r"print\('([^']+)'\);?");
  content = content.replaceAllMapped(printRegex, (match) {
    final message = match.group(1) ?? '';
    
    // Determine log level based on content
    if (message.toLowerCase().contains('error') || message.startsWith('❌') || message.startsWith('🚨')) {
      return "logError('$message');";
    } else if (message.toLowerCase().contains('warning') || message.startsWith('⚠️')) {
      return "logWarning('$message');";
    } else if (message.toLowerCase().contains('debug') || message.startsWith('🐛')) {
      return "logDebug('$message');";
    } else {
      return "logInfo('$message');";
    }
  });

  // Handle print with double quotes
  final printDoubleQuoteRegex = RegExp(r'print\("([^"]+)"\);?');
  content = content.replaceAllMapped(printDoubleQuoteRegex, (match) {
    final message = match.group(1) ?? '';
    return "logInfo('$message');";
  });

  if (modified || content != await file.readAsString()) {
    await file.writeAsString(content);
    print('  ✓ Updated ${file.path}');
  }
}