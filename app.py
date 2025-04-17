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
        
        # Calculate average scores for each style
        avg_scores = {}
        for style_num, scores in style_scores.items():
            if scores:  # Only calculate average if there are scores
                avg_scores[style_num] = sum(scores) / len(scores)
            else:
                avg_scores[style_num] = 0
        
        print("\nAverage scores:", avg_scores)
        
        # Create the bar chart
        plt.figure(figsize=(12, 6))
        plt.grid(True, axis='y', linestyle='--', alpha=0.7)
        
        # Create bars
        bars = plt.bar(styles, [avg_scores[i] for i in range(1, 9)])
        
        # Customize the chart
        plt.axhline(y=0, color='black', linewidth=0.5)
        plt.title('Your Leadership Style Profile', pad=20)
        plt.xlabel('Leadership Styles')
        plt.ylabel('Score (-2 to +2 scale)')
        
        # Rotate x-axis labels for better readability
        plt.xticks(rotation=45, ha='right')
        
        # Color code the bars
        for bar in bars:
            if bar.get_height() >= 0:
                bar.set_color('#4CAF50')
            else:
                bar.set_color('#f44336')
        
        # Adjust layout to prevent label cutoff
        plt.tight_layout()
        
        # Save the plot to a base64 string
        img = io.BytesIO()
        plt.savefig(img, format='png', bbox_inches='tight')
        img.seek(0)
        chart_data = base64.b64encode(img.getvalue()).decode()
        plt.close()
        
        # Categorize styles by score
        high_styles = []
        moderate_styles = []
        low_styles = []
        
        for i, style in enumerate(styles, 1):
            score = avg_scores[i]
            # Get style descriptions from response_df
            style_responses = response_df[response_df['Leadership Style'] == style]
            
            if score > 4:
                tendency = 'High'
            elif score < -3:
                tendency = 'Low'
            else:
                tendency = 'Moderate'
            
            style_desc = style_responses[style_responses['Tendency'] == tendency]['Description'].iloc[0]
            style_data = {
                'style': style,
                'score': score,
                'description': style_desc
            }
            
            if tendency == 'High':
                high_styles.append(style_data)
            elif tendency == 'Low':
                low_styles.append(style_data)
            else:
                moderate_styles.append(style_data)
        
        # Prepare the summary data
        summary = {
            'intro_text': "It's important to remember that there is no right or wrong score in this assessment; rather, the goal is to develop self-awareness as a leader. Each leadership style has its strengths and challenges, and understanding your tendencies allows you to recognize how your approach impacts others. By becoming more aware of your natural leadership style, you can adapt and refine your methods to better meet the needs of your team and organization. Self-awareness empowers you to make conscious decisions about when to lean into certain behaviors and when to adjust your approach, ensuring you lead in a way that fosters growth, collaboration, and positive outcomes.",
            'high_tendency': {
                'description': "If a person scores high in this assessment area, it suggests that they strongly exhibit behaviors aligned with specific leadership styles. For example, a high score in democratic leadership indicates a tendency to prioritize collaboration and actively involve team members in decision-making. A high score in transformational leadership suggests a natural ability to inspire and motivate others toward long-term goals and personal growth. These tendencies reflect an individual who is skilled in creating an inclusive and visionary environment, fostering engagement and innovation within their team.",
                'styles': high_styles
            },
            'moderate_tendency': {
                'description': "If a person scores moderately in this assessment area, it indicates that they exhibit a balanced approach to the behaviors associated with that leadership trait. They may demonstrate some strength in the area, but also show room for improvement. For example, a moderate score in decision-making suggests they are capable of making decisions, but may occasionally hesitate or seek more input from others. Similarly, a moderate score in communication might indicate that they communicate effectively at times, but could benefit from refining their clarity or engagement with different audiences. Overall, they are likely adaptable, but may need to develop more consistency in their approach to fully leverage their leadership potential.",
                'styles': moderate_styles
            },
            'low_tendency': {
                'description': "If a person scores low in this assessment area, it suggests that they may find certain behaviors associated with that leadership trait more challenging. For example, a low score in democratic leadership might indicate a preference for making decisions independently, rather than involving others in the decision-making process. A low score in servant leadership might suggest a tendency to prioritize tasks over the well-being and development of team members. These tendencies reflect areas where the individual may benefit from additional development or practice to enhance their effectiveness in specific situations.",
                'styles': low_styles
            }
        }
        
        return render_template('results.html', chart_data=chart_data, summary=summary)
    except Exception as e:
        print(f"Error in results route: {str(e)}")
        return f"An error occurred: {str(e)}", 500

if __name__ == '__main__':
    app.run(debug=True)
