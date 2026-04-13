"""
CI Elections - Interface Chatbot Streamlit
Application d'analyse électorale avec Text-to-SQL et visualisations intelligentes.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

# Import du backend SQL agent
from sql_agent import ask_database


# =============================================================================
# FONCTIONS DE RENDU DES GRAPHIQUES
# =============================================================================

def render_single_value(data: dict) -> None:
    """
    Affiche une valeur unique agrégée dans une carte visuelle.

    Utilisé quand la requête retourne une seule ligne avec une valeur
    agrégée (ex: total, moyenne, compte).
    """
    # Extraction de la valeur et de son label
    keys = list(data.keys())
    if not keys:
        st.info("Aucune donnée disponible.")
        return

    # Détection de la colonne de valeur (généralement numérique ou la première)
    value_key = None
    label_key = None

    for key in keys:
        val = data[key]
        if isinstance(val, (int, float)) and value_key is None:
            value_key = key
        elif isinstance(val, str) and label_key is None:
            label_key = key

    # Fallback si pas de valeur numérique trouvée
    if value_key is None:
        value_key = keys[-1]

    value = data[value_key]
    label = label_key if label_key else value_key
    label_value = data.get(label_key, "") if label_key else ""

    # Formatage de la valeur
    if isinstance(value, (int, float)):
        if isinstance(value, int) or value == int(value):
            formatted_value = f"{int(value):,}".replace(",", " ")
        else:
            formatted_value = f"{value:,.2f}".replace(",", " ")
    else:
        formatted_value = str(value)

    # Affichage dans une carte stylisée
    st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border-radius: 12px;
            padding: 30px;
            margin: 10px 0;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        ">
            <div style="
                font-size: 14px;
                color: rgba(255, 255, 255, 0.8);
                margin-bottom: 10px;
                text-transform: uppercase;
                letter-spacing: 1px;
            ">
                {label.replace("_", " ").title()}{f" : {label_value}" if label_value else ""}
            </div>
            <div style="
                font-size: 48px;
                font-weight: bold;
                color: white;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            ">
                {formatted_value}
            </div>
        </div>
    """, unsafe_allow_html=True)


def render_bar_chart(df: pd.DataFrame, question: str) -> None:
    """
    Affiche un graphique en barres avec détection automatique des axes.

    Détecte automatiquement quelle colonne utiliser pour l'axe X
    (catégorielle) et l'axe Y (numérique).
    Ne s'affiche pas si une seule ligne de données.
    """
    # Ne pas afficher le graphique si une seule valeur
    if len(df) <= 1:
        return

    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    string_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

    if not numeric_cols:
        st.dataframe(df, use_container_width=True)
        return

    # Sélection des colonnes pour le graphique
    y_col = numeric_cols[0]

    # Choix de la colonne catégorielle pour l'axe X
    if string_cols:
        x_col = string_cols[0]
    elif len(numeric_cols) > 1:
        x_col = numeric_cols[1] if numeric_cols[1] != y_col else numeric_cols[0]
    else:
        x_col = df.index.name if df.index.name else "Index"

    # Limitation à 20 catégories pour la lisibilité
    if len(df) > 20:
        df = df.nlargest(20, y_col)
        title_suffix = " (Top 20)"
    else:
        title_suffix = ""

    # Forcer le respect de l'ordre des catégories (ordre SQL préservé)
    category_order = df[x_col].tolist()

    fig = px.bar(
        df,
        x=x_col,
        y=y_col,
        title=f"{question}{title_suffix}",
        labels={x_col: x_col.replace("_", " ").title(), y_col: y_col.replace("_", " ").title()},
        color_discrete_sequence=["#1f77b4"],
        template="plotly_white",
        category_orders={x_col: category_order}
    )

    fig.update_layout(
        xaxis_tickangle=-45,
        showlegend=False,
        margin=dict(l=20, r=20, t=50, b=80),
        title_font_size=14,
        title_x=0.5
    )

    st.plotly_chart(fig, use_container_width=True)


def render_pie_chart(df: pd.DataFrame, question: str) -> None:
    """
    Affiche un graphique circulaire pour les distributions.

    Agrège automatiquement les petites valeurs si trop de catégories.
    """
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
    string_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()

    if not numeric_cols or not string_cols:
        st.dataframe(df, use_container_width=True)
        return

    values_col = numeric_cols[0]
    names_col = string_cols[0]

    # Agrégation si doublons dans les noms
    df_agg = df.groupby(names_col)[values_col].sum().reset_index()

    # Regroupement des petites valeurs si plus de 8 catégories
    if len(df_agg) > 8:
        df_agg = df_agg.sort_values(values_col, ascending=False)
        top_n = df_agg.head(7)
        others_sum = df_agg.iloc[7:][values_col].sum()
        if others_sum > 0:
            others_row = pd.DataFrame([{names_col: "Autres", values_col: others_sum}])
            df_agg = pd.concat([top_n, others_row], ignore_index=True)

    fig = px.pie(
        df_agg,
        names=names_col,
        values=values_col,
        title=question,
        template="plotly_white",
        hole=0.4
    )

    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        title_font_size=14,
        title_x=0.5,
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.2)
    )

    st.plotly_chart(fig, use_container_width=True)


