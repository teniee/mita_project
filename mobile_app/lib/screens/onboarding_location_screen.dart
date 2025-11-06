import 'package:flutter/material.dart';
import '../services/location_service.dart';
import '../services/onboarding_state.dart';
import '../widgets/onboarding_progress_indicator.dart';

class OnboardingLocationScreen extends StatefulWidget {
  const OnboardingLocationScreen({super.key});

  @override
  State<OnboardingLocationScreen> createState() => _OnboardingLocationScreenState();
}

class _OnboardingLocationScreenState extends State<OnboardingLocationScreen> {
  final LocationService _locationService = LocationService();
  final TextEditingController _searchController = TextEditingController();

  String _selectedCountry = 'US'; // Always USA
  String? _selectedState;
  bool _isDetectingLocation = false;
  bool _isLocationDetected = false;
  String? _locationError;
  String _searchQuery = '';

  // Popular US states
  final List<String> _popularStates = ['CA', 'NY', 'TX', 'FL', 'IL', 'PA'];

  @override
  void initState() {
    super.initState();
    _tryAutoDetectLocation();
  }

  Future<void> _tryAutoDetectLocation() async {
    setState(() {
      _isDetectingLocation = true;
      _locationError = null;
    });

    try {
      final location = await _locationService.getUserLocation();
      
      if (location['country'] != null) {
        setState(() {
          // Always use US, but try to detect the state
          _selectedCountry = 'US';
          if (location['country'] == 'US') {
            _selectedState = location['state'];
            _isLocationDetected = true;
          } else {
            _locationError = 'MITA currently supports USA only. Please select your state manually.';
          }
        });
      } else {
        setState(() {
          _locationError = location['error'] ?? 'Unable to detect location';
        });
      }
    } catch (e) {
      setState(() {
        _locationError = e.toString();
      });
    } finally {
      setState(() {
        _isDetectingLocation = false;
      });
    }
  }

  void _selectState(String stateCode) {
    setState(() {
      _selectedState = stateCode;
    });
  }

  List<Map<String, String>> _getFilteredStates() {
    final allStates = _locationService.getUSStatesForSelection();
    if (_searchQuery.isEmpty) {
      return allStates;
    }
    return allStates.where((state) {
      final name = state['name']!.toLowerCase();
      final code = state['code']!.toLowerCase();
      final query = _searchQuery.toLowerCase();
      return name.contains(query) || code.contains(query);
    }).toList();
  }

