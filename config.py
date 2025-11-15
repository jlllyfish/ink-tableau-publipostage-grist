"""
Configuration de l'application
"""

import os
from dataclasses import dataclass
from typing import Optional


class Config:
    """Configuration générale de l'application"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(32).hex()
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Uploads
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'signatures')
    LOGO_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'logos')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024))
    MAX_LOGO_SIZE = 2 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}
    ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg'}
    
    # Grist - TOKENS SECURISES via variables d'environnement
    GRIST_API_URL = os.environ.get('GRIST_API_URL', 'https://grist.incubateur.anct.gouv.fr/api')
    GRIST_API_TOKEN = os.environ.get('GRIST_API_TOKEN', '')
    GRIST_DOC_ID = os.environ.get('GRIST_DOC_ID', '')
    
    # PDF
    DEFAULT_LOGO_PATH = os.path.join(BASE_DIR, 'static', 'images', 'logo_ministere_agriculture.png')
    FONTS_FOLDER = os.path.join(BASE_DIR, 'static', 'fonts')
    
    @staticmethod
    def allowed_file(filename):
        """Vérifie si l'extension du fichier est autorisée"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_EXTENSIONS
    
    @staticmethod
    def allowed_logo_file(filename):
        """Vérifie si l'extension du logo est autorisée"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in Config.ALLOWED_LOGO_EXTENSIONS
    
    @staticmethod
    def init_app(app):
        """Initialise les dossiers nécessaires"""
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.LOGO_UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(Config.BASE_DIR, 'static', 'images'), exist_ok=True)
        os.makedirs(Config.FONTS_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(Config.BASE_DIR, 'configs'), exist_ok=True)


@dataclass
class PDFConfig:
    """Configuration pour la génération de PDF"""
    
    service_name: str = "DRAAF SRFD Occitanie"
    signer_firstname: str = ""
    signer_name: str = ""
    signer_title: str = ""
    signature_path: Optional[str] = None
    logo_path: Optional[str] = None
    
    @property
    def has_signer_info(self) -> bool:
        """Vérifie si des informations de signataire sont présentes"""
        return bool(self.signer_firstname or self.signer_name or self.signer_title)
    
    @property
    def has_signature(self) -> bool:
        """Vérifie si une signature est présente"""
        return bool(self.signature_path and os.path.exists(self.signature_path))
    
    @property
    def has_custom_logo(self) -> bool:
        """Vérifie si un logo personnalisé est présent"""
        return bool(self.logo_path and os.path.exists(self.logo_path))
    
    @property
    def effective_logo_path(self) -> str:
        """Retourne le chemin du logo à utiliser (personnalisé ou par défaut)"""
        if self.has_custom_logo:
            return self.logo_path
        return Config.DEFAULT_LOGO_PATH
    
    def to_dict(self) -> dict:
        """Convertit la configuration en dictionnaire"""
        return {
            'service_name': self.service_name,
            'signer_firstname': self.signer_firstname,
            'signer_name': self.signer_name,
            'signer_title': self.signer_title,
            'signature_path': self.signature_path,
            'logo_path': self.logo_path,
            'has_signer_info': self.has_signer_info,
            'has_signature': self.has_signature,
            'has_custom_logo': self.has_custom_logo
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'PDFConfig':
        """Crée une instance depuis un dictionnaire"""
        return cls(
            service_name=data.get('service_name', 'DRAAF SRFD Occitanie'),
            signer_firstname=data.get('signer_firstname', ''),
            signer_name=data.get('signer_name', ''),
            signer_title=data.get('signer_title', ''),
            signature_path=data.get('signature_path'),
            logo_path=data.get('logo_path')
        )


class ProductionConfig(Config):
    """Configuration pour la production"""
    DEBUG = False
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Logs en production
        import logging
        from logging.handlers import RotatingFileHandler
        
        if not app.debug:
            logs_dir = os.path.join(Config.BASE_DIR, 'logs')
            if not os.path.exists(logs_dir):
                os.mkdir(logs_dir)
            
            file_handler = RotatingFileHandler(
                os.path.join(logs_dir, 'app.log'),
                maxBytes=10240000,
                backupCount=10
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
            ))
            file_handler.setLevel(logging.INFO)
            app.logger.addHandler(file_handler)
            app.logger.setLevel(logging.INFO)
            app.logger.info('Application démarrée')


# Configuration par environnement
config = {
    'production': ProductionConfig,
    'default': ProductionConfig
}