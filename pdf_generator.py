"""
Générateur de PDF avec personnalisation complète et pagination
"""

import os
import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Optional, Dict
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from config import PDFConfig


class NumberedCanvas:
    """Canvas personnalisé pour ajouter numéros de page et pied de page"""
    
    def __init__(self, canvas, doc, pdf_config):
        self.canvas = canvas
        self.doc = doc
        self.pdf_config = pdf_config
    
    def __call__(self, canvas, doc):
        """Appelé pour chaque page"""
        canvas.saveState()
        
        # Récupérer les dimensions de la page
        page_width = doc.pagesize[0]
        page_height = doc.pagesize[1]
        
        # Ajouter le pied de page
        self.draw_footer(canvas, page_width, page_height, doc.page)
        
        canvas.restoreState()
    
    def draw_footer(self, canvas, page_width, page_height, page_num):
        """
        Dessine le pied de page avec signature et numéro de page
        
        Args:
            canvas: Canvas ReportLab
            page_width: Largeur de la page
            page_height: Hauteur de la page
            page_num: Numéro de la page actuelle
        """
        # Position du pied de page (1cm du bas)
        footer_y = 1 * cm
        
        # 1. Ligne de séparation
        canvas.setStrokeColor(colors.HexColor('#DDDDDD'))
        canvas.setLineWidth(0.5)
        canvas.line(1*cm, footer_y + 1.5*cm, page_width - 1*cm, footer_y + 1.5*cm)
        
        # 2. Informations du signataire + signature (à gauche)
        left_x = 1.5*cm
        
        if self.pdf_config.signer_firstname or self.pdf_config.signer_name:
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.HexColor('#666666'))
            
            full_name = f"{self.pdf_config.signer_firstname} {self.pdf_config.signer_name}".strip()
            canvas.drawString(left_x, footer_y + 0.8*cm, full_name)
            
            if self.pdf_config.signer_title:
                canvas.setFont('Helvetica', 7)
                canvas.drawString(left_x, footer_y + 0.4*cm, self.pdf_config.signer_title)
            
            # 3. Signature miniature juste à cÃ´té du nom (si présente)
            if self.pdf_config.signature_path:
                signature_path = self.pdf_config.signature_path
                
                # Convertir en chemin absolu avant verification
                if not os.path.isabs(signature_path):
                    signature_path = os.path.abspath(signature_path)
                    print(f"Signature convertie: {signature_path}")
                
                if os.path.exists(signature_path):
                    try:
                        # Calculer la largeur du texte du nom
                        name_width = canvas.stringWidth(full_name, 'Helvetica', 8)
                        
                        # Placer la signature juste après le nom (avec 0.5cm d'espace)
                        sig_x = left_x + name_width + 1.5*cm
                        sig_y = footer_y + 0.3*cm
                        
                        canvas.drawImage(
                            signature_path,  # â† Utiliser signature_path, pas self.pdf_config.signature_path
                            sig_x, sig_y,
                            width=2*cm,
                            height=1*cm,
                            preserveAspectRatio=True,
                            mask='auto'
                        )
                    except Exception as e:
                        print(f" Erreur affichage signature miniature: {e}")
        
        # 4. Numéro de page (à droite)
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#666666'))
        page_text = f"Page {page_num}"
        text_width = canvas.stringWidth(page_text, 'Helvetica', 8)
        canvas.drawString(page_width - 1.5*cm - text_width, footer_y + 0.8*cm, page_text)
        
        # 5. Date de génération (à droite, sous le numéro de page)
        canvas.setFont('Helvetica', 7)
        date_text = f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
        text_width = canvas.stringWidth(date_text, 'Helvetica', 7)
        canvas.drawString(page_width - 1.5*cm - text_width, footer_y + 0.4*cm, date_text)


