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
from server.database import Database

# Initialize database
db = Database()

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
    MAX_CONTENT_LENGTH=48 * 1024 * 1024  # 48MB max file size
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

@app.route('/json/<path:filename>')
def serve_json(filename):
    """Serve JSON files with proper MIME type."""
    try:
        json_path = os.path.join(OUTPUT_ROOT, 'merge and split', filename)
        if not os.path.exists(json_path):
            return jsonify({'error': 'JSON file not found'}), 404
            
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return jsonify(data)
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
        # Ensure we have JSON data
        if not request.is_json:
            return jsonify({'success': False, 'error': 'Request must be JSON'}), 400
            
        changes = request.json
        if not changes:
            return jsonify({'success': False, 'error': 'Empty request body'}), 400
            
        # Find the correct JSON file path
        # Handle various filename patterns and ensure it has .json extension
        if not filename.endswith('.json'):
            filename = filename + '.json'
        
        # Directory where JSON files are stored
        json_dir = os.path.join(OUTPUT_ROOT, 'merge and split')
        
        # Check common path patterns for the JSON file
        possible_paths = [
            os.path.join(json_dir, filename),
            os.path.join(json_dir, filename.replace('_res_visualization_with_spanning', '_res_combined_with_spanning')),
            os.path.join(json_dir, filename.replace('visualization_', '')),
            os.path.join(json_dir, 'combined_with_spanning.json')
        ]
        
        # If none of the common patterns match, check all files in the directory
        json_path = None
        for path in possible_paths:
            if os.path.exists(path):
                json_path = path
                break
        
        # If we still don't have a match, list the directory to help debug
        if not json_path:
            # List all files in the directory to help debugging
            if os.path.exists(json_dir):
                files_in_dir = [f for f in os.listdir(json_dir) if f.endswith('.json')]
                
                # Check for partial matches in the directory
                best_match = None
                for file in files_in_dir:
                    base_name = filename.split('_res_')[0]
                    if base_name in file and file.endswith('_res_combined_with_spanning.json'):
                        best_match = file
                        break
                
                if best_match:
                    json_path = os.path.join(json_dir, best_match)
                    print(f"Found best match for {filename}: {best_match}")
                else:
                    error_msg = f"Could not find JSON file for {filename}. Available files in directory: {files_in_dir}"
                    print(error_msg)
                    return jsonify({'success': False, 'error': error_msg}), 404
            else:
                return jsonify({'success': False, 'error': f"Directory {json_dir} does not exist"}), 404
            
        print(f"Found JSON file at: {json_path}")
            
        # Load current data
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                current_data = json.load(f)
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'Invalid JSON file: {str(e)}'}), 500
        
        # Track which items were edited
        edited_cells = []
        edited_texts = []
            
        # Update the data with changes
        if 'cells_with_text' in changes and changes['cells_with_text']:
            for change in changes['cells_with_text']:
                cell_id = change.get('cell_id')
                new_text = change.get('text')
                
                if cell_id is None or new_text is None:
                    continue
                    
                # Find and update the cell in the current data
                cells_updated = False
                if 'cells_with_text' in current_data:
                    for cell in current_data['cells_with_text']:
                        if cell['cell_id'] == cell_id:
                            # Check if the text actually changed
                            if cell.get('text', '') != new_text:
                                cell['text'] = new_text
                                cell['edited'] = True
                                edited_cells.append(cell_id)
                            cells_updated = True
                            break
                
                if not cells_updated:
                    print(f"Warning: Could not find cell_id {cell_id} in the JSON data")
                        
        if 'unassigned_text' in changes and changes['unassigned_text']:
            for change in changes['unassigned_text']:
                text_id = change.get('text_id')
                new_text = change.get('text')
                
                if text_id is None or new_text is None:
                    continue
                    
                # Find and update the text in the current data
                text_updated = False
                if 'unassigned_text' in current_data:
                    for text in current_data['unassigned_text']:
                        if text['text_id'] == text_id:
                            # Check if the text actually changed
                            if text.get('text', '') != new_text:
                                text['text'] = new_text
                                text['edited'] = True
                                edited_texts.append(text_id)
                            text_updated = True
                            break
                
                if not text_updated:
                    print(f"Warning: Could not find text_id {text_id} in the JSON data")
        
        # If no changes were made, still return success
        if not edited_cells and not edited_texts:
            return jsonify({'success': True, 'message': 'No changes needed'})
                        
        # Save the updated data
        try:
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(current_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            return jsonify({'success': False, 'error': f'Failed to write to JSON file: {str(e)}'}), 500
            
        print(f"Successfully saved changes to {json_path}")
            
        return jsonify({
            'success': True, 
            'edited_cells': edited_cells, 
            'edited_texts': edited_texts,
            'message': 'Changes saved successfully'
        })
        
    except Exception as e:
        print(f"Error in save_edits: {str(e)}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/save_results', methods=['POST'])
def save_results():
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'No data provided'}), 400
            
        document_name = data.get('document_name', 'Unnamed Document')
        original_image_path = data.get('original_image_path')
        output_image_path = data.get('output_image_path')
        json_data = data.get('json_data')
        filename = os.path.basename(output_image_path) if output_image_path else None
        
        # Validate required data
        if not all([original_image_path, output_image_path, json_data]):
            return jsonify({'error': 'Missing required data for saving'}), 400
            
        # Remove leading / from paths if present
        if original_image_path.startswith('/'):
            original_image_path = original_image_path[1:]
        if output_image_path.startswith('/'):
            output_image_path = output_image_path[1:]
            
        # Save to database
        document_id = db.save_document(
            document_name=document_name,
            filename=filename,
            original_image_path=original_image_path,
            output_image_path=output_image_path,
            json_data=json_data
        )
        
        # Return success response
        return jsonify({
            'success': True,
            'document_id': document_id,
            'message': f'Document "{document_name}" saved successfully'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_documents', methods=['GET'])
def get_documents():
    try:
        documents = db.get_all_documents()
        return jsonify({
            'success': True,
            'documents': documents
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/get_document/<document_id>', methods=['GET'])
def get_document(document_id):
    try:
        document = db.get_document(document_id)
        if not document:
            return jsonify({'error': 'Document not found'}), 404
            
        return jsonify({
            'success': True,
            'document': document
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/find_json/<prefix>', methods=['GET'])
def find_json(prefix):
    """
    Find JSON files in the merge and split directory that match a given prefix.
    This helps the client determine the correct filename for saving edits.
    """
    try:
        json_dir = os.path.join(OUTPUT_ROOT, 'merge and split')
        if not os.path.exists(json_dir):
            return jsonify({'success': False, 'error': f"Directory {json_dir} does not exist"}), 404
            
        # List all JSON files in the directory
        files = [f for f in os.listdir(json_dir) if f.endswith('.json')]
        
        # Find files that match the given prefix
        matching_files = [f for f in files if prefix in f]
        
        # If we have an exact match for the combined pattern, prioritize it
        combined_pattern = f"{prefix}_res_combined_with_spanning.json"
        if combined_pattern in files:
            best_match = combined_pattern
        elif matching_files:
            # Otherwise, return the first match
            best_match = matching_files[0]
        else:
            best_match = None
            
        return jsonify({
            'success': True,
            'files': files,
            'matching_files': matching_files,
            'best_match': best_match
        })
        
    except Exception as e:
        print(f"Error finding JSON files: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
