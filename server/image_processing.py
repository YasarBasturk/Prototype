import os
from image_preprocess import preprocess_image

def image_processing(image_path):
    """
    Process the uploaded image using preprocessing steps.
    
    Args:
        image_path (str): Path to the uploaded image
        
    Returns:
        str: Path to the processed image
    """
    try:
        # Create output directory for preprocessed images if it doesn't exist
        output_dir = os.path.join(os.path.dirname(os.path.dirname(image_path)), 'output', 'preprocessed')
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output path for processed image
        filename = os.path.basename(image_path)
        output_path = os.path.join(output_dir, f'processed_{filename}')
        
        # Process the image using functions from image_preprocess.py
        processed_image = preprocess_image(image_path, output_path)
        
        return output_path
        
    except Exception as e:
        print(f"Error in image processing: {str(e)}")
        raise
