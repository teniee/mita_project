"""
Validation Configuration System for MITA Financial Application

This module provides configurable validation rules to support different 
regions and compliance requirements while maintaining security standards.

Designed for easy international expansion while currently supporting US-only operations.
"""

from decimal import Decimal
from typing import Dict, List, Set, Optional, Any
from enum import Enum
from dataclasses import dataclass, field
import yaml
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class Region(Enum):
    """Supported regions for MITA application"""
    US = "US"
    # Future regions can be added here
    # CA = "CA"  # Canada
    # UK = "UK"  # United Kingdom
    # EU = "EU"  # European Union


@dataclass
class CurrencyConfig:
    """Currency configuration for a region"""
    code: str
    symbol: str
    decimal_places: int = 2
    min_amount: Decimal = Decimal('0.01')
    max_transaction: Decimal = Decimal('999999.99')
    max_annual_income: Decimal = Decimal('99999999.99')
    max_budget: Decimal = Decimal('9999999.99')
    max_goal: Decimal = Decimal('99999999.99')


@dataclass
class GeographicConfig:
    """Geographic validation configuration"""
    country_code: str
    country_name: str
    supported_states: Set[str] = field(default_factory=set)
    postal_code_pattern: str = r'^\d{5}(-\d{4})?$'  # Default US ZIP
    phone_pattern: str = r'^\+?1?[2-9]\d{2}[2-9]\d{2}\d{4}$'  # Default US phone


@dataclass
class CategoryConfig:
    """Category configuration for transactions and goals"""
    transaction_categories: Set[str] = field(default_factory=set)
    goal_categories: Set[str] = field(default_factory=set)
    budget_categories: Set[str] = field(default_factory=set)


@dataclass
class SecurityConfig:
    """Security validation configuration"""
    min_password_length: int = 8
    max_password_length: int = 128
    require_uppercase: bool = True
    require_lowercase: bool = True
    require_digits: bool = True
    require_symbols: bool = False
    max_login_attempts: int = 5
    session_timeout_minutes: int = 120  # Match ACCESS_TOKEN_EXPIRE_MINUTES for consistent session duration
    suspicious_amount_threshold: Decimal = Decimal('100000')


@dataclass
class RegionConfig:
    """Complete configuration for a region"""
    region: Region
    currency: CurrencyConfig
    geographic: GeographicConfig
    categories: CategoryConfig
    security: SecurityConfig
    is_active: bool = True
    compliance_rules: Dict[str, Any] = field(default_factory=dict)


