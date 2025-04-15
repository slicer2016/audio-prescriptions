import os
import time
import requests
import pandas as pd
from fuzzywuzzy import fuzz
import json
import re

class PrescriptionAnalyzer:
    def __init__(self, subscription_key, endpoint):
        self.subscription_key = subscription_key
        self.endpoint = endpoint.rstrip('/')
        self.text_analysis_url = f"{self.endpoint}/computervision/imageanalysis:analyze?api-version=2024-02-01&features=read"
        
        self.medicines_db = pd.read_csv('medicines.csv')
        
        self.dosage_patterns = [
            r'\d+\s*mg',
            r'\d+\s*times?\s*(?:daily|a day)',
            r'(?:once|twice|thrice)\s*daily',
            r'(?:OD|BD|TDS|QID)',
            r'(?:morning|afternoon|evening|night)',
            r'\d+\-\d+\-\d+'
        ]

        self.non_medicine_terms = {
            'name', 'age', 'sex', 'date', 'address', 'doctor', 'hospital', 'clinic',
            'prescription', 'sig', 'signature', 'lic', 'license', 'no', 'ptr', 'rx',
            'patient', 'diagnosis', 'weight', 'height', 'bp', 'temperature'
        }

    def _is_likely_medicine_line(self, text):
        """
        Check if a line of text is likely to contain a medicine name
        Returns: bool
        """
        try:
            # Convert to lowercase for comparison
            text_lower = text.lower()
            
            # Check if line contains common non-medicine terms
            words = set(text_lower.split())
            if words.intersection(self.non_medicine_terms):
                return False
                
            # Check for patterns that typically indicate medicine lines
            medicine_indicators = [
                r'\d+\s*mg',           # Dosage in mg
                r'\d+\s*mcg',          # Dosage in mcg
                r'\d+\s*ml',           # Dosage in ml
                r'tab(?:let)?s?',      # Tablets
                r'cap(?:sule)?s?',     # Capsules
                r'#\s*\d+',            # Quantity indicator
                r'\d+\s*times daily',   # Dosage frequency
            ]
            
            for pattern in medicine_indicators:
                if re.search(pattern, text_lower):
                    return True
                    
            return False
        except Exception as e:
            print(f"Warning: Error in _is_likely_medicine_line: {str(e)}")
            return False

    def _find_medicine_match(self, text):
        """
        Find best matching medicine from database with improved matching logic
        """
        try:
            # Early return if line is unlikely to contain medicine
            if not self._is_likely_medicine_line(text):
                return None
                
            best_match = None
            best_ratio = 0
            debug_matches = []
            
            # Clean and normalize the input text
            text = text.lower().strip()
            
            # Create lists of medicine names and generic names
            medicine_names = self.medicines_db['Medicine Name'].str.lower()
            generic_names = self.medicines_db['Generic Name'].str.lower()
            
            # Try different fuzzy matching approaches
            for idx, (med_name, gen_name) in enumerate(zip(medicine_names, generic_names)):
                # Calculate different match ratios
                ratio1 = fuzz.ratio(text, str(med_name))
                ratio2 = fuzz.partial_ratio(text, str(med_name))
                ratio3 = fuzz.ratio(text, str(gen_name))
                ratio4 = fuzz.partial_ratio(text, str(gen_name))
                
                # Weight exact matches more heavily than partial matches
                weighted_ratio = max(
                    ratio1 * 1.0,  # Full weight for exact medicine name match
                    ratio2 * 0.8,  # Reduced weight for partial medicine name match
                    ratio3 * 1.0,  # Full weight for exact generic name match
                    ratio4 * 0.8   # Reduced weight for partial generic name match
                )
                
                if weighted_ratio > best_ratio:
                    best_ratio = weighted_ratio
                    best_match = self.medicines_db.iloc[idx]['Medicine Name']
                    
                    # Store debug information
                    debug_matches.append({
                        'input_text': text,
                        'medicine_name': med_name,
                        'generic_name': gen_name,
                        'weighted_ratio': weighted_ratio,
                        'exact_ratio': ratio1,
                        'partial_ratio': ratio2
                    })
            
            # Print debug information for top matches
            if debug_matches:
                print("\nDebug: Top medicine matches:")
                for match in sorted(debug_matches, key=lambda x: x['weighted_ratio'], reverse=True)[:1]:
                    print(f"Input: '{match['input_text']}'")
                    print(f"Medicine: '{match['medicine_name']}'")
                    print(f"Generic: '{match['generic_name']}'")
                    print(f"Weighted Match: {match['weighted_ratio']:.2f}%")
                    print(f"Exact Match: {match['exact_ratio']:.2f}%")
                    print(f"Partial Match: {match['partial_ratio']:.2f}%")
                    print("-" * 40)
            
            # Require a higher threshold for matches
            if best_match and best_ratio > 75:  # Increased threshold
                return (best_match, best_ratio / 100)
            return None
        
        except Exception as e:
            print(f"Warning: Error in _find_medicine_match: {str(e)}")
            return None

    def analyze_prescription(self, image_path):
        """Analyze prescription image and return structured data"""
        print(f"Starting prescription analysis for: {image_path}")
        
        try:
            # Check if file exists
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")
            
            # Read the image file
            with open(image_path, 'rb') as image_file:
                image_data = image_file.read()
            
            # Define headers here
            headers = {
                'Ocp-Apim-Subscription-Key': self.subscription_key,
                'Content-Type': 'application/octet-stream'
            }
            
            print("Submitting image to Azure Computer Vision API...")
            response = requests.post(
                self.text_analysis_url,
                headers=headers,
                data=image_data
            )
            
            print(f"Request URL: {self.text_analysis_url}")
            print(f"Response Status Code: {response.status_code}")
            print(f"Response Headers: {dict(response.headers)}")
            print(f"Response Content: {response.text}")
            
            response.raise_for_status()
            result = response.json()
            return self._process_read_result(result)
                
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response'):
                print(f"Full error response: {e.response.text}")
            raise Exception(f"API request error: {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing image: {str(e)}")

    def _process_read_result(self, result):
        """Process the OCR results and extract medicines with dosages"""
        text_results = []
        
        # Extract text from the results
        try:
            if 'readResult' in result:
                for block in result['readResult'].get('blocks', []):
                    for line in block.get('lines', []):
                        text = line.get('text', '').strip()
                        # Get average confidence from words
                        confidence = sum(word.get('confidence', 0) for word in line.get('words', [])) / len(line.get('words', [1]))
                        text_results.append({
                            'text': text,
                            'confidence': confidence
                        })

        except KeyError as e:
            print(f"Warning: Unexpected response format: {str(e)}")
            print(f"Full response: {json.dumps(result, indent=2)}")

        print(f"\nFound {len(text_results)} lines of text:")
        for line in text_results:
            print(f"Text: {line['text']}, Confidence: {line['confidence']:.2f}")
        
        # Extract medicines and dosages
        findings = []
        
        for i, line in enumerate(text_results):
            text = line['text'].strip()
            
            # Look for medicine names
            medicine_match = self._find_medicine_match(text)
            if medicine_match:
                medicine_name, medicine_confidence = medicine_match
                
                # Look for dosage in current and next few lines
                next_lines = text_results[i:i+3]
                dosage_info = self._find_dosage(next_lines)
                
                # Calculate overall confidence
                overall_confidence = self._calculate_overall_confidence(
                    medicine_confidence,
                    line['confidence'],
                    dosage_info['confidence'] if dosage_info else 0
                )
                
                # Only include high-confidence matches
                if overall_confidence > 0.30:  # Filter for high confidence matches
                    findings.append({
                        'medicine': medicine_name,
                        'dosage': dosage_info['dosage'] if dosage_info else 'Not found',
                        'original_text': text,
                        'confidence': {
                            'medicine_match': medicine_confidence,
                            'text_recognition': line['confidence'],
                            'dosage_recognition': dosage_info['confidence'] if dosage_info else 0,
                            'overall': overall_confidence
                        }
                    })
        
        print(f"\nFound {len(findings)} high-confidence medicines")
        return findings
    
    def _find_dosage(self, lines):
        """Extract dosage information from text lines"""
        combined_text = ' '.join([line['text'] for line in lines])
        
        for pattern in self.dosage_patterns:
            match = re.search(pattern, combined_text, re.IGNORECASE)
            if match:
                return {
                    'dosage': match.group(),
                    'confidence': 1.0  # Default confidence for pattern matching
                }
        return None

    def _calculate_overall_confidence(self, medicine_conf, text_conf, dosage_conf):
        """Calculate overall confidence score with adjusted weights"""
        weights = {
            'medicine': 0.8,  # Increased weight for medicine match
            'text': 0.1,     # Moderate weight for text recognition
            'dosage': 0.1    # Lower weight for dosage match
        }
        return (medicine_conf * weights['medicine'] +
                text_conf * weights['text'] +
                dosage_conf * weights['dosage'])

