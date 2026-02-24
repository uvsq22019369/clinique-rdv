from flask import Flask, redirect, url_for, request, session
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_mail import Mail
from flask_babel import Babel
import os

# Importer db et les modèles depuis models.py
from models import db, User

# Initialisation des extensions (SANS l'application)
bcrypt = Bcrypt()
login_manager = LoginManager()
limiter = Limiter(key_func=get_remote_address)
csrf = CSRFProtect()
mail = Mail()
babel = Babel()

# =======================================================
# SÉLECTEUR DE LANGUE (fonction, pas décorateur)
# =======================================================
def get_locale():
    # Priorité : 1. Session, 2. En-tête du navigateur, 3. Français par défaut
    if 'language' in session:
        return session['language']
    return request.accept_languages.best_match(['fr', 'en']) or 'fr'

def create_app():
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static')
    
    # =======================================================
    # CHARGEMENT DE LA CONFIGURATION DEPUIS config.py
    # =======================================================
    app.config.from_object('config.Config')
    
    # =======================================================
    # CRÉATION DES DOSSIERS NÉCESSAIRES
    # =======================================================
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance'), exist_ok=True)
    
    # =======================================================
    # INITIALISATION DES EXTENSIONS
    # =======================================================
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    babel.init_app(app, locale_selector=get_locale)  # ← CORRIGÉ ICI
    
    # =======================================================
    # CONFIGURATION DE FLASK-LOGIN
    # =======================================================
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Veuillez vous connecter pour accéder à cette page.'
    login_manager.login_message_category = 'warning'
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # =======================================================
    # CRÉATION DES TABLES ET ADMIN PAR DÉFAUT
    # =======================================================
    with app.app_context():
        db.create_all()
        
        # Créer admin par défaut si aucun utilisateur n'existe
        if User.query.count() == 0:
            admin = User(
                nom='Administrateur',
                email='admin@clinique.sn',
                mot_de_passe_hash=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                role='super_admin',
                telephone='771234567'
            )
            db.session.add(admin)
            db.session.commit()
            print("✅ Admin créé - email: admin@clinique.sn, mdp: admin123")
        else:
            print("✅ Base de données déjà initialisée")
    
    # =======================================================
    # ENREGISTREMENT DES BLUEPRINTS
    # =======================================================
    from app.routes.auth import auth_bp
    from app.routes.appointments import appointments_bp
    from app.routes.admin import admin_bp
    from app.routes.public import public_bp
    
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(appointments_bp, url_prefix='/')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(public_bp)
    
    # =======================================================
    # ROUTE PRINCIPALE
    # =======================================================
    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))
    
    # =======================================================
    # VARIABLES GLOBALES POUR LES TEMPLATES
    # =======================================================
    @app.context_processor
    def utility_processor():
        from datetime import datetime
        return dict(now=datetime.now)
    
    # =======================================================
    # INITIALISATION DU PLANIFICATEUR DE RAPPELS SMS
    # =======================================================
    try:
        from app.utils.scheduler import init_scheduler
        init_scheduler(app)
        print("⏰ Planificateur de rappels SMS initialisé (8h tous les jours)")
    except Exception as e:
        print(f"⚠️ Impossible de démarrer le planificateur: {e}")
    
    return app