import base64
from typing import List, Tuple

import cv2
import numpy as np
import moviepy.editor as mp


def precess_image(image):
    '''
    Graying and GaussianBlur
    :param image: The image matrix,np.array
    :return: The processed image matrix,np.array
    '''
    gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray_image = cv2.GaussianBlur(gray_image, (3, 3), 0)
    return gray_image


def abs_diff(pre_image, curr_image):
    '''
    Calculate absolute difference between pre_image and curr_image
    :param pre_image:The image in past frame,np.array
    :param curr_image:The image in current frame,np.array
    :return:
    '''
    gray_pre_image = precess_image(pre_image)
    gray_curr_image = precess_image(curr_image)
    diff = cv2.absdiff(gray_pre_image, gray_curr_image)
    res, diff = cv2.threshold(diff, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)
    cnt_diff = np.sum(np.sum(diff))
    return cnt_diff


def exponential_smoothing(alpha, s):
    '''
    Primary exponential smoothing
    :param alpha:  Smoothing factor,num
    :param s:      List of data,list
    :return:       List of data after smoothing,list
    '''
    s_temp = [s[0]]
    print(s_temp)
    for i in range(1, len(s), 1):
        s_temp.append(alpha * s[i - 1] + (1 - alpha) * s_temp[i - 1])
    return s_temp


def extract_frames(video_path: str, resize: Tuple[int, int] = None, smooth=False, alpha=0.07, window=25) -> List[str]:
    """Extract frames from video."""
    frames = []
    vidcap = cv2.VideoCapture(video_path)
    diff = []
    frm = 0
    pre_image = np.array([])
    cur_image = np.array([])

    while True:
        frm = frm + 1
        success, image = vidcap.read()
        if not success:
            break

        if frm == 1:
            pre_image = image
            cur_image = image
        else:
            pre_image = cur_image
            cur_image = image

        diff.append(abs_diff(pre_image, cur_image))

    if smooth:
        diff = exponential_smoothing(alpha, diff)

    diff = np.array(diff)
    mean = np.mean(diff)
    dev = np.std(diff)
    diff = (diff - mean) / dev

    idx = []
    for i, d in enumerate(diff):
        ub = len(diff) - 1
        lb = 0
        if not i - window // 2 < lb:
            lb = i - window // 2
        if not i + window // 2 > ub:
            ub = i + window // 2

        comp_window = diff[lb: ub]
        if d >= max(comp_window):
            idx.append(i)

    tmp = np.array(idx)
    tmp = tmp + 1
    idx = set(tmp.tolist())
    vidcap.release()

    vidcap = cv2.VideoCapture(video_path)
    i = 0
    frm = 0
    while vidcap.isOpened() and i < 10:
        frm = frm + 1
        success, image = vidcap.read()
        if not success:
            break
        if frm not in idx:
            continue
        if resize is not None:
            dest_width, dest_height = resize
            width, height = image.shape[:2]
            if width > dest_width or height > dest_height:
                width_rate = dest_width / width
                height_rate = dest_height / height
                rate = min(width_rate, height_rate)
                dest_width = int(width * rate)
                dest_height = int(height * rate)
                image = cv2.resize(image, (dest_width, dest_height), interpolation=cv2.INTER_AREA)
        _, buffer = cv2.imencode(".jpg", image)
        frames.append(f"data:image/jpg;base64,{base64.b64encode(buffer).decode('utf-8')}")
        i += 1
    vidcap.release()
    return frames


def extract_audio(video_path: str, audio_path: str):
    my_clip = mp.VideoFileClip(video_path)
    my_clip.audio.write_audiofile(audio_path)
