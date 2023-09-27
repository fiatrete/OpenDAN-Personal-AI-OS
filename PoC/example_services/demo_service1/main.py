from typing import Union
from fastapi import FastAPI
from dotenv import load_dotenv
from googleapiclient.discovery import build
from llama_index import SimpleDirectoryReader, LLMPredictor, PromptHelper, GPTListIndex, ServiceContext
from youtube_transcript_api import YouTubeTranscriptApi
from urllib.parse import urlparse, parse_qs
import os
import re
import requests
import json
import logging
import sys
from langchain.chat_models import ChatOpenAI
import tweepy
import traceback
import json

logging.basicConfig(stream=sys.stdout, level=logging.INFO)
logging.getLogger().addHandler(logging.StreamHandler(stream=sys.stdout))

load_dotenv()
os.environ['OPENAI_API_KEY'] = os.getenv("JARVIS_OPENAI_API_KEY")

youtube_api_key = os.getenv("DEMO_YOUTUBE_API_KEY")
if youtube_api_key is not None and youtube_api_key != '':
    youtube_client = build('youtube', 'v3', developerKey=youtube_api_key)
youtube_video_max_result = 3
youtube_username_set = set()

# Configure prompt parameters and initialise helper
max_input_size = 4096
num_output = 512
max_chunk_overlap = 20
# llama_index
llm_predictor = LLMPredictor(llm=ChatOpenAI(
    temperature=0, model_name="gpt-3.5-turbo-0301", max_tokens=num_output))
prompt_helper = PromptHelper(max_input_size, num_output, max_chunk_overlap)

# twitter
twitter_consumer_key = os.getenv("DEMO_TWITTER_CONSUMER_KEY")
twitter_consumer_secret = os.getenv("DEMO_TWITTER_CONSUMER_SECRET")
twitter_access_token = os.getenv("DEMO_TWITTER_ACCESS_TOKEN")
twitter_access_token_secret = os.getenv("DEMO_TWITTER_ACCESS_TOKEN_SECRET")
twitter_username = os.getenv("DEMO_TWITTER_USERNAME")
twitter_api = tweepy.Client(
    consumer_key=twitter_consumer_key, consumer_secret=twitter_consumer_secret,
    access_token=twitter_access_token, access_token_secret=twitter_access_token_secret)

app = FastAPI()


@app.get(path="/videos/summary",
         summary="retrieve the summary of a youtube video based on its video_id, channel_id, username, and url")
async def videos_summary(video_id: Union[str, None] = None,
                         channel_id: Union[str, None] = None,
                         username: Union[str, None] = None,
                         url: Union[str, None] = None,
                         open_summary: Union[bool, None] = False):
    """
    - **video_id**: youtube video ID
    - **channel_id**: youtube channel Id
    - **username**: youtube username
    - **url**: youtube url
    """

    videos = {}
    if video_id is not None:
        videos = get_video_detail(video_id)
    if channel_id is not None:
        videos = get_channel_videos(channel_id)
    if username is not None:
        videos = get_user_videos(username)
    if url is not None:
        (value_type, value) = get_youtube_value(url)
        if value_type == "username":
            videos = get_user_videos(value)
        if value_type == "video_id":
            videos = get_video_detail(value)

    return gen_summary_for_videos(videos, open_summary)


@app.post(path="/timer-task/add", summary="add a task to retrieve summary information for the latest video")
async def timer_task_add(username: Union[str, None] = None,
                         url: Union[str, None] = None):
    if username is not None:
        youtube_username_set.add(username)
    if url is not None:
        (value_type, value) = get_youtube_value(url)
        if value_type == "username":
            youtube_username_set.add(value)

    return youtube_username_set


@app.get(path="/timer-tasks", summary="display the list of current tasks")
async def timer_task_list():
    return youtube_username_set


@app.post(path="/twitter/tweet_post",
          summary="post a tweet on Twitter: type=3 [success], type=0 [failed due to duplicate tweets], type=4 [other error]")
def twitter_post_tweet(content: str):
    try:
        response = twitter_api.create_tweet(text=content)
        return {
            "type": 3,
            "msg": "post tweet success",
            "tweet": {
                "id": response.data["id"],
                "text": response.data["text"],
                "url": f"https://twitter.com/{twitter_username}/status/{response.data['id']}"
            }
        }
    except Exception as e:
        if "duplicate content" in str(e):
            return {
                "type": 0,
                "msg": "duplicate tweets"
            }
        else:
            print(e)
            return {
                "type": 4,
                "msg": "other error"
            }


# get a list of youtube videos based on channel_id
def get_channel_videos(channel_id):
    res = youtube_client.channels().list(
        id=channel_id, part='contentDetails').execute()

    videos = {}

    for item in res['items']:
        playlist_id = item["contentDetails"]["relatedPlaylists"]["uploads"]
        res = youtube_client.playlistItems().list(
            playlistId=playlist_id, part='snippet', maxResults=youtube_video_max_result).execute()
        for video in res["items"]:
            video_id = video["snippet"]["resourceId"]["videoId"]
            video["videoId"] = video_id
            videos[video_id] = video

    return {k: v for k, v in sorted(videos.items(), key=lambda item: item[1]["snippet"]["publishedAt"], reverse=True)}


