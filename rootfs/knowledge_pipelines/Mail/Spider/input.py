import sys
import os
from knowledge import KnowledgePipelineEnvironment
directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../../../src/component/')

from mail_environment import EmailSpider

def init(env: KnowledgePipelineEnvironment, params: dict):
    return EmailSpider(env, params)