"""
Tests unitaires pour les modules de l'application
Exécuter avec: pytest tests/
"""

import pytest
import os
import sys
import pandas as pd
from datetime import datetime

# Ajouter le répertoire parent au path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from config import PDFConfig, Config
from grist_client import GristClient
from pdf_generator import PDFGenerator


# ============ Tests Config ============

class TestPDFConfig:
    """Tests pour la classe PDFConfig"""
    
    def test_default_values(self):
        """Test des valeurs par défaut"""
        config = PDFConfig()
        assert config.service_name == "DRAAF SRFD Occitanie"
        assert config.signer_name == ""
        assert config.signer_firstname == ""
        assert config.signer_function == ""
        assert config.signature_path is None
    
    def test_from_dict(self):
        """Test de création depuis un dictionnaire"""
        data = {
            'service_name': 'Test Service',
            'signer_name': 'Dupont',
            'signer_firstname': 'Jean',
            'signer_function': 'Directeur',
            'signature_path': '/path/to/signature.png'
        }
        config = PDFConfig.from_dict(data)
        assert config.service_name == 'Test Service'
        assert config.signer_name == 'Dupont'
        assert config.signer_firstname == 'Jean'
        assert config.signer_function == 'Directeur'
        assert config.signature_path == '/path/to/signature.png'
    
    def test_from_dict_partial(self):
        """Test avec données partielles"""
        data = {'service_name': 'Partial Service'}
        config = PDFConfig.from_dict(data)
        assert config.service_name == 'Partial Service'
        assert config.signer_name == ""
        assert config.signature_path is None


class TestConfig:
    """Tests pour la classe Config"""
    
    def test_allowed_file_valid(self):
        """Test des extensions de fichiers valides"""
        assert Config.allowed_file('test.png') == True
        assert Config.allowed_file('test.jpg') == True
        assert Config.allowed_file('test.jpeg') == True
        assert Config.allowed_file('TEST.PNG') == True  # Majuscules
    
    def test_allowed_file_invalid(self):
        """Test des extensions de fichiers invalides"""
        assert Config.allowed_file('test.pdf') == False
        assert Config.allowed_file('test.txt') == False
        assert Config.allowed_file('test') == False
        assert Config.allowed_file('') == False
    
    def test_upload_folder_exists(self):
        """Test que le dossier d'upload est défini"""
        assert hasattr(Config, 'UPLOAD_FOLDER')
        assert Config.UPLOAD_FOLDER == 'uploads/signatures'


# ============ Tests GristClient ============

class TestGristClient:
    """Tests pour la classe GristClient"""
    
    @pytest.fixture
    def mock_client(self):
        """Fixture pour créer un client de test"""
        return GristClient(
            api_url='https://test.getgrist.com',
            api_token='test_token',
            doc_id='test_doc'
        )
    
    def test_initialization(self, mock_client):
        """Test de l'initialisation"""
        assert mock_client.api_url == 'https://test.getgrist.com'
        assert mock_client.api_token == 'test_token'
        assert mock_client.doc_id == 'test_doc'
        assert 'Authorization' in mock_client.headers
        assert mock_client.headers['Authorization'] == 'Bearer test_token'
    
    def test_filter_data_by_column(self, mock_client):
        """Test du filtrage de données"""
        # Données de test
        data = [
            {'fields': {'Nom': 'Dupont', 'Ville': 'Paris', 'Age': 30}},
            {'fields': {'Nom': 'Martin', 'Ville': 'Lyon', 'Age': 25}},
            {'fields': {'Nom': 'Bernard', 'Ville': 'Paris', 'Age': 35}}
        ]
        
        # Filtrage par ville
        result = mock_client.filter_data_by_column(
            data, 
            filter_column='Ville',
            selected_columns=['Nom', 'Age']
        )
        
        groups = list(result)
        assert len(groups) == 2  # Paris et Lyon
        
        # Vérifier Paris
        paris_group = [g for g in groups if g[0] == 'Paris'][0]
        assert len(paris_group[1]) == 2  # 2 personnes à Paris
    
    def test_apply_advanced_filters(self, mock_client):
        """Test des filtres avancés"""
        df = pd.DataFrame({
            'Nom': ['Dupont', 'Martin', 'Bernard'],
            'Age': [30, 25, 35],
            'Ville': ['Paris', 'Lyon', 'Paris']
        })
        
        # Filtre: Age > 27
        filters = [{'column': 'Age', 'operator': 'greater_than', 'value': '27'}]
        result = mock_client.apply_advanced_filters(df, filters)
        
        assert len(result) == 2  # Dupont (30) et Bernard (35)
        assert 'Martin' not in result['Nom'].values
    
    def test_apply_advanced_filters_contains(self, mock_client):
        """Test du filtre 'contains'"""
        df = pd.DataFrame({
            'Nom': ['Dupont', 'Martin', 'Bernard'],
            'Email': ['j.dupont@test.fr', 'm.martin@test.fr', 'b.bernard@test.fr']
        })
        
        filters = [{'column': 'Email', 'operator': 'contains', 'value': 'martin'}]
        result = mock_client.apply_advanced_filters(df, filters)
        
        assert len(result) == 1
        assert result.iloc[0]['Nom'] == 'Martin'


