from flask_mail import Message
from flask import current_app, url_for
from app import mail

def envoyer_confirmation_rdv(patient_nom, patient_email, date_rdv, heure_rdv, medecin_nom, annulation_token):
    """
    Envoie un email de confirmation avec lien d'annulation
    """
    
    # Construire le lien d'annulation (utilise http://localhost:5000 en dev)
    lien_annulation = url_for('public.annuler_rdv_public', token=annulation_token, _external=True)
    
    sujet = f"Confirmation de votre rendez-vous - Clinique RDV"
    
    corps = f"""
    Bonjour {patient_nom},
    
    Votre rendez-vous a été confirmé :
    
    📅 Date : {date_rdv}
    ⏰ Heure : {heure_rdv}
    👨‍⚕️ Médecin : Dr. {medecin_nom}
    
    Merci de votre confiance.
    
    {"="*50}
    🔴 Pour ANNULER votre rendez-vous, cliquez ici :
    {lien_annulation}
    {"="*50}
    
    (Ce lien est valable jusqu'à la date du rendez-vous)
    
    Clinique RDV
    """
    
    msg = Message(
        subject=sujet,
        recipients=[patient_email],
        body=corps
    )
    
    try:
        mail.send(msg)
        print(f"✅ Email envoyé à {patient_email}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email : {e}")
        return False

def envoyer_confirmation_annulation(patient_nom, patient_email, date_rdv, heure_rdv, medecin_nom):
    """
    Envoie un email de confirmation d'annulation
    """
    sujet = f"Confirmation d'annulation - Clinique RDV"
    
    corps = f"""
    Bonjour {patient_nom},
    
    Votre rendez-vous a bien été annulé :
    
    📅 Date : {date_rdv}
    ⏰ Heure : {heure_rdv}
    👨‍⚕️ Médecin : Dr. {medecin_nom}
    
    Si vous souhaitez prendre un nouveau rendez-vous, visitez notre site.
    
    Clinique RDV
    """
    
    msg = Message(
        subject=sujet,
        recipients=[patient_email],
        body=corps
    )
    
    try:
        mail.send(msg)
        print(f"✅ Email d'annulation envoyé à {patient_email}")
        return True
    except Exception as e:
        print(f"❌ Erreur envoi email annulation : {e}")
        return False