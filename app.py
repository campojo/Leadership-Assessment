import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'

# Load questions from both sheets

def load_questions():
    try:
        print("Attempting to load questions from Excel...")  # Debug print
        df = pd.read_excel('https://github.com/campojo/leadership_style_questions/raw/main/Questions%202.0%20(5).xlsx', 
                          sheet_name=None)
        
        assessment_df = df['Questions']
        survey_df = df['SurveyQuestions']
        
        questions = assessment_df['Question'].tolist()
        surveys = survey_df['Question'].tolist()
        
        print(f"Successfully loaded {len(questions)} questions and {len(surveys)} surveys")  # Debug print
        return questions, surveys
    except Exception as e:
        print(f"Error loading questions: {str(e)}")  # Add error logging
        return [], []

assessment_questions, survey_questions = load_questions()

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
            # Add debug print
            print("Loading assessment page with questions:", len(assessment_questions), "survey questions:", len(survey_questions))
            if not assessment_questions or not survey_questions:
                # Just reload questions without global declaration
                assessment_questions, survey_questions = load_questions()
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
        print(f"Error in assessment route: {str(e)}")  # Add error logging
        return f"An error occurred: {str(e)}", 500

@app.route('/results')
def results():
    try:
        responses = session.get('responses', {})
        if not responses:
            return redirect(url_for('assessment'))
        
        survey = session.get('survey', {})
        print(f"Processing results with {len(responses)} responses")  # Debug print

        # Leadership styles and basic scoring
        styles = ['Transformational', 'Democratic', 'Charismatic', 'Authentic',
                  'Laissez-Faire', 'Situational', 'Transactional', 'Servant']
        value_map = {
            'Strongly Disagree': -2,
            'Disagree': -1,
            'Neutral': 0,
            'Agree': 1,
            'Strongly Agree': 2
        }

        scores = [value_map.get(responses.get(q, ''), 0) for q in assessment_questions]
        chunk_size = len(assessment_questions) // len(styles)
        results = {
            styles[i]: sum(scores[i*chunk_size:(i+1)*chunk_size])
            for i in range(len(styles))
        }

        # Plot with improvements
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.bar(results.keys(), results.values(), color='blue', zorder=1)
        ax.axhline(y=0, color='gray', linestyle='--', linewidth=1, zorder=2)
        ax.set_title('Leadership Style Assessment Results')
        ax.set_ylabel('Tendency Level')
        ax.set_xlabel('Leadership Style')
        ax.set_xticklabels(results.keys(), rotation=45, ha='right')
        ax.set_yticks([-6, -3, 0, 3, 6])
        ax.set_yticklabels(['Lower Tendency', '', 'Moderate', '', 'Higher Tendency'])
        ax.set_ylim(-8, 8)

        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        buf.seek(0)
        chart_data = base64.b64encode(buf.read()).decode()
        plt.close()

        return render_template('results.html', chart_data=chart_data)
    except Exception as e:
        print(f"Error in results route: {str(e)}")  # Add error logging
        return f"An error occurred: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