class PDFGenerator:
    """Générateur de PDF avec personnalisation complète"""
    
    def __init__(self, logo_path: str = None):
        """
        Initialise le generateur de PDF
        
        Args:
            logo_path (str): Chemin vers le logo (optionnel)
        """
        # Utiliser logo fourni ou logo par defaut
        if logo_path:
            self.logo_path = logo_path
        else:
            # Logo par defaut - calculer chemin absolu depuis l'emplacement du script
            script_dir = os.path.dirname(os.path.abspath(__file__))
            default_logo = os.path.join('static', 'images', 'logo_ministere_agriculture.png')
            self.logo_path = os.path.join(script_dir, default_logo)
        
        print(f"Logo configure: {self.logo_path}")
        print(f"   Existe? {os.path.exists(self.logo_path)}")
        
        self._register_fonts()
    
    def _register_fonts(self):
        """Enregistre les polices personnalisées (Marianne)"""
        try:
            # Tentative de chargement de Marianne
            font_paths = [
                'static/fonts/Marianne-Bold.ttf',
                'static/fonts/Marianne-Regular.ttf'
            ]
            for font_path in font_paths:
                if os.path.exists(font_path):
                    font_name = os.path.splitext(os.path.basename(font_path))[0]
                    pdfmetrics.registerFont(TTFont(font_name, font_path))
        except Exception as e:
            print(f"Avertissement: Impossible de charger Marianne, utilisation de Helvetica: {e}")
    
    def detect_date_columns(self, data: pd.DataFrame, columns: List[str], 
                           column_types: Dict[str, str] = None) -> List[str]:
        """
        Détecte les colonnes contenant des dates
        
        Args:
            data (pd.DataFrame): Données
            columns (List[str]): Liste des colonnes
            column_types (Dict[str, str]): Types des colonnes depuis l'API Grist
            
        Returns:
            List[str]: Colonnes de type date
        """
        date_columns = []
        
        # Si on a les types depuis l'API Grist, les utiliser en priorité
        if column_types:
            for col in columns:
                if col in column_types and column_types[col] in ['Date', 'DateTime']:
                    date_columns.append(col)
                    print(f" Colonne Date détectée via API: {col}")
            return date_columns
        
        # Sinon, détection heuristique plus stricte
        for col in columns:
            if col in data.columns and not data[col].empty:
                sample = data[col].dropna().head(10)
                
                # Ã‰viter de détecter les colonnes purement numériques comme des dates
                if pd.api.types.is_numeric_dtype(sample):
                    # Vérifier si ce sont des timestamps Unix (nombres très grands)
                    if sample.max() > 1000000000 and sample.max() < 10000000000:  # timestamp en secondes
                        try:
                            pd.to_datetime(sample, unit='s', errors='raise')
                            date_columns.append(col)
                            print(f" Colonne timestamp détectée: {col}")
                        except:
                            pass
                    # Sinon, c'est probablement une donnée numérique normale
                    continue
                
                # Pour les colonnes non-numériques, tester la conversion en date
                try:
                    pd.to_datetime(sample, errors='raise')
                    date_columns.append(col)
                    print(f" Colonne date détectée: {col}")
                except:
                    pass
        
        return date_columns
    
    def format_date_value(self, value) -> str:
        if pd.isna(value):
            return ""
        try:
            # Si c'est un nombre, vérifier si c'est un timestamp
            if isinstance(value, (int, float)):
                if 1000000000 < value < 10000000000:  # Timestamp en secondes
                    date_obj = pd.to_datetime(value, unit='s')
                else:
                    date_obj = pd.to_datetime(value)
            else:
                date_obj = pd.to_datetime(value)
            return date_obj.strftime('%d/%m/%Y')
        except Exception as e:
            print(f"Erreur formatage date: {value} (type: {type(value)}) - {e}")
            return str(value)
    
    def create_header(self, elements: list, styles, page_size: tuple, 
                     pdf_config: PDFConfig):
        """
        Crée l'en-tête du PDF avec logo et nom du service
        
        Args:
            elements (list): Liste des éléments du PDF
            styles: Styles ReportLab
            page_size (tuple): Taille de la page
            pdf_config (PDFConfig): Configuration PDF
        """
        try:
            logo_path = getattr(pdf_config, 'logo_path', None) or self.logo_path
            # AJOUTER CES 3 LIGNES :
            if logo_path and not os.path.isabs(logo_path):
                logo_path = os.path.abspath(logo_path)
                print(f" Logo converti: {logo_path}")

            if logo_path and os.path.exists(logo_path):
                # Logo à gauche
                target_height = 1.8 * cm
                target_width = target_height * (2670 / 1732)
                
                if target_width > 5 * cm:
                    target_width = 5 * cm
                    target_height = target_width * (1732 / 2670)
                
                logo = Image(logo_path, width=target_width, height=target_height)
                
                # Nom du service à droite
                service_style = ParagraphStyle(
                    'ServiceStyle',
                    parent=styles['Normal'],
                    fontSize=14,
                    fontName='Helvetica-Bold',
                    textColor=colors.HexColor('#000091'),
                    alignment=2
                )
                service_text = Paragraph(pdf_config.service_name.replace('\n', '<br/>'), service_style)
                
                page_width = page_size[0] - 2*cm
                logo_col_width = target_width + 1*cm
                text_col_width = max(page_width - logo_col_width, 3*cm)
                
                header_table = Table([[logo, service_text]], colWidths=[logo_col_width, text_col_width])
                header_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                    ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                ]))
                
                elements.append(header_table)
            else:
                service_style = ParagraphStyle(
                    'ServiceStyleFallback',
                    parent=styles['Normal'],
                    fontSize=14,
                    fontName='Helvetica-Bold',
                    textColor=colors.HexColor('#000091'),
                    alignment=2
                )
                elements.append(Paragraph(pdf_config.service_name, service_style))
            
            elements.append(Spacer(1, 15))
            
        except Exception as e:
            print(f"  Erreur création en-tête: {e}")
            service_style = ParagraphStyle(
                'ServiceStyleError',
                parent=styles['Normal'],
                fontSize=14,
                fontName='Helvetica-Bold',
                textColor=colors.HexColor('#000091'),
                alignment=2
            )
            elements.append(Paragraph(pdf_config.service_name, service_style))
            elements.append(Spacer(1, 15))
    
    def create_pdf(self, data: pd.DataFrame, filename: str, title: str, 
                   columns: List[str], pdf_config: PDFConfig, 
                   applied_filters: Optional[List] = None,
                   column_types: Dict[str, str] = None,
                   column_labels: Dict[str, str] = None):
        """
        Crée un PDF à partir des données avec personnalisation complète
        
        Args:
            data (pd.DataFrame): Données à inclure
            filename (str): Chemin du fichier de sortie
            title (str): Titre du document
            columns (List[str]): Colonnes à inclure (dans l'ordre)
            pdf_config (PDFConfig): Configuration PDF
            applied_filters (Optional[List]): Filtres appliqués
            column_types (Dict[str, str]): Types des colonnes depuis l'API Grist
        """
        page_size = landscape(A4)
        
        # NOUVEAU : Augmenter bottomMargin pour laisser place au pied de page
        doc = SimpleDocTemplate(
            filename, 
            pagesize=page_size, 
            leftMargin=1*cm, 
            rightMargin=1*cm,
            topMargin=1*cm, 
            bottomMargin=3*cm  # â† Augmenté de 2cm à 3cm pour le footer
        )
        
        elements = []
        styles = getSampleStyleSheet()
        
        # Détecter les colonnes de dates en passant les types depuis l'API
        date_columns = self.detect_date_columns(data, columns, column_types)
        print(f" Colonnes de dates détectées: {date_columns}")
        
        # Créer l'en-tête personnalisé
        self.create_header(elements, styles, page_size, pdf_config)
        
        # Titre du document
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=14,
            spaceAfter=20,
            alignment=1,
            textColor=colors.HexColor('#000091')
        )
        elements.append(Paragraph(title, title_style))
        elements.append(Spacer(1, 15))
        
        if not data.empty:
            # Calculer les largeurs de colonnes
            available_width = page_size[0] - 2*cm
            num_columns = len(columns)
            base_col_width = available_width / num_columns
            
            col_widths = []
            for col in columns:
                if col in data.columns:
                    if col in date_columns:
                        max_content_length = 12
                    else:
                        max_content_length = max(
                            len(str(col)),
                            data[col].astype(str).str.len().max()
                        )
                else:
                    max_content_length = len(str(col))
                
                width = min(max(base_col_width * 0.6, max_content_length * 0.15 * cm), 
                           base_col_width * 1.5)
                col_widths.append(width)
            
            total_width = sum(col_widths)
            if total_width != available_width:
                scale = available_width / total_width
                col_widths = [w * scale for w in col_widths]
            
            # Creer les donnees du tableau
            # Utiliser les labels si disponibles, sinon les IDs
            headers = []
            for col in columns:
                if col in data.columns:
                    # Utiliser le label si disponible, sinon l'ID
                    label = column_labels.get(col, col) if column_labels else col
                    headers.append(label)
            table_data = [headers]
            
            for _, row in data.iterrows():
                row_data = []
                for col in columns:
                    if col in data.columns:
                        value = row[col]
                        
                        # Gérer les différents types de valeurs
                        if isinstance(value, (list, tuple, np.ndarray)):
                            # Arrays/listes -> concaténer (filtrer le marqueur 'L' de Grist)
                            clean_values = [str(v) for v in value if v and str(v) != 'L']
                            formatted_value = ", ".join(clean_values)
                        elif col in date_columns:
                            # Dates - ne pas utiliser if value car 0 est valide
                            formatted_value = self.format_date_value(value)
                        elif pd.isna(value):
                            # NaN
                            formatted_value = ""
                        else:
                            # Texte normal
                            formatted_value = str(value)
                        
                        cell_style = ParagraphStyle(
                            'CellStyle',
                            parent=styles['Normal'],
                            fontSize=7,
                            leading=9
                        )
                        row_data.append(Paragraph(formatted_value, cell_style))
                table_data.append(row_data)
            
            # Créer et styliser le tableau
            # IMPORTANT : repeatRows=1 pour répéter l'en-tête sur chaque page
            table = Table(table_data, colWidths=col_widths, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#000091')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 8),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 1), (-1, -1), 7),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('LINEBELOW', (0, 0), (-1, 0), 1, colors.HexColor('#000091')),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ]))
            
            elements.append(table)
            
        else:
            no_data_style = ParagraphStyle(
                'NoData',
                parent=styles['Normal'],
                fontSize=12,
                alignment=1,
                textColor=colors.red
            )
            elements.append(Paragraph("Aucune donnée à afficher pour ce filtre", no_data_style))
        
        # NOUVEAU : Build avec fonction de pied de page personnalisée
        doc.build(
            elements,
            onFirstPage=NumberedCanvas(None, doc, pdf_config),
            onLaterPages=NumberedCanvas(None, doc, pdf_config)
        )
        
        print(f"PDF généré avec pagination : {filename}")
    
    def export_filtered_pdfs(self, grist_client, table_id: str, filter_column: str,
                         selected_columns: List[str], output_dir: str, 
                         filename_pattern: str, pdf_config: PDFConfig,
                         advanced_filters: Optional[List] = None) -> List[Dict]:
        """
        Exporte les PDFs filtrés avec support des filtres avancés
        
        Args:
            grist_client: Instance du client Grist
            table_id (str): ID de la table
            filter_column (str): Colonne de filtrage
            selected_columns (List[str]): Colonnes à inclure
            output_dir (str): Dossier de sortie
            filename_pattern (str): Modèle de nom de fichier
            pdf_config (PDFConfig): Configuration PDF
            advanced_filters (Optional[List]): Filtres avancés
            
        Returns:
            List[Dict]: Liste des fichiers exportés
        """
        try:
            os.makedirs(output_dir, exist_ok=True)
            data = grist_client.get_table_data(table_id)
            
            # Récupérer les types de colonnes depuis l'API Grist
            column_types = grist_client.get_table_columns_with_types(table_id)
            print(f" Types de colonnes récupérés: {column_types}")
            
            # Recuperer les labels des colonnes
            column_labels = grist_client.get_table_columns_with_labels(table_id)
            print(f"Labels de colonnes recuperes: {column_labels}")

            # Appliquer les filtres avancés si présents
            if advanced_filters:
                df_full = pd.DataFrame([record["fields"] for record in data])
                df_filtered = grist_client.apply_advanced_filters(df_full, advanced_filters, table_id)
                filtered_records = [{"fields": row.to_dict()} for _, row in df_filtered.iterrows()]
                grouped_data = grist_client.filter_data_by_column(filtered_records, filter_column, selected_columns, table_id)
            else:
                grouped_data = grist_client.filter_data_by_column(data, filter_column, selected_columns, table_id)
            
            exported_files = []
            current_date = datetime.now()
            
            for filter_value, group_data in grouped_data:
                safe_filter_value = str(filter_value).replace("/", "_").replace("\\", "_").replace(" ", "_")
                
                # Générer le nom de fichier
                filename = filename_pattern
                replacements = {
                    "{filter_value}": safe_filter_value,
                    "{timestamp}": current_date.strftime("%Y%m%d_%H%M%S"),
                    "{date}": current_date.strftime("%Y%m%d"),
                    "{table_name}": table_id,
                    "{user}": "user"
                }
                
                for old, new in replacements.items():
                    filename = filename.replace(old, new)
                
                filename = filename.replace("__", "_").replace("--", "-")
                if not filename.endswith('.pdf'):
                    filename += '.pdf'
                
                filepath = os.path.join(output_dir, filename)
                title = f"Données {filter_column}: {filter_value}"
                
                # Passer les types de colonnes à create_pdf
                self.create_pdf(group_data, filepath, title, selected_columns, 
                            pdf_config, advanced_filters, column_types, column_labels)
                
                exported_files.append({
                    'filename': filename,
                    'filter_value': str(filter_value),
                    'records_count': len(group_data),
                    'filepath': filepath
                })
            
            return exported_files
            
        except Exception as e:
            raise Exception(f"Erreur lors de l'export: {str(e)}")