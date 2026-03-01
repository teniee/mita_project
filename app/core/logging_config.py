"""
Comprehensive Logging Configuration
Sets up structured logging with audit trails, security monitoring, and performance tracking
"""

import logging
import logging.config
import sys
import json
from datetime import datetime
from pathlib import Path

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON"""
        # Base log data
        log_data = {
            'timestamp': datetime.utcnow().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'thread': record.thread,
            'thread_name': record.threadName,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add any extra fields from the record
        extra_fields = {
            key: value for key, value in record.__dict__.items()
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'lineno', 'funcName', 'created',
                'msecs', 'relativeCreated', 'thread', 'threadName', 'processName',
                'process', 'message', 'exc_info', 'exc_text', 'stack_info'
            }
        }
        
        if extra_fields:
            log_data.update(extra_fields)
        
        return json.dumps(log_data, ensure_ascii=False)


class SecurityLogFilter(logging.Filter):
    """Filter for security-related log messages"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter security-related messages"""
        security_keywords = [
            'security', 'auth', 'login', 'permission', 'violation',
            'injection', 'xss', 'csrf', 'attack', 'unauthorized',
            'forbidden', 'suspicious', 'threat', 'breach'
        ]
        
        message = record.getMessage().lower()
        return any(keyword in message for keyword in security_keywords)


class AuditLogFilter(logging.Filter):
    """Filter for audit-related log messages"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter audit-related messages"""
        audit_keywords = [
            'audit', 'request', 'response', 'data_access',
            'data_modification', 'user_action', 'compliance'
        ]
        
        message = record.getMessage().lower()
        logger_name = record.name.lower()
        
        return (
            any(keyword in message for keyword in audit_keywords) or
            'audit' in logger_name
        )


class PerformanceLogFilter(logging.Filter):
    """Filter for performance-related log messages"""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filter performance-related messages"""
        performance_keywords = [
            'performance', 'slow', 'timeout', 'response_time',
            'database', 'query', 'cache', 'memory', 'cpu'
        ]
        
        message = record.getMessage().lower()
        return any(keyword in message for keyword in performance_keywords)


def setup_logging() -> None:
    """Set up comprehensive logging configuration"""
    
    # Create logs directory
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Get log level from settings
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO').upper()
    
    # Logging configuration
    logging_config = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'standard': {
                'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'detailed': {
                'format': '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d %(funcName)s(): %(message)s',
                'datefmt': '%Y-%m-%d %H:%M:%S'
            },
            'json': {
                '()': JSONFormatter,
            }
        },
        'filters': {
            'security_filter': {
                '()': SecurityLogFilter,
            },
            'audit_filter': {
                '()': AuditLogFilter,
            },
            'performance_filter': {
                '()': PerformanceLogFilter,
            }
        },
        'handlers': {
            'console': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'standard',
                'stream': sys.stdout
            },
            'file': {
                'level': log_level,
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'detailed',
                'filename': log_dir / 'mita.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf8'
            },
            'json_file': {
                'level': log_level,
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'json',
                'filename': log_dir / 'mita.json.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'encoding': 'utf8'
            },
            'security_file': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'json',
                'filename': log_dir / 'security.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,  # Keep more security logs
                'filters': ['security_filter'],
                'encoding': 'utf8'
            },
            'audit_file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'json',
                'filename': log_dir / 'audit.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 30,  # Keep audit logs longer
                'filters': ['audit_filter'],
                'encoding': 'utf8'
            },
            'performance_file': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'json',
                'filename': log_dir / 'performance.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 7,
                'filters': ['performance_filter'],
                'encoding': 'utf8'
            },
            'error_file': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'formatter': 'json',
                'filename': log_dir / 'errors.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'encoding': 'utf8'
            }
        },
        'loggers': {
            # Root logger
            '': {
                'handlers': ['console', 'file', 'json_file'],
                'level': log_level,
                'propagate': False
            },
            # Application loggers
            'app': {
                'handlers': ['console', 'file', 'json_file', 'error_file'],
                'level': log_level,
                'propagate': False
            },
            # Security logger
            'app.core.security': {
                'handlers': ['console', 'security_file', 'error_file'],
                'level': 'INFO',
                'propagate': False
            },
            # Audit logger
            'app.core.audit_logging': {
                'handlers': ['audit_file', 'error_file'],
                'level': 'INFO',
                'propagate': False
            },
            # Error monitoring logger
            'app.core.error_monitoring': {
                'handlers': ['console', 'error_file'],
                'level': 'INFO',
                'propagate': False
            },
            # Database logger
            'sqlalchemy': {
                'handlers': ['performance_file'],
                'level': 'WARNING',
                'propagate': False
            },
            'sqlalchemy.engine': {
                'handlers': ['performance_file'],
                'level': 'WARNING',
                'propagate': False
            },
            # FastAPI logger
            'fastapi': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False
            },
            'uvicorn': {
                'handlers': ['console', 'file'],
                'level': 'INFO',
                'propagate': False
            },
            'uvicorn.access': {
                'handlers': ['audit_file'],
                'level': 'INFO',
                'propagate': False
            }
        }
    }
    
    # Apply configuration
    logging.config.dictConfig(logging_config)
    
    # Log startup message
    logger = logging.getLogger('app.core.logging_config')
    logger.info(f"Logging configured with level: {log_level}")
    logger.info(f"Log files will be written to: {log_dir.absolute()}")


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the specified name"""
    return logging.getLogger(name)


def log_structured(
    logger: logging.Logger,
    level: str,
    message: str,
    **kwargs
) -> None:
    """Log a structured message with additional context"""
    extra_data = {
        'structured_data': kwargs,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    log_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(log_level, message, extra=extra_data)


# Security logging helpers
def log_security_event(message: str, **context):
    """Log a security event with structured data"""
    logger = get_logger('app.core.security')
    log_structured(logger, 'WARNING', f"SECURITY: {message}", **context)


def log_audit_event(message: str, **context):
    """Log an audit event with structured data"""
    logger = get_logger('app.core.audit_logging')
    log_structured(logger, 'INFO', f"AUDIT: {message}", **context)


def log_performance_event(message: str, **context):
    """Log a performance event with structured data"""
    logger = get_logger('app.performance')
    log_structured(logger, 'INFO', f"PERFORMANCE: {message}", **context)


def log_error_event(message: str, **context):
    """Log an error event with structured data"""
    logger = get_logger('app.core.error_monitoring')
    log_structured(logger, 'ERROR', f"ERROR: {message}", **context)


# Initialize logging when module is imported
setup_logging()