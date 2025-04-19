from paddlex import create_model
import os
import json

def run_cell_detection(input_path, output_dir="output"):
    """
    Run cell detection on an input image and save results
    
    Args:
        input_path (str): Path to the input image
        output_dir (str): Base directory for output
        
    Returns:
        tuple: (cell_json_path, visualization_path) - paths to the JSON result and visualization
    """
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create the "cell detection" subdirectory inside output
    cell_detection_dir = os.path.join(output_dir, "cell detection")
    os.makedirs(cell_detection_dir, exist_ok=True)

    # Extract the base filename
    base_name = os.path.basename(input_path).split('.')[0]
    
    # Define expected output paths
    cell_json_path = os.path.join(cell_detection_dir, f"{base_name}_cells.json")
    visualization_path = os.path.join(cell_detection_dir, f"{base_name}.jpg")

    # Load model and run prediction
    try:
        print(f"Running cell detection on {input_path}")
        model = create_model(model_name="RT-DETR-L_wired_table_cell_det")
        output = model.predict(input_path, threshold=0.3, batch_size=1)

        for i, res in enumerate(output):
            res.print()  # Print the structured prediction output
            
            # Save visualization to the cell detection directory
            res.save_to_img(save_path=cell_detection_dir)  
            
            # Save JSON using standard Python methods - more reliable
            try:
                # Create a JSON file path in the cell detection directory
                json_path = cell_json_path
                
                # Write the data to a JSON file
                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(res.res, f, indent=2)
                
                print(f"Successfully saved cell detection JSON data to: {json_path}")
            except Exception as e:
                print(f"Error saving cell detection JSON data: {e}")
            
            # Still try the original method as a backup, but save to cell detection directory
            try:
                res.save_to_json(save_path=cell_detection_dir)
                print(f"Also tried original save_to_json method to {cell_detection_dir}")
            except Exception as e:
                print(f"Original save_to_json failed: {e}")

        print(f"All cell detection results saved to: {os.path.abspath(cell_detection_dir)}")
        
        # Check for actual output files with any naming convention
        if not os.path.exists(cell_json_path):
            # Look for any JSON file in the directory
            json_files = [f for f in os.listdir(cell_detection_dir) if f.endswith('.json')]
            if json_files:
                cell_json_path = os.path.join(cell_detection_dir, json_files[0])
                print(f"Using alternate JSON file: {cell_json_path}")
        
        # Look for visualization file
        image_files = [f for f in os.listdir(cell_detection_dir) if f.endswith(('.jpg', '.png'))]
        if image_files:
            visualization_path = os.path.join(cell_detection_dir, image_files[0])
            print(f"Using visualization file: {visualization_path}")
        
        return cell_json_path, visualization_path
        
    except Exception as e:
        print(f"Error during cell detection: {e}")
        return None, None

# This block only runs when the script is directly executed
if __name__ == "__main__":
    run_cell_detection("./input/IMG_5063.png")