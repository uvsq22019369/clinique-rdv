from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, make_response, jsonify
from flask_login import login_required, current_user
from app import db, bcrypt
from models import User, Patient, Appointment, Prescription, Clinique
from app.utils.decorators import admin_clinique_required, medecin_required, super_admin_required
from app.utils.pdf_generator import generer_ordonnance
from datetime import datetime, timedelta
import os
import secrets
import csv
import pandas as pd
from io import BytesIO, StringIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

admin_bp = Blueprint('admin', __name__)

# =======================================================
# GESTION DES CLINIQUES (super_admin uniquement)
# =======================================================
@admin_bp.route('/cliniques')
@login_required
@super_admin_required
def liste_cliniques():
    """Liste toutes les cliniques (super_admin uniquement)"""
    cliniques = Clinique.query.order_by(Clinique.nom).all()
    return render_template('admin/cliniques.html', cliniques=cliniques)

@admin_bp.route('/cliniques/ajouter', methods=['POST'])
@login_required
@super_admin_required
def ajouter_clinique():
    """Ajouter une nouvelle clinique"""
    nom = request.form.get('nom', '').strip()
    slug = request.form.get('slug', '').strip().lower()
    email = request.form.get('email', '').strip()
    telephone = request.form.get('telephone', '').strip()
    adresse = request.form.get('adresse', '').strip()
    
    if not nom or not slug:
        flash('Le nom et le slug sont obligatoires', 'danger')
        return redirect(url_for('admin.liste_cliniques'))
    
    if Clinique.query.filter_by(slug=slug).first():
        flash('Ce slug est déjà utilisé', 'danger')
        return redirect(url_for('admin.liste_cliniques'))
    
    clinique = Clinique(
        nom=nom,
        slug=slug,
        email=email,
        telephone=telephone,
        adresse=adresse,
        abonnement_actif=True,
        date_debut_abonnement=datetime.now(),
        date_fin_abonnement=datetime.now() + timedelta(days=365)
    )
    
    db.session.add(clinique)
    db.session.commit()
    
    flash(f'Clinique {nom} créée avec succès (abonnement jusqu\'au {clinique.date_fin_abonnement.strftime("%d/%m/%Y")})', 'success')
    return redirect(url_for('admin.liste_cliniques'))

@admin_bp.route('/cliniques/renouveler/<int:clinique_id>', methods=['POST'])
@login_required
@super_admin_required
def renouveler_abonnement(clinique_id):
    """Renouveler l'abonnement d'une clinique (ajouter 1 an)"""
    clinique = Clinique.query.get_or_404(clinique_id)
    
    if clinique.date_fin_abonnement and clinique.date_fin_abonnement > datetime.now():
        clinique.date_fin_abonnement += timedelta(days=365)
    else:
        clinique.date_fin_abonnement = datetime.now() + timedelta(days=365)
    
    clinique.abonnement_actif = True
    db.session.commit()
    
    flash(f'Abonnement de {clinique.nom} renouvelé jusqu\'au {clinique.date_fin_abonnement.strftime("%d/%m/%Y")}', 'success')
    return redirect(url_for('admin.liste_cliniques'))

@admin_bp.route('/cliniques/desactiver/<int:clinique_id>')
@login_required
@super_admin_required
def desactiver_clinique(clinique_id):
    """Désactiver une clinique"""
    clinique = Clinique.query.get_or_404(clinique_id)
    clinique.abonnement_actif = False
    db.session.commit()
    flash(f'Clinique {clinique.nom} désactivée', 'warning')
    return redirect(url_for('admin.liste_cliniques'))

@admin_bp.route('/cliniques/activer/<int:clinique_id>')
@login_required
@super_admin_required
def activer_clinique(clinique_id):
    """Activer une clinique"""
    clinique = Clinique.query.get_or_404(clinique_id)
    clinique.abonnement_actif = True
    db.session.commit()
    flash(f'Clinique {clinique.nom} activée', 'success')
    return redirect(url_for('admin.liste_cliniques'))

