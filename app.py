import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
import matplotlib.pyplot as plt
import io
import base64
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Global variables
assessment_questions = []
survey_questions = []

def load_questions():
    global assessment_questions, survey_questions
    try:
        print("Attempting to load questions from Excel...")
        df = pd.read_excel('https://github.com/campojo/leadership_style_questions/raw/main/Questions%202.0%20(5).xlsx', 
                          sheet_name=None)
        
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
        
        assessment_questions = selected_questions
        survey_questions = survey_df['Question'].tolist()
    except Exception as e:
        print(f"Error loading questions: {str(e)}")
        return [], []

# Initial load
load_questions()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        name = request.form.get('name')
        identifier = request.form.get('identifier')
        if name:
            session['name'] = name
            session['identifier'] = identifier
            return redirect(url_for('instructions'))
        return render_template('index.html', error="Please enter your name")
    return render_template('index.html')

@app.route('/instructions')
def instructions():
    return render_template('instructions.html')

@app.route('/assessment', methods=['GET', 'POST'])
def assessment():
    try:
        if request.method == 'GET':
            global assessment_questions, survey_questions
            print("Loading assessment page with questions:", len(assessment_questions), "survey questions:", len(survey_questions))
            if not assessment_questions or not survey_questions:
                # Reload questions if they're empty
                load_questions()
            return render_template('assessment.html', 
                                assessment_questions=assessment_questions, 
                                survey_questions=survey_questions)
        elif request.method == 'POST':
            if not request.form:
                return redirect(url_for('assessment'))
            session['responses'] = {q: request.form.get(q) for q in assessment_questions}
            session['survey'] = {f'survey_{i+1}': request.form.get(f'survey_{i+1}') 
                               for i in range(len(survey_questions))}
            return redirect(url_for('results'))
    except Exception as e:
        print(f"Error in assessment route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

@app.route('/results')
def results():
    try:
        responses = session.get('responses', {})
        if not responses:
            return redirect(url_for('assessment'))
        
        survey = session.get('survey', {})
        print(f"Processing results with {len(responses)} responses")

        # Load the original questions to get style information
        df = pd.read_excel('https://github.com/campojo/leadership_style_questions/raw/main/Questions%202.0%20(5).xlsx', 
                          sheet_name='Questions')
        
        # Leadership styles
        styles = ['Transformational', 'Democratic', 'Charismatic', 'Authentic',
                 'Laissez-Faire', 'Situational', 'Transactional', 'Servant']
        
        # Convert 1-5 scale to -2 to +2 scale for visualization
        value_map = {
            '1': -2,  # Disagree
            '2': -1,
            '3': 0,   # Neutral
            '4': 1,
            '5': 2    # Agree
        }

        # Create a dictionary to map questions to their styles
        question_style_map = dict(zip(df['Question'], df['Style_Num']))
        
        # Initialize scores for each style
        style_scores = {i+1: [] for i in range(8)}  # 8 leadership styles
        
        # Group scores by style
        for question, response in responses.items():
            if question in question_style_map:
                style_num = question_style_map[question]
                score = value_map.get(response, 0)
                style_scores[style_num].append(score)
        
        # Calculate average score for each style
        results = {}
        for i, style in enumerate(styles, 1):
            scores = style_scores.get(i, [])
            if scores:
                results[style] = sum(scores) / len(scores)  # Average score
            else:
                results[style] = 0

        # Plot with improvements
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(results.keys(), results.values(), color='blue', zorder=1)
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, zorder=2)
        ax.set_title('Leadership Style Assessment Results')
        ax.set_ylabel('Tendency Level')
        ax.set_xlabel('Leadership Style')
        ax.set_xticklabels(results.keys(), rotation=45, ha='right')
        ax.set_yticks([-2, -1, 0, 1, 2])
        ax.set_yticklabels(['Strong Disagree', 'Disagree', 'Neutral', 'Agree', 'Strong Agree'])
        ax.set_ylim(-2.5, 2.5)

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png', dpi=300)
        buf.seek(0)
        chart_data = base64.b64encode(buf.read()).decode()
        plt.close()

        return render_template('results.html', chart_data=chart_data)
    except Exception as e:
        print(f"Error in results route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
