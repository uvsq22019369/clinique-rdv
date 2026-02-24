import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # =======================================================
    # CONFIGURATION GÉNÉRALE
    # =======================================================
    
    # Clé secrète pour les sessions
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'une-cle-secrete-tres-longue-2024-pour-dev'
    
    # Base de données
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), 'instance', 'database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Dossier pour les uploads (PDF, images)
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max
    
    # =======================================================
    # SÉCURITÉ DES COOKIES
    # =======================================================
    
    SESSION_COOKIE_SECURE = False  # True en production avec HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 heure
    
    # =======================================================
    # CONFIGURATION EMAIL (GMAIL)
    # =======================================================
    
    # Serveur SMTP Gmail
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False
    
    # Tes identifiants Gmail
    MAIL_USERNAME = 'khadimsoum0907@gmail.com'
    MAIL_PASSWORD = 'lirc pzxp ktmo mmnr'  # Mot de passe d'application Gmail
    
    # Expéditeur par défaut
    MAIL_DEFAULT_SENDER = ('Clinique RDV', 'khadimsoum0907@gmail.com')
    
    # Configuration supplémentaire email
    MAIL_MAX_EMAILS = None  # Pas de limite d'envois
    MAIL_ASCII_ATTACHMENTS = False  # Pour les pièces jointes
    
    # =======================================================
    # CONFIGURATION SMS (INFOBIP)
    # =======================================================
    
    # API Infobip (récupéré depuis ton compte)
    INFOBIP_API_KEY = '6a5a3c514246733a00547c06f028955b-aadf582a-b6d4-4cc9-88d5-a6e26a67a722'
    INFOBIP_BASE_URL = 'vyvp6r.api.infobip.com'  # Sans https://
    INFOBIP_SENDER = 'CliniqueRDV'  # Nom qui apparaîtra comme expéditeur des SMS


# =======================================================
# CONFIGURATION DES LANGUES
# =======================================================
LANGUAGES = {
    'fr': 'Français',
    'en': 'English'
}
BABEL_DEFAULT_LOCALE = 'fr'