from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
import unicodedata
import json
import os
from pathlib import Path
from datetime import datetime
import plotly
import plotly.express as px
import plotly.graph_objects as go
import uuid
import tempfile

# Add project root to path and import stemmer
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from src.stemmer import ManipuriStemmer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = Path(__file__).parent / 'uploads'
app.config['UPLOAD_FOLDER'].mkdir(exist_ok=True)

# Global stemmer instance
stemmer = ManipuriStemmer(
    'data/affixes/prefixes_meitei.txt',
    'data/affixes/suffixes_meitei.txt'
)

# Store evaluation history in memory (could be replaced with DB)
EVAL_HISTORY = []

# ---------- Helper functions ----------
def normalize_text(text):
    return unicodedata.normalize('NFC', text.strip())

def store_evaluation(name, total, correct, precision, recall, f1, over, under):
    EVAL_HISTORY.append({
        'id': str(uuid.uuid4()),
        'timestamp': datetime.now().isoformat(),
        'name': name,
        'total': total,
        'correct': correct,
        'precision': precision,
        'recall': recall,
        'f1': f1,
        'overstemmed': over,
        'understemmed': under
    })
    # Keep only last 20 evaluations
    if len(EVAL_HISTORY) > 20:
        EVAL_HISTORY.pop(0)

# ---------- Routes ----------
@app.route('/')
def index():
    """Main stemmer page."""
    return render_template('index.html', 
                         prefix_count=len(stemmer.prefixes),
                         suffix_count=len(stemmer.suffixes))

@app.route('/stem', methods=['POST'])
def stem_word():
    """API endpoint to stem a single word."""
    data = request.get_json()
    word = data.get('word', '').strip()
    if not word:
        return jsonify({'error': 'Empty word'}), 400
    stem = stemmer.stem(word)
    return jsonify({'original': word, 'stem': stem})

@app.route('/evaluate', methods=['GET', 'POST'])
def evaluate():
    """Evaluation page with file upload."""
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Save uploaded file
        filepath = app.config['UPLOAD_FOLDER'] / file.filename
        file.save(filepath)
        
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
            if 'word' not in df.columns or 'true_stem' not in df.columns:
                return jsonify({'error': 'CSV must contain "word" and "true_stem" columns'}), 400
            
            # Clean data
            df['true_stem'] = df['true_stem'].astype(str).str.strip()
            df = df[df['true_stem'] != ''].copy()
            if len(df) == 0:
                return jsonify({'error': 'No valid rows with true_stem'}), 400
            
            # Stem
            df['predicted_stem'] = df['word'].astype(str).apply(stemmer.stem)
            
            # Metrics
            correct = (df['true_stem'] == df['predicted_stem']).sum()
            total = len(df)
            precision = recall = correct / total
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
            
            # Error analysis
            df['correct'] = df['true_stem'] == df['predicted_stem']
            df['overstemmed'] = ~df['correct'] & (df['predicted_stem'].str.len() < df['true_stem'].str.len())
            df['understemmed'] = ~df['correct'] & (df['predicted_stem'].str.len() > df['true_stem'].str.len())
            over_count = df['overstemmed'].sum()
            under_count = df['understemmed'].sum()
            
            # Store history
            store_evaluation(file.filename, total, correct, precision, recall, f1, over_count, under_count)
            
            # Generate charts as JSON
            metrics_fig = go.Figure(data=[
                go.Bar(x=['Precision', 'Recall', 'F1-Score'],
                       y=[precision, recall, f1],
                       marker_color=['#4F46E5', '#10B981', '#F59E0B'],
                       text=[f"{precision:.2%}", f"{recall:.2%}", f"{f1:.2%}"],
                       textposition='outside')
            ])
            metrics_fig.update_layout(title="Performance Metrics", yaxis_tickformat=".0%", height=350)
            metrics_chart = json.dumps(metrics_fig, cls=plotly.utils.PlotlyJSONEncoder)
            
            error_fig = px.pie(values=[over_count, under_count],
                               names=['Overstemmed', 'Understemmed'],
                               title="Error Distribution",
                               color_discrete_sequence=['#EF4444', '#F97316'],
                               hole=0.4)
            error_chart = json.dumps(error_fig, cls=plotly.utils.PlotlyJSONEncoder)
            
            # Prepare error table HTML
            errors = df[~df['correct']]
            error_table_html = errors[['word', 'true_stem', 'predicted_stem']].to_html(classes='table table-striped', index=False)
            
            return render_template('evaluate_result.html',
                                 filename=file.filename,
                                 total=total,
                                 correct=correct,
                                 precision=f"{precision:.2%}",
                                 recall=f"{recall:.2%}",
                                 f1=f"{f1:.2%}",
                                 over_count=over_count,
                                 under_count=under_count,
                                 metrics_chart=metrics_chart,
                                 error_chart=error_chart,
                                 error_table_html=error_table_html,
                                 results_df=df.to_dict('records'))
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    # GET request - show upload form
    return render_template('evaluate.html')

