import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../providers/advice_provider.dart';

class AdviceHistoryScreen extends StatefulWidget {
  const AdviceHistoryScreen({super.key});

  @override
  State<AdviceHistoryScreen> createState() => _AdviceHistoryScreenState();
}

class _AdviceHistoryScreenState extends State<AdviceHistoryScreen> {
  @override
  void initState() {
    super.initState();
    // Initialize the advice provider
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<AdviceProvider>().initialize();
    });
  }

  @override
  Widget build(BuildContext context) {
    // Use context.watch for reactive state updates
    final adviceProvider = context.watch<AdviceProvider>();
    final isLoading =
        adviceProvider.isLoading || adviceProvider.state == AdviceState.initial;
    final items = adviceProvider.adviceHistory;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Advice History'),
        backgroundColor: AppColors.background,
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        centerTitle: true,
        elevation: 0,
      ),
      backgroundColor: AppColors.background,
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : items.isEmpty
              ? const Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.history, size: 64, color: Colors.grey),
                      SizedBox(height: 16),
                      Text(
                        'No advice history yet',
                        style: TextStyle(
                          fontSize: 18,
                          color: Colors.grey,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                      SizedBox(height: 8),
                      Text(
                        'Your advice history will appear here',
                        style: TextStyle(color: Colors.grey),
                      ),
                    ],
                  ),
                )
              : ListView.builder(
                  itemCount: items.length,
                  itemBuilder: (_, i) {
                    final item = items[i] as Map<String, dynamic>;
                    final rawDate = item['date'] as String?;
                    final dateLabel = rawDate != null
                        ? (() {
                            try {
                              return DateFormat.yMMMd()
                                  .format(DateTime.parse(rawDate));
                            } catch (_) {
                              return rawDate;
                            }
                          })()
                        : '';
                    final text = item['text'] as String? ?? '';
                    return ListTile(
                      title: Text(text),
                      subtitle: Text(dateLabel),
                    );
                  },
                ),
    );
  }
}
