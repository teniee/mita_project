import 'package:flutter/foundation.dart';
import '../services/api_service.dart';
import '../services/logging_service.dart';
import '../utils/json_utils.dart';

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
  final ApiService _apiService;

  ChallengesProvider({ApiService? apiService})
      : _apiService = apiService ?? ApiService();

  // State
  ChallengesState _state = ChallengesState.initial;
  List<Map<String, dynamic>> _activeChallenges = [];
  List<Map<String, dynamic>> _availableChallenges = [];
  Map<String, dynamic> _gamificationStats = {};
  List<Map<String, dynamic>> _leaderboard = [];
  final Map<String, Map<String, dynamic>> _challengeProgress = {};
  String? _errorMessage;
  bool _isLoading = false;
  int _sessionGeneration = 0;
  int _challengeDataRequestId = 0;
  final Map<String, int> _progressRequestIds = {};

  // Getters
  ChallengesState get state => _state;
  List<Map<String, dynamic>> get activeChallenges => _activeChallenges;
  List<Map<String, dynamic>> get availableChallenges => _availableChallenges;
  Map<String, dynamic> get gamificationStats => _gamificationStats;
  List<Map<String, dynamic>> get leaderboard => _leaderboard;
  Map<String, Map<String, dynamic>> get challengeProgress => _challengeProgress;
  String? get errorMessage => _errorMessage;
  bool get isLoading => _isLoading;

  // Stats convenience getters
  int get currentLevel {
    final valueData = _gamificationStats['current_level'];
    return (valueData == null)
        ? 1
        : (valueData is num)
            ? valueData.toInt()
            : (valueData is String ? int.tryParse(valueData) ?? 1 : 1);
  }

  int get totalPoints {
    final valueData = _gamificationStats['total_points'];
    return (valueData == null)
        ? 0
        : (valueData is num)
            ? valueData.toInt()
            : (valueData is String ? int.tryParse(valueData) ?? 0 : 0);
  }

  int get nextLevelPoints {
    final valueData = _gamificationStats['next_level_points'];
    return (valueData == null)
        ? 100
        : (valueData is num)
            ? valueData.toInt()
            : (valueData is String ? int.tryParse(valueData) ?? 100 : 100);
  }

  int get pointsToNextLevel {
    final valueData = _gamificationStats['points_to_next_level'];
    return (valueData == null)
        ? 100
        : (valueData is num)
            ? valueData.toInt()
            : (valueData is String ? int.tryParse(valueData) ?? 100 : 100);
  }

  int get activeChallengesCount {
    final valueData = _gamificationStats['active_challenges'];
    return (valueData == null)
        ? 0
        : (valueData is num)
            ? valueData.toInt()
            : (valueData is String ? int.tryParse(valueData) ?? 0 : 0);
  }

  int get currentStreak {
    final valueData = _gamificationStats['current_streak'];
    return (valueData == null)
        ? 0
        : (valueData is num)
            ? valueData.toInt()
            : (valueData is String ? int.tryParse(valueData) ?? 0 : 0);
  }

  int get completedChallengesCount {
    final valueData = _gamificationStats['completed_challenges'];
    return (valueData == null)
        ? 0
        : (valueData is num)
            ? valueData.toInt()
            : (valueData is String ? int.tryParse(valueData) ?? 0 : 0);
  }

  List<Map<String, dynamic>> get badgesEarned =>
      asMapList(_gamificationStats['badges_earned']);

  /// Initialize the provider and load initial data
  Future<void> initialize() async {
    if (_state != ChallengesState.initial) return;
    final generation = _sessionGeneration;

    _setLoading(true, generation);
    _state = ChallengesState.loading;
    notifyListeners();

    try {
      logInfo('Initializing ChallengesProvider', tag: 'CHALLENGES_PROVIDER');

      await loadChallengeData(sessionGeneration: generation);
      if (!_isCurrent(generation)) return;

      _state = ChallengesState.loaded;
      logInfo('ChallengesProvider initialized successfully',
          tag: 'CHALLENGES_PROVIDER');
    } catch (e) {
      if (!_isCurrent(generation)) return;
      logError('Failed to initialize ChallengesProvider: $e',
          tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      _state = ChallengesState.error;
    } finally {
      _setLoading(false, generation);
    }
  }

  /// Load all challenge data
  Future<void> loadChallengeData({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return;
    final requestId = ++_challengeDataRequestId;

    try {
      _setLoading(true, generation);

      final results = await Future.wait([
        _apiService.getChallenges(),
        _apiService.getAvailableChallenges(),
        _apiService.getGameificationStats(),
        _apiService.getLeaderboard(),
      ]);
      if (!_isCurrentDataRequest(generation, requestId)) return;

      _activeChallenges = asMapList(results[0]);
      _availableChallenges = asMapList(results[1]);
      _gamificationStats = results[2] as Map<String, dynamic>;
      _leaderboard = asMapList(results[3]);

      logInfo(
          'Loaded ${_activeChallenges.length} active challenges, ${_availableChallenges.length} available',
          tag: 'CHALLENGES_PROVIDER');
      notifyListeners();

      // Load progress for each active challenge
      for (final challenge in _activeChallenges) {
        final challengeId = asStringKeyedMap(challenge)['id']?.toString();
        if (challengeId != null) {
          loadChallengeProgress(
            challengeId,
            sessionGeneration: generation,
          );
        }
      }
    } catch (e) {
      if (!_isCurrentDataRequest(generation, requestId)) return;
      logError('Failed to load challenge data: $e', tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      rethrow;
    } finally {
      if (_isCurrentDataRequest(generation, requestId)) {
        _setLoading(false, generation);
      }
    }
  }

  /// Load progress for a specific challenge
  Future<void> loadChallengeProgress(
    String challengeId, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return;
    final requestId = _nextProgressRequestId(challengeId);

    try {
      final progress = await _apiService.getChallengeProgress(challengeId);
      if (!_isCurrentProgressRequest(generation, challengeId, requestId)) {
        return;
      }
      _challengeProgress[challengeId] = progress;
      notifyListeners();
      logInfo('Loaded progress for challenge $challengeId',
          tag: 'CHALLENGES_PROVIDER');
    } catch (e) {
      if (!_isCurrentProgressRequest(generation, challengeId, requestId)) {
        return;
      }
      // Silently fail - progress not critical for display
      logError('Failed to load challenge progress: $e',
          tag: 'CHALLENGES_PROVIDER');
    }
  }

  /// Join a challenge
  Future<bool> joinChallenge(
    String challengeId, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return false;

    try {
      _invalidateChallengeData();
      _setLoading(true, generation);

      await _apiService.joinChallenge(challengeId);
      if (!_isCurrent(generation)) return false;

      // Refresh data
      await loadChallengeData(sessionGeneration: generation);
      if (!_isCurrent(generation)) return false;

      logInfo('Joined challenge $challengeId', tag: 'CHALLENGES_PROVIDER');
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Failed to join challenge: $e', tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false, generation);
    }
  }

  /// Leave a challenge
  Future<bool> leaveChallenge(
    String challengeId, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return false;

    try {
      _invalidateChallengeData();
      _setLoading(true, generation);

      await _apiService.leaveChallenge(challengeId);
      if (!_isCurrent(generation)) return false;

      // Refresh data
      await loadChallengeData(sessionGeneration: generation);
      if (!_isCurrent(generation)) return false;

      logInfo('Left challenge $challengeId', tag: 'CHALLENGES_PROVIDER');
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Failed to leave challenge: $e', tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false, generation);
    }
  }

  /// Update challenge progress
  Future<bool> updateChallengeProgress(
    String challengeId,
    Map<String, dynamic> progressData, {
    int? sessionGeneration,
  }) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return false;

    try {
      _invalidateChallengeProgress(challengeId);
      _setLoading(true, generation);

      await _apiService.updateChallengeProgress(challengeId, progressData);
      if (!_isCurrent(generation)) return false;

      // Refresh progress
      await loadChallengeProgress(
        challengeId,
        sessionGeneration: generation,
      );
      if (!_isCurrent(generation)) return false;

      logInfo('Updated progress for challenge $challengeId',
          tag: 'CHALLENGES_PROVIDER');
      return true;
    } catch (e) {
      if (!_isCurrent(generation)) return false;
      logError('Failed to update challenge progress: $e',
          tag: 'CHALLENGES_PROVIDER');
      _errorMessage = e.toString();
      return false;
    } finally {
      _setLoading(false, generation);
    }
  }

  /// Refresh all data
  Future<void> refresh({int? sessionGeneration}) async {
    final generation = sessionGeneration ?? _sessionGeneration;
    if (!_isCurrent(generation)) return;
    await loadChallengeData(sessionGeneration: generation);
  }

  /// Clear all account-owned state at an authentication boundary.
  void resetSession() {
    _sessionGeneration += 1;
    _challengeDataRequestId += 1;
    for (final challengeId in _progressRequestIds.keys.toList()) {
      _progressRequestIds[challengeId] =
          (_progressRequestIds[challengeId] ?? 0) + 1;
    }
    _state = ChallengesState.initial;
    _activeChallenges = [];
    _availableChallenges = [];
    _gamificationStats = {};
    _leaderboard = [];
    _challengeProgress.clear();
    _progressRequestIds.clear();
    _errorMessage = null;
    _isLoading = false;
    notifyListeners();
  }

  /// Clear error message
  void clearError() {
    _errorMessage = null;
    notifyListeners();
  }

  // Private helper
  void _setLoading(bool loading, int generation) {
    if (!_isCurrent(generation)) return;
    _isLoading = loading;
    notifyListeners();
  }

  bool _isCurrent(int generation) => generation == _sessionGeneration;

  bool _isCurrentDataRequest(int generation, int requestId) =>
      _isCurrent(generation) && requestId == _challengeDataRequestId;

  int _nextProgressRequestId(String challengeId) {
    final requestId = (_progressRequestIds[challengeId] ?? 0) + 1;
    _progressRequestIds[challengeId] = requestId;
    return requestId;
  }

  bool _isCurrentProgressRequest(
          int generation, String challengeId, int requestId) =>
      _isCurrent(generation) &&
      requestId == (_progressRequestIds[challengeId] ?? 0);

  void _invalidateChallengeData() {
    _challengeDataRequestId += 1;
  }

  void _invalidateChallengeProgress(String challengeId) {
    _progressRequestIds[challengeId] =
        (_progressRequestIds[challengeId] ?? 0) + 1;
  }
}
