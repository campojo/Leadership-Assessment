import matplotlib
matplotlib.use('Agg')
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
import matplotlib.pyplot as plt
import io
import base64
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

DB_FILE = 'responses.db'

def init_db():
    if not os.path.exists(DB_FILE):
        with sqlite3.connect(DB_FILE) as conn:
            conn.executescript(open('init_db.sql').read())

init_db()

def load_questions():
    import random
    df = pd.read_excel('https://raw.githubusercontent.com/campojo/Leadership-Assessment/main/Questions%202.0.xlsx', sheet_name=None, engine='openpyxl')
    assessment_df = df['Questions']
    survey_df = df['SurveyQuestions']
    # Group questions by style and select 5 random questions from each
    styles = assessment_df['Style_Num'].unique()
    selected_questions = []
    for style in styles:
        style_questions = assessment_df[assessment_df['Style_Num'] == style]['Question'].tolist()
        selected_questions.extend(random.sample(style_questions, 5))
    # Shuffle the selected questions
    random.shuffle(selected_questions)
    return selected_questions, survey_df['Question'].tolist()

assessment_questions, survey_questions = load_questions()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form.get('name')
        identifier = request.form.get('identifier')
        session['name'] = name
        session['email'] = identifier
        return redirect(url_for('instructions'))
    return render_template('index.html')

@app.route('/instructions', methods=['GET', 'POST'])
def instructions():
    if request.method == 'POST':
        session['email'] = request.form.get('email')
        return redirect(url_for('assessment'))
    return render_template('instructions.html')