# =======================================================
# GESTION DES SECRÉTAIRES
# =======================================================
@admin_bp.route('/secretaires')
@login_required
@admin_clinique_required
def liste_secretaires():
    """Liste les secrétaires de la clinique"""
    cliniques = Clinique.query.all() if current_user.role == 'super_admin' else []
    
    if current_user.role == 'super_admin':
        secretaires = User.query.filter_by(role='secretaire').order_by(User.nom).all()
    else:
        secretaires = User.query.filter_by(
            role='secretaire',
            clinique_id=current_user.clinique_id
        ).order_by(User.nom).all()
    
    return render_template('admin/secretaires.html', secretaires=secretaires, cliniques=cliniques)

@admin_bp.route('/secretaires/ajouter', methods=['POST'])
@login_required
@admin_clinique_required
def ajouter_secretaire():
    """Ajouter un secrétaire"""
    nom = request.form.get('nom', '').strip()
    email = request.form.get('email', '').strip().lower()
    telephone = request.form.get('telephone', '').strip()
    
    if current_user.role == 'super_admin':
        clinique_id = request.form.get('clinique_id')
        if not clinique_id:
            flash('Veuillez sélectionner une clinique', 'danger')
            return redirect(url_for('admin.liste_secretaires'))
    else:
        clinique_id = current_user.clinique_id
    
    errors = []
    if not nom or len(nom) < 2:
        errors.append("Le nom doit contenir au moins 2 caractères")
    if not email or '@' not in email:
        errors.append("Email invalide")
    if not telephone or len(telephone) < 9:
        errors.append("Numéro de téléphone invalide")
    
    if User.query.filter_by(email=email).first():
        errors.append("Cet email est déjà utilisé")
    
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('admin.liste_secretaires'))
    
    temp_password = secrets.token_urlsafe(8)
    hashed_password = bcrypt.generate_password_hash(temp_password).decode('utf-8')
    
    secretaire = User(
        nom=nom,
        email=email,
        mot_de_passe_hash=hashed_password,
        telephone=telephone,
        role='secretaire',
        actif=True,
        clinique_id=clinique_id
    )
    
    db.session.add(secretaire)
    db.session.commit()
    
    flash(f'✅ Secrétaire {nom} ajouté(e) avec succès!', 'success')
    flash(f'📧 Email: {email} | 🔑 Mot de passe temporaire: {temp_password}', 'info')
    return redirect(url_for('admin.liste_secretaires'))

@admin_bp.route('/secretaires/desactiver/<int:user_id>')
@login_required
@admin_clinique_required
def desactiver_secretaire(user_id):
    """Désactiver un secrétaire"""
    secretaire = User.query.get_or_404(user_id)
    
    if current_user.role != 'super_admin' and secretaire.clinique_id != current_user.clinique_id:
        flash('Vous ne pouvez pas modifier ce compte', 'danger')
        return redirect(url_for('admin.liste_secretaires'))
    
    if secretaire.role == 'secretaire':
        secretaire.actif = False
        db.session.commit()
        flash(f'Secrétaire {secretaire.nom} désactivé(e)', 'warning')
    return redirect(url_for('admin.liste_secretaires'))

@admin_bp.route('/secretaires/activer/<int:user_id>')
@login_required
@admin_clinique_required
def activer_secretaire(user_id):
    """Réactiver un secrétaire"""
    secretaire = User.query.get_or_404(user_id)
    
    if current_user.role != 'super_admin' and secretaire.clinique_id != current_user.clinique_id:
        flash('Vous ne pouvez pas modifier ce compte', 'danger')
        return redirect(url_for('admin.liste_secretaires'))
    
    if secretaire.role == 'secretaire':
        secretaire.actif = True
        db.session.commit()
        flash(f'Secrétaire {secretaire.nom} activé(e)', 'success')
    return redirect(url_for('admin.liste_secretaires'))