# ============ Tests PDFGenerator ============

class TestPDFGenerator:
    """Tests pour la classe PDFGenerator"""
    
    @pytest.fixture
    def generator(self, tmp_path):
        """Fixture pour créer un générateur avec logo temporaire"""
        logo_path = tmp_path / "test_logo.png"
        # Créer un logo factice
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(str(logo_path))
        
        return PDFGenerator(logo_path=str(logo_path))
    
    def test_initialization(self, generator):
        """Test de l'initialisation"""
        assert generator.logo_path is not None
        assert os.path.exists(generator.logo_path)
    
    def test_detect_date_columns(self, generator):
        """Test de détection des colonnes de dates"""
        df = pd.DataFrame({
            'Nom': ['Dupont', 'Martin'],
            'Date_Creation': ['2024-01-15', '2024-02-20'],
            'Age': [30, 25],
            'Date_Modif': ['15/01/2024', '20/02/2024']
        })
        
        columns = ['Nom', 'Date_Creation', 'Age', 'Date_Modif']
        date_cols = generator.detect_date_columns(df, columns)
        
        assert 'Date_Creation' in date_cols
        assert 'Nom' not in date_cols
        assert 'Age' not in date_cols
    
    def test_format_date_value(self, generator):
        """Test du formatage de dates"""
        # Date valide
        result = generator.format_date_value('2024-01-15')
        assert result == '15/01/2024'
        
        # Valeur nulle
        result = generator.format_date_value(pd.NA)
        assert result == ""
        
        # Valeur non-date
        result = generator.format_date_value('pas une date')
        assert result == 'pas une date'
    
    def test_create_pdf_basic(self, generator, tmp_path):
        """Test de création d'un PDF basique"""
        # Données de test
        df = pd.DataFrame({
            'Nom': ['Dupont', 'Martin'],
            'Age': [30, 25],
            'Ville': ['Paris', 'Lyon']
        })
        
        pdf_config = PDFConfig(
            service_name='Service Test',
            signer_name='Test',
            signer_firstname='Jean'
        )
        
        output_file = tmp_path / "test_output.pdf"
        
        # Créer le PDF
        generator.create_pdf(
            data=df,
            filename=str(output_file),
            title='Test Document',
            columns=['Nom', 'Age', 'Ville'],
            pdf_config=pdf_config
        )
        
        # Vérifier que le fichier existe
        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 0
    
    def test_create_pdf_with_signature(self, generator, tmp_path):
        """Test de création PDF avec signature"""
        # Créer une image de signature factice
        from PIL import Image
        sig_path = tmp_path / "signature.png"
        img = Image.new('RGB', (200, 100), color='blue')
        img.save(str(sig_path))
        
        df = pd.DataFrame({
            'Nom': ['Test'],
            'Ville': ['Paris']
        })
        
        pdf_config = PDFConfig(
            service_name='Service Test',
            signer_name='Dupont',
            signer_firstname='Jean',
            signer_function='Directeur',
            signature_path=str(sig_path)
        )
        
        output_file = tmp_path / "test_with_signature.pdf"
        
        generator.create_pdf(
            data=df,
            filename=str(output_file),
            title='Document avec Signature',
            columns=['Nom', 'Ville'],
            pdf_config=pdf_config
        )
        
        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 0


# ============ Tests d'intégration ============

class TestIntegration:
    """Tests d'intégration entre modules"""
    
    def test_workflow_complet(self, tmp_path):
        """Test du workflow complet sans API Grist"""
        # 1. Configuration
        pdf_config = PDFConfig.from_dict({
            'service_name': 'Test Integration',
            'signer_name': 'Testeur',
            'signer_firstname': 'Integration'
        })
        
        # 2. Données simulées (comme si elles venaient de Grist)
        data = [
            {'fields': {'Nom': 'Dupont', 'Ville': 'Paris', 'Score': 85}},
            {'fields': {'Nom': 'Martin', 'Ville': 'Paris', 'Score': 92}},
            {'fields': {'Nom': 'Bernard', 'Ville': 'Lyon', 'Score': 78}}
        ]
        
        # 3. Créer un client mock
        client = GristClient('http://test', 'token', 'doc')
        
        # 4. Filtrer les données
        grouped = client.filter_data_by_column(
            data,
            filter_column='Ville',
            selected_columns=['Nom', 'Score']
        )
        
        # 5. Générer les PDFs
        generator = PDFGenerator()
        
        for ville, groupe_df in grouped:
            output_file = tmp_path / f"test_{ville}.pdf"
            generator.create_pdf(
                data=groupe_df,
                filename=str(output_file),
                title=f'Rapport {ville}',
                columns=['Nom', 'Score'],
                pdf_config=pdf_config
            )
            
            assert os.path.exists(output_file)
        
        # Vérifier qu'on a bien 2 PDFs (Paris et Lyon)
        pdf_files = list(tmp_path.glob("*.pdf"))
        assert len(pdf_files) == 2


# ============ Configuration Pytest ============

@pytest.fixture(autouse=True)
def setup_teardown():
    """Setup et teardown pour chaque test"""
    # Setup
    yield
    # Teardown (si nécessaire)
    pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])