@app.route('/evaluate_gold', methods=['POST'])
def evaluate_gold():
    """Evaluate on the built-in gold standard file."""
    gold_path = Path('data/corpus/gold_standard/to_annotate.csv')
    if not gold_path.exists():
        return jsonify({'error': 'Gold standard file not found'}), 404
    
    df = pd.read_csv(gold_path, encoding='utf-8')
    df['true_stem'] = df['true_stem'].astype(str).str.strip()
    df = df[df['true_stem'] != ''].copy()
    if len(df) == 0:
        return jsonify({'error': 'No valid rows in gold standard'}), 400
    
    df['predicted_stem'] = df['word'].astype(str).apply(stemmer.stem)
    correct = (df['true_stem'] == df['predicted_stem']).sum()
    total = len(df)
    precision = recall = correct / total
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
    
    df['correct'] = df['true_stem'] == df['predicted_stem']
    df['overstemmed'] = ~df['correct'] & (df['predicted_stem'].str.len() < df['true_stem'].str.len())
    df['understemmed'] = ~df['correct'] & (df['predicted_stem'].str.len() > df['true_stem'].str.len())
    over_count = df['overstemmed'].sum()
    under_count = df['understemmed'].sum()
    
    store_evaluation('to_annotate.csv (gold)', total, correct, precision, recall, f1, over_count, under_count)
    
    metrics_fig = go.Figure(data=[
        go.Bar(x=['Precision', 'Recall', 'F1-Score'],
               y=[precision, recall, f1],
               marker_color=['#4F46E5', '#10B981', '#F59E0B'],
               text=[f"{precision:.2%}", f"{recall:.2%}", f"{f1:.2%}"],
               textposition='outside')
    ])
    metrics_fig.update_layout(title="Gold Standard Performance", yaxis_tickformat=".0%", height=350)
    metrics_chart = json.dumps(metrics_fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    error_fig = px.pie(values=[over_count, under_count],
                       names=['Overstemmed', 'Understemmed'],
                       title="Error Distribution",
                       color_discrete_sequence=['#EF4444', '#F97316'],
                       hole=0.4)
    error_chart = json.dumps(error_fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    errors = df[~df['correct']]
    error_table_html = errors[['word', 'true_stem', 'predicted_stem']].to_html(classes='table table-striped', index=False)
    
    return render_template('evaluate_result.html',
                         filename='to_annotate.csv (gold)',
                         total=total,
                         correct=correct,
                         precision=f"{precision:.2%}",
                         recall=f"{recall:.2%}",
                         f1=f"{f1:.2%}",
                         over_count=over_count,
                         under_count=under_count,
                         metrics_chart=metrics_chart,
                         error_chart=error_chart,
                         error_table_html=error_table_html,
                         results_df=df.to_dict('records'))

@app.route('/batch/get_columns', methods=['POST'])
def get_batch_columns():
    """Get column names from uploaded file for batch stemmer."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Empty filename'}), 400
    
    try:
        # Get file extension
        file_ext = os.path.splitext(file.filename)[1].lower()
        
        # Create a temporary file with proper extension
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext, mode='wb') as tmp_file:
            file.save(tmp_file.name)
            tmp_path = tmp_file.name
        
        try:
            # Read based on file extension
            if file_ext in ['.xlsx', '.xls']:
                # For Excel files
                df = pd.read_excel(tmp_path, nrows=1, engine='openpyxl')
            else:
                # For CSV files - try different encodings
                df = None
                for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                    try:
                        df = pd.read_csv(tmp_path, nrows=1, encoding=encoding)
                        break
                    except (UnicodeDecodeError, pd.errors.ParserError):
                        continue
                
                if df is None:
                    return jsonify({'error': 'Could not parse CSV file with any encoding'}), 400
            
            # Clean column names (remove whitespace)
            df.columns = df.columns.str.strip()
            columns = df.columns.tolist()
            
            # Clean up temp file
            os.unlink(tmp_path)
            
            if not columns:
                return jsonify({'error': 'No columns found in file'}), 400
                
            return jsonify({'columns': columns})
            
        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise e
            
    except Exception as e:
        print(f"Error in get_batch_columns: {str(e)}")
        return jsonify({'error': f'Failed to read file: {str(e)}'}), 500

@app.route('/batch', methods=['GET', 'POST'])
def batch():
    """Batch stemming page."""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            return jsonify({'error': 'No file uploaded'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'Empty filename'}), 400
        
        # Get column selection (default to first column if not specified)
        filepath = app.config['UPLOAD_FOLDER'] / file.filename
        file.save(filepath)
        
        try:
            # Detect file type (CSV or Excel)
            file_ext = os.path.splitext(file.filename)[1].lower()
            
            if file_ext in ('.xlsx', '.xls'):
                df = pd.read_excel(filepath, engine='openpyxl')
            else:
                # Try different encodings for CSV
                df = None
                for encoding in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
                    try:
                        df = pd.read_csv(filepath, encoding=encoding)
                        break
                    except (UnicodeDecodeError, pd.errors.ParserError):
                        continue
                
                if df is None:
                    return jsonify({'error': 'Could not parse CSV file with any encoding'}), 400
            
            col_choice = request.form.get('word_column')
            if col_choice and col_choice not in df.columns:
                return jsonify({'error': f'Column "{col_choice}" not found'}), 400
            elif not col_choice or col_choice == '':
                # Auto-select first string/text column
                text_cols = df.select_dtypes(include=['object']).columns
                if len(text_cols) == 0:
                    return jsonify({'error': 'No text columns found in the file'}), 400
                col_choice = text_cols[0]
            
            # Apply stemming
            df['stem'] = df[col_choice].astype(str).apply(stemmer.stem)
            
            # Generate output filename
            name, ext = os.path.splitext(file.filename)
            output_filename = f'stemmed_{name}{ext}'
            output_path = app.config['UPLOAD_FOLDER'] / output_filename
            
            # Save based on file type
            if ext.lower() in ('.xlsx', '.xls'):
                df.to_excel(output_path, index=False, engine='openpyxl')
            else:
                df.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            # Generate preview (first 20 rows)
            preview_html = df.head(20).to_html(classes='table table-sm mb-0', 
                                               index=False, 
                                               escape=False)
            
            return render_template('batch_result.html',
                                 original_filename=file.filename,
                                 output_filename=output_filename,
                                 preview=preview_html,
                                 total_rows=len(df),
                                 column_used=col_choice,
                                 file_type='Excel' if ext.lower() in ('.xlsx', '.xls') else 'CSV')
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'error': str(e)}), 500
    
    # GET request - show batch upload form
    return render_template('batch.html', 
                         prefix_count=len(stemmer.prefixes),
                         suffix_count=len(stemmer.suffixes))

@app.route('/download/<filename>')
def download_file(filename):
    """Download a file from uploads folder."""
    filepath = app.config['UPLOAD_FOLDER'] / filename
    if not filepath.exists():
        return "File not found", 404
    return send_file(filepath, as_attachment=True)

@app.route('/dashboard')
def dashboard():
    """Dashboard showing evaluation history with charts."""
    if not EVAL_HISTORY:
        return render_template('dashboard.html', has_data=False)
    
    # Prepare data for trend chart
    df_hist = pd.DataFrame(EVAL_HISTORY)
    df_hist['date'] = pd.to_datetime(df_hist['timestamp']).dt.strftime('%Y-%m-%d %H:%M')
    
    trend_fig = go.Figure()
    trend_fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['precision'], mode='lines+markers', name='Precision', line=dict(color='#4F46E5')))
    trend_fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['recall'], mode='lines+markers', name='Recall', line=dict(color='#10B981')))
    trend_fig.add_trace(go.Scatter(x=df_hist['date'], y=df_hist['f1'], mode='lines+markers', name='F1-Score', line=dict(color='#F59E0B', width=3)))
    trend_fig.update_layout(title="Performance Over Time", xaxis_title="Evaluation", yaxis_title="Score", yaxis_tickformat=".0%", height=400)
    trend_chart = json.dumps(trend_fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Error bar chart
    err_fig = go.Figure()
    err_fig.add_trace(go.Bar(x=df_hist['date'], y=df_hist['overstemmed'], name='Overstemmed', marker_color='#EF4444'))
    err_fig.add_trace(go.Bar(x=df_hist['date'], y=df_hist['understemmed'], name='Understemmed', marker_color='#F97316'))
    err_fig.update_layout(title="Error Counts Over Time", xaxis_title="Evaluation", yaxis_title="Count", barmode='group', height=350)
    error_trend_chart = json.dumps(err_fig, cls=plotly.utils.PlotlyJSONEncoder)
    
    # Summary stats
    latest = df_hist.iloc[-1]
    avg_f1 = df_hist['f1'].mean()
    
    return render_template('dashboard.html',
                         has_data=True,
                         total_evaluations=len(EVAL_HISTORY),
                         latest_name=latest['name'],
                         latest_f1=f"{latest['f1']:.2%}",
                         avg_f1=f"{avg_f1:.2%}",
                         trend_chart=trend_chart,
                         error_trend_chart=error_trend_chart,
                         history_table=df_hist[['date', 'name', 'total', 'correct', 'precision', 'recall', 'f1', 'overstemmed', 'understemmed']].to_html(classes='table table-striped', index=False))

if __name__ == '__main__':
    app.run(debug=True, port=5000)