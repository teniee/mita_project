import 'package:flutter/material.dart';
import '../theme/app_colors.dart';
import '../theme/app_typography.dart';
import 'package:intl/intl.dart';
import 'package:provider/provider.dart';
import '../providers/challenges_provider.dart';

class ChallengesScreen extends StatefulWidget {
  const ChallengesScreen({super.key});

  @override
  State<ChallengesScreen> createState() => _ChallengesScreenState();
}

class _ChallengesScreenState extends State<ChallengesScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);

    // Initialize ChallengesProvider for centralized state management
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final challengesProvider = context.read<ChallengesProvider>();
      if (challengesProvider.state == ChallengesState.initial) {
        challengesProvider.initialize();
      }
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _joinChallenge(String challengeId) async {
    final challengesProvider = context.read<ChallengesProvider>();
    final success = await challengesProvider.joinChallenge(challengeId);

    if (!mounted) return;

    if (success) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Successfully joined challenge!')),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
            content: Text(
                'Failed to join challenge: ${challengesProvider.errorMessage}')),
      );
    }
  }

  Future<void> _leaveChallenge(String challengeId) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Leave Challenge'),
        content: const Text(
            'Are you sure you want to leave this challenge? Your progress will be lost.'),
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
      final challengesProvider = context.read<ChallengesProvider>();
      final success = await challengesProvider.leaveChallenge(challengeId);

      if (!mounted) return;

      if (success) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Successfully left challenge')),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
              content: Text(
                  'Failed to leave challenge: ${challengesProvider.errorMessage}')),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    // Use context.watch for reactive state updates
    final challengesProvider = context.watch<ChallengesProvider>();
    final isLoading = challengesProvider.isLoading ||
        challengesProvider.state == ChallengesState.loading;

    return Scaffold(
      backgroundColor: AppColors.background,
      appBar: AppBar(
        title: const Text(
          'Challenges',
          style: TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
        backgroundColor: AppColors.background,
        elevation: 0,
        iconTheme: const IconThemeData(color: AppColors.textPrimary),
        centerTitle: true,
        bottom: TabBar(
          controller: _tabController,
          labelColor: AppColors.textPrimary,
          unselectedLabelColor: Colors.grey,
          indicatorColor: AppColors.secondary,
          labelStyle: const TextStyle(
            fontFamily: AppTypography.fontBody,
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
      body: isLoading
          ? const Center(child: CircularProgressIndicator())
          : TabBarView(
              controller: _tabController,
              children: [
                _buildActiveChallengesTab(challengesProvider),
                _buildAvailableChallengesTab(challengesProvider),
                _buildStatsTab(challengesProvider),
              ],
            ),
    );
  }

  Widget _buildActiveChallengesTab(ChallengesProvider challengesProvider) {
    final activeChallenges = challengesProvider.activeChallenges;

    return RefreshIndicator(
      onRefresh: () => challengesProvider.refresh(),
      child: activeChallenges.isEmpty
          ? const Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(Icons.emoji_events, size: 64, color: Colors.grey),
                  SizedBox(height: 16),
                  Text(
                    'No active challenges',
                    style: TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Join a challenge to start earning rewards!',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
                      color: Colors.grey,
                    ),
                  ),
                ],
              ),
            )
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: activeChallenges.length,
              itemBuilder: (context, index) {
                final challenge = activeChallenges[index];
                return _buildActiveChallengeCard(challenge);
              },
            ),
    );
  }

  Widget _buildAvailableChallengesTab(ChallengesProvider challengesProvider) {
    final availableChallenges = challengesProvider.availableChallenges;

    return RefreshIndicator(
      onRefresh: () => challengesProvider.refresh(),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: availableChallenges.length,
        itemBuilder: (context, index) {
          final challenge = availableChallenges[index];
          return _buildAvailableChallengeCard(challenge);
        },
      ),
    );
  }

  Widget _buildStatsTab(ChallengesProvider challengesProvider) {
    return RefreshIndicator(
      onRefresh: () => challengesProvider.refresh(),
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildStatsHeader(challengesProvider),
            const SizedBox(height: 24),
            _buildBadgesSection(challengesProvider),
            const SizedBox(height: 24),
            _buildLeaderboardSection(challengesProvider),
          ],
        ),
      ),
    );
  }

  Widget _buildActiveChallengeCard(Map<String, dynamic> challenge) {
    final progress = (challenge['current_progress'] ?? 0).toDouble();
    final target = (challenge['target_value'] ?? 1).toDouble();
    final progressPercentage =
        target > 0 ? (progress / target).clamp(0.0, 1.0) : 0.0;

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
                        fontFamily: AppTypography.fontHeading,
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: AppColors.textPrimary,
                      ),
                    ),
                  ),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                    decoration: BoxDecoration(
                      color: difficultyColor.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      challenge['difficulty']?.toString().toUpperCase() ?? '',
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
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
                  fontFamily: AppTypography.fontBody,
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
                      fontFamily: AppTypography.fontBody,
                      fontSize: 14,
                      fontWeight: FontWeight.w600,
                      color: AppColors.textPrimary,
                    ),
                  ),
                  Text(
                    '${(progressPercentage * 100).toInt()}%',
                    style: TextStyle(
                      fontFamily: AppTypography.fontHeading,
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
                            const Icon(Icons.stars,
                                color: Colors.amber, size: 16),
                            const SizedBox(width: 4),
                            Text(
                              '${challenge['reward_points']} points',
                              style: const TextStyle(
                                fontFamily: AppTypography.fontBody,
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 4),
                        Row(
                          children: [
                            const Icon(Icons.attach_money,
                                color: Colors.green, size: 16),
                            Text(
                              '\$${challenge['reward_amount']} reward',
                              style: const TextStyle(
                                fontFamily: AppTypography.fontBody,
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
                          fontFamily: AppTypography.fontBody,
                          fontSize: 12,
                          fontWeight: FontWeight.w600,
                          color: daysLeft <= 1 ? Colors.red : Colors.grey[600],
                        ),
                      ),
                      const SizedBox(height: 4),
                      Text(
                        'Ends ${DateFormat('MMM d').format(endDate)}',
                        style: TextStyle(
                          fontFamily: AppTypography.fontBody,
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
                      fontFamily: AppTypography.fontBody,
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
                      fontFamily: AppTypography.fontHeading,
                      fontSize: 18,
                      fontWeight: FontWeight.bold,
                      color: AppColors.textPrimary,
                    ),
                  ),
                ),
                Container(
                  padding:
                      const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: difficultyColor.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    challenge['difficulty']?.toString().toUpperCase() ?? '',
                    style: TextStyle(
                      fontFamily: AppTypography.fontBody,
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
                fontFamily: AppTypography.fontBody,
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
                      const Icon(Icons.stars, color: Colors.amber, size: 20),
                      const SizedBox(width: 8),
                      Text(
                        '${challenge['reward_points']} points',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontBody,
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                        ),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      const Icon(Icons.attach_money,
                          color: Colors.green, size: 20),
                      Text(
                        '\$${challenge['reward_amount']}',
                        style: const TextStyle(
                          fontFamily: AppTypography.fontHeading,
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
                  backgroundColor: AppColors.secondary,
                  foregroundColor: AppColors.textPrimary,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                  elevation: 2,
                ),
                child: const Text(
                  'Join Challenge',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
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
        Icon(icon, color: AppColors.textPrimary, size: 20),
        const SizedBox(height: 4),
        Text(
          value,
          style: const TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontSize: 14,
            fontWeight: FontWeight.bold,
            color: AppColors.textPrimary,
          ),
        ),
        Text(
          label,
          style: TextStyle(
            fontFamily: AppTypography.fontBody,
            fontSize: 10,
            color: Colors.grey[600],
          ),
        ),
      ],
    );
  }

  Widget _buildStatsHeader(ChallengesProvider challengesProvider) {
    final currentLevel = challengesProvider.currentLevel;
    final totalPoints = challengesProvider.totalPoints;
    final nextLevelPoints = challengesProvider.nextLevelPoints;
    final pointsToNext = challengesProvider.pointsToNextLevel;
    final levelProgress = nextLevelPoints > 0
        ? (totalPoints / nextLevelPoints).clamp(0.0, 1.0)
        : 0.0;
    final gamificationStats = challengesProvider.gamificationStats;

    return Column(
      children: [
        // Level card
        Card(
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 3,
          child: Container(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: LinearGradient(
                colors: [
                  AppColors.slatePurple,
                  AppColors.slatePurple.withValues(alpha: 0.7)
                ],
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
                            fontFamily: AppTypography.fontBody,
                            color: Colors.white70,
                            fontSize: 14,
                          ),
                        ),
                        Text(
                          'Level $currentLevel',
                          style: const TextStyle(
                            fontFamily: AppTypography.fontHeading,
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
                            fontFamily: AppTypography.fontBody,
                            color: Colors.white70,
                            fontSize: 14,
                          ),
                        ),
                        Text(
                          '$totalPoints',
                          style: const TextStyle(
                            fontFamily: AppTypography.fontHeading,
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
                            fontFamily: AppTypography.fontBody,
                            color: Colors.white70,
                            fontSize: 12,
                          ),
                        ),
                        Text(
                          '$pointsToNext points to go',
                          style: const TextStyle(
                            fontFamily: AppTypography.fontBody,
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
                      valueColor:
                          const AlwaysStoppedAnimation<Color>(Colors.white),
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
                '${gamificationStats['active_challenges'] ?? 0}',
                Icons.emoji_events,
                AppColors.secondary,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildQuickStat(
                'Current Streak',
                '${gamificationStats['current_streak'] ?? 0} days',
                Icons.local_fire_department,
                AppColors.warningDark,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _buildQuickStat(
                'Completed',
                '${gamificationStats['completed_challenges'] ?? 0}',
                Icons.check_circle,
                AppColors.success,
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildQuickStat(
      String label, String value, IconData icon, Color color) {
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
                fontFamily: AppTypography.fontHeading,
                fontSize: 16,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
            ),
            Text(
              label,
              style: TextStyle(
                fontFamily: AppTypography.fontBody,
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

  Widget _buildBadgesSection(ChallengesProvider challengesProvider) {
    final badges = challengesProvider.badgesEarned;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Badges Earned',
          style: TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
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
                    Icon(Icons.military_tech,
                        size: 48, color: Colors.grey[400]),
                    const SizedBox(height: 8),
                    Text(
                      'No badges earned yet',
                      style: TextStyle(
                        fontFamily: AppTypography.fontBody,
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
                fontFamily: AppTypography.fontHeading,
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: AppColors.textPrimary,
              ),
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 4),
            Text(
              badge['rarity']?.toString().toUpperCase() ?? '',
              style: TextStyle(
                fontFamily: AppTypography.fontBody,
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

  Widget _buildLeaderboardSection(ChallengesProvider challengesProvider) {
    final leaderboard = challengesProvider.leaderboard;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Leaderboard',
          style: TextStyle(
            fontFamily: AppTypography.fontHeading,
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppColors.textPrimary,
          ),
        ),
        const SizedBox(height: 12),
        Card(
          shape:
              RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          elevation: 2,
          child: Column(
            children: leaderboard.take(5).map<Widget>((entry) {
              final isCurrentUser = entry['is_current_user'] == true;
              return ListTile(
                leading: CircleAvatar(
                  backgroundColor: _getRankColor(entry['rank']),
                  child: Text(
                    '#${entry['rank']}',
                    style: const TextStyle(
                      fontFamily: AppTypography.fontHeading,
                      fontWeight: FontWeight.bold,
                      color: Colors.white,
                      fontSize: 12,
                    ),
                  ),
                ),
                title: Text(
                  entry['username'] ?? 'User',
                  style: TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight:
                        isCurrentUser ? FontWeight.bold : FontWeight.w600,
                    color: isCurrentUser
                        ? AppColors.secondary
                        : AppColors.textPrimary,
                  ),
                ),
                subtitle: Text(
                  'Level ${entry['level']} • ${entry['challenges_completed']} completed',
                  style: const TextStyle(
                    fontFamily: AppTypography.fontBody,
                    fontSize: 12,
                  ),
                ),
                trailing: Text(
                  '${entry['points']} pts',
                  style: const TextStyle(
                    fontFamily: AppTypography.fontHeading,
                    fontWeight: FontWeight.bold,
                    color: AppColors.textPrimary,
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
        return AppColors.success;
      case 'medium':
        return AppColors.warning;
      case 'hard':
        return AppColors.warningDark;
      default:
        return Colors.grey;
    }
  }

  Color _getRarityColor(String? rarity) {
    switch (rarity?.toLowerCase()) {
      case 'common':
        return Colors.grey;
      case 'rare':
        return AppColors.info;
      case 'epic':
        return AppColors.categoryEntertainment;
      case 'legendary':
        return AppColors.secondary;
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
    if (rank == 1) return AppColors.secondary; // Gold
    if (rank == 2) return Colors.grey.shade400; // Silver
    if (rank == 3) return AppColors.warning; // Bronze
    return AppColors.categoryUtilities; // Default
  }
}
