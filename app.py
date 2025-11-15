from flask import Flask, request, jsonify, render_template, send_file
import os
import time
import json
import base64  # ← NOUVEAU : pour encoder les fichiers
import requests
import pandas as pd
from datetime import datetime
from werkzeug.utils import secure_filename
from config import Config, PDFConfig
from grist_client import GristClient
from pdf_generator import PDFGenerator
from models import db, Configuration  # ← NOUVEAU : importer le modèle

app = Flask(__name__)
app.config.from_object(Config)

# ===== NOUVEAU : Configuration PostgreSQL =====
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialiser la base de données
db.init_app(app)

# Créer les tables au démarrage
with app.app_context():
    db.create_all()
# ===== FIN NOUVEAU =====

# Définir le dossier de base comme étant le dossier où se trouve app.py
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Debug: afficher où Flask démarre (aide au diagnostic)
print("="*70)
print("🔍 DIAGNOSTIC DÉMARRAGE")
print("="*70)
print(f"📁 os.getcwd():     {os.getcwd()}")
print(f"📁 __file__:        {__file__}")
print(f"📁 BASE_DIR:        {BASE_DIR}")
print("="*70)

# Modifier les chemins pour être relatifs à BASE_DIR
Config.UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'signatures')
LOGO_UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads', 'logos')
CONFIGS_FOLDER = os.path.join(BASE_DIR, 'configs')

# Configuration pour les logos
ALLOWED_LOGO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'svg'}
MAX_LOGO_SIZE = 2 * 1024 * 1024  # 2 Mo

# Créer les dossiers d'upload
os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOGO_UPLOAD_FOLDER, exist_ok=True)
os.makedirs(CONFIGS_FOLDER, exist_ok=True)

# Créer aussi les dossiers static (pour logo par défaut et polices)
STATIC_IMAGES = os.path.join(BASE_DIR, 'static', 'images')
STATIC_FONTS = os.path.join(BASE_DIR, 'static', 'fonts')
os.makedirs(STATIC_IMAGES, exist_ok=True)
os.makedirs(STATIC_FONTS, exist_ok=True)

# Vérifier que le logo par défaut existe
default_logo = os.path.join(STATIC_IMAGES, 'logo_ministere_agriculture.png')
if os.path.exists(default_logo):
    print(f"✅ Logo par défaut trouvé: {default_logo}")
else:
    print(f"⚠️  ATTENTION: Logo par défaut manquant: {default_logo}")
    print(f"   Placer un fichier logo dans: {STATIC_IMAGES}")


# Variables globales pour stocker la session
grist_client = None
pdf_generator = PDFGenerator()

# ===== NOUVEAU : Fonction pour récupérer le doc_id actuel =====
def get_current_doc_id():
    """Récupère le doc_id actuel depuis la session ou requête"""
    # Chercher d'abord dans le body de la requête
    if request.is_json:
        doc_id = request.json.get('doc_id')
        if doc_id:
            return doc_id
    
    # Sinon chercher dans les paramètres de query
    doc_id = request.args.get('doc_id')
    if doc_id:
        return doc_id
    
    # Sinon utiliser le grist_client global si connecté
    if grist_client and hasattr(grist_client, 'doc_id'):
        return grist_client.doc_id
    
    return None
# ===== FIN NOUVEAU =====

