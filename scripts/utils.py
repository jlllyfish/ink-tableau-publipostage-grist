"""
Scripts utilitaires pour la gestion de l'application
"""

import os
import sys
import shutil
import argparse
from datetime import datetime, timedelta
from pathlib import Path


def clean_uploads(days=30):
    """
    Nettoie les signatures uploadées plus anciennes que X jours
    
    Args:
        days (int): Nombre de jours avant suppression (défaut: 30)
    """
    uploads_dir = Path('uploads/signatures')
    
    if not uploads_dir.exists():
        print(f"❌ Dossier {uploads_dir} n'existe pas")
        return
    
    cutoff_date = datetime.now() - timedelta(days=days)
    deleted_count = 0
    
    for file_path in uploads_dir.glob('*'):
        if file_path.is_file():
            file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
            if file_time < cutoff_date:
                file_path.unlink()
                deleted_count += 1
                print(f"🗑️  Supprimé: {file_path.name}")
    
    print(f"\n✅ {deleted_count} fichier(s) supprimé(s)")


def backup_signatures(backup_dir='backups'):
    """
    Crée une sauvegarde des signatures
    
    Args:
        backup_dir (str): Dossier de destination
    """
    uploads_dir = Path('uploads/signatures')
    backup_path = Path(backup_dir)
    
    if not uploads_dir.exists():
        print(f"❌ Dossier {uploads_dir} n'existe pas")
        return
    
    # Créer le dossier de backup
    backup_path.mkdir(exist_ok=True)
    
    # Nom de la sauvegarde avec timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = backup_path / f'signatures_{timestamp}.zip'
    
    # Créer l'archive
    import zipfile
    with zipfile.ZipFile(backup_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in uploads_dir.glob('*'):
            if file_path.is_file():
                zipf.write(file_path, file_path.name)
    
    size_mb = backup_file.stat().st_size / (1024 * 1024)
    print(f"✅ Sauvegarde créée: {backup_file} ({size_mb:.2f} MB)")


def generate_secret_key():
    """Génère une clé secrète pour Flask"""
    import secrets
    key = secrets.token_hex(32)
    print("\n🔑 Clé secrète générée:")
    print(f"SECRET_KEY={key}")
    print("\n⚠️  Copiez cette clé dans votre fichier .env")


def check_dependencies():
    """Vérifie que toutes les dépendances sont installées"""
    required = [
        'flask',
        'pandas',
        'reportlab',
        'requests',
        'werkzeug',
        'pillow'
    ]
    
    missing = []
    
    for package in required:
        try:
            __import__(package)
            print(f"✅ {package}")
        except ImportError:
            print(f"❌ {package}")
            missing.append(package)
    
    if missing:
        print(f"\n⚠️  Packages manquants: {', '.join(missing)}")
        print(f"Installez-les avec: pip install {' '.join(missing)}")
        return False
    else:
        print("\n✅ Toutes les dépendances sont installées")
        return True


def create_project_structure():
    """Crée la structure de dossiers nécessaire"""
    folders = [
        'uploads/signatures',
        'static/css',
        'static/js',
        'static/images',
        'static/fonts',
        'templates',
        'logs',
        'backups'
    ]
    
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"✅ Dossier créé: {folder}")
    
    # Créer un .gitkeep pour les dossiers vides
    for folder in ['uploads/signatures', 'logs', 'backups']:
        gitkeep = Path(folder) / '.gitkeep'
        gitkeep.touch()
    
    print("\n✅ Structure de dossiers créée")


def check_env_file():
    """Vérifie si le fichier .env existe et est configuré"""
    env_path = Path('.env')
    env_example_path = Path('.env.example')
    
    if not env_path.exists():
        if env_example_path.exists():
            print("⚠️  Fichier .env manquant")
            print(f"Copiez .env.example vers .env:")
            print(f"  cp .env.example .env")
        else:
            print("❌ Fichiers .env et .env.example manquants")
        return False
    
    # Vérifier les variables importantes
    with open(env_path, 'r') as f:
        content = f.read()
        
    required_vars = [
        'SECRET_KEY',
        'FLASK_APP',
        'UPLOAD_FOLDER'
    ]
    
    missing = []
    for var in required_vars:
        if var not in content or f"{var}=" not in content:
            missing.append(var)
    
    if missing:
        print(f"⚠️  Variables manquantes dans .env: {', '.join(missing)}")
        return False
    
    # Vérifier si SECRET_KEY a été changée
    if 'changez-moi' in content.lower() or 'change-me' in content.lower():
        print("⚠️  SECRET_KEY n'a pas été changée!")
        print("Générez-en une nouvelle avec: python scripts/utils.py --generate-key")
        return False
    
    print("✅ Fichier .env correctement configuré")
    return True


