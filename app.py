import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, session
import matplotlib.pyplot as plt
import io
import base64
import random

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['SESSION_TYPE'] = 'filesystem'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
app.config['SESSION_COOKIE_SECURE'] = False  # Allow non-HTTPS for development

# Global variables
assessment_questions = []
survey_questions = []

def get_style_description(style):
    descriptions = {
        'Transformational': 'Focuses on inspiring and motivating followers to exceed their own self-interests for the good of the organization. Emphasizes vision, values, and intellectual stimulation.',
        'Democratic': 'Involves team members in decision-making processes and values their input. Promotes collaboration and shared responsibility.',
        'Charismatic': 'Relies on personal charm and appeal to inspire followers. Creates strong emotional bonds and enthusiasm for shared goals.',
        'Authentic': 'Emphasizes transparency, ethical behavior, and consistency between values and actions. Builds trust through genuine relationships.',
        'Laissez-Faire': 'Provides minimal direct supervision and allows team members significant autonomy in their work. Best suited for highly skilled and self-motivated teams.',
        'Situational': 'Adapts leadership approach based on the specific context and needs of followers. Flexible and responsive to changing circumstances.',
        'Transactional': 'Focuses on clear structure, rewards, and consequences. Emphasizes organization, monitoring, and performance metrics.',
        'Servant': 'Prioritizes the needs of team members and focuses on their growth and well-being. Leads through service and support.'
    }
    return descriptions.get(style, '')

def load_questions():
    global assessment_questions, survey_questions
    try:
        print("Attempting to load questions from Excel...")
        df = pd.read_excel('https://raw.githubusercontent.com/campojo/Leadership-Assessment/main/Questions%202.0.xlsx', 
                          sheet_name=None, engine='openpyxl')
        
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
        global assessment_questions, survey_questions
        if request.method == 'GET':
            print("Loading assessment page with questions:", len(assessment_questions), "survey questions:", len(survey_questions))
            if not assessment_questions or not survey_questions:
                # Reload questions if they're empty
                load_questions()
            return render_template('assessment.html', 
                                assessment_questions=assessment_questions, 
                                survey_questions=survey_questions)
        elif request.method == 'POST':
            print("\n=== Form Submission ===\nForm data:", dict(request.form))
            if not request.form:
                print("No form data received")
                return redirect(url_for('assessment'))
            
            # Store assessment responses
            # Clear any existing responses
            session.pop('responses', None)
            session.pop('survey', None)
            
            # Store new responses
            responses = {}
            for question in assessment_questions:
                value = request.form.get(question)
                if value:
                    responses[question] = value
            
            session['responses'] = responses
            # Make sure changes are saved
            session.modified = True
            
            # Store survey responses including text areas
            survey_responses = {}
            for i, _ in enumerate(survey_questions, 1):
                response = request.form.get(f'survey_{i}')
                if response:
                    survey_responses[f'survey_{i}'] = response
                # Get additional text input if it exists
                details = request.form.get(f'survey_{i}_details')
                if details:
                    survey_responses[f'survey_{i}_details'] = details
            
            session['survey'] = survey_responses
            print("\n=== Stored Data ===\nResponses:", session['responses'])
            print("Survey:", session['survey'])
            print("\n=== Redirecting to results ===\n")
            return redirect(url_for('results'))
    except Exception as e:
        print(f"Error in assessment route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

@app.route('/results')
def results():
    try:
        print("\n=== Results Route ===\nSession data:", dict(session))
        responses = session.get('responses', {})
        print("\nGot responses:", responses)
        if not responses:
            print("No responses found, redirecting to assessment")
            return redirect(url_for('assessment'))
        
        print("\nProcessing", len(responses), "responses")
        
        survey = session.get('survey', {})
        print(f"Processing results with {len(responses)} responses")

        # Load both questions and score-based responses
        excel_data = pd.read_excel('https://raw.githubusercontent.com/campojo/Leadership-Assessment/main/Questions%202.0.xlsx', 
                          sheet_name=['Questions', 'ScoreBasedResponse'])
        df = excel_data['Questions']
        response_df = excel_data['ScoreBasedResponse']
        
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
        question_style_map = {}
        for _, row in df.iterrows():
            question_style_map[row['Question']] = int(row['Style_Num'])
        
        print("\nQuestion to style mapping:", question_style_map)
        print("\nResponses received:", responses)
        
        # Initialize scores for each style
        style_scores = {i+1: [] for i in range(8)}  # 8 leadership styles
        
        # Group scores by style
        for question, response in responses.items():
            print(f"Processing question: {question} with response: {response}")
            if question in question_style_map:
                style_num = question_style_map[question]
                score = value_map.get(response, 0)
                style_scores[style_num].append(score)
                print(f"Added score {score} to style {style_num}")
            else:
                print(f"Question not found in mapping: {question}")
        results_dict = {}
        style_map = {i+1: style for i, style in enumerate(styles)}  # Map style numbers to names
        
        for style_num, scores in style_scores.items():
            style_name = style_map.get(style_num)
            if style_name and scores:
                results_dict[style_name] = sum(scores) / len(scores)  # Average score
            elif style_name:
                results_dict[style_name] = 0
        
        print("\nFinal results:", results_dict)

        # Create the plot
        plt.figure(figsize=(12, 6))
        plt.clf()  # Clear the current figure
        
        # Get the data in the right order
        styles = list(results_dict.keys())
        scores = [results_dict[style] for style in styles]
        
        # Create the bar chart
        x = range(len(styles))
        plt.bar(x, scores, align='center', color='skyblue')
        
        # Customize the plot
        plt.title('Leadership Style Assessment Results', pad=20)
        plt.ylabel('Tendency Level')
        plt.xticks(x, styles, rotation=45, ha='right')
        plt.yticks([-2, 0, 2], ['Low Tendency', 'Moderate', 'High Tendency'])
        plt.grid(True, axis='y', linestyle='--', alpha=0.7)
        
        # Add a horizontal line at y=0
        plt.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
        
        # Adjust layout to prevent label cutoff
        plt.tight_layout()
        
        # Save the plot to a base64 string
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        chart_data = base64.b64encode(img.getvalue()).decode()
        plt.close()

        # Generate summary based on top leadership styles
        sorted_styles = sorted(results_dict.items(), key=lambda x: x[1], reverse=True)
        top_styles = sorted_styles[:2]
        bottom_styles = sorted_styles[-2:]
        
        summary = {
            'dominant_styles': [{
                'style': style,
                'score': score,
                'description': get_style_description(style)
            } for style, score in top_styles],
            'lesser_styles': [{
                'style': style,
                'score': score,
                'description': get_style_description(style)
            } for style, score in bottom_styles]
        }
        
        return render_template('results.html', chart_data=chart_data, summary=summary)
    except Exception as e:
        print(f"Error in results route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