@admin_bp.route('/secretaires/reinitialiser-mot-de-passe/<int:user_id>')
@login_required
@admin_clinique_required
def reinitialiser_mdp_secretaire(user_id):
    """Réinitialiser mot de passe d'un secrétaire"""
    secretaire = User.query.get_or_404(user_id)
    
    if current_user.role != 'super_admin' and secretaire.clinique_id != current_user.clinique_id:
        flash('Vous ne pouvez pas modifier ce compte', 'danger')
        return redirect(url_for('admin.liste_secretaires'))
    
    if secretaire.role == 'secretaire':
        temp_password = secrets.token_urlsafe(8)
        secretaire.mot_de_passe_hash = bcrypt.generate_password_hash(temp_password).decode('utf-8')
        db.session.commit()
        flash(f'Nouveau mot de passe pour {secretaire.nom}: {temp_password}', 'info')
    return redirect(url_for('admin.liste_secretaires'))

# =======================================================
# GESTION DES MÉDECINS
# =======================================================
@admin_bp.route('/medecins')
@login_required
@admin_clinique_required
def liste_medecins():
    """Liste tous les médecins de la clinique"""
    cliniques = Clinique.query.all() if current_user.role == 'super_admin' else []
    
    if current_user.role == 'super_admin':
        medecins = User.query.filter_by(role='medecin').order_by(User.nom).all()
    else:
        medecins = User.query.filter_by(
            role='medecin',
            clinique_id=current_user.clinique_id
        ).order_by(User.nom).all()
    
    return render_template('admin/medecins.html', medecins=medecins, cliniques=cliniques)

@admin_bp.route('/medecins/ajouter', methods=['POST'])
@login_required
@admin_clinique_required
def ajouter_medecin():
    """L'admin ajoute un nouveau médecin"""
    nom = request.form.get('nom', '').strip()
    email = request.form.get('email', '').strip().lower()
    telephone = request.form.get('telephone', '').strip()
    specialite = request.form.get('specialite', '').strip()
    
    if current_user.role == 'super_admin':
        clinique_id = request.form.get('clinique_id')
        if not clinique_id:
            flash('Veuillez sélectionner une clinique', 'danger')
            return redirect(url_for('admin.liste_medecins'))
    else:
        clinique_id = current_user.clinique_id
    
    errors = []
    if not nom or len(nom) < 2:
        errors.append("Le nom doit contenir au moins 2 caractères")
    if not email or '@' not in email:
        errors.append("Email invalide")
    if not telephone or len(telephone) < 9:
        errors.append("Numéro de téléphone invalide")
    
    if User.query.filter_by(email=email).first():
        errors.append("Cet email est déjà utilisé")
    
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('admin.liste_medecins'))
    
    temp_password = secrets.token_urlsafe(8)
    hashed_password = bcrypt.generate_password_hash(temp_password).decode('utf-8')
    
    medecin = User(
        nom=nom,
        email=email,
        mot_de_passe_hash=hashed_password,
        telephone=telephone,
        specialite=specialite,
        role='medecin',
        actif=True,
        clinique_id=clinique_id
    )
    
    db.session.add(medecin)
    db.session.commit()
    
    flash(f'✅ Médecin {nom} ajouté avec succès!', 'success')
    flash(f'📧 Email: {email} | 🔑 Mot de passe temporaire: {temp_password}', 'info')
    return redirect(url_for('admin.liste_medecins'))

@admin_bp.route('/medecins/desactiver/<int:user_id>')
@login_required
@admin_clinique_required
def desactiver_medecin(user_id):
    """Désactiver un médecin"""
    medecin = User.query.get_or_404(user_id)
    
    if current_user.role != 'super_admin' and medecin.clinique_id != current_user.clinique_id:
        flash('Vous ne pouvez pas modifier ce médecin', 'danger')
        return redirect(url_for('admin.liste_medecins'))
    
    if medecin.role == 'medecin':
        medecin.actif = False
        db.session.commit()
        flash(f'Médecin {medecin.nom} désactivé', 'warning')
    return redirect(url_for('admin.liste_medecins'))

