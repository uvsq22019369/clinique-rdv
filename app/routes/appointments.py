from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file, jsonify, make_response
from flask_login import login_required, current_user
from app import db
from models import User, Patient, Appointment, Availability, Prescription
from app.utils.decorators import medecin_required, role_required
from app.utils.pdf_generator import generer_ordonnance
from datetime import datetime, timedelta
import json
import os
import csv
from io import StringIO, BytesIO
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

appointments_bp = Blueprint('appointments', __name__)

# =======================================================
# DASHBOARD (adapté multi-cliniques)
# =======================================================
@appointments_bp.route('/dashboard')
@login_required
def dashboard():
    today = datetime.now().date()
    
    # =======================================================
    # Pour super_admin : voit tout
    # Pour les autres : filtrer par clinique_id
    # =======================================================
    if current_user.role == 'super_admin':
        # Super admin voit tout
        total_patients = Patient.query.count()
        total_rdv_mois = Appointment.query.filter(
            Appointment.date >= today.replace(day=1)
        ).count()
        
        # Rendez-vous aujourd'hui
        rdv_aujourdhui = Appointment.query.filter_by(date=today).order_by(Appointment.heure).all()
        
        # Prochains rendez-vous
        prochains_rdv = Appointment.query.filter(
            Appointment.date >= today,
            Appointment.statut == 'confirme'
        ).order_by(Appointment.date, Appointment.heure).limit(10).all()
        
        # Statistiques globales
        rdv_annules = Appointment.query.filter_by(statut='annule').count()
        rdv_absents = Appointment.query.filter_by(statut='absent').count()
        total_rdv = Appointment.query.count()
        taux_absence = (rdv_absents / total_rdv * 100) if total_rdv > 0 else 0
        rdv_annules_aujourdhui = Appointment.query.filter_by(date=today, statut='annule').count()
        total_rdv_aujourdhui = Appointment.query.filter_by(date=today).count()
        
    else:
        # Utilisateur normal : filtrer par clinique
        clinique_id = current_user.clinique_id
        
        total_patients = Patient.query.filter_by(clinique_id=clinique_id).count()
        
        total_rdv_mois = Appointment.query.filter(
            Appointment.clinique_id == clinique_id,
            Appointment.date >= today.replace(day=1)
        ).count()
        
        # Rendez-vous aujourd'hui
        rdv_aujourdhui = Appointment.query.filter_by(
            clinique_id=clinique_id,
            date=today
        ).order_by(Appointment.heure).all()
        
        # Prochains rendez-vous
        prochains_rdv = Appointment.query.filter(
            Appointment.clinique_id == clinique_id,
            Appointment.date >= today,
            Appointment.statut == 'confirme'
        ).order_by(Appointment.date, Appointment.heure).limit(10).all()
        
        # Statistiques
        rdv_annules = Appointment.query.filter_by(
            clinique_id=clinique_id,
            statut='annule'
        ).count()
        
        rdv_absents = Appointment.query.filter_by(
            clinique_id=clinique_id,
            statut='absent'
        ).count()
        
        total_rdv = Appointment.query.filter_by(clinique_id=clinique_id).count()
        taux_absence = (rdv_absents / total_rdv * 100) if total_rdv > 0 else 0
        
        rdv_annules_aujourdhui = Appointment.query.filter_by(
            clinique_id=clinique_id,
            date=today,
            statut='annule'
        ).count()
        
        total_rdv_aujourdhui = Appointment.query.filter_by(
            clinique_id=clinique_id,
            date=today
        ).count()
    
    return render_template('dashboard.html',
                         total_patients=total_patients,
                         total_rdv_mois=total_rdv_mois,
                         rdv_annules=rdv_annules,
                         rdv_absents=rdv_absents,
                         taux_absence=round(taux_absence, 1),
                         rdv_aujourdhui=rdv_aujourdhui,
                         prochains_rdv=prochains_rdv,
                         rdv_annules_aujourdhui=rdv_annules_aujourdhui,
                         total_rdv_aujourdhui=total_rdv_aujourdhui)


