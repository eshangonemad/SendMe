""" import os
os.system("ECHO GAY") 

#for text 
# os.system("python print.py --text '{TEXT BOX CONTENT HERE}' --font 'Arial.ttf' --font-size 24 --align center --strikethrough")
# for images
# os.system("python print.py '{image.jpg}' --font 'Arial.ttf' --font-size 24 --align center --strikethrough")
# """
import os
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
import subprocess
from PIL import Image
import io

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def compress_image(image_path, max_size=(384, 1000)):
    """Compress and resize image for thermal printing"""
    try:
        with Image.open(image_path) as img:
            # Convert to RGB if it's not already
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize image to fit printer width while maintaining aspect ratio
            img.thumbnail(max_size, Image.LANCZOS)
            
            # Convert to black and white
            img = img.convert('1')
            
            # Save compressed image
            compressed_path = os.path.join(app.config['UPLOAD_FOLDER'], 'compressed_' + os.path.basename(image_path))
            img.save(compressed_path)
            return compressed_path
    except Exception as e:
        print(f"Image compression error: {e}")
        return image_path

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/print', methods=['POST'])
def print_content():
    try:
        # Check if text is provided
        if 'text' in request.form and request.form['text'].strip():
            text = request.form['text']
            cmd = f"python print.py --text '{text}' --font 'Arial.ttf' --font-size 30 "
            subprocess.run(cmd, shell=True, check=True)
            return jsonify({"success": True})

        # Check if image is provided
        if 'image' in request.files:
            image = request.files['image']
            if image.filename:
                # Save original image
                filename = secure_filename(image.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                image.save(filepath)
                
                # Compress image for printing
                compressed_filepath = compress_image(filepath)
                
                cmd = f"python print.py '{compressed_filepath}' --font 'Arial.ttf' --font-size 24 --align center"
                subprocess.run(cmd, shell=True, check=True)
                return jsonify({"success": True})

        return jsonify({"success": False, "message": "No content provided"})

    except subprocess.CalledProcessError as e:
        return jsonify({"success": False, "message": f"Print error: {str(e)}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Server error: {str(e)}"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)