"""
boataniQ App - Main Flask Application
A boat recognition and analysis application using AI and database matching
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_from_directory
from flask_cors import CORS
import os
import uuid
import pandas as pd
import json
import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

from boat_database import BoatDatabase
from boat_ai_analyzer import BoatAIAnalyzer
from boat_vertex_ai_analyzer import BoatVertexAIAnalyzer
from boat_location_analyzer import BoatLocationAnalyzer
from image_preprocessor import ImagePreprocessor
from financial_indices_fetcher import FinancialIndicesFetcher
from boat_market_analyzer import BoatMarketAnalyzer

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'your-secret-key-here')
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Enable CORS
CORS(app)

# Initialize components
boat_db = None
ai_analyzer = None
location_analyzer = None
image_preprocessor = ImagePreprocessor()
financial_fetcher = FinancialIndicesFetcher()
boat_market_analyzer = None

# Analysis history storage
HISTORY_FILE = 'analysis_history.json'

def load_analysis_history():
    """Load analysis history from JSON file"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading history: {e}")
            return []
    return []

def save_analysis_history(history):
    """Save analysis history to JSON file"""
    try:
        with open(HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2, default=str)
    except Exception as e:
        print(f"Error saving history: {e}")

def add_analysis_to_history(analysis_data):
    """Add new analysis to history"""
    history = load_analysis_history()
    
    # Create history entry
    history_entry = {
        'id': str(uuid.uuid4()),
        'timestamp': datetime.datetime.now().isoformat(),
        'boat_type': analysis_data.get('boat_type', 'Unknown'),
        'brand': analysis_data.get('brand', 'Unknown'),
        'model': analysis_data.get('model', 'Unknown'),
        'confidence': analysis_data.get('confidence', 0),
        'image_name': analysis_data.get('image_name', 'Unknown'),
        'summary': analysis_data.get('summary', ''),
        'analysis': analysis_data
    }
    
    # Add to beginning of history (most recent first)
    history.insert(0, history_entry)
    
    # Keep only last 50 analyses
    if len(history) > 50:
        history = history[:50]
    
    save_analysis_history(history)
    return history_entry

def initialize_app():
    """Initialize the application components"""
    global boat_db, ai_analyzer, location_analyzer, boat_market_analyzer
    
    try:
        # Initialize database
        csv_path = 'all_boats_data.csv'
        json_dir = 'json_boat24' if os.path.exists('json_boat24') else None  # Make JSON dir optional
        
        print(f"🔍 [INIT] Checking for database file: {csv_path}")
        print(f"   CSV exists: {os.path.exists(csv_path)}")
        if csv_path and os.path.exists(csv_path):
            try:
                boat_db = BoatDatabase(csv_path, json_dir)
                if boat_db and boat_db.boats_df is not None:
                    print(f"✅ Database initialized with {len(boat_db.boats_df)} boats")
                else:
                    print(f"❌ Database initialized but boats_df is None")
                    boat_db = None
            except Exception as db_error:
                print(f"❌ Database initialization failed: {db_error}")
                import traceback
                traceback.print_exc()
                boat_db = None
        else:
            print(f"❌ Warning: CSV file {csv_path} not found at current directory: {os.getcwd()}")
            print(f"   Files in current directory: {os.listdir('.')[:10]}")
            boat_db = None
        
        # Initialize AI analyzer - try Vertex AI first, then fallback to regular Gemini
        ai_analyzer = None
        
        # Try Vertex AI first (preferred)
        try:
            # Try to get credentials from environment variable (for deployment)
            gcp_credentials_json = os.getenv('GCP_CREDENTIALS_JSON')
            credentials_path = os.getenv('GCP_CREDENTIALS_PATH', 'static-chiller-472906-f3-4ee4a099f2f1.json')
            
            print(f"🔍 [INIT] Checking for GCP credentials...")
            print(f"   GCP_CREDENTIALS_JSON exists: {bool(gcp_credentials_json)}")
            print(f"   Credentials path exists: {os.path.exists(credentials_path) if credentials_path else False}")
            
            if gcp_credentials_json:
                # Clean the JSON string (remove any extra whitespace/newlines)
                gcp_credentials_json = gcp_credentials_json.strip()
                # Try to parse it to validate
                try:
                    import json
                    json.loads(gcp_credentials_json)  # Validate JSON
                    # Use credentials from environment variable (JSON string)
                    ai_analyzer = BoatVertexAIAnalyzer(credentials_json=gcp_credentials_json)
                    print("✅ Vertex AI analyzer initialized successfully from environment variable (Gemini Flash 2.0)")
                except json.JSONDecodeError as je:
                    print(f"❌ [INIT] Invalid JSON in GCP_CREDENTIALS_JSON: {je}")
                    print("   Trying file path...")
                    if os.path.exists(credentials_path):
                        ai_analyzer = BoatVertexAIAnalyzer(credentials_path=credentials_path)
                        print("✅ Vertex AI analyzer initialized successfully from file (Gemini Flash 2.0)")
                except Exception as ve:
                    print(f"❌ [INIT] Vertex AI initialization error: {ve}")
                    import traceback
                    traceback.print_exc()
            elif os.path.exists(credentials_path):
                # Use credentials from file (local development)
                ai_analyzer = BoatVertexAIAnalyzer(credentials_path=credentials_path)
                print("✅ Vertex AI analyzer initialized successfully from file (Gemini Flash 2.0)")
            else:
                print("⚠️  Vertex AI credentials not found, trying regular Gemini...")
        except Exception as e:
            print(f"⚠️  Vertex AI initialization failed: {e}")
            import traceback
            traceback.print_exc()
            print("   Trying regular Gemini API...")
        
        # Fallback to regular Gemini API
        if ai_analyzer is None:
            api_key = os.getenv('GEMINI_API_KEY')
            if api_key:
                try:
                    ai_analyzer = BoatAIAnalyzer(api_key)
                    print("✅ Regular Gemini analyzer initialized successfully")
                except Exception as e:
                    print(f"❌ Regular Gemini initialization failed: {e}")
                    ai_analyzer = None
            else:
                print("⚠️  GEMINI_API_KEY not found in environment variables")
                ai_analyzer = None
        
        # Initialize Location analyzer
        try:
            location_analyzer = BoatLocationAnalyzer()
            print("✅ Location analyzer initialized successfully")
        except Exception as e:
            print(f"❌ Location analyzer initialization failed: {e}")
            location_analyzer = None
        
        # Initialize Boat Market Analyzer
        boat_market_analyzer = None
        try:
            if boat_db and boat_db.boats_df is not None and len(boat_db.boats_df) > 0:
                boat_market_analyzer = BoatMarketAnalyzer(boat_db.boats_df)
                print(f"✅ Boat market analyzer initialized successfully with {len(boat_db.boats_df)} boats")
            else:
                print("⚠️  Boat market analyzer not initialized: No boat data available")
                boat_market_analyzer = None
        except Exception as e:
            print(f"❌ Boat market analyzer initialization failed: {e}")
            import traceback
            traceback.print_exc()
            boat_market_analyzer = None
            
    except Exception as e:
        print(f"Error initializing app: {e}")