# =======================================================
# GESTION DES PATIENTS
# =======================================================
@appointments_bp.route('/patients')
@login_required
def liste_patients():
    """Liste des patients (filtrés par clinique)"""
    if current_user.role == 'super_admin':
        patients = Patient.query.order_by(Patient.nom).all()
    else:
        patients = Patient.query.filter_by(clinique_id=current_user.clinique_id).order_by(Patient.nom).all()
    return render_template('patients.html', patients=patients)


@appointments_bp.route('/patient/ajouter', methods=['POST'])
@login_required
def ajouter_patient():
    """Ajouter un patient (avec clinique_id automatique)"""
    nom = request.form.get('nom', '').strip()
    telephone = request.form.get('telephone', '').strip()
    email = request.form.get('email', '').strip()
    date_naissance = request.form.get('date_naissance', '')
    
    if not nom or not telephone:
        flash('Le nom et le téléphone sont obligatoires', 'danger')
        return redirect(url_for('appointments.liste_patients'))
    
    if date_naissance:
        try:
            date_naissance = datetime.strptime(date_naissance, '%Y-%m-%d').date()
        except:
            date_naissance = None
    else:
        date_naissance = None
    
    # Créer le patient avec la clinique_id de l'utilisateur connecté
    patient = Patient(
        nom=nom,
        telephone=telephone,
        email=email if email else None,
        date_naissance=date_naissance,
        clinique_id=current_user.clinique_id
    )
    
    db.session.add(patient)
    db.session.commit()
    
    flash(f'Patient {nom} ajouté avec succès', 'success')
    return redirect(url_for('appointments.liste_patients'))


# =======================================================
# PRISE DE RENDEZ-VOUS
# =======================================================
@appointments_bp.route('/rendez-vous/prendre')
@login_required
def prendre_rdv():
    """Page de prise de RDV (médecins de la clinique uniquement)"""
    if current_user.role == 'super_admin':
        medecins = User.query.filter_by(role='medecin', actif=True).all()
    else:
        # Médecins de la même clinique uniquement
        medecins = User.query.filter_by(
            role='medecin', 
            actif=True,
            clinique_id=current_user.clinique_id
        ).all()
    return render_template('book_appointment.html', medecins=medecins)


@appointments_bp.route('/rendez-vous/disponibilites/<int:medecin_id>/<date>')
@login_required
def get_disponibilites(medecin_id, date):
    """Récupérer les créneaux disponibles (vérifie que le médecin est de la même clinique)"""
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Vérifier que le médecin appartient à la même clinique que l'utilisateur
        medecin = User.query.get(medecin_id)
        if not medecin or (current_user.role != 'super_admin' and medecin.clinique_id != current_user.clinique_id):
            return {'creneaux': [], 'error': 'Médecin non autorisé'}
        
        # Récupérer les disponibilités du médecin
        dispos = Availability.query.filter_by(
            medecin_id=medecin_id,
            date=date_obj
        ).first()
        
        # Récupérer les rendez-vous déjà pris
        rdv_pris = Appointment.query.filter_by(
            medecin_id=medecin_id,
            date=date_obj,
            statut='confirme'
        ).all()
        
        heures_pris = [r.heure for r in rdv_pris]
        
        # Générer les créneaux disponibles
        creneaux = []
        if dispos:
            debut = datetime.strptime(dispos.heure_debut, '%H:%M')
            fin = datetime.strptime(dispos.heure_fin, '%H:%M')
            duree = dispos.duree_rdv or 30
            
            current = debut
            while current < fin:
                heure_str = current.strftime('%H:%M')
                if heure_str not in heures_pris:
                    creneaux.append(heure_str)
                current += timedelta(minutes=duree)
        
        return {'creneaux': creneaux}
    except Exception as e:
        return {'creneaux': [], 'error': str(e)}


