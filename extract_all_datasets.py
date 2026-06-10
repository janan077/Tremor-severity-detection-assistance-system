import os
import cv2
import numpy as np
from pathlib import Path
import sys

# Configuration
DATASETS_DIR = r"C:\Users\Joel Jose\Downloads\project\Janan Project\datasets"
FRAMES_DIR = r"C:\Users\Joel Jose\Downloads\project\Janan Project\frames_manual_4class"
CLASSES = ["essential_tremor", "normal_movements", "other", "parkinsons"]
FRAME_SKIP = 3  # Extract every 3rd frame
SEVERITY_LEVELS = ["high", "mid", "low"]

def get_frame_severity(frame_num, total_frames):
    """Classify frame as high, mid, or low severity based on position"""
    if total_frames < 30:
        return "low"
    first_third = total_frames // 3
    second_third = 2 * total_frames // 3
    
    if frame_num < first_third:
        return "high"
    elif frame_num < second_third:
        return "mid"
    else:
        return "low"

def extract_frames_from_video(video_path, class_name, stats):
    """Extract frames from a single video"""
    try:
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            stats["errors"].append(f"Cannot open: {Path(video_path).name}")
            return 0
        
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        extracted_count = 0
        
        frame_idx = 0
        frame_count = 0
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_idx % FRAME_SKIP == 0:
                # Resize frame
                frame = cv2.resize(frame, (224, 224))
                
                # Determine severity
                severity = get_frame_severity(frame_count, total_frames)
                
                # Create output directory
                output_dir = os.path.join(FRAMES_DIR, f"{class_name}_{severity}")
                os.makedirs(output_dir, exist_ok=True)
                
                # Save frame
                timestamp = Path(video_path).stem
                output_path = os.path.join(output_dir, f"{timestamp}_{frame_count}.jpg")
                cv2.imwrite(output_path, frame)
                extracted_count += 1
            
            frame_idx += 1
            frame_count += 1
        
        cap.release()
        stats["extracted"] += extracted_count
        stats["videos_success"] += 1
        return extracted_count
        
    except Exception as e:
        stats["errors"].append(f"{Path(video_path).name}: {str(e)}")
        return 0

def main():
    print("\n" + "="*70)
    print("BATCH FRAME EXTRACTION FROM DATASETS")
    print("="*70)
    
    stats = {
        "extracted": 0,
        "videos_total": 0,
        "videos_success": 0,
        "errors": []
    }
    
    # Process each class
    for class_name in CLASSES:
        class_path = os.path.join(DATASETS_DIR, class_name)
        
        if not os.path.exists(class_path):
            continue
        
        # Get all videos in class folder
        videos = [f for f in os.listdir(class_path) if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv'))]
        
        if not videos:
            continue
        
        print(f"\n{'='*70}")
        print(f"Processing: {class_name.upper()} ({len(videos)} videos)")
        print(f"{'='*70}")
        
        for idx, video_name in enumerate(videos, 1):
            video_path = os.path.join(class_path, video_name)
            stats["videos_total"] += 1
            
            print(f"[{idx}/{len(videos)}] Processing: {video_name[:50]}...", end=" ", flush=True)
            extracted = extract_frames_from_video(video_path, class_name, stats)
            if extracted > 0:
                print(f"✓ ({extracted} frames)")
    
    # Print summary
    print(f"\n{'='*70}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"Total videos processed: {stats['videos_total']}")
    print(f"Successful extractions: {stats['videos_success']}")
    print(f"Total frames extracted: {stats['extracted']}")
    
    if stats['errors']:
        print(f"\nErrors ({len(stats['errors'])}):")
        for err in stats['errors'][:10]:  # Show first 10 errors
            print(f"  - {err}")
    
    # Count final dataset size
    print(f"\n{'='*70}")
    print("UPDATED TRAINING DATASET SIZE:")
    print(f"{'='*70}")
    
    for class_name in CLASSES:
        for severity in SEVERITY_LEVELS:
            dir_name = f"{class_name}_{severity}"
            full_path = os.path.join(FRAMES_DIR, dir_name)
            if os.path.exists(full_path):
                count = len(os.listdir(full_path))
                if count > 0:
                    print(f"{dir_name}: {count}")
    
    total = sum(len(os.listdir(os.path.join(FRAMES_DIR, d))) 
                for d in os.listdir(FRAMES_DIR) 
                if os.path.isdir(os.path.join(FRAMES_DIR, d)))
    print(f"\nTOTAL FRAMES: {total}")

if __name__ == "__main__":
    main()
