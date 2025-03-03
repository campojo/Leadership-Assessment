from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import random
import requests
import json
import matplotlib
matplotlib.use('Agg')  # Prevents rendering issues on servers
import matplotlib.pyplot as plt
from io import BytesIO
import os

app = Flask(__name__)

# GitHub Raw File URL
GITHUB_FILE_URL = "https://raw.githubusercontent.com/campojo/leadership_style_questions/main/Questions%202.0.xlsx"

def get_file_path():
    """Downloads questions from GitHub and returns them as a stream."""
    response = requests.get(GITHUB_FILE_URL)
    if response.status_code == 200:
        return BytesIO(response.content)
    else:
        print("Error: Unable to download file from GitHub. Please check the URL or try again later.")
        return None

def load_questions():
    """Loads questions from the GitHub Excel file and organizes them by style."""
    file_path = get_file_path()
    if not file_path:
        return None
    
    df = pd.read_excel(file_path)
    df['Approach'] = df['Approach'].str.strip().str.lower()
    
    styles = df[['Style_Num', 'Style_Name']].drop_duplicates()
    question_dict = {}

    for _, row in styles.iterrows():
        style_num = row['Style_Num']
        style_name = row['Style_Name']
        questions = df[df['Style_Num'] == style_num][['Questions', 'Approach']].to_dict(orient='records')
        question_dict[(style_num, style_name)] = random.sample(questions, min(5, len(questions)))  # Select up to 5

    return question_dict

@app.route('/', methods=['GET', 'POST'])
def index():
    """Home page where users enter their name and 8-digit identifier."""
    if request.method == 'POST':
        name = request.form['name']
        identifier = request.form['identifier']

        # Ensure it's an 8-digit identifier
        if not identifier.isdigit() or len(identifier) != 8:
            error = "Please enter an 8-digit number."
            return render_template('index.html', error=error)

        return redirect(url_for('instructions', name=name, identifier=identifier))

    return render_template('index.html', error=None)

@app.route('/instructions')
def instructions():
    """Displays instructions before starting the assessment."""
    name = request.args.get('name')
    identifier = request.args.get('identifier')

    instructions_text = """
    This leadership assessment is designed to help you understand your natural leadership style. 
    - Be honest with your responses.
    - Don't overthink, but don't rush.
    - Choose a quiet environment to focus.
    - Complete the assessment in one sitting.
    - There is no perfect leader—just insights into your style.

    Once ready, click "Start Assessment".
    """

    return render_template('instructions.html', name=name, identifier=identifier, instructions=instructions_text)

@app.route('/assessment', methods=['GET', 'POST'])
def assessment():
    """Displays assessment questions and records user responses."""
    try:
        if request.method == 'POST':
            responses = {key: int(value) for key, value in request.form.items() if key.startswith('q_')}
            return redirect(url_for('results', responses=json.dumps(responses)))  # Convert to JSON string

        question_dict = load_questions()
        if not question_dict:
            return "Error: Questions failed to load from the GitHub Excel file."

        questions = []
        for (style_num, style_name), q_list in question_dict.items():
            for q in q_list:
                questions.append((style_num, style_name, q['Questions'], q['Approach']))

        if not questions:
            return "Error: No questions found. Check the Excel file structure."

        random.shuffle(questions)
        return render_template('assessment.html', questions=questions)

    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

@app.route('/results', methods=['GET', 'POST'])
def results():
    """Calculates and displays leadership assessment results, grouped by style."""
    try:
        if request.method == 'POST':
            responses = {key: int(value) for key, value in request.form.items() if key.startswith('q_')}
        else:
            responses_str = request.args.get('responses')
            if not responses_str:
                return "Error: No responses received."

            # Convert JSON string back into a dictionary
            responses = json.loads(responses_str.replace("'", "\""))  # Fix single-quoted JSON issue

        weight_mapping = {1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}
        score_summary = {}

        for key, score in responses.items():
            parts = key.split('_')
            if len(parts) < 3:
                continue  # Skip if data is malformed
            
            style_name = parts[2]  # Extract style name
            adjusted_score = weight_mapping.get(int(score), 0)  # Apply weighting

            if style_name not in score_summary:
                score_summary[style_name] = 0
            score_summary[style_name] += adjusted_score  # Sum scores per style

        # Create Bar Chart
        if not os.path.exists("static"):
            os.makedirs("static")  # Ensure static folder exists

        chart_path = "static/results_chart.png"

        plt.figure(figsize=(10, 6))
        plt.bar(score_summary.keys(), score_summary.values(), color='blue')
        plt.xlabel("Leadership Style")
        plt.ylabel("Score")
        plt.title("Leadership Style Assessment Results")
        plt.xticks(rotation=45)
        plt.savefig(chart_path)
        plt.close()

        return render_template('results.html', scores=score_summary, chart_path=chart_path)

    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"

if __name__ == "__main__":
    app.run(debug=True)