# =======================================================
# RÉSERVATION DE RENDEZ-VOUS
# =======================================================
@appointments_bp.route('/rendez-vous/reserver', methods=['POST'])
@login_required
def reserver_rdv():
    medecin_id = request.form.get('medecin_id')
    patient_nom = request.form.get('patient_nom', '').strip()
    patient_tel = request.form.get('patient_tel', '').strip()
    patient_email = request.form.get('patient_email', '').strip()
    date = request.form.get('date')
    heure = request.form.get('heure')
    motif = request.form.get('motif', '').strip()
    
    # Validations
    if not all([medecin_id, patient_nom, patient_tel, date, heure]):
        flash('Tous les champs sont obligatoires', 'danger')
        return redirect(url_for('appointments.prendre_rdv'))
    
    try:
        # Vérifier que le médecin est de la bonne clinique
        medecin = User.query.get(medecin_id)
        if not medecin or (current_user.role != 'super_admin' and medecin.clinique_id != current_user.clinique_id):
            flash('Médecin non autorisé', 'danger')
            return redirect(url_for('appointments.prendre_rdv'))
        
        # Créer ou récupérer le patient
        patient = Patient.query.filter_by(telephone=patient_tel).first()
        if not patient:
            patient = Patient(
                nom=patient_nom,
                telephone=patient_tel,
                email=patient_email if patient_email else None,
                clinique_id=medecin.clinique_id
            )
            db.session.add(patient)
            db.session.commit()
        else:
            # Vérifier que le patient est de la bonne clinique
            if patient.clinique_id != medecin.clinique_id and current_user.role != 'super_admin':
                flash('Ce patient n\'appartient pas à votre clinique', 'danger')
                return redirect(url_for('appointments.prendre_rdv'))
            
            # Mettre à jour l'email si fourni
            if patient_email and patient.email != patient_email:
                patient.email = patient_email
                db.session.commit()
        
        # Vérifier que le créneau est toujours disponible
        rdv_existant = Appointment.query.filter_by(
            medecin_id=medecin_id,
            date=datetime.strptime(date, '%Y-%m-%d').date(),
            heure=heure,
            statut='confirme'
        ).first()
        
        if rdv_existant:
            flash('Ce créneau n\'est plus disponible', 'danger')
            return redirect(url_for('appointments.prendre_rdv'))
        
        # Créer le rendez-vous avec la clinique_id
        rdv = Appointment(
            patient_id=patient.id,
            medecin_id=medecin_id,
            clinique_id=medecin.clinique_id,
            date=datetime.strptime(date, '%Y-%m-%d').date(),
            heure=heure,
            motif=motif,
            statut='confirme'
        )
        
        db.session.add(rdv)
        db.session.commit()
        
        # =======================================================
        # ENVOI D'EMAIL ET SMS
        # =======================================================
        from app.utils.email_utils import envoyer_confirmation_rdv
        from app.utils.sms_utils import envoyer_sms_confirmation_rdv, formater_numero_senegal
        
        # Formatage de la date pour l'email
        date_formatee = datetime.strptime(date, '%Y-%m-%d').strftime('%d/%m/%Y')
        
        # 1. ENVOI EMAIL
        if patient.email:
            envoyer_confirmation_rdv(
                patient_nom=patient.nom,
                patient_email=patient.email,
                date_rdv=date_formatee,
                heure_rdv=heure,
                medecin_nom=medecin.nom,
                annulation_token=rdv.annulation_token
            )
        
        # 2. ENVOI SMS
        if patient.telephone:
            try:
                numero_sms = formater_numero_senegal(patient.telephone)
                envoyer_sms_confirmation_rdv(
                    numero=numero_sms,
                    patient_nom=patient.nom,
                    date_rdv=date_formatee,
                    heure_rdv=heure,
                    medecin_nom=medecin.nom
                )
            except Exception as e:
                print(f"❌ Erreur envoi SMS: {e}")
        
        flash('Rendez-vous confirmé! Un email et un SMS ont été envoyés.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur lors de la réservation: {str(e)}', 'danger')
        print(f"❌ Erreur réservation: {e}")
    
    return redirect(url_for('appointments.dashboard'))


