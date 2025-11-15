"""
Client pour interagir avec l'API Grist
"""

import os
import requests
from typing import Dict, List, Optional, Tuple, Union
import pandas as pd


class GristClient:
    """Client pour interagir avec l'API Grist"""
    
    def __init__(self, api_url: str, api_token: str, doc_id: str):
        """
        Initialise le client Grist
        
        Args:
            api_url (str): URL de base de l'API Grist
            api_token (str): Token d'authentification
            doc_id (str): ID du document Grist
        """
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.doc_id = doc_id
        self.headers = {'Authorization': f'Bearer {api_token}'}
        # NOUVEAU : Cache pour stocker les types de colonnes
        self._column_types_cache = {}
    
    # ============================================
    # NOUVEAU : MÃ‰THODES POUR RÃ‰CUPÃ‰RER LES TYPES DE COLONNES
    # ============================================
    
    def get_table_columns_with_types(self, table_id: str) -> Dict[str, str]:
        """
        RÃ©cupÃ¨re les colonnes d'une table avec leurs types depuis l'API Grist
        
        Args:
            table_id (str): ID de la table
            
        Returns:
            Dict[str, str]: Dictionnaire {nom_colonne: type_colonne}
        """
        # VÃ©rifier le cache
        cache_key = f"{self.doc_id}_{table_id}"
        if cache_key in self._column_types_cache:
            return self._column_types_cache[cache_key]
        
        url = f"{self.api_url}/api/docs/{self.doc_id}/tables/{table_id}/columns"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        columns_data = response.json().get('columns', [])
        
        column_types = {}
        
        for col in columns_data:
            col_id = None
            col_type = 'Text'  # Type par dÃ©faut
            
            # RÃ©cupÃ©rer le nom de la colonne
            if 'id' in col:
                col_id = col['id']
            elif 'colId' in col:
                col_id = col['colId']
            
            # Si on a trouvÃ© l'ID, chercher le type
            if col_id:
                # Ignorer les colonnes helper de Grist
                if str(col_id).startswith('gristHelper_'):
                    continue
                
                # RÃ©cupÃ©rer le type de la colonne
                if 'fields' in col:
                    # Le type peut Ãªtre dans fields.type
                    col_type = col['fields'].get('type', 'Text')
                elif 'type' in col:
                    # Ou directement dans col.type
                    col_type = col['type']
                
                column_types[col_id] = col_type
                
                # Log pour debug des colonnes Date
                if col_type in ['Date', 'DateTime']:
                    print(f"âœ“ Colonne Date dÃ©tectÃ©e via API: {col_id} (type: {col_type})")
        
        # Mettre en cache
        self._column_types_cache[cache_key] = column_types
        
        return column_types
    
    def get_table_columns_with_labels(self, table_id: str) -> Dict[str, str]:
        """
        Recupere le mapping ID colonne -> Label affiche
        
        Args:
            table_id (str): ID de la table
            
        Returns:
            Dict[str, str]: {col_id: label}
        """
        url = f"{self.api_url}/api/docs/{self.doc_id}/tables/{table_id}/columns"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        columns_data = response.json().get('columns', [])
        
        column_labels = {}
        
        for col in columns_data:
            col_id = col.get('id') or col.get('colId')
            if col_id and not str(col_id).startswith('gristHelper_'):
                # Chercher le label dans fields.label ou utiliser l'ID
                label = col.get('fields', {}).get('label', col_id)
                if not label:  # Si label vide, utiliser l'ID
                    label = col_id
                column_labels[col_id] = label
        
        return column_labels
    
    def is_date_column(self, table_id: str, column_name: str) -> bool:
        """
        VÃ©rifie si une colonne est de type Date ou DateTime selon l'API Grist
        
        Args:
            table_id (str): ID de la table
            column_name (str): Nom de la colonne
            
        Returns:
            bool: True si la colonne est de type Date/DateTime
        """
        column_types = self.get_table_columns_with_types(table_id)
        col_type = column_types.get(column_name, 'Text')
        return col_type in ['Date', 'DateTime']
    
    def get_table_columns(self, table_id: str) -> List[str]:
        """
        RÃ©cupÃ¨re les colonnes d'une table (noms uniquement, pour compatibilitÃ©)
        
        Args:
            table_id (str): ID de la table
            
        Returns:
            List[str]: Liste des noms de colonnes
        """
        column_types = self.get_table_columns_with_types(table_id)
        return list(column_types.keys())
    
    # ============================================
    # MÃ‰THODES EXISTANTES (modifiÃ©es pour utiliser les vrais types)
    # ============================================
    
    def filter_data_by_column(
        self, 
        data: List[Dict], 
        filter_column: str, 
        selected_columns: List[str],
        table_id: Optional[str] = None
    ) -> List[Tuple[str, pd.DataFrame]]:
        """
        Filtre les donnÃ©es par colonne et retourne les groupes
        
        Args:
            data: Liste des enregistrements
            filter_column: Colonne utilisÃ©e pour filtrer/grouper
            selected_columns: Colonnes Ã  inclure dans le rÃ©sultat
            table_id: ID de la table (pour dÃ©terminer les types de colonnes)
            
        Returns:
            List[Tuple[str, pd.DataFrame]]: Liste de tuples (valeur_filtre, donnÃ©es_filtrÃ©es)
        """
        # Convertir en DataFrame
        df = pd.DataFrame([record["fields"] if "fields" in record else record for record in data])
        
        if filter_column not in df.columns:
            raise ValueError(f"Colonne de filtrage '{filter_column}' non trouvÃ©e dans les donnÃ©es")
        
        # VÃ©rifier si c'est une colonne Date en utilisant l'API
        is_date_col = False
        if table_id:
            is_date_col = self.is_date_column(table_id, filter_column)
        
        # Grouper par la colonne de filtrage
        groups = []
        
        if is_date_col:
            print(f"ðŸ“… Groupement par colonne Date: {filter_column}")
            # Pour les colonnes Date, convertir les timestamps
            df['_date_temp'] = self._convert_timestamp_to_datetime(df[filter_column])
            df['_date_formatted'] = df['_date_temp'].dt.strftime('%d/%m/%Y')
            
            # Grouper par date formatÃ©e
            for date_value in df['_date_formatted'].dropna().unique():
                group_df = df[df['_date_formatted'] == date_value].copy()
                
                # SÃ©lectionner uniquement les colonnes demandÃ©es
                if selected_columns:
                    cols_to_keep = [col for col in selected_columns if col in group_df.columns]
                    group_df = group_df[cols_to_keep]
                
                # Nettoyer les colonnes temporaires
                if '_date_temp' in group_df.columns:
                    group_df = group_df.drop(columns=['_date_temp', '_date_formatted'])
                
                groups.append((date_value, group_df))
            
            print(f"  âœ“ {len(groups)} groupes de dates crÃ©Ã©s")
        
        else:
            # Pour les colonnes non-Date, groupement normal
            for value in df[filter_column].dropna().unique():
                group_df = df[df[filter_column] == value].copy()
                
                # SÃ©lectionner uniquement les colonnes demandÃ©es
                if selected_columns:
                    cols_to_keep = [col for col in selected_columns if col in group_df.columns]
                    group_df = group_df[cols_to_keep]
                
                groups.append((str(value), group_df))
            
            print(f"  âœ“ {len(groups)} groupes crÃ©Ã©s pour la colonne {filter_column}")
        
        return groups
    
    def apply_advanced_filters(
    self, 
    df: pd.DataFrame, 
    filters_data: Union[List[Dict], Dict],
    table_id: Optional[str] = None
) -> pd.DataFrame:
        """
        Applique des filtres avancÃ©s sur un DataFrame avec support mode ET/OU
        
        Args:
            df: DataFrame Ã  filtrer
            filters_data: Soit une liste de filtres (ancien format), 
                        soit un dict {'mode': 'and'|'or', 'filters': [...]}
            table_id: ID de la table (pour dÃ©terminer les types de colonnes)
            
        Returns:
            DataFrame filtrÃ©
        """
        if not filters_data or df.empty:
            return df
        
        # NOUVEAU : GÃ©rer les deux formats (rÃ©trocompatibilitÃ©)
        if isinstance(filters_data, dict):
            mode = filters_data.get('mode', 'and')
            filters = filters_data.get('filters', [])
        else:
            # Ancien format : liste de filtres directe
            mode = 'and'
            filters = filters_data
        
        if not filters:
            return df
        
        print(f"ðŸ” Application des filtres en mode {mode.upper()}")
        
        # MODE ET : Application sÃ©quentielle (comportement actuel)
        if mode == 'and':
            filtered_df = df.copy()
            
            for filter_config in filters:
                column = filter_config.get('column')
                operator = filter_config.get('operator')
                value = filter_config.get('value')
                
                if not column or not operator or value is None or value == '':
                    continue
                
                if column not in filtered_df.columns:
                    continue
                
                try:
                    mask = self._create_filter_mask(
                        filtered_df, column, operator, value, table_id
                    )
                    filtered_df = filtered_df[mask]
                    print(f"  âœ“ Filtre appliquÃ© (ET): {column} {operator} {value} -> {len(filtered_df)} lignes restantes")
                
                except Exception as e:
                    print(f"âš ï¸ Erreur lors de l'application du filtre {filter_config}: {e}")
                    continue
            
            return filtered_df
        
        # MODE OU : Union des rÃ©sultats
        elif mode == 'or':
            all_masks = []
            
            for filter_config in filters:
                column = filter_config.get('column')
                operator = filter_config.get('operator')
                value = filter_config.get('value')
                
                if not column or not operator or value is None or value == '':
                    continue
                
                if column not in df.columns:
                    continue
                
                try:
                    mask = self._create_filter_mask(
                        df, column, operator, value, table_id
                    )
                    all_masks.append(mask)
                    matching_count = mask.sum()
                    print(f"  âœ“ Filtre Ã©valuÃ© (OU): {column} {operator} {value} -> {matching_count} lignes correspondent")
                
                except Exception as e:
                    print(f"âš ï¸ Erreur lors de l'Ã©valuation du filtre {filter_config}: {e}")
                    continue
            
            if not all_masks:
                return df
            
            # Combiner tous les masks avec OR
            combined_mask = all_masks[0]
            for mask in all_masks[1:]:
                combined_mask = combined_mask | mask
            
            filtered_df = df[combined_mask]
            print(f"  âœ“ RÃ©sultat final (OU): {len(filtered_df)} lignes correspondent Ã  au moins un filtre")
            
            return filtered_df
        
        else:
            print(f"âš ï¸ Mode de filtre inconnu: {mode}, utilisation du mode ET par dÃ©faut")
            return self.apply_advanced_filters(
                df, {'mode': 'and', 'filters': filters}, table_id
            )


    def _create_filter_mask(
        self, 
        df: pd.DataFrame, 
        column: str, 
        operator: str, 
        value: str,
        table_id: Optional[str] = None
    ) -> pd.Series:
        """
        CrÃ©e un masque boolÃ©en pour un filtre donnÃ©
        
        Args:
            df: DataFrame Ã  filtrer
            column: Nom de la colonne
            operator: OpÃ©rateur de comparaison
            value: Valeur Ã  comparer
            table_id: ID de la table
            
        Returns:
            SÃ©rie boolÃ©enne (masque)
        """
        # VÃ©rifier si c'est une colonne Date
        is_date_column = False
        if table_id:
            is_date_column = self.is_date_column(table_id, column)
        
        if is_date_column:
            print(f"ðŸ“… Application du filtre sur la colonne Date: {column}")
            date_col = self._convert_timestamp_to_datetime(df[column])
            
            try:
                filter_date = self._parse_date_filter(value)
                
                if operator == 'equals':
                    return date_col.dt.date == filter_date.date()
                elif operator == 'not_equals':
                    return date_col.dt.date != filter_date.date()
                elif operator == 'greater_than':
                    return date_col.dt.date > filter_date.date()
                elif operator == 'less_than':
                    return date_col.dt.date < filter_date.date()
                else:
                    print(f"âš ï¸ OpÃ©rateur non supportÃ© pour les dates: {operator}")
                    return pd.Series([True] * len(df), index=df.index)
            
            except Exception as e:
                print(f"âš ï¸ Erreur parsing date '{value}': {e}")
                return pd.Series([True] * len(df), index=df.index)
        
        # Filtres pour colonnes non-date
        else:
            if operator == 'equals':
                return df[column].astype(str) == str(value)
            
            elif operator == 'contains':
                return df[column].astype(str).str.contains(
                    str(value), 
                    case=False, 
                    na=False
                )
            
            elif operator == 'starts_with':
                return df[column].astype(str).str.startswith(
                    str(value), 
                    na=False
                )
            
            elif operator == 'ends_with':
                return df[column].astype(str).str.endswith(
                    str(value), 
                    na=False
                )
            
            elif operator == 'not_equals':
                return df[column].astype(str) != str(value)
            
            elif operator == 'greater_than':
                try:
                    numeric_col = pd.to_numeric(df[column], errors='coerce')
                    mask = numeric_col > float(value)
                    return mask.fillna(False)
                except (ValueError, TypeError) as e:
                    print(f"âš ï¸ Impossible de convertir '{column}' en nombre: {e}")
                    return pd.Series([True] * len(df), index=df.index)
            
            elif operator == 'less_than':
                try:
                    numeric_col = pd.to_numeric(df[column], errors='coerce')
                    mask = numeric_col < float(value)
                    return mask.fillna(False)
                except (ValueError, TypeError) as e:
                    print(f"âš ï¸ Impossible de convertir '{column}' en nombre: {e}")
                    return pd.Series([True] * len(df), index=df.index)
            
            else:
                print(f"âš ï¸ OpÃ©rateur non supportÃ©: {operator}")
                return pd.Series([True] * len(df), index=df.index)
    
    # ============================================
    # MÃ‰THODES EXISTANTES INCHANGÃ‰ES
    # ============================================
    
    def get_tables(self) -> List[Dict]:
        """
        RÃ©cupÃ¨re la liste des tables du document
        
        Returns:
            List[Dict]: Liste des tables avec leurs mÃ©tadonnÃ©es
        """
        url = f"{self.api_url}/api/docs/{self.doc_id}/tables"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get('tables', [])
    
    def get_table_data(self, table_id: str) -> List[Dict]:
        """
        RÃ©cupÃ¨re les donnÃ©es d'une table
        
        Returns:
            List[Dict]: Liste des enregistrements avec leurs champs
        """
        url = f"{self.api_url}/api/docs/{self.doc_id}/tables/{table_id}/records"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json().get('records', [])
    
    def get_table_records(self, table_id: str) -> List[Dict]:
        """
        RÃ©cupÃ¨re les enregistrements d'une table au format simplifiÃ©
        
        Returns:
            List[Dict]: Liste des enregistrements avec leurs champs (format simplifiÃ©)
        """
        records = self.get_table_data(table_id)
        
        # Convertir le format Grist en format simplifiÃ©
        simplified_records = []
        for record in records:
            if 'fields' in record:
                simplified_records.append(record['fields'])
            else:
                # Si dÃ©jÃ  au bon format
                simplified_records.append(record)
        
        return simplified_records
    
    def validate_connection(self) -> bool:
        """
        Valide la connexion Ã  l'API Grist
        
        Returns:
            bool: True si la connexion est valide
        """
        try:
            url = f"{self.api_url}/api/docs/{self.doc_id}"
            response = requests.get(url, headers=self.headers, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    def get_table_info(self, table_id: str) -> Dict:
        """
        RÃ©cupÃ¨re les informations dÃ©taillÃ©es d'une table
        
        Returns:
            Dict: Informations sur la table (nombre de lignes, colonnes, etc.)
        """
        try:
            data = self.get_table_data(table_id)
            columns = self.get_table_columns(table_id)
            
            return {
                'table_id': table_id,
                'row_count': len(data),
                'column_count': len(columns),
                'columns': columns,
                'has_data': len(data) > 0
            }
        except Exception as e:
            return {
                'table_id': table_id,
                'error': str(e)
            }
    
    # ============================================
    # MÃ‰THODES POUR LES DATES (TIMESTAMPS)
    # ============================================
    
    def _is_timestamp_column(self, series: pd.Series) -> bool:
        """
        DEPRECATED - Utiliser is_date_column() Ã  la place
        Cette mÃ©thode est conservÃ©e uniquement pour la compatibilitÃ©
        """
        # Cette mÃ©thode n'est plus utilisÃ©e car on rÃ©cupÃ¨re le vrai type depuis l'API
        return False
    
    def _convert_timestamp_to_datetime(self, series: pd.Series) -> pd.Series:
        """
        Convertit une sÃ©rie de timestamps Unix en datetime
        
        Args:
            series: SÃ©rie contenant des timestamps
            
        Returns:
            pd.Series: SÃ©rie convertie en datetime
        """
        try:
            # Convertir les timestamps Unix (en secondes) en datetime
            return pd.to_datetime(series, unit='s', errors='coerce')
        except:
            return pd.to_datetime(series, errors='coerce')
    
    def _parse_date_filter(self, date_string: str) -> pd.Timestamp:
        """
        Parse une date depuis diffÃ©rents formats
        
        Args:
            date_string: Date au format string
            
        Returns:
            pd.Timestamp: Date parsÃ©e
            
        Raises:
            ValueError: Si le format n'est pas reconnu
        """
        # Formats acceptÃ©s
        formats = [
            '%d/%m/%Y',      # 25/12/2024
            '%d-%m-%Y',      # 25-12-2024
            '%Y-%m-%d',      # 2024-12-25 (ISO)
            '%d/%m/%y',      # 25/12/24
            '%d.%m.%Y',      # 25.12.2024
        ]
        
        print(f"  ðŸ” Parsing de la date: '{date_string}'")
        
        for fmt in formats:
            try:
                parsed = pd.to_datetime(date_string, format=fmt)
                print(f"  âœ“ Date parsÃ©e avec le format {fmt}: {parsed}")
                return parsed
            except:
                continue
        
        # Si aucun format ne fonctionne, essayer le parser automatique
        try:
            parsed = pd.to_datetime(date_string, dayfirst=True)
            print(f"  âœ“ Date parsÃ©e automatiquement: {parsed}")
            return parsed
        except Exception as e:
            print(f"  âŒ Impossible de parser la date: {e}")
            raise ValueError(f"Format de date non reconnu: {date_string}")
    
    # ============================================
    # MÃ‰THODES POUR L'UPLOAD DE PIÃˆCES JOINTES (inchangÃ©es)
    # ============================================
    
    def upload_attachment(self, file_path: str) -> int:
        """
        Upload un fichier en tant que piÃ¨ce jointe sur Grist
        
        Args:
            file_path (str): Chemin vers le fichier Ã  uploader
            
        Returns:
            int: ID de l'attachment crÃ©Ã©
            
        Raises:
            Exception: Si l'upload Ã©choue
        """
        url = f"{self.api_url}/api/docs/{self.doc_id}/attachments"
        
        try:
            # VÃ©rifier que le fichier existe
            if not os.path.exists(file_path):
                raise Exception(f"Fichier introuvable: {file_path}")
            
            # VÃ©rifier la taille du fichier
            file_size = os.path.getsize(file_path)
            print(f"      ðŸ“Š Taille du fichier: {file_size / 1024:.2f} KB")
            
            # Ouvrir et uploader le fichier avec un timeout plus long
            with open(file_path, 'rb') as f:
                files = {'upload': (os.path.basename(file_path), f, 'application/pdf')}
                
                # Timeout de 60 secondes pour l'upload
                response = requests.post(
                    url, 
                    headers=self.headers, 
                    files=files,
                    timeout=60
                )
            
            # VÃ©rifier le statut de la rÃ©ponse
            if response.status_code != 200:
                raise Exception(f"Erreur HTTP {response.status_code}: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            
            # Grist retourne une liste d'IDs
            if isinstance(result, list) and len(result) > 0:
                attachment_id = result[0]
                print(f"      âœ“ Upload rÃ©ussi, ID: {attachment_id}")
                return attachment_id
            
            raise Exception(f"Erreur upload: rÃ©ponse inattendue {result}")
            
        except requests.exceptions.Timeout:
            raise Exception(f"Timeout lors de l'upload de {os.path.basename(file_path)} (>60s)")
        except requests.exceptions.ConnectionError:
            raise Exception(f"Erreur de connexion lors de l'upload de {os.path.basename(file_path)}")
        except Exception as e:
            raise Exception(f"Erreur lors de l'upload: {str(e)}")
    
    def update_record_attachment(self, table_id: str, record_id: int, 
                                 column_name: str, attachment_ids: List[int]):
        """
        Met Ã  jour la colonne d'attachement d'un enregistrement
        """
        url = f"{self.api_url}/api/docs/{self.doc_id}/tables/{table_id}/records"
        
        data = {
            "records": [
                {
                    "id": record_id,
                    "fields": {
                        column_name: ['L'] + attachment_ids  # Format Grist pour les attachements
                    }
                }
            ]
        }
        
        response = requests.patch(url, headers=self.headers, json=data)
        response.raise_for_status()
    
    def get_record_id_by_filter_value(self, table_id: str, filter_column: str, 
                                       filter_value: str) -> Optional[int]:
        """
        Trouve l'ID d'un enregistrement par sa valeur de filtre
        """
        print(f"  ðŸ” RÃ©cupÃ©ration des enregistrements de la table {table_id}...")
        records = self.get_table_data(table_id)
        print(f"  ðŸ“Š {len(records)} enregistrements trouvÃ©s")
        
        for record in records:
            record_id = record.get('id')
            fields = record.get('fields', {})
            field_value = fields.get(filter_column)
            
            # Comparer en chaÃ®nes de caractÃ¨res
            if str(field_value) == str(filter_value):
                print(f"  âœ“ Correspondance trouvÃ©e: ID={record_id}, {filter_column}={field_value}")
                return record_id
        
        print(f"  âŒ Aucune correspondance pour {filter_column}={filter_value}")
        print(f"  ðŸ’¡ Valeurs disponibles dans '{filter_column}': {[str(r.get('fields', {}).get(filter_column)) for r in records[:5]]}...")
        return None