@admin_bp.route('/medecins/activer/<int:user_id>')
@login_required
@admin_clinique_required
def activer_medecin(user_id):
    """Réactiver un médecin"""
    medecin = User.query.get_or_404(user_id)
    
    if current_user.role != 'super_admin' and medecin.clinique_id != current_user.clinique_id:
        flash('Vous ne pouvez pas modifier ce médecin', 'danger')
        return redirect(url_for('admin.liste_medecins'))
    
    if medecin.role == 'medecin':
        medecin.actif = True
        db.session.commit()
        flash(f'Médecin {medecin.nom} activé', 'success')
    return redirect(url_for('admin.liste_medecins'))

@admin_bp.route('/medecins/reinitialiser-mot-de-passe/<int:user_id>')
@login_required
@admin_clinique_required
def reinitialiser_mot_de_passe(user_id):
    """Générer un nouveau mot de passe temporaire"""
    medecin = User.query.get_or_404(user_id)
    
    if current_user.role != 'super_admin' and medecin.clinique_id != current_user.clinique_id:
        flash('Vous ne pouvez pas modifier ce médecin', 'danger')
        return redirect(url_for('admin.liste_medecins'))
    
    if medecin.role == 'medecin':
        temp_password = secrets.token_urlsafe(8)
        medecin.mot_de_passe_hash = bcrypt.generate_password_hash(temp_password).decode('utf-8')
        db.session.commit()
        flash(f'Nouveau mot de passe pour {medecin.nom}: {temp_password}', 'info')
    return redirect(url_for('admin.liste_medecins'))

# =======================================================
# GESTION DES UTILISATEURS
# =======================================================
@admin_bp.route('/utilisateurs')
@login_required
@super_admin_required
def gestion_utilisateurs():
    """Liste tous les utilisateurs (super_admin uniquement)"""
    utilisateurs = User.query.order_by(User.role, User.nom).all()
    cliniques = Clinique.query.all()
    return render_template('users.html', utilisateurs=utilisateurs, cliniques=cliniques)

@admin_bp.route('/utilisateurs/ajouter', methods=['POST'])
@login_required
@super_admin_required
def ajouter_utilisateur():
    """Ajouter un nouvel utilisateur"""
    nom = request.form.get('nom', '').strip()
    email = request.form.get('email', '').strip().lower()
    telephone = request.form.get('telephone', '').strip()
    role = request.form.get('role', 'medecin')
    clinique_id = request.form.get('clinique_id')
    specialite = request.form.get('specialite', '').strip()
    
    errors = []
    if not nom or len(nom) < 2:
        errors.append("Le nom doit contenir au moins 2 caractères")
    if not email or '@' not in email:
        errors.append("Email invalide")
    if not telephone or len(telephone) < 9:
        errors.append("Numéro de téléphone invalide")
    
    if User.query.filter_by(email=email).first():
        errors.append("Cet email est déjà utilisé")
    
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('admin.gestion_utilisateurs'))
    
    temp_password = secrets.token_urlsafe(8)
    hashed_password = bcrypt.generate_password_hash(temp_password).decode('utf-8')
    
    nouvel_utilisateur = User(
        nom=nom,
        email=email,
        mot_de_passe_hash=hashed_password,
        telephone=telephone,
        role=role,
        specialite=specialite if role == 'medecin' else None,
        actif=True,
        clinique_id=clinique_id if clinique_id else None
    )
    
    db.session.add(nouvel_utilisateur)
    db.session.commit()
    
    flash(f'✅ Utilisateur {nom} ajouté avec succès!', 'success')
    flash(f'📧 Email: {email} | 🔑 Mot de passe temporaire: {temp_password}', 'info')
    return redirect(url_for('admin.gestion_utilisateurs'))