# =======================================================
# ANNULATION DE RENDEZ-VOUS (avec vérification clinique)
# =======================================================
@appointments_bp.route('/rendez-vous/annuler/<int:rdv_id>')
@login_required
def annuler_rdv(rdv_id):
    """Annuler un rendez-vous (vérifie que le RDV est de la même clinique)"""
    rdv = Appointment.query.get_or_404(rdv_id)
    
    # Vérification des droits (clinique + rôle)
    if current_user.role != 'super_admin':
        if rdv.clinique_id != current_user.clinique_id:
            flash('Vous ne pouvez pas annuler ce rendez-vous', 'danger')
            return redirect(url_for('appointments.dashboard'))
        
        if current_user.role == 'medecin' and rdv.medecin_id != current_user.id:
            flash('Vous ne pouvez pas annuler le rendez-vous d\'un autre médecin', 'danger')
            return redirect(url_for('appointments.dashboard'))
    
    # Sauvegarder les infos avant modification (AVEC LES BONS NOMS DE RELATIONS)
    patient_nom = rdv.patient.nom
    patient_tel = rdv.patient.telephone
    patient_email = rdv.patient.email
    medecin_nom = rdv.doctor.nom
    date_rdv = rdv.date.strftime('%d/%m/%Y')
    heure_rdv = rdv.heure
    
    rdv.statut = 'annule'
    db.session.commit()
    
    # Envoi SMS d'annulation
    try:
        from app.utils.sms_utils import envoyer_sms_annulation, formater_numero_senegal
        if patient_tel:
            numero_sms = formater_numero_senegal(patient_tel)
            envoyer_sms_annulation(
                numero=numero_sms,
                patient_nom=patient_nom,
                date_rdv=date_rdv,
                heure_rdv=heure_rdv
            )
    except Exception as e:
        print(f"❌ Erreur envoi SMS annulation: {e}")
    
    # Envoi email d'annulation si disponible
    if patient_email:
        try:
            from app.utils.email_utils import envoyer_confirmation_annulation
            envoyer_confirmation_annulation(
                patient_nom=patient_nom,
                patient_email=patient_email,
                date_rdv=date_rdv,
                heure_rdv=heure_rdv,
                medecin_nom=medecin_nom
            )
        except Exception as e:
            print(f"❌ Erreur envoi email annulation: {e}")
    
    flash('Rendez-vous annulé', 'info')
    return redirect(url_for('appointments.dashboard'))


# =======================================================
# GESTION DES CRÉNEAUX (filtrés par clinique)
# =======================================================
@appointments_bp.route('/creneaux/gestion')
@login_required
def gerer_creneaux():
    """Gestion des créneaux (uniquement ceux de la clinique)"""
    today = datetime.now().date()
    
    if current_user.role == 'super_admin':
        disponibilites = Availability.query.filter(
            Availability.date >= today
        ).order_by(Availability.date).all()
    else:
        disponibilites = Availability.query.filter_by(
            clinique_id=current_user.clinique_id
        ).filter(Availability.date >= today).order_by(Availability.date).all()
    
    return render_template('manage_slots.html', disponibilites=disponibilites)


