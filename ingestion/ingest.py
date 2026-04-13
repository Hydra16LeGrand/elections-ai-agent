import camelot
import pandas as pd
import numpy as np
import os
import time
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

def get_db_engine_with_retry(db_url: str, max_retries: int = 5, delay: int = 3):
    """
    Tente d'établir une connexion à la base de données PostgreSQL avec un mécanisme de réessai.
    Crucial pour l'orchestration Docker afin d'éviter les conditions de concurrence (race conditions) 
    lors de l'initialisation de la base de données.
    """
    print("INFO : Initialisation de la connexion à la base de données...")
    for attempt in range(max_retries):
        try:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                pass 
            print("INFO : Connexion à la base de données établie avec succès.")
            return engine
        except OperationalError:
            print(f"AVERTISSEMENT : Base de données non prête. Nouvelle tentative dans {delay}s (Tentative {attempt + 1}/{max_retries})...")
            time.sleep(delay)
    
    print("ERREUR : Échec de la connexion à la base de données après le nombre maximum de tentatives.")
    return None

def extract_all_pages(pdf_path: str, pages: str = "1-35") -> pd.DataFrame | None:
    """
    Extrait les données tabulaires des pages spécifiées du PDF en utilisant le mode 'lattice' de Camelot.
    Retourne un DataFrame pandas concaténé contenant l'ensemble des données tabulaires brutes.
    """
    print(f"INFO : Début de l'extraction des données des pages {pages}. Cette opération peut prendre quelques minutes...")
    try:
        tables = camelot.read_pdf(pdf_path, pages=pages, flavor='lattice', line_scale=40)
        if not tables:
            print("AVERTISSEMENT : Aucun tableau détecté dans le document.")
            return None
        all_dfs = [table.df for table in tables]
        df_extracted = pd.concat(all_dfs, ignore_index=True)
        print(f"INFO : Extraction terminée. {len(df_extracted)} lignes brutes récupérées.")
        return df_extracted
    except Exception as e:
        print(f"ERREUR : L'extraction a échoué. Détails : {e}")
        return None

def prepare_raw_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prépare le DataFrame de la couche Bronze.
    Effectue uniquement un nettoyage structurel (suppression des en-têtes, gestion des anomalies 
    de pagination du PDF) sans appliquer de conversion de type (cast) afin de préserver l'intégrité 
    des données brutes.
    """
    df_raw = df.copy()
    
    # 1. Nettoyage structurel : Suppression des en-têtes répétitifs et des lignes d'agrégation 'TOTAL'
    mask_headers = df_raw.iloc[:, 1].astype(str).str.contains('CIRCONSCRIPTION|TOTAL', case=False, na=False)
    mask_region = df_raw.iloc[:, 0].astype(str).str.contains('REGI|TOTAL', case=False, na=False)
    df_raw = df_raw[~(mask_headers | mask_region)]
    
    # 2. Standardisation de la nomenclature des colonnes pour la couche brute (raw)
    df_raw.columns = [
        "raw_region", "raw_code_circonscription", "raw_nom_circonscription",  
        "raw_nb_bv", "raw_inscrits", "raw_votants", "raw_taux_part", 
        "raw_bull_nuls", "raw_suf_exprimes", "raw_bull_blancs_nb", "raw_bull_blancs_pct", 
        "raw_parti", "raw_candidat", "raw_voix", "raw_pourcentage", "raw_elu"
    ]

    # =====================================================================
    # CORRECTIF DE QUALITÉ DES DONNÉES (DATA PATCH)
    # Contexte : Anomalie de saut de page dans le document source.
    # L'enregistrement pour la circonscription '028' commence à la page 4, 
    # mais sa région parente ('BOUNKANI') est rendue à la page 5.
    # Action : Injection explicite de la région correcte avant le remplissage (Forward Fill).
    # =====================================================================
    mask_028 = df_raw['raw_code_circonscription'].astype(str).str.contains('028', na=False)
    df_raw.loc[mask_028, 'raw_region'] = 'BOUNKANI'
    
    # 3. Propagation des identifiants géographiques (Forward Fill)
    colonnes_a_propager = [
        "raw_region", "raw_code_circonscription", "raw_nom_circonscription", 
        "raw_nb_bv", "raw_inscrits", "raw_votants", "raw_taux_part", 
        "raw_bull_nuls", "raw_suf_exprimes", "raw_bull_blancs_nb", "raw_bull_blancs_pct"
    ]
    df_raw[colonnes_a_propager] = df_raw[colonnes_a_propager].replace(r'^\s*$', np.nan, regex=True).infer_objects(copy=False)
    df_raw[colonnes_a_propager] = df_raw[colonnes_a_propager].ffill()
    
    # 4. Nettoyage final du texte (Suppression des retours à la ligne générés par l'OCR/Camelot)
    for col in df_raw.columns:
        df_raw[col] = df_raw[col].astype(str).str.replace('\n', ' ').str.strip()
        
    # Suppression des lignes dépourvues d'informations sur les candidats
    df_raw = df_raw[df_raw['raw_candidat'] != '']
    df_raw = df_raw[df_raw['raw_candidat'] != 'nan']

    return df_raw

def push_raw_to_postgres(df: pd.DataFrame):
    """
    Charge le DataFrame nettoyé dans la base de données PostgreSQL en tant que table brute (Couche Bronze).
    Implémente une suppression CASCADE avant l'insertion pour garantir l'idempotence du pipeline 
    et nettoyer les vues sémantiques dépendantes.
    """
    db_url = os.environ.get("DATABASE_URL")
    engine = get_db_engine_with_retry(db_url)
    if not engine:
        return None
    
    try:
        print("INFO : Nettoyage du schéma existant (Suppression CASCADE)...")
        # Bloc de connexion explicite pour exécuter la suppression CASCADE
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE IF EXISTS raw_election_data CASCADE;"))
            
        print("INFO : Insertion des données dans la table 'raw_election_data'...")
        df.to_sql("raw_election_data", engine, if_exists="replace", index=False)
        print("INFO : Chargement des données réussi.")
    except Exception as e:
        print(f"ERREUR : L'insertion SQL a échoué. Détails : {e}")

    return engine

def create_views_and_indexes(engine, sql_file_path):
    """
    Exécute le script d'initialisation SQL pour construire la couche sémantique (Vues Silver/Gold) 
    et les index de base de données requis.
    """
    print("INFO : Exécution des migrations SQL (Vues et Index)...")
    try:
        raw_conn = engine.raw_connection()
        with raw_conn.cursor() as cursor:
            with open(sql_file_path, 'r', encoding='utf-8') as file:
                sql_script = file.read()
            cursor.execute(sql_script)
        raw_conn.commit()
        raw_conn.close()
        print("INFO : Couche sémantique et index créés avec succès.")
    except Exception as e:
        print(f"ERREUR : Échec de l'exécution du script SQL. Détails : {e}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    PDF_PATH = os.path.join(current_dir, "EDAN_2025_RESULTAT_NATIONAL_DETAILS.pdf")
    SQL_PATH = os.path.join(current_dir, "init_views.sql")
    
    df_extracted = extract_all_pages(PDF_PATH, "1-35")
    
    if df_extracted is not None:
        df_raw = prepare_raw_dataframe(df_extracted)
        engine = push_raw_to_postgres(df_raw)
        
        if engine:
            create_views_and_indexes(engine, SQL_PATH)