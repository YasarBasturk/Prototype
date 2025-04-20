from flask import Flask, request, jsonify, render_template, send_file
import os
from werkzeug.utils import secure_filename
import traceback
import sys
import json

# Add the parent directory to Python path
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(parent_dir)

# Import Scripts
from Scripts.image_preprocess import preprocess_image
from Scripts.cell_processing import run_cell_detection
from Scripts.ai_processing import ai_processing

# Import local modules with proper package paths
from server.merge_split_processing import merge_split_processing

app = Flask(__name__, 
            static_folder='../Static',
            template_folder='../template')

# Configure upload folder and create necessary directories
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOAD_FOLDER = os.path.join(PROJECT_ROOT, 'uploads')
OUTPUT_ROOT = os.path.join(PROJECT_ROOT, 'output')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=16 * 1024 * 1024  # 16MB max file size
)

# Create necessary directories
directories = [
    UPLOAD_FOLDER,
    os.path.join(OUTPUT_ROOT, 'preprocessed'),
    os.path.join(OUTPUT_ROOT, 'cell detection'),
    os.path.join(OUTPUT_ROOT, 'image-preprocessing'),
    os.path.join(OUTPUT_ROOT, 'merge and split')
]

for directory in directories:
    os.makedirs(directory, exist_ok=True)
    print(f"Ensured directory exists: {directory}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/output/<path:filename>')
def output_file(filename):
    """Serve any file from the output directory."""
    return send_file(os.path.join(OUTPUT_ROOT, filename))

@app.route('/process_image', methods=['POST'])
def process_image():
    if 'file' not in request.files:
        return jsonify({'status': 'error', 'error': 'No file provided'}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({'status': 'error', 'error': 'No file selected'}), 400
        
    try:
        # Save the uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        
        # Get base name without extension
        base_name = os.path.splitext(filename)[0]
        processed_filename = f'processed_{filename}'
        
        # Step 1: Process the image
        preprocessed_path = os.path.join(OUTPUT_ROOT, 'preprocessed', processed_filename)
        preprocess_image(filepath, preprocessed_path)
        
        # Step 2: Cell Detection
        cell_json_path = run_cell_detection(preprocessed_path)
        
        # Step 3: AI Model Processing
        ai_json_path = ai_processing(preprocessed_path)
        
        # Step 4: Merge and Split Processing
        merged_json_path, merged_viz_path = merge_split_processing(
            cell_json_path=cell_json_path,
            ocr_json_path=ai_json_path,
            preprocessed_image_path=preprocessed_path
        )
        
        if not merged_viz_path or not os.path.exists(merged_viz_path):
            return jsonify({'status': 'error', 'error': 'Failed to generate visualization'}), 500
        
        # Load the JSON data to include in the response
        with open(merged_json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        
        # Construct the edit URL
        json_filename = os.path.basename(merged_json_path)
        edit_url = f'/edit_results/{json_filename}'
        
        # Get the visualization filename
        viz_filename = os.path.basename(merged_viz_path)
        
        return jsonify({
            'status': 'success',
            'original_path': f'/uploads/{filename}',
            'output_image': f'/output/merge and split/{viz_filename}',
            'edit_url': edit_url,
            'json_data': json_data  # Include the JSON data directly in the response
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'error': str(e)}), 500

@app.route('/edit_results/<filename>')
def edit_results(filename):
    try:
        json_path = os.path.join(OUTPUT_ROOT, 'merge and split', filename)
        if not os.path.exists(json_path):
            return jsonify({'error': 'File not found'}), 404
            
        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
            
        return jsonify(json_data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/save_edits/<filename>', methods=['POST'])
def save_edits(filename):
    try:
        changes = request.json
        json_path = os.path.join(OUTPUT_ROOT, 'merge and split', filename)
        
        if not os.path.exists(json_path):
            return jsonify({'error': 'File not found'}), 404
            
        # Load current data
        with open(json_path, 'r', encoding='utf-8') as f:
            current_data = json.load(f)
            
        # Update the data with changes
        if 'cells_with_text' in changes:
            for change in changes['cells_with_text']:
                for cell in current_data['cells_with_text']:
                    if cell['cell_id'] == change['cell_id']:
                        cell['text'] = change['text']
                        break
                        
        if 'unassigned_text' in changes:
            for change in changes['unassigned_text']:
                for text in current_data['unassigned_text']:
                    if text['text_id'] == change['text_id']:
                        text['text'] = change['text']
                        break
                        
        # Save the updated data
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(current_data, f, indent=2, ensure_ascii=False)
            
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
