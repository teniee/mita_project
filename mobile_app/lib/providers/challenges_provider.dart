import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';

/// State enum for challenges management
enum ChallengesState {
  initial,
  loading,
  loaded,
  error,
}

/// Centralized challenges state management provider
/// Manages challenges list, gamification stats, leaderboard, and CRUD operations
class ChallengesProvider extends ChangeNotifier {
  final ApiService _apiService = ApiService();

  // State
  ChallengesState _state = ChallengesState.initial;
  List<dynamic> _activeChallenges = [];
  List<dynamic> _availableChallenges = [];
  Map<String, dynamic> _gamificationStats = {};
  List<dynamic> _leaderboard = [];
  Map<String, Map<String, dynamic>> _challengeProgress = {};
  String? _errorMessage;
  bool _isLoading = false;

  // Getters
  ChallengesState get state => _state;
  List<dynamic> get activeChallenges => _activeChallenges;
  List<dynamic> get availableChallenges => _availableChallenges;
  Map<String, dynamic> get gamificationStats => _gamificationStats;
  List<dynamic> get leaderboard => _leaderboard;
  Map<String, Map<String, dynamic>> get challengeProgress => _challengeProgress;
  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;

  // Stats convenience getters
  int get currentLevel => _gamificationStats['current_level'] as int? ?? 1;
  int get totalPoints => _gamificationStats['total_points'] as int? ?? 0;
  int get nextLevelPoints => _gamificationStats['next_level_points'] as int? ?? 100;
  int get pointsToNextLevel => _gamificationStats['points_to_next_level'] as int? ?? 100;
  int get activeChallengesCount => _gamificationStats['active_challenges'] as int? ?? 0;
  int get currentStreak => _gamificationStats['current_streak'] as int? ?? 0;
  int get completedChallengesCount => _gamificationStats['completed_challenges'] as int? ?? 0;
  List<dynamic> get badgesEarned => _gamificationStats['badges_earned'] as List<dynamic>? ?? [];

  /// Initialize the provider and load initial data
  Future<void> initialize() async {
    if (_state != ChallengesState.initial) return;

    _setLoading(true);
    _state = ChallengesState.loading;
    notifyListeners();

    try {
      logInfo('Initializing ChallengesProvider', tag: 'CHALLENGES_PROVIDER');

      await loadChallengeData();

      _state = ChallengesState.loaded;
      logInfo('ChallengesProvider initialized successfully', tag: 'CHALLENGES_PROVIDER');
    } catch (e) {
      logError('Failed to initialize ChallengesProvider: $e', tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      _state = ChallengesState.error;
    } finally {
      _setLoading(false);
    }
  }

  /// Load all challenge data
  Future<void> loadChallengeData() async {
    try {
      _setLoading(true);

      final results = await Future.wait([
        _apiService.getChallenges(),
        _apiService.getAvailableChallenges(),
        _apiService.getGameificationStats(),
        _apiService.getLeaderboard(),
      ]);

      _activeChallenges = results[0] as List<dynamic>;
      _availableChallenges = results[1] as List<dynamic>;
      _gamificationStats = results[2] as Map<String, dynamic>;
      _leaderboard = results[3] as List<dynamic>;

      logInfo(
          'Loaded ${_activeChallenges.length} active challenges, ${_availableChallenges.length} available',
          tag: 'CHALLENGES_PROVIDER');
      notifyListeners();

      // Load progress for each active challenge
      for (final challenge in _activeChallenges) {
        final challengeId = challenge['id']?.toString();
        if (challengeId != null) {
          loadChallengeProgress(challengeId);
        }
      }
    } catch (e) {
      logError('Failed to load challenge data: $e', tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      rethrow;
    } finally {
      _setLoading(false);
    }
  }

  /// Load progress for a specific challenge
  Future<void> loadChallengeProgress(String challengeId) async {
    try {
      final progress = await _apiService.getChallengeProgress(challengeId);
      _challengeProgress[challengeId] = progress;
      notifyListeners();
      logInfo('Loaded progress for challenge $challengeId', tag: 'CHALLENGES_PROVIDER');
    } catch (e) {
      // Silently fail - progress not critical for display
      logError('Failed to load challenge progress: $e', tag: 'CHALLENGES_PROVIDER');
    }
  }

  /// Join a challenge
  Future<bool> joinChallenge(String challengeId) async {
    try {
      _setLoading(true);

      await _apiService.joinChallenge(challengeId);

      // Refresh data
      await loadChallengeData();

      logInfo('Joined challenge $challengeId', tag: 'CHALLENGES_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to join challenge: $e', tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Leave a challenge
  Future<bool> leaveChallenge(String challengeId) async {
    try {
      _setLoading(true);

      await _apiService.leaveChallenge(challengeId);

      // Refresh data
      await loadChallengeData();

      logInfo('Left challenge $challengeId', tag: 'CHALLENGES_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to leave challenge: $e', tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Update challenge progress
  Future<bool> updateChallengeProgress(
      String challengeId, Map<String, dynamic> progressData) async {
    try {
      _setLoading(true);

      await _apiService.updateChallengeProgress(challengeId, progressData);

      // Refresh progress
      await loadChallengeProgress(challengeId);

      logInfo('Updated progress for challenge $challengeId', tag: 'CHALLENGES_PROVIDER');
      return true;
    } catch (e) {
      logError('Failed to update challenge progress: $e', tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false);
    }
  }

  /// Refresh all data
  Future<void> refresh() async {
    await loadChallengeData();
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading) {
    _isLoading = loading;
    notifyListeners();
  }
}
