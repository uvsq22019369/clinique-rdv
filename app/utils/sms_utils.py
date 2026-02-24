import requests
from flask import current_app
import json

def envoyer_sms(numero, message):
    """
    Envoie un SMS via l'API Infobip
    Format numéro: 221XXXXXXXXX (indicatif + numéro sans espaces)
    """
    api_key = current_app.config.get('INFOBIP_API_KEY')
    base_url = current_app.config.get('INFOBIP_BASE_URL')
    sender = current_app.config.get('INFOBIP_SENDER', 'CliniqueRDV')
    
    if not api_key or not base_url:
        print("❌ Configuration Infobip manquante")
        return False
    
    url = f"https://{base_url}/sms/2/text/advanced"
    
    payload = {
        "messages": [
            {
                "from": sender,
                "destinations": [
                    {
                        "to": numero
                    }
                ],
                "text": message
            }
        ]
    }
    
    headers = {
        'Authorization': f'App {api_key}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            print(f"✅ SMS envoyé à {numero}")
            return True
        else:
            print(f"❌ Erreur API Infobip: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Exception lors de l'envoi SMS: {e}")
        return False

def envoyer_sms_confirmation_rdv(numero, patient_nom, date_rdv, heure_rdv, medecin_nom):
    """
    Envoie un SMS de confirmation de rendez-vous
    """
    message = f"Bonjour {patient_nom}, votre RDV avec Dr. {medecin_nom} est confirmé le {date_rdv} à {heure_rdv}. Merci de votre confiance - Clinique RDV"
    return envoyer_sms(numero, message)

def envoyer_sms_rappel_rdv(numero, patient_nom, date_rdv, heure_rdv, medecin_nom):
    """
    Envoie un SMS de rappel (24h avant)
    """
    message = f"Rappel: RDV demain {date_rdv} à {heure_rdv} avec Dr. {medecin_nom}. Merci d'être à l'heure - Clinique RDV"
    return envoyer_sms(numero, message)

def envoyer_sms_annulation(numero, patient_nom, date_rdv, heure_rdv):
    """
    Envoie un SMS d'annulation
    """
    message = f"Bonjour {patient_nom}, votre RDV du {date_rdv} à {heure_rdv} a été annulé. Pour tout reprendre, contactez la clinique."
    return envoyer_sms(numero, message)

def formater_numero_senegal(telephone):
    """
    Convertit un numéro sénégalais (77 123 45 67) au format international 221771234567
    """
    # Enlever tous les espaces et tirets
    nettoye = telephone.replace(' ', '').replace('-', '').replace('.', '')
    
    # Si le numéro commence par 0, on enlève le 0
    if nettoye.startswith('0'):
        nettoye = nettoye[1:]
    
    # Si le numéro n'a pas l'indicatif 221, on l'ajoute
    if not nettoye.startswith('221'):
        nettoye = '221' + nettoye
    
    return nettoye