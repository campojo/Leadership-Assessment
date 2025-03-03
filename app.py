from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import random
import requests
import json
import matplotlib
matplotlib.use('Agg')  # Prevents GUI rendering issues on Render
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
    
    Please follow these guidelines:
    - Be honest with your responses.
    - Don't overthink, but don't rush.
    - Choose a quiet environment to focus.
    - Complete the assessment in one sitting.
    - There is no perfect leader—just insights into your style.
    """

    return render_template('instructions.html', name=name, identifier=identifier, instructions=instructions_text)


@app.route('/assessment', methods=['GET', 'POST'])
def assessment():
    """Displays assessment questions and records user responses."""
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

    random.shuffle(questions)
    return render_template('assessment.html', questions=questions)

@app.route('/results')
def results():
    """Calculates and displays aggregated leadership assessment results, grouped by leadership style name."""
    try:
        responses_str = request.args.get('responses')
        if not responses_str:
            return "Error: No responses received."

        responses = json.loads(responses_str.replace("'", "\""))  # Convert JSON string to dictionary

        # Mapping of responses to weighted scores
        weight_mapping = {1: -2.0, 2: -1.0, 3: 0.0, 4: 1.0, 5: 2.0}
        score_summary = {}

        # Define mapping from Style_Num to Style_Name (can be improved by loading dynamically)
        style_mapping = {
            "0": "Transformational",
            "1": "Transactional",
            "2": "Servant",
            "3": "Autocratic",
            "4": "Laissez-Faire",
            "5": "Democratic"
        }

        # Aggregate scores by leadership style name
        for key, score in responses.items():
            parts = key.split('_')
            if len(parts) < 3:
                continue  # Skip malformed data
            
            style_num = parts[1]  # Extract style number (e.g., "0", "1", etc.)
            style_name = style_mapping.get(style_num, "Unknown Style")  # Get style name

            adjusted_score = weight_mapping.get(int(score), 0)  # Apply score weighting

            if style_name not in score_summary:
                score_summary[style_name] = 0
            score_summary[style_name] += adjusted_score  # Sum scores per style

        # Debugging: Print the correct Style Names in logs
        print("Score Summary with Style Names:", score_summary)

        if not score_summary:
            return "Error: No scores calculated. Please check response processing."

        sorted_styles = list(score_summary.keys())  # Get leadership style names
        sorted_scores = [score_summary[style] for style in sorted_styles]  # Get scores

        # Ensure the static directory exists
        if not os.path.exists("static"):
            os.makedirs("static")

        chart_path = "static/results_chart.png"

        # Create Bar Chart with Proper Labels
        plt.figure(figsize=(10, 6))
        plt.bar(sorted_styles, sorted_scores, color='blue')  # Use Style_Name on x-axis
        plt.xlabel("Leadership Style")
        plt.ylabel("Total Score")
        plt.title("Leadership Style Assessment Results")
        plt.xticks(rotation=45, ha="right")  # Rotate labels for readability
        plt.tight_layout()  # Ensure labels fit
        plt.savefig(chart_path)
        plt.close()

        return render_template('results.html', scores=score_summary, chart_path=chart_path)

    except Exception as e:
        return f"An unexpected error occurred: {str(e)}"


@app.route('/test-results')
def test_results():
    """Test the results calculation with predefined responses."""
    test_responses = {
        "q_0_Transformational": "4",
        "q_1_Transactional": "2",
        "q_2_Servant": "5",
        "q_3_Autocratic": "1",
        "q_4_LaissezFaire": "3",
        "q_5_Democratic": "4"
    }
    return redirect(url_for('results', responses=json.dumps(test_responses)))


if __name__ == "__main__":
    app.run(debug=True)