# =======================================================
# GESTION DES ORDONNANCES
# =======================================================
@admin_bp.route('/prescription/creer/<int:appointment_id>', methods=['GET', 'POST'])
@login_required
@medecin_required
def creer_prescription(appointment_id):
    """Créer une ordonnance pour un rendez-vous"""
    rdv = Appointment.query.get_or_404(appointment_id)
    
    if current_user.role not in ['super_admin', 'admin_clinique']:
        if rdv.medecin_id != current_user.id:
            flash('Vous ne pouvez pas créer d\'ordonnance pour ce rendez-vous', 'danger')
            return redirect(url_for('appointments.dashboard'))
    
    if request.method == 'POST':
        medicaments = request.form.get('medicaments', '').strip()
        conseils = request.form.get('conseils', '').strip()
        
        if not medicaments:
            flash('Veuillez saisir au moins un médicament', 'danger')
            return render_template('create_prescription.html', rdv=rdv)
        
        prescription = Prescription(
            appointment_id=rdv.id,
            patient_id=rdv.patient_id,
            medecin_id=current_user.id,
            clinique_id=rdv.clinique_id,
            medicaments=medicaments,
            conseils=conseils
        )
        
        db.session.add(prescription)
        rdv.statut = 'termine'
        db.session.commit()
        
        try:
            pdf_path = generer_ordonnance(
                patient=rdv.patient,
                medecin=current_user,
                prescription=prescription,
                appointment=rdv
            )
            prescription.fichier_pdf = pdf_path
            db.session.commit()
            flash('Ordonnance créée avec succès', 'success')
        except Exception as e:
            flash(f'Erreur lors de la génération du PDF: {str(e)}', 'warning')
        
        return redirect(url_for('appointments.dashboard'))
    
    return render_template('create_prescription.html', rdv=rdv)

@admin_bp.route('/prescription/<int:prescription_id>')
@login_required
def voir_prescription(prescription_id):
    """Voir une ordonnance"""
    prescription = Prescription.query.get_or_404(prescription_id)
    
    if current_user.role == 'super_admin':
        pass
    elif current_user.role == 'admin_clinique':
        if prescription.clinique_id != current_user.clinique_id:
            flash('Vous n\'avez pas accès à cette ordonnance', 'danger')
            return redirect(url_for('appointments.dashboard'))
    else:
        if prescription.medecin_id != current_user.id:
            flash('Vous n\'avez pas accès à cette ordonnance', 'danger')
            return redirect(url_for('appointments.dashboard'))
    
    return render_template('view_prescription.html', prescription=prescription)

@admin_bp.route('/prescription/pdf/<int:prescription_id>')
@login_required
def telecharger_pdf(prescription_id):
    """Télécharger le PDF d'une ordonnance"""
    prescription = Prescription.query.get_or_404(prescription_id)
    
    if current_user.role == 'super_admin':
        pass
    elif current_user.role == 'admin_clinique':
        if prescription.clinique_id != current_user.clinique_id:
            flash('Vous n\'avez pas accès à cette ordonnance', 'danger')
            return redirect(url_for('appointments.dashboard'))
    else:
        if prescription.medecin_id != current_user.id:
            flash('Vous n\'avez pas accès à cette ordonnance', 'danger')
            return redirect(url_for('appointments.dashboard'))
    
    if prescription.fichier_pdf and os.path.exists(prescription.fichier_pdf):
        return send_file(
            prescription.fichier_pdf, 
            as_attachment=True, 
            download_name=f'ordonnance_{prescription.id}.pdf'
        )
    else:
        flash('Fichier PDF non trouvé', 'danger')
        return redirect(url_for('admin.voir_prescription', prescription_id=prescription_id))

