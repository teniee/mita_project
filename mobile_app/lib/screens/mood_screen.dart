import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/reminder_service.dart';

class MoodScreen extends StatefulWidget {
  const MoodScreen({Key? key}) : super(key: key);

  @override
  State<MoodScreen> createState() => _MoodScreenState();
}

class _MoodScreenState extends State<MoodScreen> with TickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  double _mood = 3;
  bool _hasSubmittedToday = false;
  late AnimationController _animationController;
  late Animation<double> _scaleAnimation;

  final Map<int, Map<String, dynamic>> _moodData = {
    1: {
      'emoji': '😢',
      'label': 'Very Sad',
      'color': Colors.red.shade400,
      'description': 'Having a tough day',
      'tips': [
        'Take some deep breaths',
        'Consider talking to someone',
        'Remember that tough times pass',
      ],
    },
    2: {
      'emoji': '😔',
      'label': 'Sad',
      'color': Colors.orange.shade400,
      'description': 'Feeling down today',
      'tips': [
        'Try some light exercise',
        'Listen to uplifting music',
        'Focus on small positive moments',
      ],
    },
    3: {
      'emoji': '😐',
      'label': 'Neutral',
      'color': Colors.grey.shade400,
      'description': 'Feeling okay',
      'tips': [
        'This is a good starting point',
        'Consider what might lift your mood',
        'Practice gratitude for small things',
      ],
    },
    4: {
      'emoji': '😊',
      'label': 'Happy',
      'color': Colors.green.shade400,
      'description': 'Having a good day',
      'tips': [
        'Great to hear you\'re doing well!',
        'Share your positivity with others',
        'Remember what\'s making you feel good',
      ],
    },
    5: {
      'emoji': '😄',
      'label': 'Very Happy',
      'color': Colors.blue.shade400,
      'description': 'Feeling fantastic!',
      'tips': [
        'Wonderful! You\'re radiating positivity',
        'Consider what led to this great mood',
        'Spread the joy to those around you',
      ],
    },
  };

  @override
  void initState() {
    super.initState();
    ReminderService.scheduleDailyReminder();
    _animationController = AnimationController(
      duration: const Duration(milliseconds: 300),
      vsync: this,
    );
    _scaleAnimation = Tween<double>(
      begin: 1.0,
      end: 1.2,
    ).animate(CurvedAnimation(
      parent: _animationController,
      curve: Curves.easeInOut,
    ));
  }

  @override
  void dispose() {
    _animationController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    try {
      await _apiService.logMood(_mood.round());
      if (!mounted) return;
      
      _animationController.forward().then((_) {
        _animationController.reverse();
      });
      
      setState(() {
        _hasSubmittedToday = true;
      });
      
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Row(
            children: [
              const Icon(Icons.check_circle, color: Colors.white),
              const SizedBox(width: 8),
              Text('Mood saved! ${_moodData[_mood.round()]!['emoji']}'),
            ],
          ),
          backgroundColor: Colors.green,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Failed to save mood: $e'),
          backgroundColor: Colors.red,
          behavior: SnackBarBehavior.floating,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
        ),
      );
    }
  }

  Widget _buildMoodSelector() {
    return Card(
      elevation: 4,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            const Text(
              'How are you feeling today?',
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 20,
                fontWeight: FontWeight.bold,
                color: Color(0xFF193C57),
              ),
            ),
            const SizedBox(height: 24),
            
            // Emoji display
            AnimatedBuilder(
              animation: _scaleAnimation,
              builder: (context, child) {
                return Transform.scale(
                  scale: _scaleAnimation.value,
                  child: Text(
                    _moodData[_mood.round()]!['emoji'],
                    style: const TextStyle(fontSize: 80),
                  ),
                );
              },
            ),
            
            const SizedBox(height: 16),
            
            // Mood label and description
            Text(
              _moodData[_mood.round()]!['label'],
              style: TextStyle(
                fontFamily: 'Sora',
                fontSize: 24,
                fontWeight: FontWeight.bold,
                color: _moodData[_mood.round()]!['color'],
              ),
            ),
            const SizedBox(height: 8),
            Text(
              _moodData[_mood.round()]!['description'],
              style: const TextStyle(
                fontFamily: 'Manrope',
                fontSize: 16,
                color: Colors.grey,
              ),
            ),
            
            const SizedBox(height: 32),
            
            // Mood slider
            SliderTheme(
              data: SliderTheme.of(context).copyWith(
                activeTrackColor: _moodData[_mood.round()]!['color'],
                thumbColor: _moodData[_mood.round()]!['color'],
                overlayColor: _moodData[_mood.round()]!['color'].withValues(alpha: 0.2),
                trackHeight: 8.0,
                thumbShape: const RoundSliderThumbShape(enabledThumbRadius: 12.0),
              ),
              child: Slider(
                value: _mood,
                min: 1,
                max: 5,
                divisions: 4,
                onChanged: (value) {
                  setState(() {
                    _mood = value;
                  });
                },
              ),
            ),
            
            // Mood scale labels
            const Padding(
              padding: EdgeInsets.symmetric(horizontal: 16),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text('😢', style: TextStyle(fontSize: 20)),
                  Text('😔', style: TextStyle(fontSize: 20)),
                  Text('😐', style: TextStyle(fontSize: 20)),
                  Text('😊', style: TextStyle(fontSize: 20)),
                  Text('😄', style: TextStyle(fontSize: 20)),
                ],
              ),
            ),
            
            const SizedBox(height: 32),
            
            // Submit button
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: _hasSubmittedToday ? null : _submit,
                style: ElevatedButton.styleFrom(
                  backgroundColor: _hasSubmittedToday ? Colors.grey : const Color(0xFFFFD25F),
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 4,
                ),
                child: Text(
                  _hasSubmittedToday ? 'Mood Saved for Today' : 'Save My Mood',
                  style: const TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ),
            ),
            
            if (_hasSubmittedToday) ...[
              const SizedBox(height: 16),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.green.shade50,
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: Colors.green.shade200),
                ),
                child: Row(
                  children: [
                    Icon(Icons.check_circle, color: Colors.green.shade600, size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Thanks for sharing! Your mood has been recorded.',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 14,
                          color: Colors.green.shade700,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildTipsCard() {
    final currentMoodData = _moodData[_mood.round()]!;
    final tips = currentMoodData['tips'] as List<String>;
    
    return Card(
      elevation: 2,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  Icons.lightbulb_outline,
                  color: currentMoodData['color'],
                  size: 24,
                ),
                const SizedBox(width: 8),
                const Text(
                  'Mood Tips',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF193C57),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 16),
            ...tips.map((tip) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    width: 6,
                    height: 6,
                    margin: const EdgeInsets.only(top: 8),
                    decoration: BoxDecoration(
                      color: currentMoodData['color'],
                      shape: BoxShape.circle,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      tip,
                      style: const TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 14,
                        height: 1.4,
                      ),
                    ),
                  ),
                ],
              ),
            )),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Daily Mood Check-in',
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
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Main mood selector card
            _buildMoodSelector(),
            const SizedBox(height: 20),
            
            // Tips card based on selected mood
            _buildTipsCard(),
            const SizedBox(height: 20),
            
            // Weekly mood tracking placeholder
            Card(
              elevation: 2,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(
                          Icons.trending_up,
                          color: Color(0xFF193C57),
                          size: 24,
                        ),
                        const SizedBox(width: 8),
                        const Text(
                          'Mood Trends',
                          style: TextStyle(
                            fontFamily: 'Sora',
                            fontSize: 18,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF193C57),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      'Track your mood daily to see patterns and trends over time. This can help you identify what affects your wellbeing.',
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 14,
                        color: Colors.grey,
                        height: 1.4,
                      ),
                    ),
                    const SizedBox(height: 16),
                    
                    // Sample mood history
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                      children: [
                        _buildMoodHistoryItem('Mon', '😊', Colors.green.shade400),
                        _buildMoodHistoryItem('Tue', '😐', Colors.grey.shade400),
                        _buildMoodHistoryItem('Wed', '😔', Colors.orange.shade400),
                        _buildMoodHistoryItem('Thu', '😊', Colors.green.shade400),
                        _buildMoodHistoryItem('Fri', '😄', Colors.blue.shade400),
                        _buildMoodHistoryItem('Sat', '😊', Colors.green.shade400),
                        _buildMoodHistoryItem('Today', '?', Colors.grey.shade300),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMoodHistoryItem(String day, String emoji, Color color) {
    return Column(
      children: [
        Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.2),
            shape: BoxShape.circle,
            border: Border.all(color: color, width: 2),
          ),
          child: Center(
            child: Text(
              emoji,
              style: const TextStyle(fontSize: 20),
            ),
          ),
        ),
        const SizedBox(height: 8),
        Text(
          day,
          style: const TextStyle(
            fontFamily: 'Manrope',
            fontSize: 12,
            fontWeight: FontWeight.w500,
          ),
        ),
      ],
    );
  }
}
