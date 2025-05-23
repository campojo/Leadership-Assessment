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

def build_question_style_map():
    df = pd.read_excel('https://raw.githubusercontent.com/campojo/Leadership-Assessment/main/Questions%202.0.xlsx', sheet_name='Questions', engine='openpyxl')
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
    return {q: style_num_to_name.get(s, s) for q, s in zip(df['Question'], df['Style_Num'])}

question_to_style = build_question_style_map()

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
    if 'email' not in session or not session['email']:
        return redirect(url_for('index'))
    try:
        if request.method == 'GET':
            return render_template('assessment.html', 
                                   assessment_questions=assessment_questions, 
                                   survey_questions=survey_questions)
        # POST: Collect responses
        import logging
        responses = {}
        for question in assessment_questions:
            answer = request.form.get(question)
            if answer is not None:
                responses[question] = answer
        # Logging: how many answers received
        logging.basicConfig(filename='assessment_debug.log', level=logging.INFO)
        logging.info(f"Assessment submitted: {len(responses)} answers received for email {session.get('email','')}.")
        if len(responses) != len(assessment_questions):
            logging.warning(f"Incomplete submission: {len(responses)} of {len(assessment_questions)} answers received for email {session.get('email','')}.")
        # Only save if all answers present
        if len(responses) != len(assessment_questions):
            return render_template('assessment.html', assessment_questions=assessment_questions, survey_questions=survey_questions, error="Please answer all questions before submitting.")
        survey_responses = {}
        for i, question in enumerate(survey_questions):
            key = f'survey_{i}'
            answer = request.form.get(key)
            if answer is not None:
                survey_responses[question] = answer
        session['responses'] = responses
        session['survey'] = survey_responses
        # Save to DB
        import datetime
        email = session.get('email', '')
        now = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
        with sqlite3.connect(DB_FILE) as conn:
            for question, answer in responses.items():
                style = question_to_style.get(question, '')
                try:
                    conn.execute(
                        'INSERT INTO assessment_results (email, timestamp, style, question, answer) VALUES (?, ?, ?, ?, ?)',
                        (email, now, style, question, answer)
                    )
                except Exception as e:
                    logging.error(f"DB insert error for {question}: {e}")
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
                "aligned with specific leadership styles. For example, a high score in democratic leadership "
                "indicates a tendency to prioritize collaboration and actively involve team members in decision-"
                "making. A high score in transformational leadership suggests a natural ability to inspire and "
                "motivate others toward long-term goals and personal growth. These tendencies reflect an "
                "individual who is skilled in creating an inclusive and visionary environment, fostering "
                "engagement and innovation within their team."
            ),
            'Moderate': (
                "Moderate Tendency: "
                "If a person scores moderately in this assessment area, it indicates that they exhibit a balanced "
                "approach to the behaviors associated with that leadership trait. They may demonstrate some "
                "strength in the area, but also show room for improvement. For example, a moderate score in "
                "decision-making suggests they are capable of making decisions, but may occasionally hesitate "
                "or seek more input from others. Similarly, a moderate score in communication might indicate "
                "that they communicate effectively at times, but could benefit from refining their clarity or "
                "engagement with different audiences. Overall, they are likely adaptable, but may need to "
                "develop more consistency in their approach to fully leverage their leadership potential."
            ),
            'Low': (
                "Low Tendency: "
                "If a person scores low in this assessment area, it suggests that they may find certain behaviors "
                "associated with that leadership trait more challenging. For example, a low score in democratic "
                "leadership might indicate a preference for making decisions independently, rather than "
                "involving others in the decision-making process. A low score in servant leadership might suggest "
                "a tendency to prioritize tasks over the well-being and development of team members. These "
                "tendencies reflect areas where the individual may benefit from additional development or "
                "practice to enhance their effectiveness in specific situations."
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
        import datetime
        timestamp = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
        with sqlite3.connect(DB_FILE) as conn:
            for s in style_summaries:
                conn.execute(
                    'INSERT INTO summary_results (email, timestamp, style, score, tendency, description) VALUES (?, ?, ?, ?, ?, ?)',
                    (email, timestamp, s['style'], results_dict[s['style']], s['tendency'], s['description'])
                )
            conn.commit()
        return render_template('results.html', chart_data=chart_data, summary=summary)
    except Exception as e:
        print(f"Error in results route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

import functools
from flask import flash, send_file

# --- Admin authentication helpers ---
def admin_required(view_func):
    @functools.wraps(view_func)
    def wrapped_view(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return view_func(*args, **kwargs)
    return wrapped_view

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    error = None
    if request.method == 'POST':
        password = request.form.get('password')
        admin_pw = os.environ.get('ADMIN_PASSWORD', 'admin123')
        if password == admin_pw:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_results'))
        else:
            error = 'Incorrect password.'
    return render_template('admin_login.html', error=error)

@app.route('/admin/logout', methods=['POST'])
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/results')
@admin_required
def admin_results():
    error = None
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        results = conn.execute('SELECT * FROM summary_results ORDER BY timestamp DESC, email, style').fetchall()
    return render_template('admin_results.html', results=results, error=error)

@app.route('/admin/details')
@admin_required
def admin_details():
    email = request.args.get('email')
    if not email:
        return redirect(url_for('admin_results'))
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        summary = conn.execute('SELECT * FROM summary_results WHERE email = ? ORDER BY style', (email,)).fetchall()
        assessment = conn.execute('SELECT * FROM assessment_results WHERE email = ? ORDER BY question', (email,)).fetchall()
        survey = conn.execute('SELECT * FROM survey_results WHERE email = ? ORDER BY question', (email,)).fetchall()
    return render_template('admin_details.html', email=email, summary=summary, assessment=assessment, survey=survey)

import csv
import io
@app.route('/admin/export')
@admin_required
def admin_export():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        results = conn.execute('SELECT email, timestamp, style, question, answer FROM assessment_results ORDER BY email, timestamp').fetchall()
    # Write to CSV in memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Email', 'Date/TimeStamp', 'Style', 'Question', 'Answer/score Provided'])
    for row in results:
        writer.writerow([row['email'], row['timestamp'], row['style'], row['question'], row['answer']])
    output.seek(0)
    return send_file(io.BytesIO(output.read().encode('utf-8')), mimetype='text/csv', as_attachment=True, download_name='assessment_answers.csv')

if __name__ == '__main__':
    app.run(debug=True)
