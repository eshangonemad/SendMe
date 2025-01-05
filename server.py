from flask import Flask, request, render_template
import os
import subprocess

app = Flask(__name__)
image_path = ''
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

blocked_ips = ['', ''] 

@app.before_request
def block_ip():
    """Block requests from specified IPs."""
    client_ip = request.remote_addr
    if client_ip in blocked_ips:
        return f"Access denied for IP: {client_ip}, Please appeal in <a href='https://hackclub.slack.com/archives/C08671G51RS'>https://hackclub.slack.com/archives/C08671G51RS</a>", 403

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

@app.route('/postbox', methods=['POST'])
def postbox():
    textgr = request.form.get('textgr', 'false').lower() == 'true'
    text = request.form.get('text', '')
    client_ip = request.remote_addr  

    image = request.files.get('image')
    global image_path
    if image:
        filename = os.path.basename(image.filename)  
        if not filename:
            return "Invalid image filename.", 400
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        image.save(image_path)
        print(f"Image saved at {image_path}")

    if textgr:
        if not text.strip():
            return "No text provided.", 400
        try:
            
            print(f"IP: {client_ip}, Text processed: {text}")
            cmd = f'python3 print.py --text "{text}" --font-size 30 -darker -d "X5h-F1FF"'
            subprocess.run(cmd, shell=True, check=True)
            print(f"IP: {client_ip}, Text processed: {text}")
            return f"Text processed with text: {text}"
        except subprocess.CalledProcessError as e:
            print(f"Error during text processing: {e}")
            return "Error during text processing.", 500
    else:
        if not image_path:
            return "No image provided.", 400
        try:
            
            print(f"IP: {client_ip}, Image path: {image_path}")
            cmd = ['python3', 'print.py', image_path, '-d', 'X5h-F1FF']
            subprocess.run(cmd, check=True)
            print(f"IP: {client_ip}, Image path: {image_path}")
            return "Image received and processed."
        except subprocess.CalledProcessError as e:
            print(f"Error during image processing: {e}")
            return "Error during image processing.", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80, debug=True)