class ValidationConfigManager:
    """Manages validation configurations for different regions"""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path(__file__).parent / "validation_configs"
        self.configs: Dict[Region, RegionConfig] = {}
        self._load_default_configs()
        self._load_custom_configs()
    
    def _load_default_configs(self):
        """Load default configuration for supported regions"""
        
        # US Configuration
        us_currency = CurrencyConfig(
            code="USD",
            symbol="$",
            decimal_places=2,
            min_amount=Decimal('0.01'),
            max_transaction=Decimal('999999.99'),
            max_annual_income=Decimal('99999999.99'),
            max_budget=Decimal('9999999.99'),
            max_goal=Decimal('99999999.99')
        )
        
        us_geographic = GeographicConfig(
            country_code="US",
            country_name="United States",
            supported_states={
                "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
                "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"
            },
            postal_code_pattern=r'^\d{5}(-\d{4})?$',
            phone_pattern=r'^\+?1?[2-9]\d{2}[2-9]\d{2}\d{4}$'
        )
        
        us_categories = CategoryConfig(
            transaction_categories={
                'food', 'dining', 'groceries', 'transportation', 'gas', 'public_transport',
                'entertainment', 'shopping', 'clothing', 'healthcare', 'insurance',
                'utilities', 'rent', 'mortgage', 'education', 'childcare', 'pets',
                'travel', 'subscriptions', 'gifts', 'charity', 'income', 'other'
            },
            goal_categories={
                'savings', 'debt_payoff', 'investment', 'purchase', 'travel',
                'education', 'emergency_fund', 'retirement', 'healthcare', 'other'
            },
            budget_categories={
                'food', 'dining', 'groceries', 'transportation', 'gas', 'public_transport',
                'entertainment', 'shopping', 'clothing', 'healthcare', 'insurance',
                'utilities', 'rent', 'mortgage', 'education', 'childcare', 'pets',
                'travel', 'subscriptions', 'gifts', 'charity', 'other'
            }
        )
        
        us_security = SecurityConfig(
            min_password_length=8,
            max_password_length=128,
            require_uppercase=True,
            require_lowercase=True,
            require_digits=True,
            require_symbols=False,
            max_login_attempts=5,
            session_timeout_minutes=120,  # Match ACCESS_TOKEN_EXPIRE_MINUTES
            suspicious_amount_threshold=Decimal('100000')
        )
        
        us_config = RegionConfig(
            region=Region.US,
            currency=us_currency,
            geographic=us_geographic,
            categories=us_categories,
            security=us_security,
            is_active=True,
            compliance_rules={
                "financial_regulations": ["PCI_DSS", "SOX", "GLBA"],
                "data_protection": ["CCPA"],
                "retention_period_years": 7,
                "audit_requirements": True,
                "kyc_required": False,  # Not required for current scope
                "aml_monitoring": True
            }
        )
        
        self.configs[Region.US] = us_config
    
    def _load_custom_configs(self):
        """Load custom configurations from files if they exist"""
        if not self.config_dir.exists():
            return
        
        for config_file in self.config_dir.glob("*.yaml"):
            try:
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)
                
                region_code = config_file.stem.upper()
                if region_code in [r.value for r in Region]:
                    region = Region(region_code)
                    # Override or extend default config with custom data
                    if region in self.configs:
                        self._merge_config(self.configs[region], config_data)
                    else:
                        # Create new region config from data
                        self.configs[region] = self._create_config_from_data(region, config_data)
                
                logger.info(f"Loaded custom configuration for region: {region_code}")
            
            except Exception as e:
                logger.error(f"Failed to load configuration from {config_file}: {e}")
    
    def _merge_config(self, base_config: RegionConfig, custom_data: Dict[str, Any]):
        """Merge custom configuration data with base configuration"""
        # Implementation would merge the custom data with base config
        # This is a simplified version - full implementation would recursively merge
        if 'currency' in custom_data:
            for key, value in custom_data['currency'].items():
                if hasattr(base_config.currency, key):
                    setattr(base_config.currency, key, value)
        
        if 'security' in custom_data:
            for key, value in custom_data['security'].items():
                if hasattr(base_config.security, key):
                    setattr(base_config.security, key, value)
    
    def _create_config_from_data(self, region: Region, data: Dict[str, Any]) -> RegionConfig:
        """Create a new region configuration from data"""
        # Simplified implementation - would need full parsing logic
        currency_data = data.get('currency', {})
        currency = CurrencyConfig(
            code=currency_data.get('code', 'USD'),
            symbol=currency_data.get('symbol', '$'),
            **{k: v for k, v in currency_data.items() if k not in ['code', 'symbol']}
        )
        
        # Similar parsing for other components...
        # This is a placeholder implementation
        
        return RegionConfig(
            region=region,
            currency=currency,
            geographic=GeographicConfig(
                country_code=region.value,
                country_name=data.get('country_name', region.value)
            ),
            categories=CategoryConfig(),
            security=SecurityConfig()
        )
    
    def get_config(self, region: Region) -> Optional[RegionConfig]:
        """Get configuration for a specific region"""
        return self.configs.get(region)
    
    def get_active_regions(self) -> List[Region]:
        """Get list of active regions"""
        return [region for region, config in self.configs.items() if config.is_active]
    
    def is_region_supported(self, region: Region) -> bool:
        """Check if a region is supported and active"""
        config = self.configs.get(region)
        return config is not None and config.is_active
    
    def get_currency_config(self, region: Region) -> Optional[CurrencyConfig]:
        """Get currency configuration for a region"""
        config = self.get_config(region)
        return config.currency if config else None
    
    def get_geographic_config(self, region: Region) -> Optional[GeographicConfig]:
        """Get geographic configuration for a region"""
        config = self.get_config(region)
        return config.geographic if config else None
    
    def get_categories_config(self, region: Region) -> Optional[CategoryConfig]:
        """Get categories configuration for a region"""
        config = self.get_config(region)
        return config.categories if config else None
    
    def get_security_config(self, region: Region) -> Optional[SecurityConfig]:
        """Get security configuration for a region"""
        config = self.get_config(region)
        return config.security if config else None
    
    def export_config(self, region: Region, format: str = 'yaml') -> Optional[str]:
        """Export configuration for a region"""
        config = self.get_config(region)
        if not config:
            return None
        
        config_dict = {
            'region': region.value,
            'currency': {
                'code': config.currency.code,
                'symbol': config.currency.symbol,
                'decimal_places': config.currency.decimal_places,
                'min_amount': str(config.currency.min_amount),
                'max_transaction': str(config.currency.max_transaction),
                'max_annual_income': str(config.currency.max_annual_income),
                'max_budget': str(config.currency.max_budget),
                'max_goal': str(config.currency.max_goal)
            },
            'geographic': {
                'country_code': config.geographic.country_code,
                'country_name': config.geographic.country_name,
                'supported_states': list(config.geographic.supported_states),
                'postal_code_pattern': config.geographic.postal_code_pattern,
                'phone_pattern': config.geographic.phone_pattern
            },
            'categories': {
                'transaction_categories': list(config.categories.transaction_categories),
                'goal_categories': list(config.categories.goal_categories),
                'budget_categories': list(config.categories.budget_categories)
            },
            'security': {
                'min_password_length': config.security.min_password_length,
                'max_password_length': config.security.max_password_length,
                'require_uppercase': config.security.require_uppercase,
                'require_lowercase': config.security.require_lowercase,
                'require_digits': config.security.require_digits,
                'require_symbols': config.security.require_symbols,
                'max_login_attempts': config.security.max_login_attempts,
                'session_timeout_minutes': config.security.session_timeout_minutes,
                'suspicious_amount_threshold': str(config.security.suspicious_amount_threshold)
            },
            'is_active': config.is_active,
            'compliance_rules': config.compliance_rules
        }
        
        if format == 'yaml':
            return yaml.dump(config_dict, default_flow_style=False)
        elif format == 'json':
            return json.dumps(config_dict, indent=2)
        else:
            raise ValueError(f"Unsupported format: {format}")
    
    def validate_region_compatibility(self, region: Region) -> Dict[str, Any]:
        """Validate if a region configuration is compatible with the application"""
        config = self.get_config(region)
        if not config:
            return {"compatible": False, "errors": ["Region not configured"]}
        
        errors = []
        warnings = []
        
        # Check required fields
        if not config.currency.code:
            errors.append("Currency code is required")
        
        if not config.geographic.country_code:
            errors.append("Country code is required")
        
        if not config.categories.transaction_categories:
            errors.append("Transaction categories are required")
        
        # Check security requirements
        if config.security.min_password_length < 8:
            warnings.append("Password minimum length should be at least 8 characters")
        
        if not config.security.require_digits:
            warnings.append("Requiring digits in passwords is recommended for financial applications")
        
        # Check currency limits
        if config.currency.max_transaction <= config.currency.min_amount:
            errors.append("Maximum transaction amount must be greater than minimum amount")
        
        return {
            "compatible": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "region": region.value,
            "config_complete": len(errors) == 0 and len(warnings) == 0
        }


