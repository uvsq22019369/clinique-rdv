from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app
from models import Appointment, Patient, User
from datetime import datetime, timedelta
from app.utils.sms_utils import envoyer_sms_rappel_rdv, formater_numero_senegal

scheduler = BackgroundScheduler()

def check_rdv_demain():
    """Vérifie tous les jours les RDV du lendemain et envoie des rappels"""
    with current_app.app_context():
        demain = (datetime.now().date() + timedelta(days=1))
        rdvs_demain = Appointment.query.filter_by(
            date=demain,
            statut='confirme'
        ).all()
        
        print(f"📅 Vérification des RDV pour demain: {len(rdvs_demain)} trouvés")
        
        for rdv in rdvs_demain:
            patient = rdv.patient
            medecin = rdv.doctor
            
            if patient.telephone:
                try:
                    numero_sms = formater_numero_senegal(patient.telephone)
                    date_formatee = rdv.date.strftime('%d/%m/%Y')
                    
                    envoyer_sms_rappel_rdv(
                        numero=numero_sms,
                        patient_nom=patient.nom,
                        date_rdv=date_formatee,
                        heure_rdv=rdv.heure,
                        medecin_nom=medecin.nom
                    )
                    print(f"✅ Rappel SMS envoyé à {patient.nom}")
                except Exception as e:
                    print(f"❌ Erreur rappel SMS pour {patient.nom}: {e}")

def init_scheduler(app):
    """Initialise le planificateur avec l'application Flask"""
    scheduler.add_job(
        id='rappel_rdv_demain',
        func=check_rdv_demain,
        trigger='cron',
        hour=8,  # Tous les jours à 8h du matin
        minute=0
    )
    scheduler.start()
    print("⏰ Planificateur de rappels démarré (8h tous les jours)")