from flask import Flask, render_template, jsonify
import boto3
from botocore.exceptions import NoCredentialsError
import os
from apscheduler.schedulers.background import BackgroundScheduler
import time

app = Flask(__name__)

# AWS S3 setup
S3_BUCKET = 'website-image-serve'
s3_client = boto3.client('s3')

def generate_presigned_url(object_name, expiration=3600):
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': S3_BUCKET, 'Key': object_name},
                                                    ExpiresIn=expiration)
    except NoCredentialsError:
        return None
    return response

@app.route('/')
def index():
    # List images in the S3 bucket
    response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
    images = []
    if 'Contents' in response:
        for item in response['Contents']:
            image_url = generate_presigned_url(item['Key'])
            images.append({'url': image_url, 'name': item['Key']})
    return render_template('index.html', images=images)

scheduler = BackgroundScheduler()

def fetch_images_from_s3():
    print("Fetching images from S3")
    # Logic to refresh or re-poll the images

scheduler.add_job(fetch_images_from_s3, 'interval', weeks=1)
scheduler.start()

if __name__ == '__main__':
    app.run(debug=True)
