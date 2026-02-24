from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

def role_required(*roles):
    """
    Décorateur pour restreindre l'accès aux utilisateurs ayant certains rôles
    Utilisation : @role_required('super_admin', 'admin_clinique', 'medecin')
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Veuillez vous connecter pour accéder à cette page.', 'warning')
                return redirect(url_for('auth.login'))
            if current_user.role not in roles:
                flash('Vous n\'avez pas les droits pour accéder à cette page.', 'danger')
                return redirect(url_for('appointments.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def super_admin_required(f):
    """Décorateur pour super_admin uniquement"""
    return role_required('super_admin')(f)

def admin_clinique_required(f):
    """Décorateur pour admin_clinique et super_admin"""
    return role_required('super_admin', 'admin_clinique')(f)

def medecin_required(f):
    """Décorateur pour médecins et admins"""
    return role_required('super_admin', 'admin_clinique', 'medecin')(f)

def secretaire_required(f):
    """Décorateur pour secrétaires et admins"""
    return role_required('super_admin', 'admin_clinique', 'secretaire')(f)