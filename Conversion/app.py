import os
import boto3
from flask import Flask, request, jsonify, render_template, redirect
from werkzeug.utils import secure_filename
import pypandoc
from botocore.exceptions import NoCredentialsError

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['CONVERTED_FOLDER'] = 'converted'
app.config['ALLOWED_EXTENSIONS'] = {'txt', 'doc', 'docx', 'pdf'}
app.config['S3_BUCKET'] = 'flaskconversion'
app.config['S3_REGION'] = 'us-east-1'

s3 = boto3.client('s3')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/convert', methods=['POST'])
def convert_file():
    if 'file' not in request.files:
        return jsonify(error='No file part'), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify(error='No selected file'), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)

        try:
            output_filename = filename.rsplit('.', 1)[0] + '.docx' if filename.endswith('.pdf') else filename.rsplit('.', 1)[0] + '.pdf'
            output_path = os.path.join(app.config['CONVERTED_FOLDER'], output_filename)
            pypandoc.convert_file(file_path, 'docx' if filename.endswith('.pdf') else 'pdf', outputfile=output_path)

            # Upload the converted file to S3
            s3.upload_file(output_path, app.config['S3_BUCKET'], output_filename)

            # Generate the S3 file URL
            s3_file_url = f"https://{app.config['S3_BUCKET']}.s3.{app.config['S3_REGION']}.amazonaws.com/{output_filename}"

            return jsonify(message='File converted successfully', output_file=s3_file_url), 200
        except Exception as e:
            return jsonify(error=str(e)), 500
    else:
        return jsonify(error='File not allowed'), 400

@app.route('/download/<filename>')
def download_file(filename):
    try:
        url = s3.generate_presigned_url('get_object',
                                        Params={'Bucket': app.config['S3_BUCKET'], 'Key': filename},
                                        ExpiresIn=3600)
        return redirect(url)
    except NoCredentialsError:
        return jsonify(error="Credentials not available"), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
