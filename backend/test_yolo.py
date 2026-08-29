import torch.hub
import os
import traceback
try:
    if hasattr(torch.hub, '_validate_not_a_forked_repo'):
        torch.hub._validate_not_a_forked_repo = lambda a, b, c: True
    yolo_model = torch.hub.load('ultralytics/yolov5', 'custom', path='models/best.pt', force_reload=False, trust_repo=True)
    print('YOLO LOADED')
except Exception as e:
    traceback.print_exc()