def run_tests():
    """Exécute les tests unitaires"""
    try:
        import pytest
        result = pytest.main(['-v', 'tests/'])
        return result == 0
    except ImportError:
        print("❌ pytest non installé")
        print("Installez-le avec: pip install pytest pytest-flask")
        return False


def health_check():
    """Vérifie l'état général de l'application"""
    print("🔍 Vérification de l'état de l'application...\n")
    
    checks = {
        'Structure de dossiers': lambda: all(
            Path(f).exists() for f in ['uploads/signatures', 'static', 'templates']
        ),
        'Fichier .env': lambda: check_env_file(),
        'Dépendances': lambda: check_dependencies(),
        'Fichiers principaux': lambda: all(
            Path(f).exists() for f in ['app.py', 'config.py', 'grist_client.py', 'pdf_generator.py']
        )
    }
    
    results = {}
    for check_name, check_func in checks.items():
        try:
            results[check_name] = check_func()
        except Exception as e:
            print(f"❌ {check_name}: Erreur - {e}")
            results[check_name] = False
    
    print("\n" + "="*50)
    print("RÉSUMÉ:")
    print("="*50)
    
    for check_name, result in results.items():
        status = "✅" if result else "❌"
        print(f"{status} {check_name}")
    
    all_ok = all(results.values())
    
    print("\n" + "="*50)
    if all_ok:
        print("✅ Application prête à être utilisée!")
    else:
        print("⚠️  Certaines vérifications ont échoué")
    print("="*50)
    
    return all_ok


def show_info():
    """Affiche les informations sur le projet"""
    print("""
╔════════════════════════════════════════════════════╗
║     Export PDF Grist - Utilitaires                 ║
║     Version 2.0 - Architecture Modulaire           ║
╚════════════════════════════════════════════════════╝

📁 Structure:
   ├── app.py              # Application Flask
   ├── config.py           # Configuration
   ├── grist_client.py     # Client API Grist
   ├── pdf_generator.py    # Générateur PDF
   ├── templates/          # Templates HTML
   ├── static/             # Fichiers statiques
   ├── uploads/            # Fichiers uploadés
   └── tests/              # Tests unitaires

🛠️  Commandes disponibles:
   --health-check          Vérification complète
   --clean-uploads [days]  Nettoyer les uploads
   --backup                Sauvegarder les signatures
   --generate-key          Générer SECRET_KEY
   --check-deps            Vérifier dépendances
   --create-structure      Créer structure
   --run-tests             Lancer les tests
   --info                  Afficher cette aide

📚 Documentation:
   - README.md             Guide principal
   - DEPLOYMENT.md         Guide de déploiement
   - MIGRATION.md          Guide de migration

💡 Exemples:
   python scripts/utils.py --health-check
   python scripts/utils.py --clean-uploads 30
   python scripts/utils.py --backup
""")


def main():
    """Point d'entrée principal"""
    parser = argparse.ArgumentParser(
        description='Utilitaires pour Export PDF Grist'
    )
    
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Vérification complète de l\'application'
    )
    
    parser.add_argument(
        '--clean-uploads',
        type=int,
        nargs='?',
        const=30,
        help='Nettoyer les uploads plus vieux que X jours (défaut: 30)'
    )
    
    parser.add_argument(
        '--backup',
        action='store_true',
        help='Créer une sauvegarde des signatures'
    )
    
    parser.add_argument(
        '--generate-key',
        action='store_true',
        help='Générer une clé secrète'
    )
    
    parser.add_argument(
        '--check-deps',
        action='store_true',
        help='Vérifier les dépendances'
    )
    
    parser.add_argument(
        '--create-structure',
        action='store_true',
        help='Créer la structure de dossiers'
    )
    
    parser.add_argument(
        '--run-tests',
        action='store_true',
        help='Exécuter les tests unitaires'
    )
    
    parser.add_argument(
        '--info',
        action='store_true',
        help='Afficher les informations'
    )
    
    args = parser.parse_args()
    
    # Si aucun argument, afficher l'info
    if len(sys.argv) == 1:
        show_info()
        return
    
    # Exécuter les commandes
    if args.info:
        show_info()
    
    if args.health_check:
        health_check()
    
    if args.clean_uploads is not None:
        clean_uploads(args.clean_uploads)
    
    if args.backup:
        backup_signatures()
    
    if args.generate_key:
        generate_secret_key()
    
    if args.check_deps:
        check_dependencies()
    
    if args.create_structure:
        create_project_structure()
    
    if args.run_tests:
        success = run_tests()
        sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()