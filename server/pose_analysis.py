import mediapipe as mp
import numpy as np
import cv2

mp_pose = mp.solutions.pose
pose = mp_pose.Pose(static_image_mode=True, model_complexity=2, min_detection_confidence=0.5)

def normalize_landmarks(landmarks):
    """Normalize landmarks to be invariant to scale and translation."""
    points = np.array([[lm.x, lm.y, lm.z] for lm in landmarks.landmark])
    
    # Center the points
    centroid = np.mean(points, axis=0)
    points = points - centroid
    
    # Scale to unit size
    scale = np.sqrt(np.sum(points ** 2))
    if scale > 0:
        points = points / scale
    
    return points.flatten()

def analyze_pose(image):
    """Analyze pose in the given image and return normalized landmarks."""
    # Convert BGR to RGB
    image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    
    # Process the image
    results = pose.process(image_rgb)
    
    if not results.pose_landmarks:
        raise ValueError("No pose detected in the image")
    
    # Normalize landmarks
    normalized_landmarks = normalize_landmarks(results.pose_landmarks)
    
    return normalized_landmarks 