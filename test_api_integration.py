"""
Test the full backend API integration with proper confidence scores
"""
import requests
import cv2
import numpy as np
from pathlib import Path
import os

# Start test
print("="*70)
print("FULL API INTEGRATION TEST")
print("="*70)

API_URL = "http://localhost:8000"
UPLOAD_URL = f"{API_URL}/classify/video"

def test_video_upload(video_path, expected_label):
    """Upload video and get prediction from backend"""
    if not os.path.exists(video_path):
        print(f"  ✗ File not found: {video_path}")
        return None
    
    with open(video_path, 'rb') as f:
        files = {'file': (Path(video_path).name, f, 'video/mp4')}
        try:
            response = requests.post(UPLOAD_URL, files=files, timeout=30)
            if response.status_code == 200:
                result = response.json()
                prediction = result.get('prediction', 'unknown')
                confidence = result.get('confidence', 0)
                
                match = "✓" if prediction == expected_label else "✗"
                print(f"  {match} {Path(video_path).name}")
                print(f"     Expected: {expected_label}, Got: {prediction} ({confidence:.1%})")
                
                if 'validation_result' in result:
                    print(f"     Validation: {result['validation_result']}")
                return result
            else:
                print(f"  ✗ Request failed: {response.status_code}")
                try:
                    print(f"     Response: {response.json()}")
                except:
                    print(f"     Response: {response.text[:200]}")
                return None
        except requests.exceptions.ConnectionError:
            print(f"  ✗ Cannot connect to backend at {API_URL}")
            print(f"     Make sure backend is running: python backend/main.py")
            return None
        except Exception as e:
            print(f"  ✗ Request error: {e}")
            return None

def test_detection():
    """Test detection on sample videos"""
    
    print("\n🔌 Testing Backend API Integration...\n")
    print("Note: Backend must be running on http://localhost:8000")
    print("Start it with: python backend/main.py\n")
    
    # Test essential tremor
    print("ESSENTIAL_TREMOR:")
    et_videos = list(Path("datasets/essential_tremor").glob("*.mp4"))[:2]
    for video in et_videos:
        test_video_upload(str(video), "essential_tremor")
    
    # Test parkinsons
    print("\nPARKINSONS:")
    pd_videos = list(Path("datasets/parkinsons").glob("*.mp4"))[:2]
    for video in pd_videos:
        test_video_upload(str(video), "parkinsons")
    
    # Test normal
    print("\nNORMAL_MOVEMENTS:")
    normal_videos = list(Path("datasets/normal_movements").glob("*.mp4"))[:2]
    for video in normal_videos:
        test_video_upload(str(video), "normal_movements")
    
    # Test other
    print("\nOTHER:")
    other_videos = list(Path("datasets/other").glob("*.mp4"))[:2]
    for video in other_videos:
        test_video_upload(str(video), "other")
    
    print("\n" + "="*70)
    print("API TEST COMPLETE")
    print("="*70)

if __name__ == "__main__":
    test_detection()