@app.route('/assessment', methods=['GET', 'POST'])
def assessment():
    try:
        if request.method == 'GET':
            return render_template('assessment.html', 
                                   assessment_questions=assessment_questions, 
                                   survey_questions=survey_questions)
        # POST: Collect responses
        responses = {}
        for question in assessment_questions:
            answer = request.form.get(question)
            if answer is not None:
                responses[question] = answer
        survey_responses = {}
        for i, question in enumerate(survey_questions):
            key = f'survey_{i}'
            answer = request.form.get(key)
            if answer is not None:
                survey_responses[question] = answer
        session['responses'] = responses
        session['survey'] = survey_responses
        # Save to DB
        email = session.get('email', '')
        with sqlite3.connect(DB_FILE) as conn:
            for question, answer in responses.items():
                conn.execute(
                    'INSERT INTO assessment_results (email, question, answer) VALUES (?, ?, ?)',
                    (email, question, answer)
                )
            for question, answer in survey_responses.items():
                conn.execute(
                    'INSERT INTO survey_results (email, question, answer) VALUES (?, ?, ?)',
                    (email, question, answer)
                )
            conn.commit()
        return redirect(url_for('results'))
    except Exception as e:
        print(f"Error in assessment route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

# All duplicate assessment() definitions removed to resolve AssertionError

# Duplicate /assessment route removed to eliminate AssertionError

@app.route('/results')
def results():
    try:
        responses = session.get('responses', {})
        survey = session.get('survey', {})
        if not responses:
            return redirect(url_for('assessment'))
        # Load questions and style mappings
        excel_data = pd.read_excel('https://raw.githubusercontent.com/campojo/Leadership-Assessment/main/Questions%202.0.xlsx', sheet_name=['Questions', 'ScoreBasedResponse'], engine='openpyxl')
        df = excel_data['Questions']
        response_df = excel_data['ScoreBasedResponse']
        styles = ['Transformational', 'Democratic', 'Charismatic', 'Autocratic',
                 'Laissez-Faire', 'Situational', 'Transactional', 'Servant']
        value_map = {'1': -2, '2': -1, '3': 0, '4': 1, '5': 2}
        # Map Style_Num to style name (as in app.py)
        style_num_to_name = {
            1: 'Transformational',
            2: 'Democratic',
            3: 'Charismatic',
            4: 'Autocratic',
            5: 'Laissez-Faire',
            6: 'Situational',
            7: 'Transactional',
            8: 'Servant'
        }
        # Map questions to style names
        question_style_map = {q: style_num_to_name.get(s, str(s)) for q, s in zip(df['Question'], df['Style_Num'])}
        style_scores = {style: [] for style in styles}
        for question, answer in responses.items():
            style = question_style_map.get(question)
            if style and answer:
                mapped = value_map.get(str(answer), 0)
                style_scores[style].append(mapped)
        # Sum scores for each style
        results_dict = {style: sum(scores) for style, scores in style_scores.items()}
        # Chart
        x = range(len(styles))
        scores = [results_dict[style] for style in styles]
        plt.figure(figsize=(10, 5))
        plt.bar(x, scores, align='center', color='skyblue')
        plt.title('Leadership Style Assessment Results', pad=20)
        plt.ylabel('Tendency Level')
        plt.xticks(x, styles, rotation=45, ha='right')
        plt.yticks([-10, 0, 10], ['Low Tendency', 'Moderate', 'High Tendency'])
        plt.grid(True, axis='y', linestyle='--', alpha=0.7)
        plt.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
        plt.tight_layout()
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        chart_data = base64.b64encode(img.getvalue()).decode()
        plt.close()
        # Summary logic (sum-based, with thresholds)
        intro_paragraph = (
            "It's important to remember that there is no right or wrong score in this assessment; rather, the "
            "goal is to develop self-awareness as a leader. Each leadership style has its strengths and "
            "challenges, and understanding your tendencies allows you to recognize how your approach "
            "impacts others. By becoming more aware of your natural leadership style, you can adapt and "
            "refine your methods to better meet the needs of your team and organization. Self-awareness "
            "empowers you to make conscious decisions about when to lean into certain behaviors and "
            "when to adjust your approach, ensuring you lead in a way that fosters growth, collaboration, "
            "and positive outcomes."
        )
        tendency_explanations = {
            'High': (
                "High Tendency: "
                "If a person scores high in this assessment area, it suggests that they strongly exhibit behaviors "
                "aligned with specific leadership styles. ..."
            ),
            'Moderate': (
                "Moderate Tendency: "
                "If a person scores moderately in this assessment area, it indicates that they exhibit a balanced ..."
            ),
            'Low': (
                "Low Tendency: "
                "If a person scores low in this assessment area, it suggests that they may find certain behaviors ..."
            )
        }
        style_summaries = []
        for style in styles:
            score = results_dict[style]
            if 5 <= score <= 10:
                tendency = 'High'
            elif 0 <= score <= 4:
                tendency = 'Moderate'
            else:
                tendency = 'Low'
            # Append ' Leadership' to match Excel values
            excel_style = f"{style} Leadership"
            desc_row = response_df[(response_df['Leadership Style'] == excel_style) & (response_df['Tendency'] == tendency)]
            if not desc_row.empty:
                description = desc_row['Description'].values[0]
            else:
                description = f"No description found for {style} ({tendency})"
            style_summaries.append({'style': style, 'tendency': tendency, 'description': description})
        summary = {
            'intro_paragraph': intro_paragraph,
            'tendency_explanations': tendency_explanations,
            'style_summaries': style_summaries
        }
        # Save all-time summary results to DB
        email = session.get('email', '')
        with sqlite3.connect(DB_FILE) as conn:
            for s in style_summaries:
                conn.execute(
                    'INSERT INTO summary_results (email, style, score, tendency, description) VALUES (?, ?, ?, ?, ?)',
                    (email, s['style'], results_dict[s['style']], s['tendency'], s['description'])
                )
            conn.commit()
        return render_template('results.html', chart_data=chart_data, summary=summary)
    except Exception as e:
        print(f"Error in results route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

# Duplicate /assessment and /results routes removed below this line to resolve AssertionError and ensure only one definition exists.

if __name__ == '__main__':
    app.run(debug=True)
