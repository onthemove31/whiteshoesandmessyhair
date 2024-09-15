from flask import Flask, render_template, send_file, jsonify
import boto3
from botocore.exceptions import NoCredentialsError
import os
from PIL import Image
import io

app = Flask(__name__)

# AWS S3 setup
S3_BUCKET = 'website-image-serve'
S3_REGION = os.getenv('AWS_DEFAULT_REGION', 'us-east-1')

# Initialize S3 client using environment variables
s3_client = boto3.client(
    's3',
    region_name=S3_REGION,
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

def generate_presigned_url(object_name, expiration=3600 * 24 * 7):  # 1 week expiration
    """Generate a pre-signed URL to share an S3 object"""
    try:
        response = s3_client.generate_presigned_url('get_object',
                                                    Params={'Bucket': S3_BUCKET, 'Key': object_name},
                                                    ExpiresIn=expiration)
    except NoCredentialsError:
        return None
    return response

def optimize_image(image_bytes, max_width=None, max_height=None):
    """Resize and compress PNG image while maintaining aspect ratio"""
    image = Image.open(io.BytesIO(image_bytes))

    # Preserve the aspect ratio during resizing
    if max_width or max_height:
        image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)  # Resize maintaining aspect ratio

    # Optimize the image
    output = io.BytesIO()
    image.save(output, format='PNG', optimize=True)  # Save as PNG, preserving transparency
    output.seek(0)
    
    return output

@app.route('/')
def index():
    """List all images in the S3 bucket and generate pre-signed URLs"""
    try:
        response = s3_client.list_objects_v2(Bucket=S3_BUCKET)
        images = []
        if 'Contents' in response:
            for item in response['Contents']:
                key = item['Key']
                
                # Filter out folders (keys that end with '/')
                if key.endswith('/'):
                    continue
                
                # Optionally, filter for specific image formats (png, jpg, jpeg, etc.)
                if not (key.endswith('.png') or key.endswith('.jpg') or key.endswith('.jpeg')):
                    continue

                # Generate a pre-signed URL for the full-size image
                fullsize_url = generate_presigned_url(key)
                
                # Generate an optimized version for the gallery (this is served from /image/<image_name>)
                optimized_url = f"/image/{key}"  # This will hit the Flask optimization route

                images.append({
                    'fullsize_url': fullsize_url,  # For the modal (actual full-size image)
                    'optimized_url': optimized_url,  # For the gallery (optimized image)
                    'name': key  # Image key (file name)
                })
        return render_template('index.html', images=images)
    except Exception as e:
        return f"Error fetching images: {e}", 500
    
@app.route('/image/<path:image_name>')
def serve_image(image_name):
    """Serve the requested image from S3"""
    print(f"Request for image: {image_name}")  # Debugging log
    try:
        # Get the image object from S3
        image_obj = s3_client.get_object(Bucket=S3_BUCKET, Key=image_name)
        image_bytes = image_obj['Body'].read()

        # Optimize image (resize and compress while maintaining aspect ratio)
        optimized_image = optimize_image(image_bytes, max_width=800, max_height=600)

        # Return the optimized image
        return send_file(optimized_image, mimetype='image/png')  # Use 'image/png' for PNG format

    except Exception as e:
        print(f"Error retrieving image {image_name}: {e}")
        return "Image not found", 404

if __name__ == '__main__':
    app.run(debug=True)
