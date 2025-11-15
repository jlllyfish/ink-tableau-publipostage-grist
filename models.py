"""
Modèles de base de données PostgreSQL
"""

from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Text, LargeBinary
import hashlib

db = SQLAlchemy()


class Configuration(db.Model):
    """Configuration de personnalisation par doc_id"""
    __tablename__ = 'configurations'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Isolation par doc_id (hash pour anonymisation)
    doc_id_hash = db.Column(db.String(64), nullable=False, index=True)
    
    # Métadonnées
    config_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Connexion (pas le token - juste pour référence)
    api_url = db.Column(db.String(500))
    doc_id = db.Column(db.String(255))  # En clair pour affichage
    
    # Table et colonnes (JSON)
    table_id = db.Column(db.String(255))
    filter_column = db.Column(db.String(255))
    selected_columns = db.Column(Text)  # JSON stringifié
    
    # Filtres avancés (JSON)
    advanced_filters = db.Column(Text)  # JSON stringifié
    
    # Personnalisation
    service_name = db.Column(db.String(255))
    signer_firstname = db.Column(db.String(100))
    signer_name = db.Column(db.String(100))
    signer_title = db.Column(db.String(255))
    
    # Fichiers (stockage base64)
    logo_data = db.Column(LargeBinary)  # Image en bytes
    logo_filename = db.Column(db.String(255))
    logo_mimetype = db.Column(db.String(100))
    
    signature_data = db.Column(LargeBinary)  # Image en bytes
    signature_filename = db.Column(db.String(255))
    signature_mimetype = db.Column(db.String(100))
    
    # Export
    output_dir = db.Column(db.String(500))
    filename_pattern = db.Column(db.String(255))
    
    @staticmethod
    def hash_doc_id(doc_id: str) -> str:
        """Hash le doc_id pour isolation sécurisée"""
        return hashlib.sha256(doc_id.encode()).hexdigest()
    
    @classmethod
    def get_by_doc_id(cls, doc_id: str):
        """Récupère toutes les configs pour un doc_id"""
        doc_hash = cls.hash_doc_id(doc_id)
        return cls.query.filter_by(doc_id_hash=doc_hash).order_by(cls.created_at.desc()).all()
    
    @classmethod
    def get_config(cls, config_id: int, doc_id: str):
        """Récupère une config spécifique SI elle appartient au doc_id"""
        doc_hash = cls.hash_doc_id(doc_id)
        return cls.query.filter_by(id=config_id, doc_id_hash=doc_hash).first()
    
    def to_dict(self):
        """Convertit en dictionnaire"""
        import json
        
        return {
            'id': self.id,
            'config_name': self.config_name,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'connection': {
                'api_url': self.api_url,
                'doc_id': self.doc_id
            },
            'table': {
                'table_id': self.table_id,
                'filter_column': self.filter_column,
                'selected_columns': json.loads(self.selected_columns) if self.selected_columns else []
            },
            'filters': {
                'advanced_filters': json.loads(self.advanced_filters) if self.advanced_filters else []
            },
            'customization': {
                'service_name': self.service_name,
                'signer_firstname': self.signer_firstname,
                'signer_name': self.signer_name,
                'signer_title': self.signer_title,
                'has_logo': bool(self.logo_data),
                'has_signature': bool(self.signature_data)
            },
            'export': {
                'output_dir': self.output_dir,
                'filename_pattern': self.filename_pattern
            }
        }
    
    def __repr__(self):
        return f'<Configuration {self.config_name} for {self.doc_id[:8]}...>'