# Global configuration manager instance
config_manager = ValidationConfigManager()

# Convenience functions for backward compatibility
def get_current_region() -> Region:
    """Get the current active region (US for now)"""
    return Region.US

def get_supported_currencies() -> Set[str]:
    """Get set of supported currency codes"""
    currencies = set()
    for region in config_manager.get_active_regions():
        config = config_manager.get_currency_config(region)
        if config:
            currencies.add(config.code)
    return currencies

def get_supported_countries() -> Set[str]:
    """Get set of supported country codes"""
    countries = set()
    for region in config_manager.get_active_regions():
        config = config_manager.get_geographic_config(region)
        if config:
            countries.add(config.country_code)
    return countries

def get_transaction_categories(region: Region = None) -> Set[str]:
    """Get valid transaction categories for a region"""
    region = region or get_current_region()
    config = config_manager.get_categories_config(region)
    return config.transaction_categories if config else set()

def get_goal_categories(region: Region = None) -> Set[str]:
    """Get valid goal categories for a region"""
    region = region or get_current_region()
    config = config_manager.get_categories_config(region)
    return config.goal_categories if config else set()

def get_currency_limits(region: Region = None) -> Dict[str, Decimal]:
    """Get currency limits for a region"""
    region = region or get_current_region()
    config = config_manager.get_currency_config(region)
    if not config:
        return {}
    
    return {
        "min_amount": config.min_amount,
        "max_transaction": config.max_transaction,
        "max_annual_income": config.max_annual_income,
        "max_budget": config.max_budget,
        "max_goal": config.max_goal
    }