"""
Resilient GPT Service with Circuit Breaker Protection
Enhanced version of GPT agent with proper error handling, retries, and fallbacks
"""

import logging
import asyncio
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import openai
from openai import AsyncOpenAI

from app.core.circuit_breaker import get_circuit_breaker_manager, CircuitBreakerConfig

logger = logging.getLogger(__name__)


class ResilientGPTService:
    """Enhanced GPT service with circuit breaker protection and error handling"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        """Initialize the resilient GPT service"""
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.circuit_breaker_manager = get_circuit_breaker_manager()
        
        # Register service with custom config for OpenAI
        self.circuit_breaker_manager.register_service(
            'openai_chat',
            CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_duration=300,  # 5 minutes for OpenAI recovery
                max_retry_attempts=2,
                retry_backoff_factor=1.5,
                timeout_seconds=120.0,  # 2 minutes per request
                trigger_exceptions=(
                    openai.APIConnectionError,
                    openai.APITimeoutError,
                    openai.RateLimitError,
                    openai.InternalServerError,
                    ConnectionError,
                    TimeoutError,
                    OSError,
                )
            )
        )
        
        self.system_prompts = {
            'financial_advisor': (
                "You are a professional financial assistant for MITA, a smart budgeting app. "
                "You help users manage their budgets, categorize their expenses, "
                "and offer smart advice based on their country and spending profile. "
                "Be concise, clear, supportive, and actionable. "
                "Always focus on practical financial guidance."
            ),
            'budget_analyzer': (
                "You are an expert budget analyst. Analyze spending patterns, "
                "identify trends, suggest optimizations, and provide insights "
                "that help users make better financial decisions. "
                "Be specific and data-driven in your recommendations."
            ),
            'expense_categorizer': (
                "You are an expense categorization expert. "
                "Accurately categorize expenses and suggest appropriate spending categories. "
                "Consider context, merchant names, and spending patterns."
            )
        }
        
        # Fallback responses for when service is unavailable
        self.fallback_responses = {
            'financial_advice': [
                "I'm temporarily unavailable, but here's a tip: Review your largest expense categories this month and see if there are opportunities to save.",
                "While I'm offline, consider the 50/30/20 rule: 50% needs, 30% wants, 20% savings.",
                "Quick advice: Track your daily spending for better budget awareness, even when I'm not available.",
            ],
            'budget_analysis': [
                "Budget analysis is temporarily unavailable. Try reviewing your spending by category to identify patterns.",
                "While I'm offline, focus on your top 3 expense categories - that's usually where the biggest savings opportunities are.",
            ],
            'categorization': [
                "Expense categorization is temporarily unavailable. Use your best judgment or check similar past transactions.",
            ]
        }
    
    async def ask_financial_advice(
        self, 
        user_messages: List[Dict[str, str]], 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Get financial advice with resilient error handling"""
        return await self._make_chat_request(
            user_messages=user_messages,
            system_prompt_key='financial_advisor',
            fallback_type='financial_advice',
            context=context
        )
    
    async def analyze_budget(
        self, 
        spending_data: Dict[str, Any],
        user_context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Analyze budget with spending data"""
        messages = [
            {
                "role": "user",
                "content": f"Analyze my spending data and provide insights: {spending_data}"
            }
        ]
        
        if user_context:
            messages.insert(0, {
                "role": "user", 
                "content": f"My context: {user_context}"
            })
        
        return await self._make_chat_request(
            user_messages=messages,
            system_prompt_key='budget_analyzer',
            fallback_type='budget_analysis',
            max_tokens=800
        )
    
    async def categorize_expense(
        self, 
        description: str, 
        amount: float, 
        merchant: Optional[str] = None
    ) -> Dict[str, Any]:
        """Categorize an expense with confidence scoring"""
        context = f"Description: {description}, Amount: ${amount:.2f}"
        if merchant:
            context += f", Merchant: {merchant}"
        
        messages = [
            {
                "role": "user",
                "content": f"Categorize this expense and provide a confidence score (0-100): {context}"
            }
        ]
        
        try:
            response = await self._make_chat_request(
                user_messages=messages,
                system_prompt_key='expense_categorizer',
                fallback_type='categorization',
                max_tokens=200
            )
            
            # Parse response for structured data
            return self._parse_categorization_response(response, description)
            
        except Exception as e:
            logger.error(f"Expense categorization failed: {str(e)}")
            return {
                'category': 'Other',
                'confidence': 50,
                'reasoning': 'Automatic categorization unavailable',
                'suggested_category': None
            }
    
    async def _make_chat_request(
        self,
        user_messages: List[Dict[str, str]],
        system_prompt_key: str,
        fallback_type: str,
        context: Optional[Dict[str, Any]] = None,
        max_tokens: int = 600,
        temperature: float = 0.3
    ) -> str:
        """Make a chat completion request with circuit breaker protection"""
        
        # Prepare messages
        messages = [
            {"role": "system", "content": self.system_prompts[system_prompt_key]}
        ]
        
        # Add context if provided
        if context:
            messages.append({
                "role": "system", 
                "content": f"Additional context: {context}"
            })
        
        messages.extend(user_messages)
        
        try:
            # Use circuit breaker protection
            async def _make_request():
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=60.0  # Request-level timeout
                )
                return response.choices[0].message.content.strip()
            
            result = await self.circuit_breaker_manager.call_service(
                'openai_chat',
                _make_request
            )
            
            logger.info(f"Successfully generated {system_prompt_key} response")
            return result
            
        except openai.RateLimitError as e:
            logger.warning(f"OpenAI rate limit hit: {str(e)}")
            return self._get_rate_limit_response()
            
        except openai.APIConnectionError as e:
            logger.error(f"OpenAI connection error: {str(e)}")
            return self._get_fallback_response(fallback_type)
            
        except openai.APITimeoutError as e:
            logger.error(f"OpenAI timeout error: {str(e)}")
            return "I'm taking longer than usual to respond. Please try again in a moment."
            
        except openai.AuthenticationError as e:
            logger.critical(f"OpenAI authentication error: {str(e)}")
            return "There's an issue with the AI service configuration. Please contact support."
            
        except openai.BadRequestError as e:
            logger.error(f"OpenAI bad request error: {str(e)}")
            return "I couldn't process your request. Please try rephrasing it."
            
        except Exception as e:
            logger.error(f"Unexpected error in GPT service: {str(e)}", exc_info=True)
            return self._get_fallback_response(fallback_type)
    
    def _get_fallback_response(self, fallback_type: str) -> str:
        """Get a fallback response when AI is unavailable"""
        responses = self.fallback_responses.get(fallback_type, [
            "I'm temporarily unavailable. Please try again in a few minutes."
        ])
        
        # Rotate through responses to avoid repetition
        import random
        return random.choice(responses)
    
    def _get_rate_limit_response(self) -> str:
        """Get response for rate limit scenarios"""
        return (
            "I'm currently experiencing high demand. "
            "Please wait a moment and try again. "
            "In the meantime, you can review your recent transactions manually."
        )
    
    def _parse_categorization_response(
        self, 
        response: str, 
        description: str
    ) -> Dict[str, Any]:
        """Parse categorization response into structured data"""
        try:
            # Simple parsing logic - in production, you might want more sophisticated parsing
            lines = response.lower().split('\n')
            category = 'Other'
            confidence = 70  # Default confidence
            reasoning = response
            
            # Look for category indicators
            category_keywords = {
                'food': ['food', 'restaurant', 'dining', 'grocery', 'meal'],
                'transportation': ['transport', 'gas', 'fuel', 'uber', 'taxi', 'bus'],
                'shopping': ['shopping', 'retail', 'store', 'purchase'],
                'entertainment': ['entertainment', 'movie', 'game', 'fun'],
                'utilities': ['utility', 'electric', 'water', 'internet', 'phone'],
                'healthcare': ['health', 'medical', 'doctor', 'pharmacy'],
                'travel': ['travel', 'hotel', 'flight', 'vacation'],
            }
            
            description_lower = description.lower()
            for cat, keywords in category_keywords.items():
                if any(keyword in description_lower for keyword in keywords):
                    category = cat.title()
                    confidence = 85
                    break
            
            return {
                'category': category,
                'confidence': confidence,
                'reasoning': reasoning[:200],  # Truncate for storage
                'suggested_category': category if confidence < 80 else None
            }
            
        except Exception as e:
            logger.error(f"Error parsing categorization response: {str(e)}")
            return {
                'category': 'Other',
                'confidence': 50,
                'reasoning': 'Parsing failed',
                'suggested_category': None
            }
    
    async def get_service_health(self) -> Dict[str, Any]:
        """Get health status of the GPT service"""
        circuit_breaker = self.circuit_breaker_manager.get_circuit_breaker('openai_chat')
        stats = circuit_breaker.get_stats()
        
        return {
            'service_name': 'resilient_gpt_service',
            'status': 'healthy' if stats['state'] == 'closed' else 'degraded' if stats['state'] == 'half_open' else 'unhealthy',
            'circuit_breaker_state': stats['state'],
            'total_requests': stats['total_requests'],
            'success_rate': stats['success_rate'],
            'consecutive_failures': stats['consecutive_failures'],
            'last_request_time': stats['last_success_time'] or stats['last_failure_time'],
            'model': self.model,
            'available_features': [
                'financial_advice',
                'budget_analysis', 
                'expense_categorization'
            ]
        }
    
    async def test_connection(self) -> bool:
        """Test connection to OpenAI API"""
        try:
            test_messages = [
                {"role": "user", "content": "Hello, are you working?"}
            ]
            
            result = await self._make_chat_request(
                user_messages=test_messages,
                system_prompt_key='financial_advisor',
                fallback_type='financial_advice',
                max_tokens=50
            )
            
            return "temporarily unavailable" not in result.lower()
            
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False


# Global instance management
_gpt_service: Optional[ResilientGPTService] = None

def get_gpt_service(api_key: str, model: str = "gpt-4") -> ResilientGPTService:
    """Get singleton GPT service instance"""
    global _gpt_service
    if _gpt_service is None:
        _gpt_service = ResilientGPTService(api_key, model)
    return _gpt_service