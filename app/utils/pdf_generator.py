from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
from datetime import datetime

def generer_ordonnance(patient, medecin, prescription, appointment):
    """
    Génère un PDF d'ordonnance
    """
    # Créer le dossier uploads s'il n'existe pas
    from flask import current_app
    upload_dir = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    # Nom du fichier
    filename = f"ordonnance_{prescription.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(upload_dir, filename)
    
    # Créer le PDF
    doc = SimpleDocTemplate(filepath, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []
    
    # Titre
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        alignment=1,  # Centre
        spaceAfter=30
    )
    story.append(Paragraph("ORDONNANCE MÉDICALE", title_style))
    story.append(Spacer(1, 0.5*cm))
    
    # Informations médecin
    doctor_info = f"""
    <b>Dr. {medecin.nom}</b><br/>
    {medecin.specialite if medecin.specialite else 'Médecin généraliste'}<br/>
    Tél: {medecin.telephone}<br/>
    Email: {medecin.email}
    """
    story.append(Paragraph(doctor_info, styles['Normal']))
    story.append(Spacer(1, 0.5*cm))
    
    # Informations patient
    patient_info = f"""
    <b>Patient:</b> {patient.nom}<br/>
    <b>Date:</b> {appointment.date.strftime('%d/%m/%Y')}
    """
    story.append(Paragraph(patient_info, styles['Normal']))
    story.append(Spacer(1, 1*cm))
    
    # Médicaments
    story.append(Paragraph("<b>PRESCRIPTION:</b>", styles['Heading2']))
    story.append(Spacer(1, 0.3*cm))
    
    # Traiter les médicaments (format texte ou JSON)
    medicaments_text = prescription.medicaments.replace('\n', '<br/>')
    story.append(Paragraph(medicaments_text, styles['Normal']))
    story.append(Spacer(1, 1*cm))
    
    # Conseils
    if prescription.conseils:
        story.append(Paragraph("<b>CONSEILS:</b>", styles['Heading2']))
        story.append(Spacer(1, 0.3*cm))
        story.append(Paragraph(prescription.conseils.replace('\n', '<br/>'), styles['Normal']))
        story.append(Spacer(1, 1*cm))
    
    # Signature
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("Signature du médecin:", styles['Normal']))
    story.append(Spacer(1, 1*cm))
    story.append(Paragraph(f"Dr. {medecin.nom}", styles['Normal']))
    
    # Pied de page
    story.append(Spacer(1, 2*cm))
    story.append(Paragraph("Document généré électroniquement - Valide sans signature manuscrite", styles['Italic']))
    
    # Construire le PDF
    doc.build(story)
    
    return filepath