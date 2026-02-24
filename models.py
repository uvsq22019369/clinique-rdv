from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
import secrets

db = SQLAlchemy()

# =======================================================
# MODÈLE CLINIQUE
# =======================================================
class Clinique(db.Model):
    __tablename__ = 'cliniques'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False)
    adresse = db.Column(db.String(200))
    telephone = db.Column(db.String(20))
    email = db.Column(db.String(100))
    
    # Gestion abonnement
    abonnement_actif = db.Column(db.Boolean, default=True)
    date_debut_abonnement = db.Column(db.DateTime, default=datetime.utcnow)
    date_fin_abonnement = db.Column(db.DateTime)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations (une seule par type)
    users = db.relationship('User', backref='clinique', lazy=True)
    patients = db.relationship('Patient', backref='clinique', lazy=True)
    appointments = db.relationship('Appointment', backref='clinique', lazy=True)
    availabilities = db.relationship('Availability', backref='clinique', lazy=True)
    prescriptions = db.relationship('Prescription', backref='clinique', lazy=True)

    def __repr__(self):
        return f'<Clinique {self.nom}>'


# =======================================================
# MODÈLE UTILISATEUR
# =======================================================
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    mot_de_passe_hash = db.Column(db.String(200), nullable=False)
    
    # Rôles : 'super_admin', 'admin_clinique', 'medecin', 'secretaire'
    role = db.Column(db.String(20), default='medecin')
    
    telephone = db.Column(db.String(20))
    specialite = db.Column(db.String(100))
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)
    actif = db.Column(db.Boolean, default=True)
    
    # Lien vers clinique (NULL pour super_admin)
    clinique_id = db.Column(db.Integer, db.ForeignKey('cliniques.id'), nullable=True)
    
    # Relations (une seule par type)
    appointments = db.relationship('Appointment', backref='doctor', lazy=True, foreign_keys='Appointment.medecin_id')
    availabilities = db.relationship('Availability', backref='doctor', lazy=True)
    prescriptions = db.relationship('Prescription', backref='doctor', lazy=True, foreign_keys='Prescription.medecin_id')

    def __repr__(self):
        return f'<User {self.nom} ({self.role})>'


# =======================================================
# MODÈLE PATIENT
# =======================================================
class Patient(db.Model):
    __tablename__ = 'patients'
    
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(100))
    date_naissance = db.Column(db.Date)
    adresse = db.Column(db.String(200))
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Lien vers clinique
    clinique_id = db.Column(db.Integer, db.ForeignKey('cliniques.id'), nullable=False)
    
    # Relations (une seule par type)
    appointments = db.relationship('Appointment', backref='patient', lazy=True)
    prescriptions = db.relationship('Prescription', backref='patient', lazy=True)

    def __repr__(self):
        return f'<Patient {self.nom}>'


# =======================================================
# MODÈLE RENDEZ-VOUS
# =======================================================
class Appointment(db.Model):
    __tablename__ = 'appointments'
    
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    clinique_id = db.Column(db.Integer, db.ForeignKey('cliniques.id'), nullable=False)

    date = db.Column(db.Date, nullable=False)
    heure = db.Column(db.String(5), nullable=False)
    motif = db.Column(db.String(200))
    notes = db.Column(db.Text)
    statut = db.Column(db.String(20), default='confirme')  # confirme, termine, annule, absent
    
    # Token unique pour annulation
    annulation_token = db.Column(db.String(100), unique=True, nullable=False, 
                                  default=lambda: secrets.token_urlsafe(32))
    
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relations (simples, sans _ref, sans _list)
    # Les backref sont définis dans les autres classes
    patient = db.relationship('Patient', backref='appointments', lazy=True)
    doctor = db.relationship('User', backref='appointments', lazy=True, foreign_keys=[medecin_id])
    clinique = db.relationship('Clinique', backref='appointments', lazy=True)
    prescription = db.relationship('Prescription', uselist=False, lazy=True)

    # Contrainte d'unicité : pas deux RDV au même moment pour le même médecin
    __table_args__ = (
        db.UniqueConstraint('medecin_id', 'date', 'heure', name='unique_creneau'),
    )

    def __repr__(self):
        return f'<Appointment {self.date} {self.heure} - {self.statut}>'

    def annuler(self):
        """Annule le rendez-vous et met à jour le statut"""
        self.statut = 'annule'
        db.session.commit()

    def terminer(self):
        """Marque le rendez-vous comme terminé"""
        self.statut = 'termine'
        db.session.commit()

    def marquer_absent(self):
        """Marque le patient comme absent"""
        self.statut = 'absent'
        db.session.commit()

    @property
    def est_passe(self):
        """Vérifie si le rendez-vous est déjà passé"""
        return datetime.now().date() > self.date

    @property
    def est_annule(self):
        return self.statut == 'annule'

    @property
    def est_confirme(self):
        return self.statut == 'confirme'


# =======================================================
# MODÈLE DISPONIBILITÉS
# =======================================================
class Availability(db.Model):
    __tablename__ = 'availability'
    
    id = db.Column(db.Integer, primary_key=True)
    medecin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    heure_debut = db.Column(db.String(5), nullable=False)
    heure_fin = db.Column(db.String(5), nullable=False)
    duree_rdv = db.Column(db.Integer, default=30)
    
    # Lien vers clinique
    clinique_id = db.Column(db.Integer, db.ForeignKey('cliniques.id'), nullable=False)
    
    # Relations (simples)
    doctor = db.relationship('User', backref='availabilities', lazy=True)
    clinique = db.relationship('Clinique', backref='availabilities', lazy=True)

    def __repr__(self):
        return f'<Availability {self.date} {self.heure_debut}-{self.heure_fin}>'


# =======================================================
# MODÈLE ORDONNANCE
# =======================================================
class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    appointment_id = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=False)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    medecin_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    medicaments = db.Column(db.Text, nullable=False)
    conseils = db.Column(db.Text)
    date_creation = db.Column(db.DateTime, default=datetime.utcnow)
    fichier_pdf = db.Column(db.String(200))
    
    # Lien vers clinique
    clinique_id = db.Column(db.Integer, db.ForeignKey('cliniques.id'), nullable=False)
    
    # Relations (simples)
    appointment = db.relationship('Appointment', backref='prescriptions', lazy=True)
    patient = db.relationship('Patient', backref='prescriptions', lazy=True)
    doctor = db.relationship('User', backref='prescriptions', lazy=True)
    clinique = db.relationship('Clinique', backref='prescriptions', lazy=True)

    def __repr__(self):
        return f'<Prescription {self.id}>'