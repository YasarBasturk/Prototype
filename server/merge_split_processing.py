import os
from Scripts.merge_split import process_document

def merge_split_processing(cell_json_path, ocr_json_path, preprocessed_image_path):
    """
    Process the cell detection and OCR results to merge and handle split text.
    
    Args:
        cell_json_path (str): Path to the JSON file from cell detection (_res.json)
        ocr_json_path (str): Path to the JSON file from OCR/AI model
        preprocessed_image_path (str): Path to the preprocessed image for visualization
        
    Returns:
        tuple: (merged_json_path, visualization_path) - paths to the output files
    """
    try:
        # Verify all input files exist
        for file_path in [cell_json_path, ocr_json_path, preprocessed_image_path]:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Required input file not found: {file_path}")

        # Verify the cell detection JSON is the _res.json file
        if not cell_json_path.endswith('_res.json'):
            # Try to find the correct file
            dir_path = os.path.dirname(cell_json_path)
            base_name = os.path.basename(cell_json_path).split('_')[0]
            correct_path = os.path.join(dir_path, f"{base_name}_res.json")
            
            if os.path.exists(correct_path):
                print(f"Warning: Switching to correct cell detection JSON file: {correct_path}")
                cell_json_path = correct_path
            else:
                raise FileNotFoundError(f"Could not find cell detection _res.json file for {base_name}")

        # Get the project root (Prototype directory)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Create output directory for merge and split results
        output_dir = os.path.join(project_root, 'output', 'merge and split')
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"Starting merge and split processing:")
        print(f"  Project Root: {project_root}")
        print(f"  Cell Detection JSON: {cell_json_path}")
        print(f"  OCR/AI Model JSON: {ocr_json_path}")
        print(f"  Preprocessed Image: {preprocessed_image_path}")
        print(f"  Output Directory: {output_dir}")
        
        # Process the document using merge_split functionality
        merged_data = process_document(
            cell_json_path=cell_json_path,
            ocr_json_path=ocr_json_path,
            output_dir=output_dir,
            image_path=preprocessed_image_path,  # Use preprocessed image for visualization
            overlap_threshold=0.5,  # Threshold for text-cell overlap
            min_overlap_for_spanning=0.1  # Threshold for identifying spanning text
        )
        
        if merged_data and 'output_paths' in merged_data:
            print(f"Successfully processed merge and split:")
            print(f"  JSON output: {merged_data['output_paths']['json']}")
            print(f"  Visualization: {merged_data['output_paths']['visualization']}")
            return (
                merged_data['output_paths']['json'],
                merged_data['output_paths']['visualization']
            )
        else:
            print("Error: Merge and split processing did not return expected output paths")
            return None, None
            
    except Exception as e:
        print(f"Error in merge and split processing: {str(e)}")
        raise 