# =======================================================
# STATISTIQUES
# =======================================================
@admin_bp.route('/statistiques')
@login_required
@admin_clinique_required
def statistiques():
    """Statistiques globales (filtrées par clinique)"""
    today = datetime.now().date()
    
    if current_user.role == 'super_admin':
        stats = {
            'medecins': User.query.filter_by(role='medecin').count(),
            'medecins_actifs': User.query.filter_by(role='medecin', actif=True).count(),
            'secretaires': User.query.filter_by(role='secretaire').count(),
            'patients': Patient.query.count(),
            'nouveaux_patients': Patient.query.filter(
                Patient.date_creation >= today.replace(day=1)
            ).count(),
            'rdv_mois': Appointment.query.filter(
                Appointment.date >= today.replace(day=1)
            ).count(),
            'rdv_annules': Appointment.query.filter_by(statut='annule').count(),
            'rdv_aujourdhui': Appointment.query.filter_by(date=today).count(),
            'abonnements_expires': Clinique.query.filter(
                Clinique.date_fin_abonnement < datetime.now()
            ).count()
        }
        
        rdv_confirme = Appointment.query.filter_by(statut='confirme').count()
        rdv_termine = Appointment.query.filter_by(statut='termine').count()
        rdv_annule = Appointment.query.filter_by(statut='annule').count()
        rdv_absent = Appointment.query.filter_by(statut='absent').count()
        
    else:
        clinique_id = current_user.clinique_id
        
        stats = {
            'medecins': User.query.filter_by(role='medecin', clinique_id=clinique_id).count(),
            'medecins_actifs': User.query.filter_by(role='medecin', clinique_id=clinique_id, actif=True).count(),
            'secretaires': User.query.filter_by(role='secretaire', clinique_id=clinique_id).count(),
            'patients': Patient.query.filter_by(clinique_id=clinique_id).count(),
            'nouveaux_patients': Patient.query.filter(
                Patient.clinique_id == clinique_id,
                Patient.date_creation >= today.replace(day=1)
            ).count(),
            'rdv_mois': Appointment.query.filter(
                Appointment.clinique_id == clinique_id,
                Appointment.date >= today.replace(day=1)
            ).count(),
            'rdv_annules': Appointment.query.filter_by(clinique_id=clinique_id, statut='annule').count(),
            'rdv_aujourdhui': Appointment.query.filter_by(clinique_id=clinique_id, date=today).count(),
            'fin_abonnement': current_user.clinique.date_fin_abonnement if current_user.clinique else None,
            'jours_restants': (current_user.clinique.date_fin_abonnement - datetime.now()).days if current_user.clinique and current_user.clinique.date_fin_abonnement else 0
        }
        
        rdv_confirme = Appointment.query.filter_by(clinique_id=clinique_id, statut='confirme').count()
        rdv_termine = Appointment.query.filter_by(clinique_id=clinique_id, statut='termine').count()
        rdv_annule = Appointment.query.filter_by(clinique_id=clinique_id, statut='annule').count()
        rdv_absent = Appointment.query.filter_by(clinique_id=clinique_id, statut='absent').count()
    
    return render_template('admin/statistiques.html', 
                         stats=stats,
                         rdv_confirme=rdv_confirme,
                         rdv_termine=rdv_termine,
                         rdv_annule=rdv_annule,
                         rdv_absent=rdv_absent)