@appointments_bp.route('/creneaux/ajouter', methods=['POST'])
@login_required
def ajouter_creneaux():
    """Ajouter des créneaux (avec clinique_id automatique)"""
    date = request.form.get('date')
    heure_debut = request.form.get('heure_debut')
    heure_fin = request.form.get('heure_fin')
    duree_rdv = request.form.get('duree_rdv', 30)
    
    print(f"=== AJOUT CRÉNEAU ===")
    print(f"Date: {date}")
    print(f"Début: {heure_debut}")
    print(f"Fin: {heure_fin}")
    print(f"Durée: {duree_rdv}")
    print(f"User ID: {current_user.id}")
    print(f"User role: {current_user.role}")
    print(f"Clinique ID: {current_user.clinique_id}")
    
    if not all([date, heure_debut, heure_fin]):
        flash('Tous les champs sont obligatoires', 'danger')
        return redirect(url_for('appointments.gerer_creneaux'))
    
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d').date()
        
        # Vérifier si des créneaux existent déjà pour cette date
        existant = Availability.query.filter_by(
            medecin_id=current_user.id,
            date=date_obj
        ).first()
        
        if existant:
            flash('Des créneaux existent déjà pour cette date', 'warning')
            return redirect(url_for('appointments.gerer_creneaux'))
        
        # S'assurer que clinique_id n'est pas NULL
        clinique_id = current_user.clinique_id
        if not clinique_id and current_user.role != 'super_admin':
            # Si pas de clinique, prendre la première disponible
            from models import Clinique
            clinique = Clinique.query.first()
            if clinique:
                clinique_id = clinique.id
                print(f"⚠️ Clinique ID forcé à: {clinique_id}")
            else:
                flash('Aucune clinique disponible. Contactez l\'administrateur.', 'danger')
                return redirect(url_for('appointments.gerer_creneaux'))
        
        disponibilite = Availability(
            medecin_id=current_user.id,
            clinique_id=clinique_id,
            date=date_obj,
            heure_debut=heure_debut,
            heure_fin=heure_fin,
            duree_rdv=int(duree_rdv)
        )
        
        db.session.add(disponibilite)
        db.session.commit()
        
        print(f"✅ Créneau ajouté avec ID: {disponibilite.id}")
        flash(f'Créneaux ajoutés pour le {date}', 'success')
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ ERREUR: {str(e)}")
        flash(f'Erreur: {str(e)}', 'danger')
    
    return redirect(url_for('appointments.gerer_creneaux'))


@appointments_bp.route('/creneaux/supprimer/<int:dispo_id>')
@login_required
def supprimer_creneaux(dispo_id):
    """Supprimer des créneaux (vérifie que c'est de la même clinique)"""
    dispo = Availability.query.get_or_404(dispo_id)
    
    if current_user.role != 'super_admin' and dispo.clinique_id != current_user.clinique_id:
        flash('Vous ne pouvez pas supprimer ces créneaux', 'danger')
        return redirect(url_for('appointments.gerer_creneaux'))
    
    if dispo.medecin_id != current_user.id and current_user.role != 'super_admin':
        flash('Vous ne pouvez pas supprimer les créneaux d\'un autre médecin', 'danger')
        return redirect(url_for('appointments.gerer_creneaux'))
    
    db.session.delete(dispo)
    db.session.commit()
    flash('Créneaux supprimés', 'success')
    return redirect(url_for('appointments.gerer_creneaux'))


# =======================================================
# ROUTE DE TEST
# =======================================================
@appointments_bp.route('/test-ajout')
@login_required
def test_ajout():
    """Route de test pour ajouter un créneau automatiquement"""
    try:
        date_obj = datetime.now().date() + timedelta(days=1)
        
        # S'assurer que clinique_id n'est pas NULL
        clinique_id = current_user.clinique_id
        if not clinique_id:
            from models import Clinique
            clinique = Clinique.query.first()
            if clinique:
                clinique_id = clinique.id
            else:
                return "❌ Aucune clinique disponible"
        
        dispo = Availability(
            medecin_id=current_user.id,
            clinique_id=clinique_id,
            date=date_obj,
            heure_debut="09:00",
            heure_fin="12:00",
            duree_rdv=30
        )
        
        db.session.add(dispo)
        db.session.commit()
        
        return f"✅ Créneau ajouté pour {date_obj} (clinique {clinique_id})"
    except Exception as e:
        return f"❌ Erreur: {str(e)}"


