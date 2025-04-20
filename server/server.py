from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
import base64
import numpy as np
from PIL import Image
import io
import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import solutions
from mediapipe.framework.formats import landmark_pb2
import json
import faiss
import requests
from io import BytesIO
from rembg import remove
import os
from pose_analysis import analyze_pose
from poster_retrieval import get_similar_posters

app = Flask(__name__)
# Enable CORS with specific configuration
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:5173", "http://localhost:5174"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "Accept"],
        "expose_headers": ["Content-Type"],
        "supports_credentials": True,
        "max_age": 3600
    }
})

@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:5173')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

# Function for drawing landmarks
def draw_landmarks_on_image(rgb_image, detection_result):
    pose_landmarks_list = detection_result.pose_landmarks
    annotated_image = np.copy(rgb_image)

    # Loop through the detected poses to visualize.
    for idx in range(len(pose_landmarks_list)):
        pose_landmarks = pose_landmarks_list[idx]

        # Draw the pose landmarks.
        pose_landmarks_proto = landmark_pb2.NormalizedLandmarkList()
        pose_landmarks_proto.landmark.extend([
            landmark_pb2.NormalizedLandmark(x=landmark.x, y=landmark.y, z=landmark.z) for landmark in pose_landmarks
        ])
        solutions.drawing_utils.draw_landmarks(
            annotated_image,
            pose_landmarks_proto,
            solutions.pose.POSE_CONNECTIONS,
            solutions.drawing_styles.get_default_pose_landmarks_style())
    return annotated_image

def findVector2(image):
    '''
    Takes in an image and outputs the detection results
    '''
    model_path = os.path.join(current_dir, 'models', 'pose_landmarker_full.task')

    BaseOptions = mp.tasks.BaseOptions
    PoseLandmarker = mp.tasks.vision.PoseLandmarker
    PoseLandmarkerOptions = mp.tasks.vision.PoseLandmarkerOptions
    VisionRunningMode = mp.tasks.vision.RunningMode

    options = PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=model_path),
        running_mode=VisionRunningMode.IMAGE)

    with PoseLandmarker.create_from_options(options) as landmarker:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=image)
        detection_result = landmarker.detect(mp_image)
        return detection_result

def normalize(result):
    result = result.pose_world_landmarks[0]
    finalResult = []
    for i in result:
        arr = []
        arr.append(i.x)
        arr.append(i.y)
        arr.append(i.z)
        arr.append(1 if i.visibility >= 0.7 else 0)
        finalResult.append(arr)
    return finalResult

def findSimilarVectors(img, k):
    # Img is normalized pose landmark vector
    data_path = os.path.join(current_dir, 'data.json')
    with open(data_path, "r") as file:
        data = json.load(file)

    titles = [item['title'] for item in data]
    urls = [item['poster_url'] for item in data]

    embeddings = []
    for item in data:
        data_item = item.get('data', None)
        if data_item is not None:
            flattened_item = np.array(data_item).flatten()
            filtered = np.delete(flattened_item, np.arange(3, len(flattened_item), 4))
            embeddings.append(filtered)

    embeddings = np.array(embeddings, dtype='float32')
    d = embeddings.shape[1]

    index = faiss.IndexFlatL2(d)
    index.add(embeddings)

    img = np.array(img).flatten()
    xq = img
    xq = np.delete(xq, np.arange(3, len(xq), 4))
    xq = np.array(xq, dtype='float32').reshape(1, -1)

    D, I = index.search(xq, k)
    resultArr = []
    for i in I[0]:
        resultArr.append(data[i])

    return resultArr

def similarKeypoints(arr1, arr2):
    similar = []
    for i in range(len(arr1)):
        if arr1[i][3] == 1 and arr2[i][3] == 1:
            similar.append(i)
    return similar

def normalizePoseLandmarks(result):
    result = result.pose_landmarks[0]
    finalResult = []
    for i in result:
        arr = []
        arr.append(i.x)
        arr.append(i.y)
        arr.append(i.z)
        arr.append(1 if i.visibility >= 0.7 else 0)
        finalResult.append(arr)
    return finalResult

def findTranslation(img, poster_url):
    response = requests.get(poster_url)
    poster = Image.open(BytesIO(response.content))
    img = np.array(img)
    poster = np.array(poster)
    posterArr = findVector2(poster)
    if not posterArr.pose_landmarks:
        print('NO LANDMARKS')
        return None, None, None
    
    imgArr = normalizePoseLandmarks(findVector2(img))
    posterArr = normalizePoseLandmarks(findVector2(poster))

    similarity = similarKeypoints(imgArr, posterArr)

    img_pil = Image.fromarray(img)
    i_width, i_height = img_pil.size
    i_keypoints = [(imgArr[i][0]*i_width, imgArr[i][1]*i_height) for i in [0,11,12]]

    poster_pil = Image.fromarray(poster)
    p_width, p_height = poster_pil.size
    p_keypoints = [(posterArr[i][0]*p_width, posterArr[i][1]*p_height) for i in [0,11,12]]

    return i_keypoints, p_keypoints, similarity

@app.route('/process-image', methods=['POST'])
def process_image():
    try:
        data = request.json
        if not data or 'image' not in data:
            return jsonify({'error': 'No image data provided'}), 400

        # Decode base64 image
        image_data = data['image'].split(',')[1]  # Remove the data:image/jpeg;base64, prefix
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        image_np = np.array(image)

        # Analyze pose
        pose_results = analyze_pose(image_np)
        
        # Get similar posters
        similar_posters = get_similar_posters(pose_results)
        
        return jsonify({
            'success': True,
            'similar_posters': similar_posters
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 