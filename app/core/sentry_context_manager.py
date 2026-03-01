"""
Advanced Sentry Context Management for MITA Finance
Provides comprehensive context tracking, custom error handlers, and financial compliance monitoring
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from enum import Enum

from sentry_sdk import (
    set_user, set_tag, set_context, add_breadcrumb,
    push_scope, capture_message
)

logger = logging.getLogger(__name__)


class FinancialComplianceLevel(Enum):
    """Financial compliance levels for data classification"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"  # PCI DSS, sensitive financial data


class AuditEventType(Enum):
    """Types of audit events for financial compliance"""
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    TRANSACTION_CREATE = "transaction_create"
    TRANSACTION_UPDATE = "transaction_update"
    TRANSACTION_DELETE = "transaction_delete"
    PAYMENT_PROCESS = "payment_process"
    DATA_ACCESS = "data_access"
    DATA_EXPORT = "data_export"
    SECURITY_EVENT = "security_event"
    CONFIGURATION_CHANGE = "configuration_change"
    ERROR_OCCURRED = "error_occurred"


@dataclass
class FinancialContext:
    """Comprehensive financial operation context"""
    user_id: Optional[str] = None
    transaction_id: Optional[str] = None
    amount: Optional[float] = None
    currency: Optional[str] = None
    account_id: Optional[str] = None
    merchant: Optional[str] = None
    category: Optional[str] = None
    compliance_level: FinancialComplianceLevel = FinancialComplianceLevel.CONFIDENTIAL
    audit_required: bool = True
    pci_scope: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for Sentry context"""
        data = asdict(self)
        data['compliance_level'] = self.compliance_level.value
        return data


@dataclass
class UserContext:
    """Enhanced user context for financial applications"""
    user_id: str
    email: Optional[str] = None
    subscription_tier: Optional[str] = None
    account_type: Optional[str] = None
    risk_level: Optional[str] = None
    location: Optional[str] = None
    device_info: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    last_login: Optional[datetime] = None
    
    def to_sentry_user(self) -> Dict[str, Any]:
        """Convert to Sentry user format"""
        return {
            "id": self.user_id,
            "email": self.email,
            "data": {
                "subscription_tier": self.subscription_tier,
                "account_type": self.account_type,
                "risk_level": self.risk_level,
                "location": self.location,
                "device_info": self.device_info,
                "session_id": self.session_id,
                "ip_address": self.ip_address,
                "last_login": self.last_login.isoformat() if self.last_login else None
            }
        }


class SentryContextManager:
    """Advanced context management for financial applications"""
    
    def __init__(self):
        self.current_contexts: Dict[str, Any] = {}
        self.audit_trail: List[Dict[str, Any]] = []
        self.max_audit_entries = 1000
    
    @contextmanager
    def financial_operation_context(
        self,
        operation_name: str,
        financial_ctx: FinancialContext,
        user_ctx: Optional[UserContext] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        """Context manager for financial operations with comprehensive tracking"""
        
        operation_id = f"{operation_name}_{datetime.utcnow().isoformat()}"
        start_time = datetime.utcnow()
        
        with push_scope() as scope:
            try:
                # Set financial operation tags
                scope.set_tag("financial_operation", operation_name)
                scope.set_tag("compliance_level", financial_ctx.compliance_level.value)
                scope.set_tag("audit_required", financial_ctx.audit_required)
                scope.set_tag("pci_scope", financial_ctx.pci_scope)
                scope.set_tag("operation_id", operation_id)
                
                # Set user context
                if user_ctx:
                    scope.set_user(user_ctx.to_sentry_user())
                elif financial_ctx.user_id:
                    scope.set_user({"id": financial_ctx.user_id})
                
                # Set financial context
                scope.set_context("financial_operation", {
                    "name": operation_name,
                    "operation_id": operation_id,
                    "start_time": start_time.isoformat(),
                    **financial_ctx.to_dict()
                })
                
                # Set compliance context
                scope.set_context("compliance", {
                    "pci_dss_applicable": financial_ctx.pci_scope,
                    "data_classification": financial_ctx.compliance_level.value,
                    "audit_trail_required": financial_ctx.audit_required,
                    "retention_period": "7_years" if financial_ctx.pci_scope else "1_year",
                    "monitoring_level": "enhanced"
                })
                
                # Set additional context
                if additional_context:
                    for key, value in additional_context.items():
                        scope.set_extra(key, value)
                
                # Add operation start breadcrumb
                add_breadcrumb(
                    message=f"Starting financial operation: {operation_name}",
                    category="financial_operation",
                    level="info",
                    data={
                        "operation": operation_name,
                        "operation_id": operation_id,
                        "user_id": financial_ctx.user_id,
                        "transaction_id": financial_ctx.transaction_id,
                        "compliance_level": financial_ctx.compliance_level.value
                    }
                )
                
                # Store current context
                self.current_contexts[operation_id] = {
                    "operation_name": operation_name,
                    "financial_context": financial_ctx.to_dict(),
                    "user_context": user_ctx.to_sentry_user() if user_ctx else None,
                    "start_time": start_time,
                    "additional_context": additional_context
                }
                
                # Record audit event
                self._record_audit_event(
                    event_type=AuditEventType.DATA_ACCESS,
                    operation_name=operation_name,
                    user_id=financial_ctx.user_id,
                    details={
                        "operation_id": operation_id,
                        "compliance_level": financial_ctx.compliance_level.value,
                        "context": "operation_start"
                    }
                )
                
                yield {
                    "operation_id": operation_id,
                    "start_time": start_time,
                    "scope": scope,
                    "set_result": lambda result: scope.set_extra("operation_result", str(type(result).__name__)),
                    "add_metadata": lambda key, value: scope.set_extra(key, value)
                }
                
                # Record successful completion
                duration = datetime.utcnow() - start_time
                
                add_breadcrumb(
                    message=f"Completed financial operation: {operation_name}",
                    category="financial_success",
                    level="info",
                    data={
                        "operation": operation_name,
                        "operation_id": operation_id,
                        "duration_ms": duration.total_seconds() * 1000,
                        "success": True
                    }
                )
                
                self._record_audit_event(
                    event_type=AuditEventType.DATA_ACCESS,
                    operation_name=operation_name,
                    user_id=financial_ctx.user_id,
                    details={
                        "operation_id": operation_id,
                        "duration_ms": duration.total_seconds() * 1000,
                        "context": "operation_success"
                    }
                )
                
            except Exception as e:
                # Record failed operation
                duration = datetime.utcnow() - start_time
                
                add_breadcrumb(
                    message=f"Failed financial operation: {operation_name}",
                    category="financial_error",
                    level="error",
                    data={
                        "operation": operation_name,
                        "operation_id": operation_id,
                        "duration_ms": duration.total_seconds() * 1000,
                        "error": str(e),
                        "success": False
                    }
                )
                
                self._record_audit_event(
                    event_type=AuditEventType.ERROR_OCCURRED,
                    operation_name=operation_name,
                    user_id=financial_ctx.user_id,
                    details={
                        "operation_id": operation_id,
                        "duration_ms": duration.total_seconds() * 1000,
                        "error": str(e),
                        "context": "operation_failure"
                    }
                )
                
                raise
                
            finally:
                # Clean up context
                if operation_id in self.current_contexts:
                    del self.current_contexts[operation_id]
    
    def set_financial_user_context(self, user_ctx: UserContext):
        """Set comprehensive user context for financial operations"""
        
        set_user(user_ctx.to_sentry_user())
        
        # Set user-related tags
        set_tag("user_authenticated", True)
        set_tag("subscription_tier", user_ctx.subscription_tier or "unknown")
        set_tag("account_type", user_ctx.account_type or "unknown")
        set_tag("risk_level", user_ctx.risk_level or "unknown")
        
        # Set user context for compliance
        set_context("user_details", {
            "user_id": user_ctx.user_id,
            "subscription_tier": user_ctx.subscription_tier,
            "account_type": user_ctx.account_type,
            "risk_level": user_ctx.risk_level,
            "location": user_ctx.location,
            "last_login": user_ctx.last_login.isoformat() if user_ctx.last_login else None
        })
        
        # Add user context breadcrumb
        add_breadcrumb(
            message="User context set",
            category="user_context",
            level="info",
            data={
                "user_id": user_ctx.user_id,
                "subscription_tier": user_ctx.subscription_tier,
                "account_type": user_ctx.account_type,
                "session_id": user_ctx.session_id
            }
        )
        
        # Record audit event
        self._record_audit_event(
            event_type=AuditEventType.USER_LOGIN,
            user_id=user_ctx.user_id,
            details={
                "session_id": user_ctx.session_id,
                "ip_address": user_ctx.ip_address,
                "device_info": user_ctx.device_info,
                "context": "user_context_set"
            }
        )
    
    def clear_user_context(self, user_id: Optional[str] = None):
        """Clear user context (e.g., on logout)"""
        
        # Record logout event before clearing context
        if user_id:
            self._record_audit_event(
                event_type=AuditEventType.USER_LOGOUT,
                user_id=user_id,
                details={"context": "user_context_cleared"}
            )
        
        # Clear Sentry user context
        set_user(None)
        
        # Remove user-related tags
        set_tag("user_authenticated", False)
        set_tag("subscription_tier", None)
        set_tag("account_type", None)
        set_tag("risk_level", None)
        
        add_breadcrumb(
            message="User context cleared",
            category="user_context",
            level="info",
            data={"user_id": user_id, "action": "logout"}
        )
    
    def set_transaction_context(
        self,
        transaction_id: str,
        user_id: str,
        amount: float,
        currency: str,
        transaction_type: str,
        merchant: Optional[str] = None,
        category: Optional[str] = None
    ):
        """Set transaction-specific context"""
        
        set_tag("transaction_id", transaction_id)
        set_tag("transaction_type", transaction_type)
        set_tag("currency", currency)
        
        set_context("transaction", {
            "transaction_id": transaction_id,
            "user_id": user_id,
            "amount": amount,
            "currency": currency,
            "transaction_type": transaction_type,
            "merchant": merchant,
            "category": category,
            "timestamp": datetime.utcnow().isoformat(),
            "compliance_scope": "pci_dss"
        })
        
        add_breadcrumb(
            message=f"Transaction context set: {transaction_type}",
            category="transaction",
            level="info",
            data={
                "transaction_id": transaction_id,
                "user_id": user_id,
                "amount": amount,
                "currency": currency,
                "merchant": merchant
            }
        )
        
        # Record audit event
        self._record_audit_event(
            event_type=AuditEventType.TRANSACTION_CREATE,
            operation_name=f"transaction_{transaction_type}",
            user_id=user_id,
            details={
                "transaction_id": transaction_id,
                "amount": amount,
                "currency": currency,
                "merchant": merchant,
                "category": category
            }
        )
    
    def set_security_context(
        self,
        event_type: str,
        severity: str,
        details: Dict[str, Any],
        user_id: Optional[str] = None
    ):
        """Set security event context"""
        
        set_tag("security_event", True)
        set_tag("security_event_type", event_type)
        set_tag("security_severity", severity)
        
        set_context("security", {
            "event_type": event_type,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details,
            "compliance_impact": "high" if severity in ["critical", "high"] else "medium"
        })
        
        add_breadcrumb(
            message=f"Security event: {event_type}",
            category="security",
            level="warning" if severity in ["critical", "high"] else "info",
            data={
                "event_type": event_type,
                "severity": severity,
                "user_id": user_id,
                **details
            }
        )
        
        # Record security audit event
        self._record_audit_event(
            event_type=AuditEventType.SECURITY_EVENT,
            operation_name=f"security_{event_type}",
            user_id=user_id,
            details={
                "severity": severity,
                "event_details": details,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    
    def set_compliance_context(
        self,
        regulation: str,
        requirement: str,
        status: str,
        details: Optional[Dict[str, Any]] = None
    ):
        """Set compliance-related context"""
        
        set_tag("compliance_regulation", regulation)
        set_tag("compliance_requirement", requirement)
        set_tag("compliance_status", status)
        
        set_context("compliance", {
            "regulation": regulation,
            "requirement": requirement,
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "details": details or {}
        })
        
        add_breadcrumb(
            message=f"Compliance check: {regulation} - {requirement}",
            category="compliance",
            level="warning" if status == "non_compliant" else "info",
            data={
                "regulation": regulation,
                "requirement": requirement,
                "status": status,
                "details": details
            }
        )
    
    def capture_financial_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        operation: str,
        user_id: Optional[str] = None,
        additional_tags: Optional[Dict[str, str]] = None
    ):
        """Capture performance metrics for financial operations"""
        
        # Set performance context
        set_context("performance", {
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "operation": operation,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id
        })
        
        # Set performance tags
        set_tag("performance_metric", metric_name)
        set_tag("performance_operation", operation)
        
        if additional_tags:
            for key, value in additional_tags.items():
                set_tag(f"perf_{key}", value)
        
        # Add performance breadcrumb
        add_breadcrumb(
            message=f"Performance metric: {metric_name} = {value} {unit}",
            category="performance",
            level="info",
            data={
                "metric": metric_name,
                "value": value,
                "unit": unit,
                "operation": operation,
                "user_id": user_id
            }
        )
        
        # Log slow operations
        if metric_name == "duration_ms" and value > 2000:  # 2 seconds threshold
            logger.warning(
                f"Slow financial operation detected: {operation} took {value}ms for user {user_id}"
            )
            
            capture_message(
                f"Slow financial operation: {operation}",
                level="warning",
                extras={
                    "duration_ms": value,
                    "operation": operation,
                    "user_id": user_id,
                    "threshold_exceeded": True
                }
            )
    
    def _record_audit_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        operation_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Record audit event for compliance"""
        
        audit_entry = {
            "event_type": event_type.value,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "operation_name": operation_name,
            "details": details or {},
            "source": "sentry_context_manager"
        }
        
        self.audit_trail.append(audit_entry)
        
        # Trim audit trail if too large
        if len(self.audit_trail) > self.max_audit_entries:
            self.audit_trail = self.audit_trail[-self.max_audit_entries:]
        
        # Add audit breadcrumb
        add_breadcrumb(
            message=f"Audit event: {event_type.value}",
            category="audit",
            level="info",
            data=audit_entry
        )
    
    def get_audit_trail(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[AuditEventType] = None,
        hours_back: int = 24
    ) -> List[Dict[str, Any]]:
        """Get audit trail for compliance reporting"""
        
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_back)
        
        filtered_trail = []
        for entry in self.audit_trail:
            entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            
            if entry_time < cutoff_time:
                continue
            
            if user_id and entry.get("user_id") != user_id:
                continue
                
            if event_type and entry.get("event_type") != event_type.value:
                continue
            
            filtered_trail.append(entry)
        
        return filtered_trail
    
    def export_compliance_report(
        self,
        output_file: str,
        user_id: Optional[str] = None,
        days_back: int = 30
    ):
        """Export compliance report for audit purposes"""
        
        audit_data = self.get_audit_trail(
            user_id=user_id,
            hours_back=days_back * 24
        )
        
        report = {
            "report_generated": datetime.utcnow().isoformat(),
            "report_period_days": days_back,
            "user_filter": user_id,
            "total_events": len(audit_data),
            "audit_events": audit_data,
            "summary": self._generate_audit_summary(audit_data)
        }
        
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Compliance report exported to {output_file}")
        
        # Record export event
        self._record_audit_event(
            event_type=AuditEventType.DATA_EXPORT,
            details={
                "export_file": output_file,
                "report_period_days": days_back,
                "user_filter": user_id,
                "total_events": len(audit_data)
            }
        )
    
    def _generate_audit_summary(self, audit_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics for audit data"""
        
        if not audit_data:
            return {"message": "No audit data available"}
        
        # Count events by type
        event_counts = {}
        user_activity = {}
        
        for entry in audit_data:
            event_type = entry.get("event_type", "unknown")
            user_id = entry.get("user_id")
            
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            
            if user_id:
                if user_id not in user_activity:
                    user_activity[user_id] = []
                user_activity[user_id].append(entry)
        
        return {
            "total_events": len(audit_data),
            "event_type_counts": event_counts,
            "unique_users": len(user_activity),
            "most_active_user": max(user_activity.items(), key=lambda x: len(x[1]))[0] if user_activity else None,
            "period_start": min(entry["timestamp"] for entry in audit_data),
            "period_end": max(entry["timestamp"] for entry in audit_data)
        }


# Global instance
sentry_context_manager = SentryContextManager()


# Convenience functions
def set_financial_user(user_ctx: UserContext):
    """Set financial user context"""
    return sentry_context_manager.set_financial_user_context(user_ctx)


def clear_user():
    """Clear user context"""
    return sentry_context_manager.clear_user_context()


def set_transaction(transaction_id: str, user_id: str, amount: float, currency: str, **kwargs):
    """Set transaction context"""
    return sentry_context_manager.set_transaction_context(
        transaction_id, user_id, amount, currency, **kwargs
    )


def financial_operation(operation_name: str, financial_ctx: FinancialContext, **kwargs):
    """Financial operation context manager"""
    return sentry_context_manager.financial_operation_context(
        operation_name, financial_ctx, **kwargs
    )