# Create upload directory
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def clean_boat_data_for_json(boats):
    """Clean NaN values from boat data for JSON serialization"""
    cleaned_boats = []
    for boat in boats:
        cleaned_boat = {}
        for key, value in boat.items():
            if pd.isna(value) or value is None or str(value).lower() == 'nan':
                cleaned_boat[key] = None
            else:
                cleaned_boat[key] = value
        cleaned_boats.append(cleaned_boat)
    return cleaned_boats

def clean_single_boat_data(boat_data):
    """Clean a single boat data dictionary for JSON serialization"""
    if not boat_data:
        return None
    
    cleaned_boat = {}
    for key, value in boat_data.items():
        if pd.isna(value) or value is None or str(value).lower() == 'nan':
            cleaned_boat[key] = None
        else:
            cleaned_boat[key] = value
    return cleaned_boat

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    """Serve static files"""
    return send_from_directory('static', filename)

@app.route('/map')
def map_page():
    """Interactive map page"""
    return render_template('map.html')

@app.route('/data-insights')
def data_insights():
    """Data insights dashboard page"""
    return render_template('data_insights.html')

@app.route('/investment-comparison')
def investment_comparison():
    """Investment comparison page - boats vs financial indices"""
    return render_template('investment_comparison.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and analysis"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            # Generate unique filename
            filename = secure_filename(file.filename)
            unique_filename = f"{uuid.uuid4()}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
            
            # Save file
            file.save(filepath)
            
            # Analyze the image
            if ai_analyzer:
                analysis_result = ai_analyzer.analyze_boat_image(filepath)
                
                # Find similar boats
                similar_boats = []
                if boat_db and 'error' not in analysis_result:
                    similar_boats = boat_db.find_similar_boats(analysis_result, limit=10)
                
                # Generate summary
                summary = ai_analyzer.get_analysis_summary(analysis_result)
                
                # Clean up uploaded file
                os.remove(filepath)
                
                return jsonify({
                    'success': True,
                    'analysis': analysis_result,
                    'summary': summary,
                    'similar_boats': similar_boats,
                    'total_similar': len(similar_boats)
                })
            else:
                return jsonify({'error': 'AI analyzer not available'}), 500
                
        except Exception as e:
            # Clean up file on error
            if os.path.exists(filepath):
                os.remove(filepath)
            return jsonify({'error': f'Error processing image: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/search', methods=['GET'])
def search_boats():
    """Search boats by various criteria"""
    if not boat_db:
        return jsonify({'error': 'Database not available'}), 500
    
    search_type = request.args.get('type', 'all')
    query = request.args.get('q', '')
    limit = int(request.args.get('limit', 10))
    
    print(f"🔍 [SEARCH] Query: '{query}', Type: {search_type}, Limit: {limit}")
    
    try:
        if search_type == 'brand':
            results = boat_db.search_by_brand(query, limit)
        elif search_type == 'model':
            results = boat_db.search_by_model(query, limit)
        elif search_type == 'year':
            year = int(query) if query.isdigit() else 2020
            results = boat_db.search_by_year_range(year-5, year+5, limit)
        else:
            # Use EXACT keyword search for general queries - FLAWLESS matching
            results = boat_db.search_by_keywords(query, limit)
        
        # Clean results for JSON serialization
        cleaned_results = clean_boat_data_for_json(results)
        
        print(f"✅ [SEARCH] Found {len(cleaned_results)} results")
        
        return jsonify({
            'success': True,
            'results': cleaned_results,
            'total': len(cleaned_results)
        })
        
    except Exception as e:
        return jsonify({'error': f'Search error: {str(e)}'}), 500

@app.route('/api/filter-options', methods=['GET'])
def get_filter_options():
    """Get available filter options for the UI"""
    try:
        if boat_db is None:
            return jsonify({'error': 'Database not available'}), 500
        
        options = boat_db.get_filter_options()
        return jsonify(options)
        
    except Exception as e:
        print(f"❌ Filter options error: {str(e)}")
        return jsonify({'error': f'Failed to get filter options: {str(e)}'}), 500

@app.route('/api/search-filtered', methods=['POST'])
def search_with_filters():
    """Search boats with advanced filters"""
    try:
        data = request.get_json()
        keywords = data.get('keywords', '').strip()
        filters = data.get('filters', {})
        limit = data.get('limit', 20)
        
        print(f"🔍 FILTERED SEARCH: '{keywords}', filters: {filters}")
        
        if boat_db is None:
            return jsonify({'error': 'Database not available'}), 500
        
        # Use the new filtered search method
        results = boat_db.search_with_filters(keywords, filters, limit)
        
        print(f"✅ Found {len(results)} filtered results")
        
        # Clean the data for JSON serialization
        cleaned_results = [clean_single_boat_data(boat) for boat in results]
        
        return jsonify({
            'results': cleaned_results,
            'count': len(cleaned_results),
            'keywords': keywords,
            'filters': filters
        })
        
    except Exception as e:
        print(f"❌ Filtered search error: {str(e)}")
        return jsonify({'error': f'Filtered search failed: {str(e)}'}), 500

@app.route('/api/stats')
def get_stats():
    """Get database statistics"""
    if not boat_db:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        # Simple stats without complex calculations
        stats = {
            'total_boats': len(boat_db.boats_df),
            'unique_brands': len(boat_db.boats_df['title'].str.split().str[0].unique()),
            'year_range': {
                'min': 'N/A',
                'max': 'N/A'
            },
            'price_range': {
                'min': 'N/A',
                'max': 'N/A'
            }
        }
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        # Return basic stats even if there's an error
        return jsonify({
            'success': True,
            'stats': {
                'total_boats': len(boat_db.boats_df) if boat_db else 0,
                'unique_brands': 'N/A',
                'year_range': {'min': 'N/A', 'max': 'N/A'},
                'price_range': {'min': 'N/A', 'max': 'N/A'}
            }
        })

@app.route('/api/analyze', methods=['POST'])
def analyze_image():
    """Analyze image without uploading to server"""
    print("🔍 [ANALYZE] Starting image analysis request...")
    
    if 'file' not in request.files:
        print("❌ [ANALYZE] No file in request")
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    print(f"📁 [ANALYZE] File received: {file.filename}")
    
    if file.filename == '':
        print("❌ [ANALYZE] No file selected")
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            print("✅ [ANALYZE] File validation passed")
            
            # Read file into memory
            file_bytes = file.read()
            print(f"📊 [ANALYZE] File size: {len(file_bytes)} bytes")
            
            # PRODUCTION-LEVEL VALIDATION: Validate image quality and boat detection BEFORE processing
            print("🔍 [VALIDATION] Starting comprehensive image validation...")
            validation_result = image_preprocessor.validate_boat_image(file_bytes)
            
            if not validation_result['can_proceed']:
                rejection_reason = validation_result.get('rejection_reason', 'Image validation failed')
                print(f"❌ [VALIDATION] Image rejected: {rejection_reason}")
                
                # Provide helpful error message
                error_message = f"Image not suitable for analysis. {rejection_reason}"
                if validation_result.get('quality_validation', {}).get('recommendations'):
                    error_message += " " + " ".join(validation_result['quality_validation']['recommendations'])
                else:
                    error_message += " Please upload a clear, well-lit boat image from a good angle where the boat is clearly visible."
                
                return jsonify({
                    'success': False,
                    'error': error_message,
                    'validation': {
                        'quality_score': validation_result.get('quality_validation', {}).get('quality_score', 0),
                        'boat_detected': validation_result.get('boat_detection', {}).get('boat_detected', False),
                        'combined_confidence': validation_result.get('combined_confidence', 0),
                        'issues': validation_result.get('quality_validation', {}).get('issues', []) + 
                                 validation_result.get('boat_detection', {}).get('issues', [])
                    },
                    'rejection_reason': rejection_reason
                }), 400
            
            print(f"✅ [VALIDATION] Image validation passed (Quality: {validation_result.get('quality_validation', {}).get('quality_score', 0):.2f}, Boat Detection: {validation_result.get('boat_detection', {}).get('confidence', 0):.2f})")
            
            # Preprocess image for better recognition
            print("🖼️ [PREPROCESS] Starting image preprocessing...")
            processed_bytes, preprocessing_info = image_preprocessor.preprocess_image(file_bytes, enhance_quality=True)
            print(f"✅ [PREPROCESS] Preprocessing completed in {preprocessing_info.get('processing_time_ms', 0)}ms")
            print(f"   Enhancements: {', '.join(preprocessing_info.get('enhancements_applied', []))}")
            
            # Analyze the image
            analysis_result = None
            location_result = None
            
            # Save file temporarily for analysis (use processed image)
            temp_filename = secure_filename(file.filename)
            temp_path = os.path.join(app.config['UPLOAD_FOLDER'], temp_filename)
            with open(temp_path, 'wb') as temp_file:
                temp_file.write(processed_bytes)
            
            if ai_analyzer:
                print("🤖 [ANALYZE] Starting AI analysis...")
                # Use preprocessed image for better results
                analysis_result = ai_analyzer.analyze_boat_image_from_bytes(processed_bytes)
                print(f"✅ [ANALYZE] AI analysis completed: {analysis_result.get('boat_type', 'Unknown')}")
                
                # Check if analysis failed
                if 'error' in analysis_result:
                    print(f"❌ [ANALYZE] AI analysis failed: {analysis_result['error']}")
                    return jsonify({
                        'success': False,
                        'error': analysis_result['error'],
                        'debug_info': {
                            'analyzer_type': getattr(ai_analyzer, 'analyzer_type', 'unknown'),
                            'model_used': analysis_result.get('model_used', 'unknown')
                        }
                    }), 500
                
                # Check AI validation (if AI says image is invalid or confidence too low)
                if not analysis_result.get('is_valid_image', True) or analysis_result.get('rejection_reason'):
                    rejection_reason = analysis_result.get('rejection_reason', 'AI determined image is not suitable')
                    print(f"❌ [ANALYZE] AI validation failed: {rejection_reason}")
                    
                    confidence = analysis_result.get('confidence', 0)
                    if isinstance(confidence, str):
                        try:
                            confidence = float(confidence)
                        except:
                            confidence = 0
                    
                    return jsonify({
                        'success': False,
                        'error': f"Image not suitable for analysis. {rejection_reason}",
                        'ai_validation': {
                            'is_valid_image': False,
                            'rejection_reason': rejection_reason,
                            'confidence': confidence,
                            'quality_assessment': analysis_result.get('image_quality_assessment', 'Unknown')
                        },
                        'recommendation': 'Please upload a clear, well-lit boat image from a good angle where the boat is clearly visible and in focus.'
                    }), 400
                
                # Check confidence threshold (additional safety)
                confidence = analysis_result.get('confidence', 0)
                if isinstance(confidence, str):
                    try:
                        confidence = float(confidence)
                    except:
                        confidence = 0
                
                if confidence < 30:
                    print(f"⚠️ [ANALYZE] Low confidence ({confidence}%) - image may be unclear")
                    return jsonify({
                        'success': False,
                        'error': f'Analysis confidence too low ({confidence}%). The image may be too blurry, unclear, not a boat, or from a poor angle. Please upload a clear boat image from a good angle.',
                        'confidence': confidence,
                        'recommendation': 'Please upload a clear, well-lit boat image from a good angle where the boat is clearly visible and in focus.'
                    }), 400
            else:
                print("❌ [ANALYZE] No AI analyzer available")
                return jsonify({'error': 'AI analyzer not available'}), 500
            
            # Clean up temporary file
            try:
                os.remove(temp_path)
            except:
                pass
            
            # Generate summary
            print("📝 [ANALYZE] Generating summary...")
            summary = ai_analyzer.get_analysis_summary(analysis_result) if ai_analyzer else "Analysis completed"
            
            # Add image name to analysis result
            analysis_result['image_name'] = file.filename
            
            # Save to analysis history
            print("💾 [ANALYZE] Saving to analysis history...")
            history_entry = add_analysis_to_history(analysis_result)
            
            # MVP Response - Focus only on core analysis
            response_data = {
                'success': True,
                'analysis': analysis_result,
                'summary': summary,
                'history_id': history_entry['id'],
                'preprocessing': preprocessing_info,
                'mvp_mode': True,
                'premium_features': {
                    'similar_boats': 'Available with premium membership',
                    'location_analysis': 'Available with premium membership',
                    'interactive_maps': 'Available with premium membership'
                }
            }
            
            print("🎉 [ANALYZE] MVP Analysis completed successfully!")
            
            print(f"📊 [ANALYZE] Response data size: {len(str(response_data))} characters")
            return jsonify(response_data)
                
        except Exception as e:
            return jsonify({'error': f'Error processing image: {str(e)}'}), 500
    
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/health')
def health_check():
    """Health check endpoint with detailed diagnostics"""
    status = {
        'database': boat_db is not None,
        'ai_analyzer': ai_analyzer is not None,
        'upload_folder': os.path.exists(app.config['UPLOAD_FOLDER'])
    }
    
    # Detailed diagnostics
    diagnostics = {
        'current_directory': os.getcwd(),
        'csv_file_exists': os.path.exists('all_boats_data.csv'),
        'csv_file_size': os.path.getsize('all_boats_data.csv') if os.path.exists('all_boats_data.csv') else 0,
        'database_boats_count': len(boat_db.boats_df) if boat_db and boat_db.boats_df is not None else 0,
        'gcp_credentials_env_set': bool(os.getenv('GCP_CREDENTIALS_JSON')),
        'gcp_credentials_file_exists': os.path.exists('static-chiller-472906-f3-4ee4a099f2f1.json'),
    }
    
    # Get AI model info if available
    model_info = None
    if ai_analyzer and hasattr(ai_analyzer, 'get_model_info'):
        try:
            model_info = ai_analyzer.get_model_info()
        except:
            pass
    
    return jsonify({
        'status': 'healthy' if all([status['database'], status['ai_analyzer']]) else 'degraded',
        'components': status,
        'diagnostics': diagnostics,
        'ai_model': model_info
    })

@app.route('/api/map/boats')
def get_boats_for_map():
    """Get boats with location data for map visualization"""
    if boat_db is None:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        limit = request.args.get('limit', 1000, type=int)
        boats = boat_db.get_boats_for_map(limit)
        
        return jsonify({
            'success': True,
            'boats': clean_boat_data_for_json(boats),
            'count': len(boats)
        })
    except Exception as e:
        return jsonify({'error': f'Error getting boats for map: {str(e)}'}), 500

@app.route('/api/map/search')
def search_boats_by_location():
    """Search boats by location coordinates"""
    if boat_db is None:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        lat = request.args.get('lat', type=float)
        lon = request.args.get('lon', type=float)
        radius = request.args.get('radius', 50, type=float)  # km
        limit = request.args.get('limit', 20, type=int)
        
        if lat is None or lon is None:
            return jsonify({'error': 'Latitude and longitude are required'}), 400
        
        boats = boat_db.search_by_location(lat, lon, radius, limit)
        
        return jsonify({
            'success': True,
            'boats': clean_boat_data_for_json(boats),
            'count': len(boats),
            'search_center': {'lat': lat, 'lon': lon},
            'radius_km': radius
        })
    except Exception as e:
        return jsonify({'error': f'Error searching boats by location: {str(e)}'}), 500

@app.route('/api/map/location/<location_name>')
def search_boats_by_location_name(location_name):
    """Search boats by location name"""
    if boat_db is None:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        radius = request.args.get('radius', 50, type=float)  # km
        limit = request.args.get('limit', 20, type=int)
        
        boats = boat_db.search_by_location_name(location_name, radius, limit)
        
        return jsonify({
            'success': True,
            'boats': clean_boat_data_for_json(boats),
            'count': len(boats),
            'location': location_name,
            'radius_km': radius
        })
    except Exception as e:
        return jsonify({'error': f'Error searching boats by location name: {str(e)}'}), 500

@app.route('/api/map/analyze-location', methods=['POST'])
def analyze_image_location():
    """Analyze boat image to detect location"""
    print("🗺️ [LOCATION] Starting location analysis request...")
    
    if location_analyzer is None:
        print("❌ [LOCATION] Location analyzer not available")
        return jsonify({'error': 'Location analyzer not available'}), 500
    
    if 'file' not in request.files:
        print("❌ [LOCATION] No file in request")
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    print(f"📁 [LOCATION] File received: {file.filename}")
    
    if file.filename == '':
        print("❌ [LOCATION] No file selected")
        return jsonify({'error': 'No file selected'}), 400
    
    if file and allowed_file(file.filename):
        try:
            print("✅ [LOCATION] File validation passed")
            file_bytes = file.read()
            print(f"📊 [LOCATION] File size: {len(file_bytes)} bytes")
            
            print("🤖 [LOCATION] Starting location analysis...")
            location_result = location_analyzer.analyze_image_location(file_bytes)
            print(f"✅ [LOCATION] Location analysis result: {location_result}")
            
            if location_result.get('success'):
                print("🔍 [LOCATION] Searching for nearby boats...")
                # Get nearby boats for each detected location
                nearby_boats = []
                for location in location_result.get('detected_locations', []):
                    print(f"🔍 [LOCATION] Searching near {location['name']} ({location['lat']}, {location['lon']})")
                    boats = boat_db.search_by_location(
                        location['lat'], 
                        location['lon'], 
                        radius_km=50, 
                        limit=10
                    )
                    print(f"✅ [LOCATION] Found {len(boats)} boats near {location['name']}")
                    nearby_boats.extend(boats)
                
                print(f"🎉 [LOCATION] Total nearby boats found: {len(nearby_boats)}")
                
                return jsonify({
                    'success': True,
                    'detected_locations': location_result.get('detected_locations'),
                    'nearby_boats': clean_boat_data_for_json(nearby_boats),
                    'confidence': location_result.get('confidence'),
                    'analysis_method': location_result.get('analysis_method')
                })
            else:
                print(f"❌ [LOCATION] Location analysis failed: {location_result.get('error')}")
                return jsonify({
                    'success': False,
                    'error': location_result.get('error')
                }), 500
                
        except Exception as e:
            print(f"❌ [LOCATION] Exception during analysis: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({'error': f'Error analyzing image location: {str(e)}'}), 500
    
    print("❌ [LOCATION] Invalid file type")
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/api/map/stats')
def get_location_stats():
    """Get location statistics"""
    if boat_db is None:
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        stats = boat_db.get_location_statistics()
        return jsonify({
            'success': True,
            'location_stats': stats
        })
    except Exception as e:
        return jsonify({'error': f'Error getting location stats: {str(e)}'}), 500

@app.route('/api/model-info')
def get_model_info():
    """Get AI model information"""
    if not ai_analyzer:
        return jsonify({'error': 'AI analyzer not available'}), 500
    
    try:
        if hasattr(ai_analyzer, 'get_model_info'):
            model_info = ai_analyzer.get_model_info()
            return jsonify({
                'success': True,
                'model_info': model_info
            })
        else:
            return jsonify({
                'success': True,
                'model_info': {
                    'model_name': 'gemini-1.5-flash',
                    'provider': 'Google AI Studio',
                    'analyzer_type': 'regular_gemini'
                }
            })
    except Exception as e:
        return jsonify({'error': f'Error getting model info: {str(e)}'}), 500

@app.route('/api/history')
def get_analysis_history():
    """Get analysis history"""
    try:
        history = load_analysis_history()
        return jsonify({
            'success': True,
            'history': history,
            'total': len(history)
        })
    except Exception as e:
        return jsonify({'error': f'Error loading history: {str(e)}'}), 500

@app.route('/api/history/<history_id>')
def get_analysis_by_id(history_id):
    """Get specific analysis by ID"""
    try:
        history = load_analysis_history()
        analysis = next((item for item in history if item['id'] == history_id), None)
        
        if analysis:
            return jsonify({
                'success': True,
                'analysis': analysis
            })
        else:
            return jsonify({'error': 'Analysis not found'}), 404
    except Exception as e:
        return jsonify({'error': f'Error loading analysis: {str(e)}'}), 500

@app.route('/api/history/<history_id>', methods=['DELETE'])
def delete_analysis(history_id):
    """Delete analysis from history"""
    try:
        history = load_analysis_history()
        history = [item for item in history if item['id'] != history_id]
        save_analysis_history(history)
        
        return jsonify({
            'success': True,
            'message': 'Analysis deleted successfully'
        })
    except Exception as e:
        return jsonify({'error': f'Error deleting analysis: {str(e)}'}), 500

@app.route('/api/analyze-text', methods=['POST'])
def analyze_boat_text():
    """Analyze boat from text search without photo"""
    print("🔍 [TEXT-ANALYZE] Starting text-based boat analysis...")
    
    if not ai_analyzer:
        print("❌ [TEXT-ANALYZE] No AI analyzer available")
        return jsonify({'error': 'AI analyzer not available'}), 500
    
    if not boat_db:
        print("❌ [TEXT-ANALYZE] No database available")
        return jsonify({'error': 'Database not available'}), 500
    
    try:
        data = request.get_json()
        boat_id = data.get('boat_id')
        search_mode = data.get('search_mode', False)
        
        print(f"🔍 [TEXT-ANALYZE] Boat ID: {boat_id}, Search mode: {search_mode}")
        
        if not boat_id:
            return jsonify({'error': 'Boat ID is required'}), 400
        
        # Find the boat in database
        boat_data = None
        if search_mode:
            # Search by title or ID
            boats = boat_db.search_by_brand(boat_id, limit=1)
            if not boats:
                boats = boat_db.search_by_model(boat_id, limit=1)
            if boats:
                boat_data = boats[0]
        else:
            # Direct lookup by ID
            boat_data = boat_db.get_boat_by_id(boat_id)
        
        if not boat_data:
            print(f"❌ [TEXT-ANALYZE] Boat not found: {boat_id}")
            return jsonify({'error': 'Boat not found in database'}), 404
        
        print(f"✅ [TEXT-ANALYZE] Found boat: {boat_data.get('title', 'Unknown')}")
        
        # Clean boat data for JSON serialization
        boat_data = clean_single_boat_data(boat_data)
        
        # Create analysis result from boat data
        analysis_result = create_analysis_from_boat_data(boat_data)
        
        # Generate summary
        print("📝 [TEXT-ANALYZE] Generating summary...")
        summary = ai_analyzer.get_analysis_summary(analysis_result) if ai_analyzer else "Analysis completed"
        
        # Add metadata
        analysis_result['image_name'] = f"Text Search: {boat_data.get('title', 'Unknown Boat')}"
        analysis_result['search_mode'] = True
        analysis_result['boat_id'] = boat_id
        
        # Save to analysis history
        print("💾 [TEXT-ANALYZE] Saving to analysis history...")
        history_entry = add_analysis_to_history(analysis_result)
        
        # Response
        response_data = {
            'success': True,
            'analysis': analysis_result,
            'summary': summary,
            'history_id': history_entry['id'],
            'search_mode': True,
            'boat_data': boat_data
        }
        
        print("🎉 [TEXT-ANALYZE] Text analysis completed successfully!")
        return jsonify(response_data)
        
    except Exception as e:
        print(f"❌ [TEXT-ANALYZE] Error: {str(e)}")
        return jsonify({'error': f'Error analyzing boat: {str(e)}'}), 500

def create_analysis_from_boat_data(boat_data):
    """Create analysis result from boat database data"""
    analysis = {
        'boat_type': boat_data.get('boat_type', 'Unknown'),
        'brand': boat_data.get('brand', 'Unknown'),
        'model': boat_data.get('model', 'Unknown'),
        'model_line': boat_data.get('model_line', 'Unknown'),
        'estimated_year': boat_data.get('year_built', 'Unknown'),
        'length_estimate': boat_data.get('length', 'Unknown'),
        'width_estimate': boat_data.get('width', 'Unknown'),
        'hull_material': boat_data.get('hull_material', 'Unknown'),
        'engine_type': boat_data.get('engine_type', 'Unknown'),
        'hull_type': boat_data.get('hull_type', 'Unknown'),
        'key_features': extract_key_features(boat_data),
        'distinctive_elements': extract_distinctive_elements(boat_data),
        'condition': 'Database Entry',
        'price_estimate': boat_data.get('price', 'Unknown'),
        'confidence': calculate_confidence(boat_data),
        'detailed_description': create_detailed_description(boat_data),
        'identification_clues': create_identification_clues(boat_data),
        'technical_specs': extract_technical_specs(boat_data),
        'design_analysis': create_design_analysis(boat_data),
        'market_positioning': create_market_positioning(boat_data),
        'historical_context': create_historical_context(boat_data),
        'model_used': 'database-analysis',
        'analyzer_type': 'text_search'
    }
    
    return analysis

def extract_key_features(boat_data):
    """Extract key features from boat data"""
    features = []
    if boat_data.get('features'):
        features.append(boat_data['features'])
    if boat_data.get('equipment'):
        features.append(boat_data['equipment'])
    if boat_data.get('special_features'):
        features.append(boat_data['special_features'])
    return features

def extract_distinctive_elements(boat_data):
    """Extract distinctive elements from boat data"""
    elements = []
    if boat_data.get('design_features'):
        elements.append(boat_data['design_features'])
    if boat_data.get('unique_selling_points'):
        elements.append(boat_data['unique_selling_points'])
    return elements

def calculate_confidence(boat_data):
    """Calculate confidence based on data completeness"""
    confidence = 50  # Base confidence
    
    # Increase confidence based on available data
    if boat_data.get('brand'): confidence += 10
    if boat_data.get('model'): confidence += 10
    if boat_data.get('year_built'): confidence += 10
    if boat_data.get('length'): confidence += 5
    if boat_data.get('price'): confidence += 5
    if boat_data.get('engine_type'): confidence += 5
    if boat_data.get('hull_type'): confidence += 5
    
    return min(confidence, 95)  # Cap at 95%

def create_detailed_description(boat_data):
    """Create detailed description from boat data"""
    desc_parts = []
    
    if boat_data.get('title'):
        desc_parts.append(f"This is a {boat_data['title']}")
    
    if boat_data.get('boat_type'):
        desc_parts.append(f"classified as a {boat_data['boat_type']}")
    
    if boat_data.get('year_built'):
        desc_parts.append(f"built in {boat_data['year_built']}")
    
    if boat_data.get('length'):
        desc_parts.append(f"with a length of {boat_data['length']}")
    
    if boat_data.get('description'):
        desc_parts.append(f"Description: {boat_data['description']}")
    
    return ". ".join(desc_parts) + "."

def create_identification_clues(boat_data):
    """Create identification clues from boat data"""
    clues = []
    if boat_data.get('brand'): clues.append(f"Brand: {boat_data['brand']}")
    if boat_data.get('model'): clues.append(f"Model: {boat_data['model']}")
    if boat_data.get('year_built'): clues.append(f"Year: {boat_data['year_built']}")
    return "; ".join(clues)

def extract_technical_specs(boat_data):
    """Extract technical specifications from boat data"""
    specs = {}
    if boat_data.get('engine_power'): specs['engine_power'] = boat_data['engine_power']
    if boat_data.get('fuel_capacity'): specs['fuel_capacity'] = boat_data['fuel_capacity']
    if boat_data.get('water_capacity'): specs['water_capacity'] = boat_data['water_capacity']
    if boat_data.get('max_speed'): specs['max_speed'] = boat_data['max_speed']
    if boat_data.get('berths'): specs['berths'] = boat_data['berths']
    return specs

def create_design_analysis(boat_data):
    """Create design analysis from boat data"""
    return {
        'hull_design': boat_data.get('hull_design', 'Design information not available'),
        'cabin_layout': boat_data.get('cabin_layout', 'Cabin layout information not available'),
        'deck_features': boat_data.get('deck_features', 'Deck features information not available'),
        'aerodynamics': boat_data.get('aerodynamics', 'Aerodynamics information not available')
    }

def create_market_positioning(boat_data):
    """Create market positioning from boat data"""
    return {
        'target_market': boat_data.get('target_market', 'Market information not available'),
        'competitors': boat_data.get('competitors', 'Competitor information not available'),
        'unique_selling_points': boat_data.get('unique_selling_points', 'USP information not available'),
        'ideal_use_cases': boat_data.get('ideal_use_cases', 'Use case information not available')
    }

def create_historical_context(boat_data):
    """Create historical context from boat data"""
    return {
        'design_era': boat_data.get('design_era', 'Era information not available'),
        'manufacturer_history': boat_data.get('manufacturer_history', 'Manufacturer history not available'),
        'model_evolution': boat_data.get('model_evolution', 'Model evolution not available'),
        'market_reception': boat_data.get('market_reception', 'Market reception not available')
    }

# Data Insights API Endpoints
@app.route('/api/data-insights/summary')
def get_data_insights_summary():
    """Get executive summary statistics"""
    try:
        if boat_db is None:
            return jsonify({
                'error': 'Database not available',
                'message': 'Boat database not initialized. Please check server logs.',
                'diagnostics': {
                    'csv_exists': os.path.exists('all_boats_data.csv'),
                    'current_dir': os.getcwd()
                }
            }), 500
        
        if boat_db.boats_df is None or len(boat_db.boats_df) == 0:
            return jsonify({
                'error': 'Database empty',
                'message': 'Boat database is initialized but contains no data.'
            }), 500
        
        df = boat_db.boats_df
        total_boats = len(df)
        
        def extract_price(price_str):
            if pd.isna(price_str) or price_str == '' or 'Price on Request' in str(price_str) or 'Under Offer' in str(price_str):
                return None
            try:
                price_clean = str(price_str).replace('EUR', '').replace(',', '').replace('.', '').replace('-', '').replace(' ', '').strip()
                import re
                numbers = re.findall(r'\d+', price_clean)
                if numbers:
                    return int(''.join(numbers))
                return None
            except:
                return None
        
        prices = df['price'].apply(extract_price).dropna()
        years = pd.to_numeric(df['year_built'], errors='coerce').dropna()
        
        def extract_length(dim_str):
            if pd.isna(dim_str) or dim_str == '' or 'N/A' in str(dim_str):
                return None
            try:
                import re
                match = re.search(r'(\d+\.?\d*)\s*x', str(dim_str))
                if match:
                    return float(match.group(1))
                return None
            except:
                return None
        
        lengths = df['dimensions'].apply(extract_length).dropna()
        
        def extract_brand(title):
            if pd.isna(title):
                return None
            words = str(title).split()
            if words:
                return words[0]
            return None
        
        brands = df['title'].apply(extract_brand).dropna()
        top_brands = brands.value_counts().head(10).to_dict()
        
        summary = {
            'total_boats': total_boats,
            'price_stats': {
                'count': len(prices),
                'median': float(prices.median()) if len(prices) > 0 else None,
                'mean': float(prices.mean()) if len(prices) > 0 else None,
                'min': float(prices.min()) if len(prices) > 0 else None,
                'max': float(prices.max()) if len(prices) > 0 else None,
                'q25': float(prices.quantile(0.25)) if len(prices) > 0 else None,
                'q75': float(prices.quantile(0.75)) if len(prices) > 0 else None
            },
            'year_stats': {
                'count': len(years),
                'min': int(years.min()) if len(years) > 0 else None,
                'max': int(years.max()) if len(years) > 0 else None,
                'median': int(years.median()) if len(years) > 0 else None,
                'mean': float(years.mean()) if len(years) > 0 else None
            },
            'length_stats': {
                'count': len(lengths),
                'min': float(lengths.min()) if len(lengths) > 0 else None,
                'max': float(lengths.max()) if len(lengths) > 0 else None,
                'median': float(lengths.median()) if len(lengths) > 0 else None,
                'mean': float(lengths.mean()) if len(lengths) > 0 else None
            },
            'top_brands': {str(k): int(v) for k, v in top_brands.items()}
        }
        
        return jsonify({'success': True, 'summary': summary})
    except Exception as e:
        return jsonify({'error': f'Error generating summary: {str(e)}'}), 500

@app.route('/api/data-insights/price-distribution')
def get_price_distribution():
    """Get price distribution data for histogram"""
    try:
        if boat_db is None or boat_db.boats_df is None or len(boat_db.boats_df) == 0:
            return jsonify({
                'error': 'Database not available',
                'message': 'Boat database not initialized or empty.'
            }), 500
        
        df = boat_db.boats_df
        
        def extract_price(price_str):
            if pd.isna(price_str) or price_str == '' or 'Price on Request' in str(price_str) or 'Under Offer' in str(price_str):
                return None
            try:
                price_clean = str(price_str).replace('EUR', '').replace(',', '').replace('.', '').replace('-', '').replace(' ', '').strip()
                import re
                numbers = re.findall(r'\d+', price_clean)
                if numbers:
                    return int(''.join(numbers))
                return None
            except:
                return None
        
        prices = df['price'].apply(extract_price).dropna()
        
        if len(prices) > 0:
            max_price = prices.max()
            bins = [0, 10000, 25000, 50000, 100000, 200000, 500000, 1000000, max_price]
            labels = ['<10K', '10K-25K', '25K-50K', '50K-100K', '100K-200K', '200K-500K', '500K-1M', '>1M']
            price_categories = pd.cut(prices, bins=bins, labels=labels, include_lowest=True)
            distribution = price_categories.value_counts().sort_index().to_dict()
            
            return jsonify({
                'success': True,
                'distribution': {str(k): int(v) for k, v in distribution.items()},
                'raw_data': prices.tolist()[:1000]
            })
        else:
            return jsonify({'success': True, 'distribution': {}, 'raw_data': []})
    except Exception as e:
        return jsonify({'error': f'Error generating price distribution: {str(e)}'}), 500

@app.route('/api/data-insights/year-distribution')
def get_year_distribution():
    """Get year distribution data"""
    try:
        if boat_db is None or boat_db.boats_df is None or len(boat_db.boats_df) == 0:
            return jsonify({'error': 'Database not available', 'message': 'Boat database not initialized or empty.'}), 500
        
        df = boat_db.boats_df
        years = pd.to_numeric(df['year_built'], errors='coerce').dropna()
        
        if len(years) > 0:
            decades = {}
            for year in years:
                decade = (int(year) // 10) * 10
                decades[decade] = decades.get(decade, 0) + 1
            
            max_year = int(years.max())
            recent_years = {}
            for year in years:
                if year >= max_year - 20:
                    recent_years[int(year)] = recent_years.get(int(year), 0) + 1
            
            return jsonify({
                'success': True,
                'by_decade': {str(k): int(v) for k, v in sorted(decades.items())},
                'recent_years': {str(k): int(v) for k, v in sorted(recent_years.items())},
                'all_years': {str(int(k)): int(v) for k, v in years.value_counts().head(50).items()}
            })
        else:
            return jsonify({'success': True, 'by_decade': {}, 'recent_years': {}, 'all_years': {}})
    except Exception as e:
        return jsonify({'error': f'Error generating year distribution: {str(e)}'}), 500

@app.route('/api/data-insights/brand-stats')
def get_brand_stats():
    """Get brand statistics"""
    try:
        if boat_db is None or boat_db.boats_df is None or len(boat_db.boats_df) == 0:
            return jsonify({'error': 'Database not available', 'message': 'Boat database not initialized or empty.'}), 500
        
        df = boat_db.boats_df
        
        def extract_brand(title):
            if pd.isna(title):
                return None
            words = str(title).split()
            if words:
                return words[0]
            return None
        
        def extract_price(price_str):
            if pd.isna(price_str) or price_str == '' or 'Price on Request' in str(price_str) or 'Under Offer' in str(price_str):
                return None
            try:
                price_clean = str(price_str).replace('EUR', '').replace(',', '').replace('.', '').replace('-', '').replace(' ', '').strip()
                import re
                numbers = re.findall(r'\d+', price_clean)
                if numbers:
                    return int(''.join(numbers))
                return None
            except:
                return None
        
        brands = df['title'].apply(extract_brand).dropna()
        brand_counts = brands.value_counts().head(20)
        
        brand_price_stats = {}
        for brand in brand_counts.index[:10]:
            brand_df = df[df['title'].str.startswith(brand, na=False)]
            prices = brand_df['price'].apply(extract_price)
            prices = prices.dropna()
            if len(prices) > 0:
                brand_price_stats[brand] = {
                    'count': len(brand_df),
                    'avg_price': float(prices.mean()),
                    'median_price': float(prices.median())
                }
        
        return jsonify({
            'success': True,
            'brand_counts': {str(k): int(v) for k, v in brand_counts.items()},
            'brand_price_stats': brand_price_stats
        })
    except Exception as e:
        return jsonify({'error': f'Error generating brand stats: {str(e)}'}), 500

@app.route('/api/data-insights/size-distribution')
def get_size_distribution():
    """Get boat size (length) distribution"""
    try:
        if boat_db is None or boat_db.boats_df is None or len(boat_db.boats_df) == 0:
            return jsonify({'error': 'Database not available', 'message': 'Boat database not initialized or empty.'}), 500
        
        df = boat_db.boats_df
        
        def extract_length(dim_str):
            if pd.isna(dim_str) or dim_str == '' or 'N/A' in str(dim_str):
                return None
            try:
                import re
                match = re.search(r'(\d+\.?\d*)\s*x', str(dim_str))
                if match:
                    return float(match.group(1))
                return None
            except:
                return None
        
        lengths = df['dimensions'].apply(extract_length).dropna()
        
        if len(lengths) > 0:
            bins = [0, 5, 8, 10, 12, 15, 20, 30, lengths.max()]
            labels = ['<5m', '5-8m', '8-10m', '10-12m', '12-15m', '15-20m', '20-30m', '>30m']
            size_categories = pd.cut(lengths, bins=bins, labels=labels, include_lowest=True)
            distribution = size_categories.value_counts().sort_index().to_dict()
            
            return jsonify({
                'success': True,
                'distribution': {str(k): int(v) for k, v in distribution.items()},
                'stats': {
                    'min': float(lengths.min()),
                    'max': float(lengths.max()),
                    'median': float(lengths.median()),
                    'mean': float(lengths.mean())
                }
            })
        else:
            return jsonify({'success': True, 'distribution': {}, 'stats': {}})
    except Exception as e:
        return jsonify({'error': f'Error generating size distribution: {str(e)}'}), 500

@app.route('/api/data-insights/market-trends')
def get_market_trends():
    """Get market trends over time"""
    try:
        if boat_db is None or boat_db.boats_df is None or len(boat_db.boats_df) == 0:
            return jsonify({'error': 'Database not available', 'message': 'Boat database not initialized or empty.'}), 500
        
        df = boat_db.boats_df
        
        def extract_price(price_str):
            if pd.isna(price_str) or price_str == '' or 'Price on Request' in str(price_str) or 'Under Offer' in str(price_str):
                return None
            try:
                price_clean = str(price_str).replace('EUR', '').replace(',', '').replace('.', '').replace('-', '').replace(' ', '').strip()
                import re
                numbers = re.findall(r'\d+', price_clean)
                if numbers:
                    return int(''.join(numbers))
                return None
            except:
                return None
        
        def extract_length(dim_str):
            if pd.isna(dim_str) or dim_str == '' or 'N/A' in str(dim_str):
                return None
            try:
                import re
                match = re.search(r'(\d+\.?\d*)\s*x', str(dim_str))
                if match:
                    return float(match.group(1))
                return None
            except:
                return None
        
        df_copy = df.copy()
        df_copy['price_numeric'] = df_copy['price'].apply(extract_price)
        df_copy['length_numeric'] = df_copy['dimensions'].apply(extract_length)
        df_copy['year_numeric'] = pd.to_numeric(df_copy['year_built'], errors='coerce')
        
        valid_data = df_copy.dropna(subset=['year_numeric', 'price_numeric'])
        
        if len(valid_data) > 0:
            yearly_stats = valid_data.groupby('year_numeric').agg({
                'price_numeric': ['count', 'mean', 'median'],
                'length_numeric': 'mean'
            }).reset_index()
            
            yearly_stats.columns = ['year', 'count', 'avg_price', 'median_price', 'avg_length']
            
            trends = {
                'years': [int(row['year']) for row in yearly_stats.to_dict('records')],
                'counts': [int(row['count']) for row in yearly_stats.to_dict('records')],
                'avg_prices': [float(row['avg_price']) for row in yearly_stats.to_dict('records')],
                'median_prices': [float(row['median_price']) for row in yearly_stats.to_dict('records')],
                'avg_lengths': [float(row['avg_length']) if pd.notna(row['avg_length']) else None for row in yearly_stats.to_dict('records')]
            }
            
            return jsonify({'success': True, 'trends': trends})
        else:
            return jsonify({
                'success': True,
                'trends': {
                    'years': [], 'counts': [], 'avg_prices': [],
                    'median_prices': [], 'avg_lengths': []
                }
            })
    except Exception as e:
        return jsonify({'error': f'Error generating market trends: {str(e)}'}), 500

# Investment Comparison API Endpoints
@app.route('/api/investment-comparison/financial-indices')
def get_financial_indices():
    """Get financial indices performance data"""
    try:
        period = request.args.get('period', '5y')
        start_date = request.args.get('start_date', None)
        
        summary = financial_fetcher.get_comparison_summary(period=period, start_date=start_date)
        
        return jsonify({
            'success': True,
            'data': summary
        })
    except Exception as e:
        return jsonify({'error': f'Error fetching financial indices: {str(e)}'}), 500

@app.route('/api/investment-comparison/boat-market')
def get_boat_market_performance():
    """Get boat market performance data"""
    try:
        if boat_market_analyzer is None:
            error_msg = 'Boat market analyzer not available. '
            if boat_db is None:
                error_msg += 'Boat database not initialized.'
            elif boat_db.boats_df is None or len(boat_db.boats_df) == 0:
                error_msg += 'No boat data available in database.'
            else:
                error_msg += 'Initialization failed.'
            return jsonify({'error': error_msg}), 500
        
        start_year = request.args.get('start_year', type=int)
        end_year = request.args.get('end_year', type=int)
        
        performance = boat_market_analyzer.calculate_market_performance(
            start_year=start_year,
            end_year=end_year
        )
        
        return jsonify({
            'success': True,
            'data': performance
        })
    except Exception as e:
        return jsonify({'error': f'Error calculating boat market performance: {str(e)}'}), 500

@app.route('/api/investment-comparison/comparison')
def get_investment_comparison():
    """Get comprehensive comparison between boat market and financial indices"""
    try:
        period = request.args.get('period', '5y')
        start_year = request.args.get('start_year', type=int)
        
        # Get financial indices data
        financial_data = financial_fetcher.get_comparison_summary(period=period)
        
        # Get boat market data
        if boat_market_analyzer is None:
            error_msg = 'Boat market analyzer not available. '
            if boat_db is None:
                error_msg += 'Boat database not initialized.'
            elif boat_db.boats_df is None or len(boat_db.boats_df) == 0:
                error_msg += 'No boat data available in database.'
            else:
                error_msg += 'Initialization failed.'
            return jsonify({'error': error_msg}), 500
        
        boat_performance = boat_market_analyzer.calculate_market_performance(start_year=start_year)
        
        # Calculate comparison metrics
        comparison = {
            'boat_market': boat_performance,
            'financial_indices': financial_data,
            'comparison_metrics': {}
        }
        
        # Compare returns
        if 'total_return_pct' in boat_performance and not boat_performance.get('error'):
            boat_return = boat_performance['total_return_pct']
            
            # Get average financial return
            indices_returns = [
                idx.get('total_return_pct', 0) 
                for idx in financial_data['indices'].values() 
                if 'error' not in idx
            ]
            
            if indices_returns:
                avg_financial_return = sum(indices_returns) / len(indices_returns)
                
                comparison['comparison_metrics'] = {
                    'boat_return_pct': boat_return,
                    'avg_financial_return_pct': round(avg_financial_return, 2),
                    'outperformance_pct': round(boat_return - avg_financial_return, 2),
                    'boat_annualized_return_pct': boat_performance.get('annualized_return_pct', 0),
                    'boat_volatility_pct': boat_performance.get('volatility_pct', 0),
                    'best_financial_index': financial_data.get('best_performer'),
                    'period': period,
                    'start_year': start_year or (datetime.datetime.now().year - 5)
                }
        
        return jsonify({
            'success': True,
            'data': comparison
        })
    except Exception as e:
        return jsonify({'error': f'Error generating comparison: {str(e)}'}), 500

@app.route('/api/investment-comparison/historical')
def get_historical_comparison():
    """Get historical price data for comparison charts"""
    try:
        period = request.args.get('period', '5y')
        index_name = request.args.get('index', 'SP500')  # SP500, NASDAQ, BIST100
        
        # Get financial index historical data
        financial_historical = financial_fetcher.get_historical_prices(index_name, period)
        
        # Get boat market yearly data
        if boat_market_analyzer is None:
            error_msg = 'Boat market analyzer not available. '
            if boat_db is None:
                error_msg += 'Boat database not initialized.'
            elif boat_db.boats_df is None or len(boat_db.boats_df) == 0:
                error_msg += 'No boat data available in database.'
            else:
                error_msg += 'Initialization failed.'
            return jsonify({'error': error_msg}), 500
        
        start_year = request.args.get('start_year', type=int)
        boat_performance = boat_market_analyzer.calculate_market_performance(start_year=start_year)
        
        historical_data = {
            'financial_index': {
                'name': index_name,
                'data': []
            },
            'boat_market': {
                'data': []
            }
        }
        
        # Format financial data
        if financial_historical is not None and not financial_historical.empty:
            for date, row in financial_historical.iterrows():
                historical_data['financial_index']['data'].append({
                    'date': date.strftime('%Y-%m-%d'),
                    'price': float(row['Close']),
                    'year': date.year
                })
        
        # Format boat market data
        if 'yearly_data' in boat_performance:
            yearly_data = boat_performance['yearly_data']
            for i, year in enumerate(yearly_data['years']):
                historical_data['boat_market']['data'].append({
                    'year': year,
                    'avg_price': yearly_data['avg_prices'][i],
                    'median_price': yearly_data['median_prices'][i],
                    'count': yearly_data['counts'][i]
                })
        
        return jsonify({
            'success': True,
            'data': historical_data
        })
    except Exception as e:
        return jsonify({'error': f'Error fetching historical data: {str(e)}'}), 500

# Initialize app when module is imported (for gunicorn/production)
print("=" * 60)
print("🚀 Initializing boataniQ App...")
print("=" * 60)
initialize_app()

if boat_db is None:
    print("⚠️  WARNING: Database not initialized. Some features may not work.")
else:
    print(f"✅ Database ready with {len(boat_db.boats_df)} boats")

if ai_analyzer is None:
    print("⚠️  WARNING: AI analyzer not initialized. Image analysis will not work.")
    print("   Please set GCP_CREDENTIALS_JSON or GEMINI_API_KEY environment variable.")
else:
    print("✅ AI analyzer ready")

print("=" * 60)
print("✅ Application initialization complete!")
print("=" * 60)

if __name__ == '__main__':
    print("Starting Flask application in development mode...")
    app.run(debug=True, host='0.0.0.0', port=5001)