# =======================================================
# API POUR LES DISPONIBILITÉS
# =======================================================
@appointments_bp.route('/api/disponibilites')
@login_required
def api_disponibilites():
    """API pour récupérer les créneaux de disponibilité au format JSON pour FullCalendar"""
    import re
    
    start = request.args.get('start')
    end = request.args.get('end')
    medecin_filter = request.args.get('medecin', 'all')
    
    # Fonction pour parser les dates FullCalendar
    def parse_fullcalendar_date(date_str):
        if not date_str:
            return None
        # Enlever le décalage horaire (ex: +01:00) et l'espace
        date_str = re.sub(r'[+-]\d{2}:\d{2}', '', date_str)
        date_str = date_str.replace(' ', 'T')
        try:
            return datetime.fromisoformat(date_str).date()
        except:
            return None
    
    # Convertir les dates
    start_date = parse_fullcalendar_date(start)
    end_date = parse_fullcalendar_date(end)
    
    if not start_date:
        start_date = datetime.now().date()
    
    if not end_date:
        end_date = start_date + timedelta(days=30)
    
    # Construire la requête de base
    query = Availability.query
    
    # Filtrer par clinique
    if current_user.role != 'super_admin':
        query = query.filter_by(clinique_id=current_user.clinique_id)
    
    # Filtrer par période
    query = query.filter(Availability.date >= start_date, Availability.date <= end_date)
    
    # Filtrer par médecin
    if medecin_filter != 'all':
        query = query.filter_by(medecin_id=medecin_filter)
    
    disponibilites = query.order_by(Availability.date, Availability.heure_debut).all()
    
    # Formater pour FullCalendar
    result = []
    for dispo in disponibilites:
        medecin = User.query.get(dispo.medecin_id)
        
        result.append({
            'id': f"dispo_{dispo.id}",
            'title': f"Disponible - Dr. {medecin.nom}",
            'start': f"{dispo.date.isoformat()}T{dispo.heure_debut}",
            'end': f"{dispo.date.isoformat()}T{dispo.heure_fin}",
            'backgroundColor': '#6c757d',  # Gris
            'borderColor': '#6c757d',
            'display': 'background',
            'extendedProps': {
                'type': 'disponibilite',
                'medecin_id': dispo.medecin_id,
                'medecin_nom': medecin.nom
            }
        })
    
    return jsonify(result)


# =======================================================
# ROUTE DE DÉBOGAGE
# =======================================================
@appointments_bp.route('/debug/creneaux')
@login_required
def debug_creneaux():
    if current_user.role == 'super_admin':
        creneaux = Availability.query.all()
    else:
        creneaux = Availability.query.filter_by(clinique_id=current_user.clinique_id).all()
    
    result = "<h3>Vos créneaux en base :</h3><ul>"
    for c in creneaux:
        result += f"<li>ID: {c.id} - Clinique: {c.clinique_id} - {c.date} - {c.heure_debut} à {c.heure_fin}</li>"
    result += f"</ul><p>Total: {len(creneaux)} créneaux</p>"
    result += '<br><a href="/creneaux/gestion">Retour à la gestion</a>'
    return result


# =======================================================
# API POUR LE CALENDRIER (RENDEZ-VOUS)
# =======================================================
@appointments_bp.route('/api/rendez-vous')
@login_required
def api_rendez_vous():
    """API pour récupérer les rendez-vous au format JSON pour FullCalendar"""
    import re
    
    start = request.args.get('start')
    end = request.args.get('end')
    medecin_filter = request.args.get('medecin', 'all')
    statut_filter = request.args.get('statut', 'all')
    
    # Fonction pour parser les dates FullCalendar
    def parse_fullcalendar_date(date_str):
        if not date_str:
            return None
        # Enlever le décalage horaire (ex: +01:00) et l'espace
        date_str = re.sub(r'[+-]\d{2}:\d{2}', '', date_str)
        date_str = date_str.replace(' ', 'T')
        try:
            return datetime.fromisoformat(date_str).date()
        except:
            return None
    
    # Convertir les dates
    start_date = parse_fullcalendar_date(start)
    end_date = parse_fullcalendar_date(end)
    
    if not start_date:
        start_date = datetime.now().date()
    
    if not end_date:
        end_date = start_date + timedelta(days=30)
    
    # Construire la requête de base
    query = Appointment.query
    
    # Filtrer par clinique
    if current_user.role != 'super_admin':
        query = query.filter_by(clinique_id=current_user.clinique_id)
    
    # Filtrer par période
    query = query.filter(Appointment.date >= start_date, Appointment.date <= end_date)
    
    # Filtrer par médecin
    if medecin_filter != 'all':
        query = query.filter_by(medecin_id=medecin_filter)
    
    # Filtrer par statut
    if statut_filter != 'all':
        query = query.filter_by(statut=statut_filter)
    
    rdvs = query.order_by(Appointment.date, Appointment.heure).all()
    
    # Formater pour FullCalendar (AVEC LES BONS NOMS DE RELATIONS)
    result = []
    for rdv in rdvs:
        # Calculer l'heure de fin (par défaut 30 min)
        heure_debut = datetime.strptime(rdv.heure, '%H:%M')
        heure_fin = (heure_debut + timedelta(minutes=30)).strftime('%H:%M')
        
        result.append({
            'id': rdv.id,
            'patient_nom': rdv.patient.nom,
            'patient_tel': rdv.patient.telephone,
            'medecin_nom': rdv.doctor.nom,
            'date': rdv.date.isoformat(),
            'heure': rdv.heure,
            'fin': heure_fin,
            'statut': rdv.statut,
            'motif': rdv.motif
        })
    
    return jsonify(result)


