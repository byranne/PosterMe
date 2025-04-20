import numpy as np
import faiss
import json
import os

def load_poster_data():
    """Load and validate poster data from the JSON file."""
    try:
        with open('data.json', 'r') as f:
            data = json.load(f)
            
        if not isinstance(data, dict) or 'posters' not in data:
            raise ValueError("Invalid data format: expected a dictionary with 'posters' key")
            
        posters = data['posters']
        if not posters:
            raise ValueError("No posters found in the data")
            
        # Validate each poster has the required fields
        for poster in posters:
            if 'pose_features' not in poster:
                raise ValueError(f"Poster {poster.get('id', 'unknown')} missing pose_features")
                
        return data
    except FileNotFoundError:
        raise FileNotFoundError("data.json file not found")
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format in data.json")

def build_index(poster_data):
    """Build a FAISS index from the poster features."""
    posters = poster_data['posters']
    features = []
    
    for poster in posters:
        pose_features = poster['pose_features']
        if not isinstance(pose_features, list):
            raise ValueError(f"Invalid pose_features format for poster {poster.get('id', 'unknown')}")
        features.append(pose_features)
    
    features = np.array(features, dtype=np.float32)
    dimension = len(features[0])
    
    index = faiss.IndexFlatL2(dimension)
    index.add(features)
    
    return index

# Load the poster database and build the index
poster_data = load_poster_data()
index = build_index(poster_data)

def get_similar_posters(query_features, k=5):
    """Find k most similar posters based on pose features."""
    try:
        # Ensure query_features is in the right format
        query_features = np.array(query_features, dtype=np.float32).reshape(1, -1)
        
        if query_features.shape[1] != index.d:
            raise ValueError(f"Query features dimension ({query_features.shape[1]}) does not match index dimension ({index.d})")
        
        # Search the index
        distances, indices = index.search(query_features, min(k, len(poster_data['posters'])))
        
        # Get the similar posters
        similar_posters = []
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            poster = poster_data['posters'][idx]
            similar_posters.append({
                'id': poster.get('id', idx),
                'title': poster.get('title', f'Poster {idx}'),
                'image_url': poster.get('image_url', ''),
                'similarity': float(1.0 / (1.0 + distance))  # Convert distance to similarity score
            })
        
        return similar_posters
    except Exception as e:
        print(f"Error in get_similar_posters: {str(e)}")
        return [] 