def format_results(findings):
    """Format findings for display"""
    if not findings:
        return "No medicines found in the prescription."
    
    formatted = []
    for finding in findings:
        formatted.append(
            f"\nMedicine: {finding['medicine']}\n"
            f"Dosage: {finding['dosage']}\n"
            f"Original Text: {finding['original_text']}\n"
            f"Confidence Scores:\n"
            f"  - Medicine Match: {finding['confidence']['medicine_match']:.2%}\n"
            f"  - Text Recognition: {finding['confidence']['text_recognition']:.2%}\n"
            f"  - Dosage Recognition: {finding['confidence']['dosage_recognition']:.2%}\n"
            f"{'-' * 50}"
        )
    return "\n".join(formatted)

def main():
    subscription_key = "EzLX96tItVCB36j2hHvwLgbDvfRQiggJsViGvczQar1d2Ca8bshfJQQJ99AKACYeBjFXJ3w3AAAFACOGkmWS"
    endpoint = "https://vinaypoc.cognitiveservices.azure.com/"
    
    analyzer = PrescriptionAnalyzer(subscription_key, endpoint)
    
    image_path = "prescription5.jpeg"
    
    try:
        findings = analyzer.analyze_prescription(image_path)
        print("\nAnalysis Results:")
        print(format_results(findings))
        
        with open('prescription_analysis.json', 'w') as f:
            json.dump(findings, f, indent=4)
            print("\nResults saved to prescription_analysis.json")
            
    except Exception as e:
        print(f"Error analyzing prescription: {str(e)}")

if __name__ == "__main__":
    main()