  List<Map<String, String>> _getPopularStatesList() {
    final allStates = _locationService.getUSStatesForSelection();
    return allStates.where((state) => _popularStates.contains(state['code'])).toList();
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  Future<void> _continueWithLocation() async {
    if (_selectedState == null) return;

    // Save location to preferences
    await _locationService.saveUserLocation(
      _selectedCountry,
      stateCode: _selectedState,
      manuallySet: !_isLocationDetected,
    );

    // Store in onboarding state
    OnboardingState.instance.countryCode = _selectedCountry;
    OnboardingState.instance.stateCode = _selectedState;

    // Navigate to income screen
    Navigator.pushNamed(context, '/onboarding_income');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFFF9F0),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const SizedBox(height: 8),
              const OnboardingProgressIndicator(
                currentStep: 1,
                totalSteps: 7,
              ),
              const SizedBox(height: 24),

              // Header
              Card(
                elevation: 3,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(28),
                ),
                color: Colors.white,
                child: const Padding(
                  padding: EdgeInsets.symmetric(vertical: 40, horizontal: 28),
                  child: Column(
                    children: [
                      Icon(
                        Icons.location_on_rounded,
                        size: 64,
                        color: Color(0xFF193C57),
                      ),
                      SizedBox(height: 20),
                      Text(
                        'Which US state are you in?',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontFamily: 'Sora',
                          fontWeight: FontWeight.w700,
                          fontSize: 28,
                          color: Color(0xFF193C57),
                        ),
                      ),
                      SizedBox(height: 16),
                      Text(
                        'We\'ll customize income thresholds and financial advice based on your state\'s cost of living.',
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          color: Colors.black54,
                          fontSize: 16,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 24),

              // Auto-detection status
              if (_isDetectingLocation)
                Card(
                  elevation: 2,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: const Padding(
                    padding: EdgeInsets.all(20),
                    child: Row(
                      children: [
                        CircularProgressIndicator(
                          color: Color(0xFF193C57),
                        ),
                        SizedBox(width: 16),
                        Text(
                          'Detecting your location...',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 16,
                            color: Color(0xFF193C57),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              // Location detected success
              if (_isLocationDetected && _selectedState != null)
                Card(
                  elevation: 2,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.check_circle_rounded,
                              color: Colors.green.shade600,
                              size: 24,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Location Detected',
                              style: TextStyle(
                                fontFamily: 'Sora',
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                                color: Colors.green.shade600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Text(
                          _locationService.formatLocationForDisplay(_selectedCountry, stateCode: _selectedState),
                          style: const TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 16,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              // Location error
              if (_locationError != null)
                Card(
                  elevation: 2,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.warning_rounded,
                              color: Colors.orange.shade600,
                              size: 24,
                            ),
                            const SizedBox(width: 12),
                            Text(
                              'Auto-detection failed',
                              style: TextStyle(
                                fontFamily: 'Sora',
                                fontWeight: FontWeight.bold,
                                fontSize: 16,
                                color: Colors.orange.shade600,
                              ),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          'Please select your location manually below.',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 14,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),

              const SizedBox(height: 24),

              // State selection
              const Text(
                'Select your state:',
                style: TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.w600,
                  fontSize: 18,
                  color: Color(0xFF193C57),
                ),
              ),
              const SizedBox(height: 16),

              // Search field
              TextField(
                controller: _searchController,
                decoration: InputDecoration(
                  hintText: 'Search states...',
                  prefixIcon: const Icon(Icons.search, color: Color(0xFF193C57)),
                  filled: true,
                  fillColor: Colors.white,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: Colors.grey.shade300),
                  ),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide(color: Colors.grey.shade300),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: const BorderSide(color: Color(0xFF193C57), width: 2),
                  ),
                  contentPadding: const EdgeInsets.symmetric(vertical: 14, horizontal: 16),
                ),
                onChanged: (value) {
                  setState(() {
                    _searchQuery = value;
                  });
                },
              ),
              const SizedBox(height: 16),

              // Popular states (shown only when no search query)
              if (_searchQuery.isEmpty) ...[
                const Text(
                  'Popular States:',
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _getPopularStatesList().map((state) {
                    final isSelected = _selectedState == state['code'];
                    return ActionChip(
                      label: Text(
                        state['name']!,
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontWeight: FontWeight.w600,
                          color: isSelected ? Colors.white : const Color(0xFF193C57),
                        ),
                      ),
                      backgroundColor: isSelected ? const Color(0xFF193C57) : Colors.white,
                      side: BorderSide(
                        color: isSelected ? const Color(0xFF193C57) : Colors.grey.shade300,
                      ),
                      onPressed: () => _selectState(state['code']!),
                    );
                  }).toList(),
                ),
                const SizedBox(height: 16),
                const Text(
                  'All States:',
                  style: TextStyle(
                    fontFamily: 'Manrope',
                    fontWeight: FontWeight.w600,
                    fontSize: 14,
                    color: Colors.grey,
                  ),
                ),
                const SizedBox(height: 8),
              ],

              Container(
                height: 300,
                decoration: BoxDecoration(
                  border: Border.all(color: Colors.grey.shade300),
                  borderRadius: BorderRadius.circular(12),
                  color: Colors.white,
                ),
                child: _getFilteredStates().isEmpty
                    ? const Center(
                        child: Text(
                          'No states found',
                          style: TextStyle(
                            fontFamily: 'Manrope',
                            color: Colors.grey,
                          ),
                        ),
                      )
                    : ListView.builder(
                        itemCount: _getFilteredStates().length,
                        itemBuilder: (context, index) {
                          final state = _getFilteredStates()[index];
                    return ListTile(
                      title: Text(
                        state['name']!,
                        style: TextStyle(
                          fontFamily: 'Manrope',
                          fontWeight: _selectedState == state['code']
                              ? FontWeight.w600
                              : FontWeight.w400,
                        ),
                      ),
                      trailing: _selectedState == state['code']
                          ? const Icon(
                              Icons.check_circle_rounded,
                              color: Color(0xFF193C57),
                            )
                          : null,
                      selected: _selectedState == state['code'],
                      selectedTileColor: const Color(0xFF193C57).withValues(alpha: 0.1),
                      onTap: () => _selectState(state['code']!),
                    );
                  },
                ),
              ),

              const SizedBox(height: 32),

              // Continue button
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: _selectedState != null
                      ? _continueWithLocation
                      : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF193C57),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(16),
                    ),
                    padding: const EdgeInsets.symmetric(vertical: 18),
                    textStyle: const TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.w600,
                      fontSize: 18,
                    ),
                  ),
                  child: const Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text('Continue'),
                      SizedBox(width: 8),
                      Icon(
                        Icons.arrow_forward_rounded,
                        size: 20,
                      ),
                    ],
                  ),
                ),
              ),

              const SizedBox(height: 40),
            ],
          ),
        ),
      ),
    );
  }
}