# retrieve the information of a youtube video based on its video_id
def get_video_detail(video_id):
    res = youtube_client.videos().list(id=video_id, part='snippet').execute()
    print(res)
    videos = {}
    for video in res["items"]:
        video["videoId"] = video_id
        videos[video_id] = video
    return videos


def get_user_videos(username):
    print(username)
    return get_user_videos_by_channel_id_list(get_channel_id_list_by_url(f"https://www.youtube.com/@{username}"))


# retrieve a list of channel IDs using a youtube url
def get_channel_id_list_by_url(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding
        html = response.text
        pattern = r'https://www.youtube.com/channel/(.*?)[?#"\']'
        text_list = re.findall(pattern, html)
        return set(text_list)
    except Exception as e:
        print(f"Error occurred: {e}")
        raise e


# retrieve a list of youtube videos based on a list of channels
def get_user_videos_by_channel_id_list(channel_id_list: set):
    try:
        user_videos = {}
        for channel_id in channel_id_list:
            print(channel_id)
            user_videos.update(get_channel_videos(channel_id))
        return {k: v for k, v in
                sorted(user_videos.items(), key=lambda item: item[1]["snippet"]["publishedAt"], reverse=True)}
    except Exception as e:
        print(f"Error occurred: {e}")
        raise e


# Generate a summary report using a list of videos
def gen_summary_for_videos(videos, open_summary):
    return {k: (lambda x: gen_summary_for_video(x, open_summary))(v) for k, v in videos.items()}


# Generate a summary report using a youtube video
def gen_summary_for_video(video, open_summary):
    video_id = video["videoId"]
    video_title = video["snippet"]["title"]
    video_published_at = video["snippet"]["publishedAt"]
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    summary = ""
    has_caption = None
    if open_summary is not None and open_summary == True:
        try:
            has_caption = False
            (inner_has_caption, dir_name,
             filename) = download_youtube_caption(video_id)
            has_caption = inner_has_caption
            if has_caption:
                summary = gen_summary_for_text(dir_name)
            else:
                summary = ""
        except Exception as e:
            print(e)
            traceback.print_exc()
            print(f"Error occurred: {e}")
    return {"title": video_title, "video_id": video_id, "published_at": video_published_at, "video_url": video_url,
            "has_caption": has_caption, "summary": summary}


# generate a summary report using a directory of documents
def gen_summary_for_text(dir_name: str):
    documents = SimpleDirectoryReader(dir_name).load_data()
    service_context = ServiceContext.from_defaults(
        llm_predictor=llm_predictor, prompt_helper=prompt_helper, chunk_size_limit=3584)
    index = GPTListIndex.from_documents(
        documents, service_context=service_context)
    query_engine = index.as_query_engine(response_mode="tree_summarize")
    summary = query_engine.query("Summarize the text, using English. ".strip())
    return str(summary)


def download_youtube_caption(video_id: str):
    file_name = "data/" + video_id + "/index.txt"
    if os.path.exists(file_name):
        return True, "data/" + video_id, file_name

    transcript = YouTubeTranscriptApi.get_transcripts(
        [video_id], languages=['en', 'zh-CN', 'zh', 'zh-Hans', 'zh-Hant'])
    transcript_json_array = json.loads('[]')
    if transcript:
        transcript_json_array = transcript[0][video_id]
    texts = [text['text'] for text in transcript_json_array]
    texts = list(filter(lambda x: len(x.strip()) > 0, texts))
    transcript_text = "\n".join(texts)
    return save_file(transcript_text, video_id)


def save_file(context: str, video_id: str):
    dir_name = "data/" + video_id
    if not os.path.exists(dir_name):
        os.makedirs(dir_name)
    filename = dir_name + "/index.txt"
    if len(context) > 0:
        with open(filename, "w") as file:
            file.write(context)
    return len(context) > 0, dir_name, filename


# retrieve a video ID or channel ID using a url
def get_youtube_value(url):
    parsed_url = urlparse(url)
    if 'youtube.com' in parsed_url.netloc:
        # check if it contains: youtube.com/@xx
        match = re.search(r'@([\d\w.-]+)\/?', parsed_url.path)
        if match:
            return "username", match.group(1)
        # check if it contains: youtube.com/watch?v=xx
        if '/watch' in parsed_url.path:
            query_params = parse_qs(parsed_url.query)
            if 'v' in query_params:
                return "video_id", query_params['v'][0]
    if 'youtu.be' in parsed_url.netloc:
        # check if it contains: https://youtu.be/xxx
        video_id = parsed_url.path[1:]
        if not "/" in video_id:
            return "video_id", video_id
    return "None", "None"
