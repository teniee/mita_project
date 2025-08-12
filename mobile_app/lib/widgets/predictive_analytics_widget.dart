import 'package:flutter/material.dart';
import 'dart:math' as math;
import '../services/advanced_financial_engine.dart';

/// Predictive Analytics Widget
/// 
/// Displays AI-powered financial predictions, risk assessment, and future
/// spending insights using data from the Advanced Financial Engine.
class PredictiveAnalyticsWidget extends StatefulWidget {
  final AdvancedFinancialEngine financialEngine;
  final bool showRiskAssessment;
  final bool showSpendingPrediction;
  final bool showBehavioralPredictions;

  const PredictiveAnalyticsWidget({
    super.key,
    required this.financialEngine,
    this.showRiskAssessment = true,
    this.showSpendingPrediction = true,
    this.showBehavioralPredictions = true,
  });

  @override
  State<PredictiveAnalyticsWidget> createState() => _PredictiveAnalyticsWidgetState();
}

class _PredictiveAnalyticsWidgetState extends State<PredictiveAnalyticsWidget> 
    with TickerProviderStateMixin {

  late AnimationController _chartAnimationController;
  late AnimationController _riskAnimationController;
  late Animation<double> _chartAnimation;
  late Animation<double> _riskAnimation;
  
  Map<String, dynamic>? _predictiveAnalytics;
  Map<String, dynamic>? _riskAssessment;
  int _selectedTimeFrame = 30; // days

  @override
  void initState() {
    super.initState();
    _initializeAnimations();
    _subscribeToUpdates();
    _loadInitialData();
  }

  void _initializeAnimations() {
    _chartAnimationController = AnimationController(
      duration: const Duration(milliseconds: 1200),
      vsync: this,
    );
    
    _riskAnimationController = AnimationController(
      duration: const Duration(milliseconds: 800),
      vsync: this,
    );

    _chartAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _chartAnimationController,
      curve: Curves.easeInOutCubic,
    ));

    _riskAnimation = Tween<double>(
      begin: 0.0,
      end: 1.0,
    ).animate(CurvedAnimation(
      parent: _riskAnimationController,
      curve: Curves.elasticOut,
    ));

    _chartAnimationController.forward();
    _riskAnimationController.forward();
  }

  void _subscribeToUpdates() {
    widget.financialEngine.addListener(_onDataUpdated);
  }

  void _onDataUpdated() {
    if (mounted) {
      setState(() {
        _predictiveAnalytics = widget.financialEngine.predictiveAnalytics;
        _riskAssessment = widget.financialEngine.riskAssessment;
      });
    }
  }

  void _loadInitialData() {
    setState(() {
      _predictiveAnalytics = widget.financialEngine.predictiveAnalytics;
      _riskAssessment = widget.financialEngine.riskAssessment;
    });
  }

  @override
  void dispose() {
    widget.financialEngine.removeListener(_onDataUpdated);
    _chartAnimationController.dispose();
    _riskAnimationController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_predictiveAnalytics == null && _riskAssessment == null) {
      return const SizedBox.shrink();
    }

    return Card(
      elevation: 4,
      margin: const EdgeInsets.all(16),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(16),
          gradient: LinearGradient(
            colors: [
              const Color(0xFF6366F1),
              const Color(0xFF8B5CF6).withValues(alpha: 0.9),
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
                children: [
                  Container(
                    padding: const EdgeInsets.all(10),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.2),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Icon(
                      Icons.trending_up,
                      color: Colors.white,
                      size: 24,
                    ),
                  ),
                  const SizedBox(width: 12),
                  const Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Predictive Analytics',
                          style: const TextStyle(
                            fontFamily: 'Sora',
                            fontWeight: FontWeight.bold,
                            fontSize: 18,
                            color: Colors.white,
                          ),
                        ),
                        Text(
                          'AI-powered financial forecasts',
                          style: const TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 12,
                            color: Colors.white70,
                          ),
                        ),
                      ],
                    ),
                  ),
                  // Time Frame Selector
                  _buildTimeFrameSelector(),
                ],
              ),
              
              const SizedBox(height: 24),
              
              // Risk Assessment Section
              if (widget.showRiskAssessment && _riskAssessment != null)
                _buildRiskAssessmentSection(),
              
              // Spending Prediction Section
              if (widget.showSpendingPrediction && _predictiveAnalytics != null) ...[
                if (widget.showRiskAssessment && _riskAssessment != null)
                  const SizedBox(height: 20),
                _buildSpendingPredictionSection(),
              ],
              
              // Behavioral Predictions Section
              if (widget.showBehavioralPredictions && _predictiveAnalytics != null) ...[
                const SizedBox(height: 20),
                _buildBehavioralPredictionsSection(),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTimeFrameSelector() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      decoration: BoxDecoration(
        color: Colors.white.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(20),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [7, 30, 90].map((days) {
          final isSelected = _selectedTimeFrame == days;
          return GestureDetector(
            onTap: () {
              setState(() {
                _selectedTimeFrame = days;
              });
            },
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: isSelected ? Colors.white : Colors.transparent,
                borderRadius: BorderRadius.circular(16),
              ),
              child: Text(
                '${days}d',
                style: const TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: isSelected ? const Color(0xFF6366F1) : Colors.white70,
                ),
              ),
            ),
          );
        }).toList(),
      ),
    );
  }

  Widget _buildRiskAssessmentSection() {
    final riskScore = (_riskAssessment!['risk_score'] as num?)?.toDouble() ?? 0.0;
    final riskLevel = _riskAssessment!['risk_level'] as String? ?? 'moderate';
    final recommendations = _riskAssessment!['recommendations'] as List<dynamic>? ?? [];

    return AnimatedBuilder(
      animation: _riskAnimation,
      builder: (context, child) {
        return Transform.scale(
          scale: 0.8 + (_riskAnimation.value * 0.2),
          child: Opacity(
            opacity: _riskAnimation.value,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text(
                      'Financial Risk Assessment',
                      style: const TextStyle(
                        fontFamily: 'Sora',
                        fontWeight: FontWeight.w600,
                        fontSize: 16,
                        color: Colors.white,
                      ),
                    ),
                    const Spacer(),
                    _buildRiskLevelIndicator(riskLevel),
                  ],
                ),
                
                const SizedBox(height: 16),
                
                // Risk Score Gauge
                Center(
                  child: _buildRiskGauge(riskScore, riskLevel),
                ),
                
                const SizedBox(height: 16),
                
                // Risk Recommendations
                if (recommendations.isNotEmpty) ...[
                  const Text(
                    'Recommendations:',
                    style: const TextStyle(
                      fontFamily: 'Sora',
                      fontWeight: FontWeight.w600,
                      fontSize: 14,
                      color: Colors.white,
                    ),
                  ),
                  const SizedBox(height: 8),
                  ...recommendations.take(2).map((rec) => Padding(
                    padding: const EdgeInsets.only(bottom: 4),
                    child: Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '• ',
                          style: const TextStyle(
                            fontFamily: 'Manrope',
                            fontSize: 12,
                            color: Colors.white.withValues(alpha: 0.8),
                          ),
                        ),
                        Expanded(
                          child: Text(
                            rec.toString(),
                            style: const TextStyle(
                              fontFamily: 'Manrope',
                              fontSize: 12,
                              color: Colors.white.withValues(alpha: 0.8),
                            ),
                          ),
                        ),
                      ],
                    ),
                  )),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildRiskLevelIndicator(String riskLevel) {
    Color riskColor;
    IconData riskIcon;
    
    switch (riskLevel.toLowerCase()) {
      case 'high':
        riskColor = Colors.red.shade300;
        riskIcon = Icons.warning;
        break;
      case 'moderate':
        riskColor = Colors.yellow.shade300;
        riskIcon = Icons.info;
        break;
      case 'low':
      default:
        riskColor = Colors.green.shade300;
        riskIcon = Icons.check_circle;
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: riskColor.withValues(alpha: 0.2),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: riskColor.withValues(alpha: 0.4)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(
            riskIcon,
            color: riskColor,
            size: 14,
          ),
          const SizedBox(width: 4),
          Text(
            riskLevel.toUpperCase(),
            style: const TextStyle(
              fontFamily: 'Manrope',
              fontSize: 11,
              fontWeight: FontWeight.w600,
              color: riskColor,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRiskGauge(double riskScore, String riskLevel) {
    return SizedBox(
      width: 120,
      height: 120,
      child: Stack(
        alignment: Alignment.center,
        children: [
          // Background Circle
          Container(
            width: 120,
            height: 120,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white.withValues(alpha: 0.1),
            ),
          ),
          
          // Risk Arc
          AnimatedBuilder(
            animation: _riskAnimation,
            builder: (context, child) {
              return CustomPaint(
                size: const Size(120, 120),
                painter: RiskGaugePainter(
                  riskScore: riskScore * _riskAnimation.value,
                  riskLevel: riskLevel,
                ),
              );
            },
          ),
          
          // Score Text
          Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Text(
                '${riskScore.toStringAsFixed(0)}%',
                style: const const TextStyle(
                  fontFamily: 'Sora',
                  fontWeight: FontWeight.bold,
                  fontSize: 20,
                  color: Colors.white,
                ),
              ),
              Text(
                'Risk Score',
                style: const TextStyle(
                  fontFamily: 'Manrope',
                  fontSize: 10,
                  color: Colors.white.withValues(alpha: 0.7),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildSpendingPredictionSection() {
    final spendingPrediction = _predictiveAnalytics!['spending_prediction'] as Map<String, dynamic>? ?? {};
    final predictedAmount = (spendingPrediction['predicted_amount'] as num?)?.toDouble() ?? 0.0;
    final confidence = (spendingPrediction['confidence'] as num?)?.toDouble() ?? 0.0;

    return AnimatedBuilder(
      animation: _chartAnimation,
      builder: (context, child) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Spending Forecast',
              style: const TextStyle(
                fontFamily: 'Sora',
                fontWeight: FontWeight.w600,
                fontSize: 16,
                color: Colors.white,
              ),
            ),
            
            const SizedBox(height: 12),
            
            // Prediction Chart
            Container(
              height: 100,
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: CustomPaint(
                  size: const Size(double.infinity, 68),
                  painter: SpendingChartPainter(
                    animationProgress: _chartAnimation.value,
                    predictedAmount: predictedAmount,
                    timeFrame: _selectedTimeFrame,
                  ),
                ),
              ),
            ),
            
            const SizedBox(height: 12),
            
            // Prediction Details
            Row(
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Predicted Spending',
                        style: const TextStyle(
                          fontFamily: 'Manrope',
                          fontSize: 12,
                          color: Colors.white.withValues(alpha: 0.7),
                        ),
                      ),
                      Text(
                        '\$${predictedAmount.toStringAsFixed(0)}',
                        style: const const TextStyle(
                          fontFamily: 'Sora',
                          fontWeight: FontWeight.bold,
                          fontSize: 18,
                          color: Colors.white,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withValues(alpha: 0.2),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    '${(confidence * 100).toStringAsFixed(0)}% confident',
                    style: const TextStyle(
                      fontFamily: 'Manrope',
                      fontSize: 11,
                      fontWeight: FontWeight.w500,
                      color: Colors.white.withValues(alpha: 0.9),
                    ),
                  ),
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  Widget _buildBehavioralPredictionsSection() {
    final behaviorPredictions = _predictiveAnalytics!['behavior_predictions'] as Map<String, dynamic>? ?? {};
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'Behavioral Insights',
          style: const TextStyle(
            fontFamily: 'Sora',
            fontWeight: FontWeight.w600,
            fontSize: 16,
            color: Colors.white,
          ),
        ),
        
        const SizedBox(height: 12),
        
        // Behavioral predictions would go here
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: Colors.white.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(8),
          ),
          child: Row(
            children: [
              Icon(
                Icons.psychology,
                color: Colors.white.withValues(alpha: 0.7),
                size: 16,
              ),
              const SizedBox(width: 8),
              Expanded(
                child: Text(
                  'Behavioral patterns suggest continued mindful spending',
                  style: const TextStyle(
                    fontFamily: 'Manrope',
                    fontSize: 12,
                    color: Colors.white.withValues(alpha: 0.8),
                  ),
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }
}

// Custom Painter for Risk Gauge
class RiskGaugePainter extends CustomPainter {
  final double riskScore;
  final String riskLevel;

  RiskGaugePainter({
    required this.riskScore,
    required this.riskLevel,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = size.width / 2 - 10;
    
    // Background Arc
    final backgroundPaint = Paint()
      ..color = Colors.white.withValues(alpha: 0.2)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8;
    
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi,
      math.pi,
      false,
      backgroundPaint,
    );
    
    // Risk Arc
    Color arcColor;
    switch (riskLevel.toLowerCase()) {
      case 'high':
        arcColor = Colors.red.shade300;
        break;
      case 'moderate':
        arcColor = Colors.yellow.shade300;
        break;
      case 'low':
      default:
        arcColor = Colors.green.shade300;
    }
    
    final riskPaint = Paint()
      ..color = arcColor
      ..style = PaintingStyle.stroke
      ..strokeWidth = 8
      ..strokeCap = StrokeCap.round;
    
    final sweepAngle = (riskScore / 100) * math.pi;
    
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      -math.pi,
      sweepAngle,
      false,
      riskPaint,
    );
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}

// Custom Painter for Spending Chart
class SpendingChartPainter extends CustomPainter {
  final double animationProgress;
  final double predictedAmount;
  final int timeFrame;

  SpendingChartPainter({
    required this.animationProgress,
    required this.predictedAmount,
    required this.timeFrame,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = Colors.white.withValues(alpha: 0.8)
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2;
    
    final fillPaint = Paint()
      ..shader = LinearGradient(
        colors: [
          Colors.white.withValues(alpha: 0.3),
          Colors.white.withValues(alpha: 0.1),
        ],
        begin: Alignment.topCenter,
        end: Alignment.bottomCenter,
      ).createShader(Rect.fromLTWH(0, 0, size.width, size.height));
    
    final path = Path();
    final fillPath = Path();
    
    // Generate sample data points
    final points = <Offset>[];
    for (int i = 0; i <= timeFrame; i++) {
      final x = (i / timeFrame) * size.width;
      final baseY = size.height * 0.7;
      final variationY = (math.sin(i * 0.3) * 15) + (i * 2);
      final y = baseY - variationY;
      points.add(Offset(x, y * animationProgress + size.height * (1 - animationProgress)));
    }
    
    // Draw the path
    if (points.isNotEmpty) {
      path.moveTo(points.first.dx, points.first.dy);
      fillPath.moveTo(points.first.dx, size.height);
      fillPath.lineTo(points.first.dx, points.first.dy);
      
      for (int i = 1; i < points.length; i++) {
        path.lineTo(points[i].dx, points[i].dy);
        fillPath.lineTo(points[i].dx, points[i].dy);
      }
      
      fillPath.lineTo(points.last.dx, size.height);
      fillPath.close();
      
      canvas.drawPath(fillPath, fillPaint);
      canvas.drawPath(path, paint);
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => true;
}