# =======================================================
# PAGE DU CALENDRIER
# =======================================================
@appointments_bp.route('/calendrier')
@login_required
def calendrier():
    """Page du calendrier des rendez-vous"""
    # Récupérer les médecins pour le filtre
    if current_user.role == 'super_admin':
        medecins = User.query.filter_by(role='medecin', actif=True).all()
    else:
        medecins = User.query.filter_by(
            role='medecin', 
            actif=True,
            clinique_id=current_user.clinique_id
        ).all()
    
    return render_template('calendrier.html', medecins=medecins)


# =======================================================
# EXPORT POUR LES MÉDECINS
# =======================================================
@appointments_bp.route('/export/mes-patients/csv')
@login_required
def export_mes_patients_csv():
    """Exporter la liste des patients du médecin connecté au format CSV"""
    # Récupérer les patients du médecin (via ses rendez-vous)
    rdvs = Appointment.query.filter_by(medecin_id=current_user.id).all()
    patient_ids = set([rdv.patient_id for rdv in rdvs])
    patients = Patient.query.filter(Patient.id.in_(patient_ids)).all()
    
    si = StringIO()
    cw = csv.writer(si)
    
    cw.writerow(['ID', 'Nom', 'Téléphone', 'Email', 'Date naissance', 'Dernier RDV'])
    
    for p in patients:
        # Dernier rendez-vous du patient avec ce médecin
        dernier_rdv = Appointment.query.filter_by(
            patient_id=p.id, 
            medecin_id=current_user.id
        ).order_by(Appointment.date.desc()).first()
        
        cw.writerow([
            p.id,
            p.nom,
            p.telephone,
            p.email or '',
            p.date_naissance.strftime('%d/%m/%Y') if p.date_naissance else '',
            dernier_rdv.date.strftime('%d/%m/%Y') if dernier_rdv else '-'
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=mes_patients_{current_user.nom}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@appointments_bp.route('/export/mes-rendez-vous/pdf')
@login_required
def export_mes_rendez_vous_pdf():
    """Exporter la liste des rendez-vous du médecin au format PDF"""
    # Récupérer les rendez-vous du médecin
    rdvs = Appointment.query.filter_by(medecin_id=current_user.id).order_by(Appointment.date, Appointment.heure).all()
    
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4))
    elements = []
    
    styles = getSampleStyleSheet()
    title = Paragraph(f"Mes rendez-vous - Dr. {current_user.nom} - {datetime.now().strftime('%d/%m/%Y')}", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 20))
    
    data = [['Date', 'Heure', 'Patient', 'Motif', 'Statut']]
    for rdv in rdvs:
        data.append([
            rdv.date.strftime('%d/%m/%Y'),
            rdv.heure,
            rdv.patient.nom,  # ← CORRIGÉ : patient au lieu de patient_ref
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
    response.headers["Content-Disposition"] = f"attachment; filename=mes_rdv_{current_user.nom}.pdf"
    response.headers["Content-type"] = "application/pdf"
    return response