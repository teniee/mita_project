import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/api_service.dart';

class ChallengesScreen extends StatefulWidget {
  const ChallengesScreen({Key? key}) : super(key: key);

  @override
  State<ChallengesScreen> createState() => _ChallengesScreenState();
}

class _ChallengesScreenState extends State<ChallengesScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  late TabController _tabController;
  
  bool _isLoading = true;
  List<dynamic> _activeChallenges = [];
  List<dynamic> _availableChallenges = [];
  Map<String, dynamic> _gamificationStats = {};
  List<dynamic> _leaderboard = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadChallengeData();
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadChallengeData() async {
    setState(() => _isLoading = true);
    
    try {
      final results = await Future.wait([
        _apiService.getChallenges(),
        _apiService.getAvailableChallenges(),
        _apiService.getGameificationStats(),
        _apiService.getLeaderboard(),
      ]);

      if (!mounted) return;
      setState(() {
        _activeChallenges = results[0] as List<dynamic>;
        _availableChallenges = results[1] as List<dynamic>;
        _gamificationStats = results[2] as Map<String, dynamic>;
        _leaderboard = results[3] as List<dynamic>;
        _isLoading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() => _isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to load challenges: $e')),
      );
    }
  }

  Future<void> _joinChallenge(String challengeId) async {
    try {
      await _apiService.joinChallenge(challengeId);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Successfully joined challenge!')),
      );
      _loadChallengeData(); // Refresh data
    } catch (e) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to join challenge: $e')),
      );
    }
  }

  Future<void> _leaveChallenge(String challengeId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Leave Challenge'),
        content: const Text('Are you sure you want to leave this challenge? Your progress will be lost.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Leave'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      try {
        await _apiService.leaveChallenge(challengeId);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Successfully left challenge')),
        );
        _loadChallengeData(); // Refresh data
      } catch (e) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Failed to leave challenge: $e')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      appBar: AppBar(
        title: const Text(
          'Challenges',
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
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF193C57),
          unselectedLabelColor: Colors.grey,
          indicatorColor: const Color(0xFFFFD25F),
          labelStyle: const TextStyle(
            fontFamily: 'Manrope',
            fontWeight: FontWeight.w600,
            fontSize: 12,
          ),
          tabs: const [
            Tab(text: 'Active'),
            Tab(text: 'Available'),
            Tab(text: 'Stats'),
          ],
        ),
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildActiveChallengesTab(),
                _buildAvailableChallengesTab(),
                _buildStatsTab(),
              ],
            ),
    );
  }

  Widget _buildActiveChallengesTab() {
    return RefreshIndicator(
      onRefresh: _loadChallengeData,
      child: _activeChallenges.isEmpty
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.emoji_events, size: 64, color: Colors.grey),
                  SizedBox(height: 16),
                  Text(
                    'No active challenges',
                    style: TextStyle(
                      fontFamily: 'Sora',
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF193C57),
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Join a challenge to start earning rewards!',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      color: Colors.grey,
                    ),
                  ),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _activeChallenges.length,
              itemBuilder: (context, index) {
                final challenge = _activeChallenges[index];
                return _buildActiveChallengeCard(challenge);
              },
            ),
    );
  }

  Widget _buildAvailableChallengesTab() {
    return RefreshIndicator(
      onRefresh: _loadChallengeData,
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _availableChallenges.length,
        itemBuilder: (context, index) {
          final challenge = _availableChallenges[index];
          return _buildAvailableChallengeCard(challenge);
        },
      ),
    );
  }

  Widget _buildStatsTab() {
    return RefreshIndicator(
      onRefresh: _loadChallengeData,
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildStatsHeader(),
            const SizedBox(height: 24),
            _buildBadgesSection(),
            const SizedBox(height: 24),
            _buildLeaderboardSection(),
          ],
        ),
      ),
    );
  }

  Widget _buildActiveChallengeCard(Map<String, dynamic> challenge) {
    final progress = (challenge['current_progress'] ?? 0).toDouble();
    final target = (challenge['target_value'] ?? 1).toDouble();
    final progressPercentage = target > 0 ? (progress / target).clamp(0.0, 1.0) : 0.0;
    
    final startDate = DateTime.parse(challenge['start_date']);
    final endDate = DateTime.parse(challenge['end_date']);
    final daysLeft = endDate.difference(DateTime.now()).inDays;
    
    Color difficultyColor = _getDifficultyColor(challenge['difficulty']);
    
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 3,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: LinearGradient(
            colors: [
              difficultyColor.withValues(alpha: 0.05),
              difficultyColor.withValues(alpha: 0.02),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Expanded(
                    child: Text(
                      challenge['title'] ?? '',
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Color(0xFF193C57),
                      ),
                    ),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: difficultyColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      challenge['difficulty']?.toString().toUpperCase() ?? '',
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        fontSize: 10,
                        fontWeight: FontWeight.w600,
                        color: difficultyColor,
                      ),
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 8),
              
              Text(
                challenge['description'] ?? '',
                style: TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 14,
                  color: Colors.grey[600],
                ),
              ),
              
              const SizedBox(height: 16),
              
              // Progress
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(
                    'Progress: ${progress.toInt()}/${target.toInt()}',
                    style: const TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF193C57),
                    ),
                  ),
                  Text(
                    '${(progressPercentage * 100).toInt()}%',
                    style: TextStyle(
                      fontFamily: 'Sora',
                      fontSize: 14,
                      fontWeight: FontWeight.bold,
                      color: difficultyColor,
                    ),
                  ),
                ],
              ),
              
              const SizedBox(height: 8),
              
              LinearProgressIndicator(
                value: progressPercentage,
                backgroundColor: Colors.grey[200],
                valueColor: AlwaysStoppedAnimation<Color>(difficultyColor),
                minHeight: 6,
              ),
              
              const SizedBox(height: 16),
              
              // Rewards and time
              Row(
                children: [
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(Icons.stars, color: Colors.amber, size: 16),
                            const SizedBox(width: 4),
                            Text(
                              '${challenge['reward_points']} points',
                              style: const TextStyle(
                                fontFamily: 'Manrope',
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            Icon(Icons.attach_money, color: Colors.green, size: 16),
                            Text(
                              '\$${challenge['reward_amount']} reward',
                              style: const TextStyle(
                                fontFamily: 'Manrope',
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Text(
                        daysLeft > 0 ? '$daysLeft days left' : 'Ending today',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: daysLeft <= 1 ? Colors.red : Colors.grey[600],
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Ends ${DateFormat('MMM d').format(endDate)}',
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 10,
                          color: Colors.grey[500],
                        ),
                      ),
                    ],
                  ),
                ],
              ),
              
              const SizedBox(height: 16),
              
              // Action button
              SizedBox(
                width: double.infinity,
                height: 40,
                child: OutlinedButton(
                  onPressed: () => _leaveChallenge(challenge['id']),
                  style: OutlinedButton.styleFrom(
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                    ),
                    side: BorderSide(color: Colors.red[300]!),
                  ),
                  child: Text(
                    'Leave Challenge',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontWeight: FontWeight.w600,
                      color: Colors.red[400],
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildAvailableChallengeCard(Map<String, dynamic> challenge) {
    Color difficultyColor = _getDifficultyColor(challenge['difficulty']);
    final successRate = (challenge['success_rate'] ?? 0.0) * 100;
    
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Text(
                    challenge['title'] ?? '',
                    style: const TextStyle(
                      fontFamily: 'Sora',
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: Color(0xFF193C57),
                    ),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: difficultyColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    challenge['difficulty']?.toString().toUpperCase() ?? '',
                    style: TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: difficultyColor,
                    ),
                  ),
                ),
              ],
            ),
            
            const SizedBox(height: 8),
            
            Text(
              challenge['description'] ?? '',
              style: TextStyle(
                fontFamily: 'Manrope',
                fontSize: 14,
                color: Colors.grey[600],
              ),
            ),
            
            const SizedBox(height: 16),
            
            // Stats
            Row(
              children: [
                Expanded(
                  child: _buildStatItem(
                    'Duration',
                    '${challenge['duration_days']} days',
                    Icons.schedule,
                  ),
                ),
                Expanded(
                  child: _buildStatItem(
                    'Participants',
                    '${challenge['participants']}',
                    Icons.people,
                  ),
                ),
                Expanded(
                  child: _buildStatItem(
                    'Success Rate',
                    '${successRate.toInt()}%',
                    Icons.trending_up,
                  ),
                ),
              ],
            ),
            
            const SizedBox(height: 16),
            
            // Rewards
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.green[50],
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.green[200]!),
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Row(
                    children: [
                      Icon(Icons.stars, color: Colors.amber, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        '${challenge['reward_points']} points',
                        style: const TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      Icon(Icons.attach_money, color: Colors.green, size: 20),
                      Text(
                        '\$${challenge['reward_amount']}',
                        style: const TextStyle(
                          fontFamily: 'Sora',
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                          color: Colors.green,
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            
            const SizedBox(height: 16),
            
            // Join button
            SizedBox(
              width: double.infinity,
              height: 48,
              child: ElevatedButton(
                onPressed: () => _joinChallenge(challenge['id']),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFFFD25F),
                  foregroundColor: const Color(0xFF193C57),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 2,
                ),
                child: const Text(
                  'Join Challenge',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.bold,
                    fontSize: 16,
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatItem(String label, String value, IconData icon) {
    return Column(
      children: [
        Icon(icon, color: const Color(0xFF193C57), size: 20),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            fontFamily: 'Sora',
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: Color(0xFF193C57),
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontFamily: 'Manrope',
            fontSize: 10,
            color: Colors.grey[600],
          ),
        ),
      ],
    );
  }

  Widget _buildStatsHeader() {
    final currentLevel = _gamificationStats['current_level'] ?? 1;
    final totalPoints = _gamificationStats['total_points'] ?? 0;
    final nextLevelPoints = _gamificationStats['next_level_points'] ?? 100;
    final pointsToNext = _gamificationStats['points_to_next_level'] ?? 100;
    final levelProgress = nextLevelPoints > 0 ? (totalPoints / nextLevelPoints).clamp(0.0, 1.0) : 0.0;
    
    return Column(
      children: [
        // Level card
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 3,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: const LinearGradient(
                colors: [Color(0xFF6A5ACD), Color(0xFF9370DB)],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            padding: const EdgeInsets.all(20),
            child: Column(
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Current Level',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            color: Colors.white70,
                            fontSize: 14,
                          ),
                        ),
                        Text(
                          'Level $currentLevel',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            color: Colors.white,
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                    Column(
                      crossAxisAlignment: CrossAxisAlignment.end,
                      children: [
                        const Text(
                          'Total Points',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            color: Colors.white70,
                            fontSize: 14,
                          ),
                        ),
                        Text(
                          '$totalPoints',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            color: Colors.white,
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
                
                const SizedBox(height: 16),
                
                // Progress to next level
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        const Text(
                          'Progress to Next Level',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            color: Colors.white70,
                            fontSize: 12,
                          ),
                        ),
                        Text(
                          '$pointsToNext points to go',
                          style: const TextStyle(
                            fontFamily: 'Manrope',
                            color: Colors.white70,
                            fontSize: 12,
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    LinearProgressIndicator(
                      value: levelProgress,
                      backgroundColor: Colors.white24,
                      valueColor: const AlwaysStoppedAnimation<Color>(Colors.white),
                      minHeight: 6,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        
        const SizedBox(height: 16),
        
        // Quick stats
        Row(
          children: [
            Expanded(
              child: _buildQuickStat(
                'Active Challenges',
                '${_gamificationStats['active_challenges'] ?? 0}',
                Icons.emoji_events,
                const Color(0xFFFFD25F),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildQuickStat(
                'Current Streak',
                '${_gamificationStats['current_streak'] ?? 0} days',
                Icons.local_fire_department,
                const Color(0xFFFF5722),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildQuickStat(
                'Completed',
                '${_gamificationStats['completed_challenges'] ?? 0}',
                Icons.check_circle,
                const Color(0xFF4CAF50),
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildQuickStat(String label, String value, IconData icon, Color color) {
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          children: [
            Icon(icon, color: color, size: 24),
            const SizedBox(height: 8),
            Text(
              value,
              style: const TextStyle(
                fontFamily: 'Sora',
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: Color(0xFF193C57),
              ),
            ),
            Text(
              label,
              style: TextStyle(
                fontFamily: 'Manrope',
                fontSize: 10,
                color: Colors.grey[600],
              ),
              textAlign: TextAlign.center,
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBadgesSection() {
    final badges = _gamificationStats['badges_earned'] as List<dynamic>? ?? [];
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Badges Earned',
          style: TextStyle(
            fontFamily: 'Sora',
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: Color(0xFF193C57),
          ),
        ),
        const SizedBox(height: 12),
        
        if (badges.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Center(
                child: Column(
                  children: [
                    Icon(Icons.military_tech, size: 48, color: Colors.grey[400]),
                    const SizedBox(height: 8),
                    Text(
                      'No badges earned yet',
                      style: TextStyle(
                        fontFamily: 'Manrope',
                        color: Colors.grey[600],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          )
        else
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 2,
              crossAxisSpacing: 12,
              mainAxisSpacing: 12,
              childAspectRatio: 1.5,
            ),
            itemCount: badges.length,
            itemBuilder: (context, index) {
              final badge = badges[index];
              return _buildBadgeCard(badge);
            },
          ),
      ],
    );
  }

  Widget _buildBadgeCard(Map<String, dynamic> badge) {
    Color rarityColor = _getRarityColor(badge['rarity']);
    IconData badgeIcon = _getBadgeIcon(badge['icon']);
    
    return Card(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      elevation: 2,
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          gradient: LinearGradient(
            colors: [
              rarityColor.withValues(alpha: 0.1),
              rarityColor.withValues(alpha: 0.05),
            ],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        padding: const EdgeInsets.all(12),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(badgeIcon, color: rarityColor, size: 32),
            const SizedBox(height: 8),
            Text(
              badge['name'] ?? '',
              style: const TextStyle(
                fontFamily: 'Sora',
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: Color(0xFF193C57),
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            Text(
              badge['rarity']?.toString().toUpperCase() ?? '',
              style: TextStyle(
                fontFamily: 'Manrope',
                fontSize: 10,
                fontWeight: FontWeight.w600,
                color: rarityColor,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLeaderboardSection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Leaderboard',
          style: TextStyle(
            fontFamily: 'Sora',
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: Color(0xFF193C57),
          ),
        ),
        const SizedBox(height: 12),
        
        Card(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          elevation: 2,
          child: Column(
            children: _leaderboard.take(5).map<Widget>((entry) {
              final isCurrentUser = entry['is_current_user'] == true;
              return ListTile(
                leading: CircleAvatar(
                  backgroundColor: _getRankColor(entry['rank']),
                  child: Text(
                    '#${entry['rank']}',
                    style: const TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                      fontSize: 12,
                    ),
                  ),
                ),
                title: Text(
                  entry['username'] ?? 'User',
                  style: TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: isCurrentUser ? FontWeight.bold : FontWeight.w600,
                    color: isCurrentUser ? const Color(0xFFFFD25F) : const Color(0xFF193C57),
                  ),
                ),
                subtitle: Text(
                  'Level ${entry['level']} • ${entry['challenges_completed']} completed',
                  style: const TextStyle(
                    fontFamily: 'Manrope',
                    fontSize: 12,
                  ),
                ),
                trailing: Text(
                  '${entry['points']} pts',
                  style: const TextStyle(
                    fontFamily: 'Sora',
                    fontWeight: FontWeight.bold,
                    color: Color(0xFF193C57),
                  ),
                ),
              );
            }).toList(),
          ),
        ),
      ],
    );
  }

  Color _getDifficultyColor(String? difficulty) {
    switch (difficulty?.toLowerCase()) {
      case 'easy':
        return const Color(0xFF4CAF50);
      case 'medium':
        return const Color(0xFFFF9800);
      case 'hard':
        return const Color(0xFFFF5722);
      default:
        return Colors.grey;
    }
  }

  Color _getRarityColor(String? rarity) {
    switch (rarity?.toLowerCase()) {
      case 'common':
        return Colors.grey;
      case 'rare':
        return const Color(0xFF2196F3);
      case 'epic':
        return const Color(0xFF9C27B0);
      case 'legendary':
        return const Color(0xFFFFD700);
      default:
        return Colors.grey;
    }
  }

  IconData _getBadgeIcon(String? icon) {
    switch (icon?.toLowerCase()) {
      case 'coffee':
        return Icons.coffee;
      case 'trophy':
        return Icons.emoji_events;
      case 'star':
        return Icons.star;
      case 'fire':
        return Icons.local_fire_department;
      default:
        return Icons.military_tech;
    }
  }

  Color _getRankColor(int rank) {
    if (rank == 1) return const Color(0xFFFFD700); // Gold
    if (rank == 2) return const Color(0xFFC0C0C0); // Silver
    if (rank == 3) return const Color(0xFFCD7F32); // Bronze
    return const Color(0xFF607D8B); // Default
  }
}