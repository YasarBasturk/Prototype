import os
from paddleocr import PPStructure, draw_structure_result, save_structure_res
from PIL import Image

def ai_processing(image_path):
    """
    Process the image using PaddleOCR structure analysis.
    
    Args:
        image_path (str): Path to the input image
        
    Returns:
        string: json_path - path to the output file
    """
    try:
        # Get the project root (Prototype directory)
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Create output directory for AI model results
        output_dir = os.path.join(project_root, 'output', 'ai-model')
        os.makedirs(output_dir, exist_ok=True)
        
        # Get base name for output files
        base_name = os.path.basename(image_path).split('.')[0]
        
        # Define output paths
        result_output_dir = os.path.join(output_dir, base_name)
        visualization_path = os.path.join(result_output_dir, f"{base_name}_structure.png")
        json_path = os.path.join(result_output_dir, 'res_0.json')
        
        print(f"Running AI model processing on {image_path}")
        print(f"Output directory: {result_output_dir}")
        
        # Initialize model
        table_engine = PPStructure(show_log=False)
        
        # Process the image
        result = table_engine(image_path)

        save_structure_res(result, output_dir, os.path.basename(image_path).split('.')[0])

        # Convert .txt file to .json file
        rename_txt_to_json(output_dir)
        
        # Draw the structure result and save the visualization
        image = Image.open(image_path).convert('RGB')
        font_path = '/System/Library/Fonts/Times.ttc'
        im_show = draw_structure_result(image, result, font_path=font_path)
        im_show = Image.fromarray(im_show)
        im_show.save(visualization_path)
        
        print(f"AI model processing completed. Results saved to: {output_dir}")
        
        return json_path
        
    except Exception as e:
        print(f"Error in AI model processing: {str(e)}")
        raise

def rename_txt_to_json(directory):
    # Walk through all directories and files
    for root, dirs, files in os.walk(directory):
        for file in files:
            # Check if file is res_0.txt
            if file == 'res_0.txt':
                txt_path = os.path.join(root, file)
                # Create new path with .json extension
                json_path = os.path.join(root, 'res_0.json')
                # Rename the file
                os.rename(txt_path, json_path)
                print(f"Renamed: {txt_path} -> {json_path}")