# =======================================================
# EXPORT DES DONNÉES
# =======================================================
@admin_bp.route('/export/patients/csv')
@login_required
@admin_clinique_required
def export_patients_csv():
    """Exporter la liste des patients au format CSV"""
    if current_user.role == 'super_admin':
        patients = Patient.query.all()
    else:
        patients = Patient.query.filter_by(clinique_id=current_user.clinique_id).all()
    
    si = StringIO()
    cw = csv.writer(si)
    
    cw.writerow(['ID', 'Nom', 'Téléphone', 'Email', 'Date naissance', 'Date création'])
    
    for p in patients:
        cw.writerow([
            p.id,
            p.nom,
            p.telephone,
            p.email or '',
            p.date_naissance.strftime('%d/%m/%Y') if p.date_naissance else '',
            p.date_creation.strftime('%d/%m/%Y')
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=patients.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@admin_bp.route('/export/patients/excel')
@login_required
@admin_clinique_required
def export_patients_excel():
    """Exporter la liste des patients au format Excel"""
    if current_user.role == 'super_admin':
        patients = Patient.query.all()
    else:
        patients = Patient.query.filter_by(clinique_id=current_user.clinique_id).all()
    
    data = []
    for p in patients:
        data.append({
            'ID': p.id,
            'Nom': p.nom,
            'Téléphone': p.telephone,
            'Email': p.email or '',
            'Date naissance': p.date_naissance.strftime('%d/%m/%Y') if p.date_naissance else '',
            'Date création': p.date_creation.strftime('%d/%m/%Y')
        })
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Patients', index=False)
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=patients.xlsx"
    response.headers["Content-type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response

@admin_bp.route('/export/rendez-vous/pdf')
@login_required
@admin_clinique_required
def export_rendez_vous_pdf():
    """Exporter la liste des rendez-vous au format PDF"""
    if current_user.role == 'super_admin':
        rdvs = Appointment.query.order_by(Appointment.date, Appointment.heure).all()
    else:
        rdvs = Appointment.query.filter_by(clinique_id=current_user.clinique_id).order_by(Appointment.date, Appointment.heure).all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    
    styles = getSampleStyleSheet()
    title = Paragraph(f"Liste des rendez-vous - {datetime.now().strftime('%d/%m/%Y')}", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['Date', 'Heure', 'Patient', 'Médecin', 'Motif', 'Statut']]
    for rdv in rdvs:
        data.append([
            rdv.date.strftime('%d/%m/%Y'),
            rdv.heure,
            rdv.patient.nom,
            rdv.doctor.nom,
            rdv.motif or '-',
            rdv.statut
        ])
    
    table = Table(data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    doc.build(elements)
    
    buffer.seek(0)
    
    response = make_response(buffer.getvalue())
    response.headers["Content-Disposition"] = "attachment; filename=rendez-vous.pdf"
    response.headers["Content-type"] = "application/pdf"
    return response

@admin_bp.route('/export/statistiques')
@login_required
@super_admin_required
def export_statistiques():
    """Exporter les statistiques globales au format CSV"""
    cliniques = Clinique.query.all()
    
    si = StringIO()
    cw = csv.writer(si)
    
    cw.writerow(['Clinique', 'Médecins', 'Patients', 'RDV total', 'RDV confirmés', 'RDV annulés', 'Taux absence', 'Abonnement fin'])
    
    for clinique in cliniques:
        medecins = User.query.filter_by(role='medecin', clinique_id=clinique.id).count()
        patients = Patient.query.filter_by(clinique_id=clinique.id).count()
        rdv_total = Appointment.query.filter_by(clinique_id=clinique.id).count()
        rdv_confirme = Appointment.query.filter_by(clinique_id=clinique.id, statut='confirme').count()
        rdv_annule = Appointment.query.filter_by(clinique_id=clinique.id, statut='annule').count()
        rdv_absent = Appointment.query.filter_by(clinique_id=clinique.id, statut='absent').count()
        taux_absence = (rdv_absent / rdv_total * 100) if rdv_total > 0 else 0
        
        cw.writerow([
            clinique.nom,
            medecins,
            patients,
            rdv_total,
            rdv_confirme,
            rdv_annule,
            f"{taux_absence:.1f}%",
            clinique.date_fin_abonnement.strftime('%d/%m/%Y') if clinique.date_fin_abonnement else '-'
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=statistiques.csv"
    output.headers["Content-type"] = "text/csv"
    return output