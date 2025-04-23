import cv2
import numpy as np
from PIL import Image
import os
import torch
import torch.nn as nn
from torchvision import transforms, models
from torch.nn import functional as F
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ImageQualityAssessor:
    def __init__(self, min_resolution=(640, 480), 
                 blur_threshold=50,  # Adjusted for iPhone camera
                 brightness_range=(0.2, 0.9),  # Adjusted for iPhone camera
                 aspect_ratio_tolerance=0.5):  # Increased to accept both portrait and landscape
        
        logger.info("Initializing ImageQualityAssessor...")
        self.min_resolution = min_resolution
        self.blur_threshold = blur_threshold
        self.brightness_range = brightness_range
        self.aspect_ratio_tolerance = aspect_ratio_tolerance
        
        # Initialize device (GPU if available)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"Using device: {self.device}")
        
        # Load NIMA model
        logger.info("Loading NIMA model...")
        self.model = self._load_nima_model()
        logger.info("NIMA model loaded successfully")
        
        # Define image preprocessing
        self.preprocess = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                               std=[0.229, 0.224, 0.225])
        ])
        
    def _load_nima_model(self):
        """Load NIMA model for image quality assessment."""
        try:
            # Load pre-trained ResNet50
            model = models.resnet50(weights=models.ResNet50_Weights.DEFAULT)
            
            # Modify the last layer for quality prediction
            num_features = model.fc.in_features
            model.fc = nn.Sequential(
                nn.Dropout(p=0.75),
                nn.Linear(num_features, 10),
                nn.Softmax(dim=1)
            )
            
            # Move model to device
            model = model.to(self.device)
            model.eval()
            
            return model
        except Exception as e:
            logger.error(f"Error loading NIMA model: {str(e)}")
            raise
    
    def _predict_quality_score(self, img):
        """Predict quality score using NIMA model."""
        try:
            # Convert image to RGB if it has alpha channel
            if img.mode == 'RGBA':
                img = img.convert('RGB')
            
            # Convert PIL image to tensor and preprocess
            img_tensor = self.preprocess(img).unsqueeze(0).to(self.device)
            
            with torch.no_grad():
                # Get predictions
                predictions = self.model(img_tensor)
                
                # Calculate mean score (1-10 scale)
                scores = torch.arange(1, 11, dtype=torch.float32).to(self.device)
                mean_score = torch.sum(predictions * scores, dim=1).item()
                
                # Calculate standard deviation
                std_score = torch.sqrt(torch.sum(predictions * (scores - mean_score) ** 2, dim=1)).item()
                
            return {
                "mean_score": mean_score,
                "std_score": std_score,
                "score_distribution": predictions.cpu().numpy()[0]
            }
        except Exception as e:
            logger.error(f"Error in quality prediction: {str(e)}")
            raise
    
    def assess_image(self, image_path):
        """Assess an image for quality and return results with a verdict."""
        logger.info(f"Assessing image: {image_path}")
        try:
            # Load image
            logger.info("Loading image...")
            cv_img = cv2.imread(image_path)
            if cv_img is None:
                logger.error(f"Could not load image at path: {image_path}")
                return {"status": "error", "message": "Could not load image"}
            
            pil_img = Image.open(image_path)
            logger.info(f"Image loaded successfully. Size: {pil_img.size}")
            
            # Run traditional quality checks
            logger.info("Running traditional quality checks...")
            results = {
                "resolution_check": self._check_resolution(pil_img),
                "blur_check": self._check_blur(cv_img),
                "brightness_check": self._check_brightness(cv_img),
                "aspect_ratio_check": self._check_aspect_ratio(pil_img),
            }
            
            # Run ML-based quality assessment
            logger.info("Running ML-based quality assessment...")
            ml_results = self._predict_quality_score(pil_img)
            results["ml_quality"] = {
                "pass": ml_results["mean_score"] >= 5.0,  # Consider scores >= 5 as acceptable
                "mean_score": ml_results["mean_score"],
                "std_score": ml_results["std_score"],
                "message": f"ML Quality Score: {ml_results['mean_score']:.2f} ± {ml_results['std_score']:.2f}"
            }
            
            # Overall verdict (pass if all checks pass)
            results["pass"] = all(check["pass"] for check in results.values() 
                                 if isinstance(check, dict) and "pass" in check)
            
            logger.info("Assessment completed successfully")
            return results
            
        except Exception as e:
            logger.error(f"Error during assessment: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    def _check_resolution(self, img):
        """Check if image resolution meets minimum requirements."""
        width, height = img.size
        min_width, min_height = self.min_resolution
        
        # Fix: Check if both dimensions are at least the minimum
        passes = width >= min_width and height >= min_height
        
        return {
            "pass": passes,
            "actual": (width, height),
            "required": self.min_resolution,
            "message": "Resolution OK" if passes else "Resolution too low"
        }
    
    def _check_blur(self, img):
        """Check image for blurriness using Laplacian variance."""
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        
        passes = laplacian_var >= self.blur_threshold
        
        return {
            "pass": passes,
            "value": laplacian_var,
            "threshold": self.blur_threshold,
            "message": "Image sharpness OK" if passes else "Image is too blurry"
        }
    
    def _check_brightness(self, img):
        """Check if image brightness is within acceptable range."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        brightness = hsv[:, :, 2].mean() / 255.0
        
        min_bright, max_bright = self.brightness_range
        passes = min_bright <= brightness <= max_bright
        
        return {
            "pass": passes,
            "value": brightness,
            "range": self.brightness_range,
            "message": "Brightness OK" if passes else 
                       "Image too dark" if brightness < min_bright else "Image too bright"
        }
    
    def _check_aspect_ratio(self, img):
        """Check if image aspect ratio is within normal range for iPhone photos."""
        width, height = img.size
        aspect = width / height
        
        # Accept both portrait (3:4) and landscape (4:3) orientations
        std_aspect_portrait = 3/4  # iPhone portrait mode
        std_aspect_landscape = 4/3  # iPhone landscape mode
        
        # Calculate deviation from both standard ratios
        deviation_portrait = abs(aspect - std_aspect_portrait) / std_aspect_portrait
        deviation_landscape = abs(aspect - std_aspect_landscape) / std_aspect_landscape
        
        # Pass if close to either standard ratio
        passes = (deviation_portrait <= self.aspect_ratio_tolerance or 
                 deviation_landscape <= self.aspect_ratio_tolerance)
        
        return {
            "pass": passes,
            "value": aspect,
            "deviation": min(deviation_portrait, deviation_landscape),
            "tolerance": self.aspect_ratio_tolerance,
            "message": "Aspect ratio OK" if passes else "Unusual aspect ratio detected",
            "orientation": "portrait" if deviation_portrait < deviation_landscape else "landscape"
        }

# Usage example
if __name__ == "__main__":
    logger.info("Starting image quality assessment...")
    assessor = ImageQualityAssessor()
    
    # Test on a sample image
    sample_path = "Input/IMG_5063.png"
    logger.info(f"Testing with image: {sample_path}")
    
    if os.path.exists(sample_path):
        logger.info("Image file exists")
        results = assessor.assess_image(sample_path)
        
        print("\nImage Quality Assessment Results:")
        print(f"Overall verdict: {'PASS' if results.get('pass', False) else 'FAIL'}")
        
        for check_name, result in results.items():
            if isinstance(result, dict) and "message" in result:
                status = "✓" if result.get("pass", False) else "✗"
                print(f"\n{status} {check_name}: {result['message']}")
                
                # Print additional details
                for key, value in result.items():
                    if key not in ["pass", "message"]:
                        print(f"  - {key}: {value}")
    else:
        logger.error(f"Sample image not found: {sample_path}")
        print(f"Sample image not found: {sample_path}")
