from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, current_user, logout_user, login_required
from app import db, bcrypt, limiter
from models import User
from app.utils.decorators import super_admin_required

auth_bp = Blueprint('auth', __name__)

# =======================================================
# CONNEXION (avec vérification clinique)
# =======================================================
@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Page de connexion"""
    if current_user.is_authenticated:
        return redirect(url_for('appointments.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = True if request.form.get('remember') else False
        
        if not email or not password:
            flash('Veuillez remplir tous les champs', 'danger')
            return render_template('login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and bcrypt.check_password_hash(user.mot_de_passe_hash, password):
            
            # Vérifier que l'utilisateur est actif
            if not user.actif:
                flash('Votre compte est désactivé. Contactez l\'administrateur.', 'danger')
                return render_template('login.html')
            
            # Vérifier que l'utilisateur appartient à une clinique (sauf super_admin)
            if user.role != 'super_admin' and not user.clinique_id:
                flash('Votre compte n\'est pas associé à une clinique. Contactez l\'administrateur.', 'danger')
                return render_template('login.html')
            
            # Vérifier que la clinique est active (sauf super_admin)
            if user.role != 'super_admin' and user.clinique:
                if not user.clinique.abonnement_actif:
                    flash('L\'abonnement de votre clinique a expiré. Contactez l\'administrateur.', 'danger')
                    return render_template('login.html')
            
            login_user(user, remember=remember)
            next_page = request.args.get('next')
            
            flash(f'Bienvenue {user.nom}!', 'success')
            return redirect(next_page) if next_page else redirect(url_for('appointments.dashboard'))
        else:
            flash('Email ou mot de passe incorrect', 'danger')
    
    return render_template('login.html')

# =======================================================
# INSCRIPTION (réservée au super_admin)
# =======================================================
@auth_bp.route('/register', methods=['GET', 'POST'])
@login_required
@super_admin_required
def register():
    """Page d'inscription désactivée - seule la création via admin est possible"""
    flash('L\'inscription publique est désactivée. Seul l\'administrateur peut créer des comptes via le panel admin.', 'warning')
    return redirect(url_for('auth.login'))

# =======================================================
# DÉCONNEXION
# =======================================================
@auth_bp.route('/logout')
@login_required
def logout():
    """Déconnexion"""
    nom = current_user.nom
    logout_user()
    flash(f'À bientôt {nom}!', 'info')
    return redirect(url_for('auth.login'))

# =======================================================
# PROFIL UTILISATEUR
# =======================================================
@auth_bp.route('/profil')
@login_required
def profil():
    """Page de profil utilisateur"""
    return render_template('profil.html', user=current_user)

@auth_bp.route('/profil/modifier', methods=['POST'])
@login_required
def modifier_profil():
    """Modifier les informations du profil"""
    nom = request.form.get('nom', '').strip()
    telephone = request.form.get('telephone', '').strip()
    specialite = request.form.get('specialite', '').strip()
    
    if nom and len(nom) >= 2:
        current_user.nom = nom
    
    if telephone and len(telephone) >= 9:
        current_user.telephone = telephone
    
    if specialite:
        current_user.specialite = specialite
    
    db.session.commit()
    flash('Profil mis à jour avec succès', 'success')
    return redirect(url_for('auth.profil'))

@auth_bp.route('/changer-mot-de-passe', methods=['POST'])
@login_required
@limiter.limit("3 per hour")
def changer_mot_de_passe():
    """Changer le mot de passe"""
    ancien = request.form.get('ancien_mot_de_passe', '')
    nouveau = request.form.get('nouveau_mot_de_passe', '')
    confirmer = request.form.get('confirmer_mot_de_passe', '')
    
    if not bcrypt.check_password_hash(current_user.mot_de_passe_hash, ancien):
        flash('Ancien mot de passe incorrect', 'danger')
        return redirect(url_for('auth.profil'))
    
    if len(nouveau) < 6:
        flash('Le nouveau mot de passe doit contenir au moins 6 caractères', 'danger')
        return redirect(url_for('auth.profil'))
    
    if nouveau != confirmer:
        flash('Les mots de passe ne correspondent pas', 'danger')
        return redirect(url_for('auth.profil'))
    
    current_user.mot_de_passe_hash = bcrypt.generate_password_hash(nouveau).decode('utf-8')
    db.session.commit()
    
    flash('Mot de passe changé avec succès', 'success')
    return redirect(url_for('auth.profil'))


# =======================================================
# CHANGEMENT DE LANGUE (AJOUTER À LA FIN)
# =======================================================
@auth_bp.route('/changer-langue/<lang>')
@login_required
def changer_langue(lang):
    """Changer la langue de l'interface"""
    if lang in ['fr', 'en']:
        session['language'] = lang
        flash('Langue changée avec succès', 'success')
    return redirect(request.referrer or url_for('appointments.dashboard'))