def render_line_chart(df: pd.DataFrame, question: str) -> None:
    """
    Affiche un graphique linéaire pour les tendances.

    Détecte automatiquement les colonnes temporelles ou séquentielles.
    """
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if len(numeric_cols) < 1:
        st.dataframe(df, use_container_width=True)
        return

    # Détection de colonne pour l'axe X
    x_col = None
    for col in df.columns:
        if any(keyword in col.lower() for keyword in ["date", "annee", "year", "temps", "time", "ordre"]):
            x_col = col
            break

    if x_col is None:
        string_cols = df.select_dtypes(include=["object", "string"]).columns.tolist()
        x_col = string_cols[0] if string_cols else df.columns[0]

    y_col = numeric_cols[0]

    fig = px.line(
        df,
        x=x_col,
        y=y_col,
        title=question,
        markers=True,
        template="plotly_white",
        labels={x_col: x_col.replace("_", " ").title(), y_col: y_col.replace("_", " ").title()}
    )

    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=50),
        title_font_size=14,
        title_x=0.5
    )

    st.plotly_chart(fig, use_container_width=True)


def render_scatter_chart(df: pd.DataFrame, question: str) -> None:
    """
    Affiche un nuage de points pour les corrélations.

    Nécessite au moins 2 colonnes numériques.
    """
    numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()

    if len(numeric_cols) < 2:
        # Fallback sur bar chart si pas assez de colonnes numériques
        render_bar_chart(df, question)
        return

    x_col = numeric_cols[0]
    y_col = numeric_cols[1]

    # Détection d'une colonne pour la couleur
    color_col = None
    for col in df.columns:
        if col not in numeric_cols:
            color_col = col
            break

    fig = px.scatter(
        df,
        x=x_col,
        y=y_col,
        color=color_col,
        title=question,
        template="plotly_white",
        labels={x_col: x_col.replace("_", " ").title(), y_col: y_col.replace("_", " ").title()},
        opacity=0.7
    )

    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=50),
        title_font_size=14,
        title_x=0.5
    )

    st.plotly_chart(fig, use_container_width=True)


def render_data_table(df: pd.DataFrame) -> None:
    """
    Affiche les données dans un tableau interactif Streamlit.
    """
    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True
    )


def render_chart(data: list, chart_type: str, question: str, sql: str = "") -> None:
    """
    Route vers la fonction de rendu appropriée selon le type de graphique.
    Affiche un tableau pour les grandes quantités de données (>15 lignes).

    Args:
        data: Liste de dictionnaires contenant les données
        chart_type: Type de graphique (bar, pie, line, scatter, table)
        question: Question de l'utilisateur pour le titre
        sql: Requête SQL pour détecter les ORDER BY
    """
    if not data or len(data) == 0:
        st.info("Aucune donnée disponible pour la visualisation.")
        return

    df = pd.DataFrame(data)
    num_rows = len(df)

    # Seuil: au-delà de 15 lignes, un tableau est souvent plus lisible qu'un graphique
    if num_rows > 15 or chart_type == "table":
        st.caption(f"📊 {num_rows} résultats affichés sous forme de tableau")
        render_data_table(df)
        return

    # Pour les petits jeux de données, laisser le choix entre graphique et tableau
    if num_rows <= 15:
        col1, col2 = st.columns([1, 3])
        with col1:
            view_mode = st.radio(
                "Affichage:",
                ["📈 Graphique", "📋 Tableau"],
                horizontal=True,
                label_visibility="collapsed"
            )

        if view_mode == "📋 Tableau":
            render_data_table(df)
        else:
            # Afficher le graphique choisi par le LLM
            if chart_type == "bar":
                render_bar_chart(df, question)
            elif chart_type == "pie":
                render_pie_chart(df, question)
            elif chart_type == "line":
                render_line_chart(df, question)
            elif chart_type == "scatter":
                render_scatter_chart(df, question)
            else:
                render_data_table(df)


# =============================================================================
# FONCTION DE RENDU D'UN MESSAGE DU BOT
# =============================================================================

def render_bot_response(response: dict, question: str) -> None:
    """
    Affiche la réponse complète du bot avec narrative, SQL et visualisation.

    Args:
        response: Dictionnaire retourné par ask_database()
        question: Question posée par l'utilisateur
    """
    # Affichage de la réponse narrative
    if response.get("narrative"):
        st.markdown(response["narrative"])

    # Affichage du SQL dans un expander
    if response.get("sql"):
        with st.expander("Voir la requête SQL générée"):
            st.code(response["sql"], language="sql")

    # Affichage des données et visualisation
    data = response.get("data", [])
    sql_query = response.get("sql", "")
    if data and len(data) > 0:
        if len(data) == 1:
            # Une seule valeur - afficher en grand sans tableau
            render_single_value(data[0])
        else:
            # Plusieurs lignes - afficher selon le choix du backend et la taille
            chart_type = response.get("chart_type", "table")
            render_chart(data, chart_type, question, sql_query)