def allowed_logo_file(filename):
    """Vérifie si l'extension du logo est autorisée"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_LOGO_EXTENSIONS


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/connect', methods=['POST'])
def connect():
    """Initialise la connexion à Grist"""
    global grist_client
    try:
        data = request.json
        api_url = data.get('api_url')
        api_token = data.get('api_token')
        doc_id = data.get('doc_id')
        
        if not all([api_url, api_token, doc_id]):
            return jsonify({'error': 'Paramètres manquants'}), 400
        
        grist_client = GristClient(api_url, api_token, doc_id)
        tables = grist_client.get_tables()
        
        return jsonify({'success': True, 'tables': tables})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/tables', methods=['POST'])
def get_tables():
    """Récupère la liste des tables depuis Grist"""
    global grist_client
    try:
        data = request.json
        api_url = data.get('api_url')
        api_token = data.get('api_token')
        doc_id = data.get('doc_id')
        
        if not all([api_url, api_token, doc_id]):
            return jsonify({'error': 'Paramètres manquants'}), 400
        
        print(f"🔌 Connexion à Grist: {api_url} / Doc: {doc_id}")
        grist_client = GristClient(api_url, api_token, doc_id)
        tables = grist_client.get_tables()
        print(f"✅ Client Grist initialisé avec succès - {len(tables)} tables trouvées")
        
        return jsonify({'tables': tables})
    except Exception as e:
        print(f"❌ Erreur lors de la connexion: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/columns/<table_id>', methods=['GET'])
def get_columns(table_id):
    """Récupère les colonnes d'une table avec leurs types"""
    global grist_client
    try:
        if not grist_client:
            return jsonify({'error': 'Client Grist non initialisé'}), 400
        
        # Récupérer les colonnes avec leurs types
        column_types = grist_client.get_table_columns_with_types(table_id)
        
        # Formater la réponse
        columns_info = []
        for col_name, col_type in column_types.items():
            columns_info.append({
                'name': col_name,
                'type': col_type,
                'is_date': col_type in ['Date', 'DateTime']
            })
        
        # Pour la compatibilité avec le code existant
        columns = list(column_types.keys())
        
        return jsonify({
            'columns': columns,
            'columns_info': columns_info,
            'column_types': column_types
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/count-pdfs', methods=['POST'])
def count_pdfs():
    """Compte le nombre de PDFs qui seront générés"""
    global grist_client
    try:
        if not grist_client:
            return jsonify({'error': 'Client Grist non initialisé'}), 400
        
        data = request.json
        table_id = data.get('table_id')
        filter_column = data.get('filter_column')
        advanced_filters_data = data.get('advanced_filters', {})
        
        # CORRECTION : Ne PAS extraire séparément, passer le dict complet
        # Le dict contient déjà 'mode' et 'filters'
        
        if not table_id or not filter_column:
            return jsonify({'error': 'Paramètres manquants'}), 400
        
        # Récupérer les données
        records = grist_client.get_table_records(table_id)
        df = pd.DataFrame(records)
        
        # CORRECTION : Passer le dictionnaire complet (pas mode séparé)
        if advanced_filters_data and advanced_filters_data.get('filters'):
            df = grist_client.apply_advanced_filters(df, advanced_filters_data, table_id)
        
        # Compter les valeurs uniques dans la colonne de filtrage
        if filter_column in df.columns:
            is_date_col = grist_client.is_date_column(table_id, filter_column)
            
            if is_date_col:
                print(f"📅 Colonne {filter_column} identifiée comme Date")
                date_series = grist_client._convert_timestamp_to_datetime(df[filter_column])
                unique_values = date_series.dt.date.unique()
                count = len([v for v in unique_values if pd.notna(v)])
            else:
                unique_values = df[filter_column].dropna().unique()
                count = len(unique_values)
            
            return jsonify({
                'count': int(count),
                'filter_column': filter_column,
                'total_records': len(df),
                'filter_mode': advanced_filters_data.get('mode', 'and')
            })
        else:
            return jsonify({'error': f'Colonne {filter_column} introuvable'}), 404
            
    except Exception as e:
        print(f"Erreur lors du comptage: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload-logo', methods=['POST'])
def upload_logo():
    """Upload un logo personnalisé"""
    try:
        if 'logo' not in request.files:
            return jsonify({'error': 'Aucun fichier fourni'}), 400
        
        file = request.files['logo']
        
        if file.filename == '':
            return jsonify({'error': 'Nom de fichier vide'}), 400
        
        if not allowed_logo_file(file.filename):
            return jsonify({'error': 'Type de fichier non autorisé'}), 400
        
        # Sécuriser le nom de fichier
        filename = secure_filename(file.filename)
        timestamp = int(time.time())
        filename = f"{timestamp}_{filename}"
        
        # Sauvegarder le fichier
        filepath = os.path.join(LOGO_UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # CORRECTION : Retourner le chemin RELATIF avec des slashes
        filepath_relative = f"uploads/logos/{filename}"
        
        return jsonify({
            'success': True,
            'filepath': filepath_relative,
            'filename': filename
        })
        
    except Exception as e:
        print(f"Erreur upload logo: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/upload-signature', methods=['POST'])
def upload_signature():
    """Upload une signature"""
    try:
        if 'signature' not in request.files:
            return jsonify({'error': 'Aucun fichier fourni'}), 400
        
        file = request.files['signature']
        
        if file.filename == '':
            return jsonify({'error': 'Nom de fichier vide'}), 400
        
        if not Config.allowed_file(file.filename):
            return jsonify({'error': 'Type de fichier non autorisé'}), 400
        
        # Sécuriser et horodater le nom
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        
        # Sauvegarder
        filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # CORRECTION : Retourner le chemin RELATIF avec des slashes
        filepath_relative = f"uploads/signatures/{filename}"
        
        return jsonify({
            'success': True,
            'filepath': filepath_relative,
            'filename': filename
        })
        
    except Exception as e:
        print(f"Erreur upload signature: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export', methods=['POST'])
def export_pdfs():
    """Génère les PDFs filtrés"""
    global grist_client, pdf_generator
    
    try:
        if not grist_client:
            return jsonify({'error': 'Client Grist non initialisé. Veuillez d\'abord charger les tables.'}), 400
        
        data = request.json
        table_id = data.get('table_id')
        filter_column = data.get('filter_column')
        selected_columns = data.get('selected_columns', [])
        output_dir = data.get('output_dir')
        filename_pattern = data.get('filename_pattern', '{filter_value}_{date}.pdf')
        
        # Récupération des informations de personnalisation
        service_name = data.get('service_name', 'DRAAF SRFD Occitanie')
        signer_firstname = data.get('signer_firstname', '')
        signer_name = data.get('signer_name', '')
        signer_title = data.get('signer_title', '')
        signature_path = data.get('signature_path', None)
        logo_path = data.get('logo_path', None)

        # Convertir en chemins absolus
        if signature_path and not os.path.isabs(signature_path):
            signature_path = os.path.join(BASE_DIR, signature_path)
            print(f"📝 Signature convertie: {signature_path}")

        if logo_path and not os.path.isabs(logo_path):
            logo_path = os.path.join(BASE_DIR, logo_path)
            print(f"🖼️  Logo converti: {logo_path}")
        
        # Récupérer le dictionnaire complet des filtres
        advanced_filters_data = data.get('advanced_filters', {})
        
        if not table_id or not filter_column or not selected_columns:
            return jsonify({'error': 'Paramètres manquants'}), 400
        
        # NOUVEAU : Vérifier si le fichier logo existe
        if logo_path and not os.path.exists(logo_path):
            print(f"⚠️ Logo introuvable: {logo_path}")
            print(f"   Utilisation du logo par défaut")
            logo_path = None  # Utiliser le logo par défaut
        
        # Récupérer les données de Grist
        records = grist_client.get_table_records(table_id)
        df = pd.DataFrame(records)
        
        # Configuration PDF
        pdf_config = PDFConfig(
            service_name=service_name,
            signer_firstname=signer_firstname,
            signer_name=signer_name,
            signer_title=signer_title,
            signature_path=signature_path,
            logo_path=logo_path
        )
        
        # Créer le générateur PDF avec le logo
        if logo_path and os.path.exists(logo_path):
            pdf_generator = PDFGenerator(logo_path=logo_path)
            print(f"✓ Logo chargé: {logo_path}")
        else:
            pdf_generator = PDFGenerator()
            print(f"✓ Logo par défaut utilisé")
        
        # Passer le dictionnaire complet
        filters_to_apply = advanced_filters_data if advanced_filters_data.get('filters') else None
        
        # Générer les PDFs
        result_files = pdf_generator.export_filtered_pdfs(
            grist_client=grist_client,
            table_id=table_id,
            filter_column=filter_column,
            selected_columns=selected_columns,
            output_dir=output_dir,
            filename_pattern=filename_pattern,
            pdf_config=pdf_config,
            advanced_filters=filters_to_apply
        )
        
        # SUPPRIMÉ : Ne plus supprimer automatiquement le logo
        # Les logos uploadés sont conservés pour pouvoir être réutilisés
        # Un nettoyage périodique peut être fait manuellement si nécessaire
        
        return jsonify({
            'success': True,
            'files': result_files,
            'files_count': len(result_files),
            'filter_mode': advanced_filters_data.get('mode', 'and')
        })
        
    except Exception as e:
        print(f"Erreur lors de l'export: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# NOUVEAU : Route pour nettoyer manuellement les vieux logos
@app.route('/api/cleanup-logos', methods=['POST'])
def cleanup_logos():
    """Nettoie les logos non utilisés dans les configurations"""
    try:
        if not os.path.exists(LOGO_UPLOAD_FOLDER):
            return jsonify({'message': 'Aucun logo à nettoyer'}), 200
        
        # Récupérer tous les logos utilisés dans les configurations
        used_logos = set()
        if os.path.exists(CONFIGS_FOLDER):
            for filename in os.listdir(CONFIGS_FOLDER):
                if filename.endswith('.json'):
                    filepath = os.path.join(CONFIGS_FOLDER, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            config = json.load(f)
                            logo_path = config.get('customization', {}).get('logo_path')
                            if logo_path:
                                used_logos.add(logo_path)
                    except:
                        pass
        
        # Supprimer les logos non utilisés
        deleted_count = 0
        for filename in os.listdir(LOGO_UPLOAD_FOLDER):
            filepath = os.path.join(LOGO_UPLOAD_FOLDER, filename)
            if os.path.isfile(filepath) and filepath not in used_logos:
                try:
                    os.remove(filepath)
                    deleted_count += 1
                    print(f"✓ Logo non utilisé supprimé: {filename}")
                except Exception as e:
                    print(f"⚠️ Erreur suppression {filename}: {e}")
        
        return jsonify({
            'success': True,
            'deleted_count': deleted_count,
            'message': f'{deleted_count} logo(s) nettoyé(s)'
        })
        
    except Exception as e:
        print(f"Erreur nettoyage logos: {e}")
        return jsonify({'error': str(e)}), 500
    

# ============================================================================
# ROUTES DE CONFIGURATION AVEC POSTGRESQL ET ISOLATION PAR DOC_ID
# ============================================================================

@app.route('/api/config/list', methods=['GET'])
def list_configurations():
    """Liste les configurations pour le doc_id actuel uniquement"""
    try:
        doc_id = get_current_doc_id()
        if not doc_id:
            return jsonify({'error': 'doc_id non trouvé'}), 400
        
        # Récupérer UNIQUEMENT les configs de ce doc_id
        configs = Configuration.get_by_doc_id(doc_id)
        
        configs_list = [{
            'id': cfg.id,
            'filename': f"config_{cfg.id}",  # Pour compatibilité frontend
            'name': cfg.config_name,
            'table_id': cfg.table_id or 'N/A',
            'created_at': cfg.created_at.isoformat() if cfg.created_at else None,
            'has_logo': bool(cfg.logo_data),
            'has_signature': bool(cfg.signature_data)
        } for cfg in configs]
        
        return jsonify({'configs': configs_list})
        
    except Exception as e:
        print(f"Erreur liste configurations: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/save', methods=['POST'])
def save_configuration():
    """Sauvegarde une configuration associée au doc_id"""
    try:
        data = request.json
        config_name = data.get('config_name')
        doc_id = data.get('doc_id')
        
        if not config_name or not doc_id:
            return jsonify({'error': 'Nom et doc_id requis'}), 400
        
        # Créer la configuration
        config = Configuration(
            doc_id_hash=Configuration.hash_doc_id(doc_id),
            doc_id=doc_id,
            config_name=config_name,
            
            # Connexion
            api_url=data.get('api_url', ''),
            
            # Table
            table_id=data.get('table_id', ''),
            filter_column=data.get('filter_column', ''),
            selected_columns=json.dumps(data.get('selected_columns', [])),
            
            # Filtres
            advanced_filters=json.dumps(data.get('advanced_filters', [])),
            
            # Personnalisation
            service_name=data.get('service_name', ''),
            signer_firstname=data.get('signer_firstname', ''),
            signer_name=data.get('signer_name', ''),
            signer_title=data.get('signer_title', ''),
            
            # Export
            output_dir=data.get('output_dir', ''),
            filename_pattern=data.get('filename_pattern', '{filter_value}_{date}.pdf')
        )
        
        # Gérer les fichiers (logo et signature)
        # Le frontend doit envoyer les fichiers en base64
        if data.get('logo_base64'):
            try:
                logo_data = base64.b64decode(data['logo_base64'])
                config.logo_data = logo_data
                config.logo_filename = data.get('logo_filename', 'logo.png')
                config.logo_mimetype = data.get('logo_mimetype', 'image/png')
            except Exception as e:
                print(f"Erreur décodage logo: {e}")
        
        if data.get('signature_base64'):
            try:
                sig_data = base64.b64decode(data['signature_base64'])
                config.signature_data = sig_data
                config.signature_filename = data.get('signature_filename', 'signature.png')
                config.signature_mimetype = data.get('signature_mimetype', 'image/png')
            except Exception as e:
                print(f"Erreur décodage signature: {e}")
        
        db.session.add(config)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'id': config.id,
            'message': f'Configuration "{config_name}" sauvegardée avec succès'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erreur sauvegarde configuration: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/load/<int:config_id>', methods=['GET'])
def load_configuration(config_id):
    """Charge une configuration SI elle appartient au doc_id actuel"""
    try:
        doc_id = get_current_doc_id()
        if not doc_id:
            return jsonify({'error': 'doc_id non trouvé'}), 400
        
        # Sécurité: récupérer UNIQUEMENT si le doc_id correspond
        config = Configuration.get_config(config_id, doc_id)
        
        if not config:
            return jsonify({'error': 'Configuration non trouvée ou accès refusé'}), 404
        
        config_dict = config.to_dict()
        
        # Ajouter les URLs pour télécharger les fichiers si présents
        if config.logo_data:
            config_dict['customization']['logo_url'] = f'/api/config/{config_id}/logo'
        
        if config.signature_data:
            config_dict['customization']['signature_url'] = f'/api/config/{config_id}/signature'
        
        return jsonify({
            'success': True,
            'config': config_dict
        })
        
    except Exception as e:
        print(f"Erreur chargement configuration: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/<int:config_id>/logo', methods=['GET'])
def get_config_logo(config_id):
    """Récupère le logo d'une configuration"""
    try:
        doc_id = get_current_doc_id()
        if not doc_id:
            return jsonify({'error': 'doc_id non trouvé'}), 400
        
        config = Configuration.get_config(config_id, doc_id)
        
        if not config or not config.logo_data:
            return jsonify({'error': 'Logo non trouvé'}), 404
        
        # Retourner l'image
        from io import BytesIO
        return send_file(
            BytesIO(config.logo_data),
            mimetype=config.logo_mimetype or 'image/png',
            as_attachment=False,
            download_name=config.logo_filename or 'logo.png'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/<int:config_id>/signature', methods=['GET'])
def get_config_signature(config_id):
    """Récupère la signature d'une configuration"""
    try:
        doc_id = get_current_doc_id()
        if not doc_id:
            return jsonify({'error': 'doc_id non trouvé'}), 400
        
        config = Configuration.get_config(config_id, doc_id)
        
        if not config or not config.signature_data:
            return jsonify({'error': 'Signature non trouvée'}), 404
        
        from io import BytesIO
        return send_file(
            BytesIO(config.signature_data),
            mimetype=config.signature_mimetype or 'image/png',
            as_attachment=False,
            download_name=config.signature_filename or 'signature.png'
        )
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/config/delete/<int:config_id>', methods=['DELETE'])
def delete_configuration(config_id):
    """Supprime une configuration SI elle appartient au doc_id actuel"""
    try:
        doc_id = get_current_doc_id()
        if not doc_id:
            return jsonify({'error': 'doc_id non trouvé'}), 400
        
        # Sécurité: supprimer UNIQUEMENT si le doc_id correspond
        config = Configuration.get_config(config_id, doc_id)
        
        if not config:
            return jsonify({'error': 'Configuration non trouvée ou accès refusé'}), 404
        
        db.session.delete(config)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Configuration supprimée avec succès'
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Erreur suppression configuration: {e}")
        return jsonify({'error': str(e)}), 500

# ============================================================================
# FIN DES ROUTES DE CONFIGURATION
# ============================================================================


@app.route('/api/upload-pdfs-to-grist', methods=['POST'])
def upload_pdfs_to_grist():
    """
    Upload les PDFs générés vers les enregistrements Grist correspondants
    Attache chaque PDF groupé à la PREMIÈRE ligne du groupe
    """
    global grist_client
    
    try:
        if not grist_client:
            return jsonify({'error': 'Client Grist non initialisé'}), 400
        
        data = request.json
        table_id = data.get('table_id')
        filter_column = data.get('filter_column')
        attachment_column = data.get('attachment_column')
        pdf_files = data.get('pdf_files', [])
        
        if not all([table_id, filter_column, attachment_column, pdf_files]):
            return jsonify({'error': 'Paramètres manquants'}), 400
        
        print(f"📤 Upload de {len(pdf_files)} PDFs vers Grist...")
        print(f"   Table: {table_id}")
        print(f"   Colonne de filtrage: {filter_column}")
        print(f"   Colonne d'attachement: {attachment_column}")
        
        results = []
        success_count = 0
        error_count = 0
        
        # Récupérer tous les enregistrements une seule fois
        print(f"📊 Récupération des enregistrements de la table {table_id}...")
        all_records = grist_client.get_table_data(table_id)
        print(f"   ✓ {len(all_records)} enregistrements récupérés")
        
        # Vérifier si la colonne de filtrage est une colonne Date
        is_date_column = grist_client.is_date_column(table_id, filter_column)
        
        for pdf_info in pdf_files:
            filter_value = pdf_info['filter_value']
            filepath = pdf_info['filepath']
            
            print(f"\n🔄 Traitement: {filter_value}")
            
            try:
                # Vérifier que le fichier existe et est accessible
                if not os.path.exists(filepath):
                    raise Exception(f"Fichier introuvable: {filepath}")
                
                # 1. Uploader le PDF comme attachment dans Grist
                print(f"   📎 Upload du fichier {os.path.basename(filepath)}...")
                
                # Attendre un peu entre chaque upload pour éviter les problèmes de concurrence
                if pdf_files.index(pdf_info) > 0:
                    time.sleep(0.5)
                
                attachment_id = grist_client.upload_attachment(filepath)
                print(f"   ✓ Attachment ID: {attachment_id}")
                
                # 2. Trouver la PREMIÈRE ligne qui correspond au filtre
                target_record = None
                
                for record in all_records:
                    record_fields = record.get('fields', {})
                    field_value = record_fields.get(filter_column)
                    
                    # Comparer les valeurs
                    if is_date_column:
                        # Pour les dates, convertir et comparer en DD/MM/YYYY
                        try:
                            date_series = pd.Series([field_value])
                            converted_date = grist_client._convert_timestamp_to_datetime(date_series)
                            formatted_date = converted_date.dt.strftime('%d/%m/%Y').iloc[0]
                            
                            if str(formatted_date) == str(filter_value):
                                target_record = record
                                break
                        except:
                            # Si conversion échoue, comparer directement
                            if str(field_value) == str(filter_value):
                                target_record = record
                                break
                    else:
                        # Pour les autres colonnes, comparaison directe
                        if str(field_value) == str(filter_value):
                            target_record = record
                            break
                
                if not target_record:
                    raise Exception(f"Aucun enregistrement trouvé pour {filter_column} = {filter_value}")
                
                record_id = target_record['id']
                print(f"   ✓ Première ligne trouvée: Record ID {record_id}")
                
                # 3. Attacher le PDF à la première ligne du groupe
                print(f"   🔗 Attachement du PDF à l'enregistrement {record_id}...")
                
                # Utiliser la méthode d'update de Grist
                url = f"{grist_client.api_url}/api/docs/{grist_client.doc_id}/tables/{table_id}/records"
                
                payload = {
                    "records": [
                        {
                            "id": record_id,
                            "fields": {
                                attachment_column: ['L', attachment_id]  # Format Grist pour les attachments
                            }
                        }
                    ]
                }
                
                response = requests.patch(url, headers=grist_client.headers, json=payload)
                response.raise_for_status()
                
                print(f"   ✅ PDF attaché avec succès!")
                
                results.append({
                    'filter_value': filter_value,
                    'success': True,
                    'record_id': record_id,
                    'attachment_id': attachment_id,
                    'message': f'PDF attaché à la première ligne du groupe (ID: {record_id})'
                })
                success_count += 1
                
            except Exception as e:
                print(f"   ❌ Erreur: {str(e)}")
                import traceback
                traceback.print_exc()
                
                results.append({
                    'filter_value': filter_value,
                    'success': False,
                    'error': str(e)
                })
                error_count += 1
        
        print(f"\n✅ Upload terminé: {success_count} succès, {error_count} erreurs")
        
        return jsonify({
            'success': True,
            'success_count': success_count,
            'error_count': error_count,
            'results': results
        })
        
    except Exception as e:
        print(f"❌ Erreur globale lors de l'upload: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

# Ajoute cette route dans app.py (après les autres routes)

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Sert les fichiers uploadés (logos et signatures)"""
    try:
        # Normaliser le chemin avec des backslashes Windows
        filepath = os.path.join(BASE_DIR, 'uploads', filename)
        
        if not os.path.exists(filepath):
            print(f"❌ Fichier introuvable: {filepath}")
            return jsonify({'error': 'Fichier introuvable'}), 404
        
        print(f"✅ Fichier servi: {filepath}")
        return send_file(filepath)
        
    except Exception as e:
        print(f"Erreur serveur fichier: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 Démarrage de l'application...")
    app.run(debug=True, host='0.0.0.0', port=5000)