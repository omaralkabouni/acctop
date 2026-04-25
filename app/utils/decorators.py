"""Helper decorators for RBAC and audit trail."""
from functools import wraps
from flask import abort, request, current_app
from flask_login import current_user
from ..extensions import db
from ..models.audit import AuditLog
import json


def role_required(*roles):
    """Restrict route to specific roles."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role.name not in roles:
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission):
    """Restrict route to users with a specific permission."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.can(permission):
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def audit_trail(action, entity):
    """Log financial actions to audit log."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            try:
                log = AuditLog(
                    user_id=current_user.id if current_user.is_authenticated else None,
                    action=action,
                    entity=entity,
                    ip_address=request.remote_addr,
                )
                db.session.add(log)
                db.session.commit()
            except Exception:
                pass
            return result
        return decorated_function
    return decorator


def log_action(user_id, action, entity, entity_id, old_values=None, new_values=None):
    """Direct function to log an audit entry."""
    try:
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            old_values=json.dumps(old_values, ensure_ascii=False, default=str) if old_values else None,
            new_values=json.dumps(new_values, ensure_ascii=False, default=str) if new_values else None,
            ip_address=request.remote_addr if request else None,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()
