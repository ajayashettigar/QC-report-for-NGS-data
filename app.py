from flask import Flask, request, render_template, send_from_directory, redirect, url_for
from werkzeug.utils import secure_filename
import os
import subprocess
import shutil
import zipfile

app = Flask(__name__)

# Define the folders
UPLOAD_FOLDER = 'raw_data'
FASTQC_REPORT_FOLDER = 'fastqc_report'
MULTIQC_REPORT_FOLDER = 'multiqc_report'
DEMO_DATA_FOLDER = 'demo_data'  # Folder for demo data
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(FASTQC_REPORT_FOLDER, exist_ok=True)
os.makedirs(MULTIQC_REPORT_FOLDER, exist_ok=True)
os.makedirs(DEMO_DATA_FOLDER, exist_ok=True)

# Utility function to clear directory contents
def clear_directory(folder):
    if os.path.exists(folder):
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

# Route for the initial page
@app.route('/')
def initial_page():
    # Clear contents of the directories
    clear_directory('raw_data')
    clear_directory('fastqc_report')
    clear_directory('multiqc_report')
    clear_directory('result')

    # Render the initial page template
    return render_template('index.html')

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        read_type = request.form.get('read_type')
        if read_type == 'demo':
            # Use demo data
            return redirect(url_for('process_demo_data'))
        else:
            # Redirect to the upload_files route
            return redirect(url_for('upload_files', read_type=read_type))
    
    # Display the read type selection form
    return render_template('index.html')

@app.route('/upload_files', methods=['GET', 'POST'])
def upload_files():
    read_type = request.args.get('read_type')
    
    if request.method == 'POST':
        files = request.files.getlist('files')  # Get list of uploaded files
        for file in files:
            if file and (file.filename.endswith('.fastq') or file.filename.endswith('.fastq.gz')):
                file_path = os.path.join(UPLOAD_FOLDER, file.filename)
                file.save(file_path)
        
        # Run FastQC on the uploaded files
        command = f"fastqc {UPLOAD_FOLDER}/*.fastq* -o {FASTQC_REPORT_FOLDER}"
        subprocess.run(command, shell=True)

        # Redirect to the reports page after FastQC completes
        return redirect(url_for('list_reports', read_type=read_type))

    # Display the upload form
    return '''
    <!doctype html>
    <title>Upload FASTQ Files</title>
    <h1>Upload Multiple FASTQ Files</h1>
    <form method="POST" enctype="multipart/form-data">
      <input type="file" name="files" multiple>
      <input type="submit" value="Upload">
    </form>
    '''


@app.route('/process_demo_data')
def process_demo_data():
    # Copy demo files to the raw_data folder if they are not already present
    demo_files = ['alb1_1.fastq.gz', 'alb1_2.fastq.gz']
    for demo_file in demo_files:
        demo_file_path = os.path.join(DEMO_DATA_FOLDER, demo_file)
        target_path = os.path.join(UPLOAD_FOLDER, demo_file)
        if not os.path.exists(target_path):
            shutil.copy(demo_file_path, target_path)
    
    # Run FastQC on demo files
    command = f"fastqc {UPLOAD_FOLDER}/*.fastq* -o {FASTQC_REPORT_FOLDER}"
    subprocess.run(command, shell=True)
    
    # Redirect to the reports page after FastQC completes
    return redirect(url_for('list_reports', read_type='demo'))

@app.route('/reports', methods=['GET', 'POST'])
def list_reports():
    # List all the .html files in the fastqc_report folder
    report_files = [f for f in os.listdir(FASTQC_REPORT_FOLDER) if f.endswith('.html')]
    read_type = request.args.get('read_type')
    
    if request.method == 'POST':
        if request.form.get('multiqc') == 'yes':
            # Run MultiQC
            command = f"multiqc {FASTQC_REPORT_FOLDER} -o {MULTIQC_REPORT_FOLDER}"
            subprocess.run(command, shell=True)
            # Find the generated MultiQC report
            multiqc_files = [f for f in os.listdir(MULTIQC_REPORT_FOLDER) if f.endswith('.html')]
            if multiqc_files:
                # Render the MultiQC report template with the first report found
                return render_template('multiqc_report.html', 
                                    multiqc_report=multiqc_files[0], 
                                    read_type=read_type,
                                    show_all_reports=True)
            else:
                # Handle the case where no MultiQC report was found
                return "MultiQC report not found. Please check your configuration.", 404

        elif request.form.get('multiqc') == 'no':
            # Redirect to allow the user to download all files 
            return render_template('all_reports.html', reports=report_files, read_type=read_type)

    # Render FastQC reports page
    return render_template('reports.html', reports=report_files, read_type=read_type)

@app.route('/view_multiqc_report/<filename>')
def view_multiqc_report(filename):
    # Define the path to the MultiQC report folder
    multiqc_report_path = os.path.join(MULTIQC_REPORT_FOLDER, filename)
    
    # Check if the file exists
    if os.path.exists(multiqc_report_path):
        # Serve the file
        return send_from_directory(MULTIQC_REPORT_FOLDER, filename)
    else:
        # Return a 404 error if the file is not found
        os.abort(404)


@app.route('/download_all')
def download_all():
    zip_filename = 'raw_data_quality_reports.zip'
    zip_path = os.path.join('result', zip_filename)
    
    # Ensure the 'result' directory exists
    os.makedirs('result', exist_ok=True)
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for folder in [FASTQC_REPORT_FOLDER, MULTIQC_REPORT_FOLDER]:
            if os.path.exists(folder):
                for root, _, files in os.walk(folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Store the file in the zip archive with a relative path
                        zipf.write(file_path, os.path.relpath(file_path, os.path.join(folder, '..')))
    
    # Return the zip file as an attachment
    return send_from_directory('result', zip_filename, as_attachment=True)



if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5003)

