from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_cors import CORS
from google.cloud import storage

from os.path import basename

from PIL import Image, ExifTags

import os
import subprocess
import logging

storage_client = storage.Client()
bucket_conversions = storage_client.get_bucket('marsha-prd-converted')

app = Flask(__name__, static_folder="./app/dist/static", template_folder="./app/dist")

app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config["SERVER_NAME"] = "heictojpg.site"

CORS(app)


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path == "manifest.json":
        return send_from_directory('./app/dist/', 'manifest.json')
    if path == "favicon.ico":
        return send_from_directory('./app/dist/', 'favicon.ico')
    if path == "sitemap.xml":
        return send_from_directory('./app/dist/', 'sitemap.xml')
    if path == "robots.txt":
        return send_from_directory('./app/dist/', 'robots.txt')
    return render_template("index.html")


@app.route('/url', methods=['GET'])
def url():
    return jsonify({'msg': 'http://onvictinitor.com/afu.php?zoneid=3015098'}), 200


@app.route('/convert', methods=['POST'])
def convert():
    folder = '/tmp'

    f = request.files.get('photo')
    filename = f.filename
    filename_no_ext = os.path.splitext(basename(filename))[0]

    f.save(os.path.join(folder, f.filename))

    final_uploaded_filepath = os.path.join(folder, filename)
    final_converted_filepath = os.path.join(folder, filename_no_ext + '.jpg')

    bash_command = "tifig " + final_uploaded_filepath + " -o " + final_converted_filepath
    process = subprocess.Popen(bash_command.split(), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, close_fds=True)
    output_conversion = process.stdout.read()
    output, error = process.communicate()

    image = Image.open(final_converted_filepath)
    os.remove(final_uploaded_filepath)
    os.remove(final_converted_filepath)
    for orientation in ExifTags.TAGS.keys():
        if ExifTags.TAGS[orientation] == 'Orientation':
            break
    exif = dict(image._getexif().items())

    if exif[orientation] == 3:
        image = image.rotate(180, expand=True)
    elif exif[orientation] == 6:
        image = image.rotate(270, expand=True)
    elif exif[orientation] == 8:
        image = image.rotate(90, expand=True)
    image.save(final_converted_filepath, quality=70, optimize=True)

    blob = bucket_conversions.blob(filename_no_ext + '.jpg')
    blob.upload_from_filename(final_converted_filepath)
    blob.make_public()

    # os.remove(final_converted_filepath)

    logging.warning(error)
    logging.warning(blob)

    if error is not None and len(str(error)) > 0:
        return jsonify(str(error)), 411
    elif output_conversion is not None and len(str(output_conversion)) > 0:
        return jsonify(str(output_conversion)), 411
    else:
        return jsonify({'url': blob.public_url, 'filename': filename_no_ext + '.jpg'}), 200


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5050))
    app.run(host='0.0.0.0', port=port)