# =============================================================================
# CONFIGURATION DE LA PAGE
# =============================================================================

def setup_page_config():
    """Configure les paramètres de la page Streamlit."""
    st.set_page_config(
        page_title="CI Elections - Agent d'Analyse",
        page_icon="🗳️",
        layout="wide",
        initial_sidebar_state="expanded"
    )


# =============================================================================
# SIDEBAR
# =============================================================================

def render_sidebar():
    """Affiche la barre latérale avec informations et exemples."""
    with st.sidebar:
        st.title("🗳️ CI Elections")
        st.markdown("---")

        st.subheader("À propos")
        st.markdown("""
        Agent d'analyse électorale pour les élections locales ivoiriennes.

        **Fonctionnalités:**
        - Questions en langage naturel
        - Génération automatique de SQL
        - Visualisations intelligentes
        - Sécurité renforcée (accès lecture seule)
        """)

        st.markdown("---")

        st.subheader("Exemples de questions")
        example_questions = [
            "Quel est le candidat qui a gagné à Abidjan ?",
            "Quels sont les partis avec le plus de sièges ?",
            "Montre-moi le taux de participation par région",
            "Combien de bulletins nuls ont été enregistrés ?",
            "Quel candidat a obtenu le plus de voix au sud ?",
            "Liste des élus du parti RHDP"
        ]

        for q in example_questions:
            if st.button(f"💬 {q}", key=f"btn_{q[:20]}"):
                st.session_state.suggested_question = q
                st.rerun()

        st.markdown("---")
        st.caption("v1.0 - Développé pour Artefact")


# =============================================================================
# INITIALISATION DE L'HISTORIQUE
# =============================================================================

def init_chat_history():
    """Initialise l'historique des messages dans session_state."""
    if "messages" not in st.session_state:
        st.session_state.messages = []

        # Message de bienvenue
        welcome_message = {
            "role": "assistant",
            "content": {
                "status": "success",
                "narrative": """👋 Bienvenue sur **CI Elections - Agent d'Analyse Électorale** !

Je suis votre assistant pour interroger les résultats des élections locales ivoiriennes.

**Ce que vous pouvez me demander :**
- Des informations sur les candidats élus
- Les taux de participation par circonscription
- La répartition des sièges par parti
- Les statistiques de vote (bulletins nuls, exprimés, etc.)

Posez votre question ci-dessous ou utilisez les exemples dans la barre latérale.""",
                "data": [],
                "sql": ""
            },
            "question": "Bienvenue"
        }
        st.session_state.messages.append(welcome_message)


# =============================================================================
# AFFICHAGE DE L'HISTORIQUE
# =============================================================================

def render_chat_history():
    """Affiche tous les messages de l'historique de conversation."""
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            if message["role"] == "user":
                st.markdown(message["content"])
            else:
                render_bot_response(message["content"], message.get("question", ""))


# =============================================================================
# GESTION DE LA QUESTION UTILISATEUR
# =============================================================================

def handle_user_input(prompt: str):
    """
    Traite la question de l'utilisateur et génère une réponse.

    Args:
        prompt: Question posée par l'utilisateur
    """
    # Ajout du message utilisateur à l'historique
    st.session_state.messages.append({"role": "user", "content": prompt})

    # Affichage du message utilisateur
    with st.chat_message("user"):
        st.markdown(prompt)

    # Génération de la réponse
    with st.chat_message("assistant"):
        with st.spinner("Analyse de votre question..."):
            try:
                response = ask_database(prompt)

                # Gestion des erreurs
                if response.get("status") == "error":
                    st.error(f"⚠️ {response.get('narrative', 'Une erreur est survenue')}")
                else:
                    render_bot_response(response, prompt)

                # Ajout à l'historique
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": response,
                    "question": prompt
                })

            except Exception as e:
                error_msg = f"Désolé, une erreur technique est survenue. Veuillez réessayer."
                st.error(f"⚠️ {error_msg}")

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": {
                        "status": "error",
                        "narrative": error_msg,
                        "data": [],
                        "sql": ""
                    },
                    "question": prompt
                })


# =============================================================================
# POINT D'ENTRÉE PRINCIPAL
# =============================================================================

def main():
    """
    Fonction principale de l'application Streamlit.
    """
    setup_page_config()
    render_sidebar()
    init_chat_history()

    # En-tête de la page principale
    st.title("🗳️ CI Elections - Agent d'Analyse Électorale")
    st.markdown("*Posez vos questions sur les résultats électoraux ivoiriens en langage naturel*")
    st.markdown("---")

    # Affichage de l'historique
    render_chat_history()

    # Zone de saisie utilisateur
    user_input = st.chat_input("Posez votre question sur les élections...")

    # Gestion de la question suggérée depuis la sidebar
    if "suggested_question" in st.session_state:
        user_input = st.session_state.suggested_question
        del st.session_state.suggested_question

    # Traitement de la question
    if user_input:
        handle_user_input(user_input)


if __name__ == "__main__":
    main()
