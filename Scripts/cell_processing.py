from paddlex import create_model
import os

def run_cell_detection(input_path, output_dir="output"):
    """
    Run cell detection on an input image and save results
    
    Args:
        input_path (str): Path to the input image
        output_dir (str): Base directory for output
        
    Returns:
        string: json_path - path to the output file
    """
    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create the "cell detection" subdirectory inside output
    cell_detection_dir = os.path.join(output_dir, "cell detection")
    os.makedirs(cell_detection_dir, exist_ok=True)

    # Extract the base filename
    base_name = os.path.basename(input_path).split('.')[0]
    
    # Define expected output paths
    json_path = os.path.join(cell_detection_dir, f"{base_name}_res.json")

    print(f"JSON PATH: {json_path}")
    
    # Load model and run prediction
    try:
        print(f"Running cell detection on {input_path}")
        model = create_model(model_name="RT-DETR-L_wired_table_cell_det")
        output = model.predict(input_path, threshold=0.3, batch_size=1)

        for i, res in enumerate(output):
            res.print()  # Print the structured prediction output
            
            # Save visualization to the cell detection directory
            res.save_to_img(save_path=cell_detection_dir)  
            
            # Still try the original method as a backup, but save to cell detection directory
            try:
                res.save_to_json(save_path=cell_detection_dir)
                print(f"Also tried original save_to_json method to {cell_detection_dir}")
            except Exception as e:
                print(f"Original save_to_json failed: {e}")

        print(f"All cell detection results saved to: {os.path.abspath(cell_detection_dir)}")
        
        return json_path
        
    except Exception as e:
        print(f"Error during cell detection: {e}")
        return None
