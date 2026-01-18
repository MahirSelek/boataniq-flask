"""
Boat AI Analyzer for BoatanIQ App
Uses Google Gemini for multimodal boat recognition and analysis
"""

import google.generativeai as genai
import os
from PIL import Image
import json
from typing import Dict, Optional
import base64
from io import BytesIO

class BoatAIAnalyzer:
    def __init__(self, api_key: str = None):
        """
        Initialize the AI analyzer
        
        Args:
            api_key: Google Gemini API key. If None, will try to get from environment
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY')
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set GEMINI_API_KEY environment variable or pass api_key parameter.")
        
        # Configure Gemini
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Define the analysis prompt with validation
        self.analysis_prompt = """
        You are an expert marine analyst. Analyze this boat image and provide detailed information about the boat.

        CRITICAL VALIDATION: Before analyzing, you MUST validate the image:
        1. Is this image actually a boat? (not a car, plane, building, or other object)
        2. Is the image clear and not too blurry?
        3. Is the boat clearly visible and from a reasonable angle?
        4. Can you see enough detail to identify the boat?
        
        If the image is NOT suitable (not a boat, too blurry, wrong angle, unclear), set "is_valid_image" to false and "rejection_reason" with a clear explanation. Do NOT proceed with analysis if the image is unsuitable.

        Please respond with a JSON object containing the following information:

        {
            "is_valid_image": true,
            "rejection_reason": null,
            "image_quality_assessment": "Assessment of image quality (Clear, Acceptable, Blurry, Poor)",
            "boat_type": "Type of boat (e.g., Sailing Yacht, Motorboat, Cruiser, etc.)",
            "brand": "Brand name if identifiable (e.g., Bavaria, Beneteau, etc.)",
            "model": "Specific model if identifiable",
            "estimated_year": "Estimated year of manufacture (range if uncertain)",
            "length_estimate": "Estimated length in meters",
            "width_estimate": "Estimated width in meters",
            "hull_material": "Hull material if identifiable (e.g., Fiberglass, Steel, etc.)",
            "engine_type": "Engine type if visible (e.g., Inboard, Outboard, Sail)",
            "key_features": ["List of key visible features"],
            "condition": "Overall condition assessment",
            "price_estimate": "Estimated price range if possible",
            "confidence": "Confidence level (0-100) of the analysis. MUST be honest - if image is unclear or not a boat, set confidence below 30",
            "detailed_description": "Detailed description of what you see in the image"
        }

        Guidelines:
        - FIRST: Validate if this is actually a boat image. If not, set is_valid_image=false and provide rejection_reason
        - If image is blurry, unclear, or from a bad angle, set is_valid_image=false with appropriate rejection_reason
        - Be honest about confidence - if uncertain, set confidence below 50. If very uncertain or image is poor quality, set below 30
        - Please be as specific as possible and only include information you can actually see or reasonably infer from the image.
        - If you're uncertain about any detail, indicate that in your response.
        - REJECTION REASONS should be clear and helpful: "Image is too blurry", "This does not appear to be a boat", "Boat is not clearly visible", "Image angle is too extreme", etc.
        """
    
    def analyze_boat_image(self, image_path: str) -> Dict:
        """
        Analyze a boat image and extract features
        
        Args:
            image_path: Path to the boat image
            
        Returns:
            Dictionary containing analyzed boat features
        """
        try:
            # Load and process image
            image = Image.open(image_path)
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Generate analysis
            response = self.model.generate_content([self.analysis_prompt, image])
            
            # Parse response
            analysis_text = response.text.strip()
            
            # Try to extract JSON from response
            try:
                # Look for JSON in the response
                start_idx = analysis_text.find('{')
                end_idx = analysis_text.rfind('}') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = analysis_text[start_idx:end_idx]
                    analysis_result = json.loads(json_str)
                else:
                    # Fallback: create structured response from text
                    analysis_result = self._parse_text_response(analysis_text)
                
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                analysis_result = self._parse_text_response(analysis_text)
            
            # Add metadata
            analysis_result['image_path'] = image_path
            analysis_result['raw_response'] = analysis_text
            analysis_result['model_used'] = 'gemini-1.5-flash'
            analysis_result['analyzer_type'] = 'regular_gemini'
            
            # Handle validation fields (default to valid if not present)
            if 'is_valid_image' not in analysis_result:
                analysis_result['is_valid_image'] = True
            if 'rejection_reason' not in analysis_result:
                analysis_result['rejection_reason'] = None
            
            # Check confidence threshold
            confidence = analysis_result.get('confidence', 0)
            if isinstance(confidence, str):
                try:
                    confidence = float(confidence)
                except:
                    confidence = 0
            
            # If confidence is very low or image is invalid, mark as rejected
            if not analysis_result.get('is_valid_image', True) or confidence < 30:
                if not analysis_result.get('rejection_reason'):
                    if confidence < 30:
                        analysis_result['rejection_reason'] = 'AI confidence too low - image may be unclear, not a boat, or from a poor angle'
                    else:
                        analysis_result['rejection_reason'] = 'Image validation failed'
            
            return analysis_result
            
        except Exception as e:
            return {
                'error': f"Error analyzing image: {str(e)}",
                'image_path': image_path,
                'confidence': 0
            }
    
    def analyze_boat_image_from_bytes(self, image_bytes: bytes) -> Dict:
        """
        Analyze a boat image from bytes (for web uploads)
        
        Args:
            image_bytes: Image data as bytes
            
        Returns:
            Dictionary containing analyzed boat features
        """
        try:
            # Convert bytes to PIL Image
            image = Image.open(BytesIO(image_bytes))
            
            # Convert to RGB if necessary
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Generate analysis
            response = self.model.generate_content([self.analysis_prompt, image])
            
            # Parse response
            analysis_text = response.text.strip()
            
            # Try to extract JSON from response
            try:
                # Look for JSON in the response
                start_idx = analysis_text.find('{')
                end_idx = analysis_text.rfind('}') + 1
                
                if start_idx != -1 and end_idx != -1:
                    json_str = analysis_text[start_idx:end_idx]
                    analysis_result = json.loads(json_str)
                else:
                    # Fallback: create structured response from text
                    analysis_result = self._parse_text_response(analysis_text)
                
            except json.JSONDecodeError:
                # Fallback parsing if JSON is malformed
                analysis_result = self._parse_text_response(analysis_text)
            
            # Add metadata
            analysis_result['raw_response'] = analysis_text
            analysis_result['model_used'] = 'gemini-1.5-flash'
            analysis_result['analyzer_type'] = 'regular_gemini'
            
            # Handle validation fields (default to valid if not present)
            if 'is_valid_image' not in analysis_result:
                analysis_result['is_valid_image'] = True
            if 'rejection_reason' not in analysis_result:
                analysis_result['rejection_reason'] = None
            
            # Check confidence threshold
            confidence = analysis_result.get('confidence', 0)
            if isinstance(confidence, str):
                try:
                    confidence = float(confidence)
                except:
                    confidence = 0
            
            # If confidence is very low or image is invalid, mark as rejected
            if not analysis_result.get('is_valid_image', True) or confidence < 30:
                if not analysis_result.get('rejection_reason'):
                    if confidence < 30:
                        analysis_result['rejection_reason'] = 'AI confidence too low - image may be unclear, not a boat, or from a poor angle'
                    else:
                        analysis_result['rejection_reason'] = 'Image validation failed'
            
            return analysis_result
            
        except Exception as e:
            return {
                'error': f"Error analyzing image: {str(e)}",
                'confidence': 0
            }
    
    def _parse_text_response(self, text: str) -> Dict:
        """
        Parse text response when JSON parsing fails
        
        Args:
            text: Raw response text
            
        Returns:
            Structured dictionary
        """
        result = {
            'boat_type': 'Unknown',
            'brand': 'Unknown',
            'model': 'Unknown',
            'estimated_year': 'Unknown',
            'length_estimate': 'Unknown',
            'width_estimate': 'Unknown',
            'hull_material': 'Unknown',
            'engine_type': 'Unknown',
            'key_features': [],
            'condition': 'Unknown',
            'price_estimate': 'Unknown',
            'confidence': 50,
            'detailed_description': text
        }
        
        text_lower = text.lower()
        
        # Extract boat type
        boat_types = ['sailing yacht', 'motorboat', 'cruiser', 'speedboat', 'fishing boat', 'catamaran']
        for boat_type in boat_types:
            if boat_type in text_lower:
                result['boat_type'] = boat_type.title()
                break
        
        # Extract brand
        brands = ['bavaria', 'beneteau', 'jeanneau', 'princess', 'sunseeker', 'azimut', 'ferretti']
        for brand in brands:
            if brand in text_lower:
                result['brand'] = brand.title()
                break
        
        # Extract year
        import re
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            result['estimated_year'] = year_match.group()
        
        return result
    
    def get_analysis_summary(self, analysis_result: Dict) -> str:
        """
        Generate a human-readable summary of the analysis
        
        Args:
            analysis_result: Result from analyze_boat_image
            
        Returns:
            Formatted summary string
        """
        if 'error' in analysis_result:
            return f"Analysis Error: {analysis_result['error']}"
        
        summary_parts = []
        
        # Basic info
        if analysis_result.get('boat_type') != 'Unknown':
            summary_parts.append(f"**Boat Type:** {analysis_result['boat_type']}")
        
        if analysis_result.get('brand') != 'Unknown':
            summary_parts.append(f"**Brand:** {analysis_result['brand']}")
        
        if analysis_result.get('model') != 'Unknown':
            summary_parts.append(f"**Model:** {analysis_result['model']}")
        
        if analysis_result.get('estimated_year') != 'Unknown':
            summary_parts.append(f"**Estimated Year:** {analysis_result['estimated_year']}")
        
        # Dimensions
        if analysis_result.get('length_estimate') != 'Unknown':
            summary_parts.append(f"**Estimated Length:** {analysis_result['length_estimate']}")
        
        if analysis_result.get('width_estimate') != 'Unknown':
            summary_parts.append(f"**Estimated Width:** {analysis_result['width_estimate']}")
        
        # Features
        if analysis_result.get('key_features'):
            features = analysis_result['key_features']
            if isinstance(features, list) and features:
                summary_parts.append(f"**Key Features:** {', '.join(features)}")
        
        # Condition and price
        if analysis_result.get('condition') != 'Unknown':
            summary_parts.append(f"**Condition:** {analysis_result['condition']}")
        
        if analysis_result.get('price_estimate') != 'Unknown':
            summary_parts.append(f"**Price Estimate:** {analysis_result['price_estimate']}")
        
        # Confidence
        confidence = analysis_result.get('confidence', 0)
        summary_parts.append(f"**Analysis Confidence:** {confidence}%")
        
        # Detailed description
        if analysis_result.get('detailed_description'):
            summary_parts.append(f"\n**Detailed Analysis:**\n{analysis_result['detailed_description']}")
        
        return '\n'.join(summary_parts)
