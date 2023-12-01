import sys
import os
from aios import KnowledgePipelineEnvironment
directory = os.path.dirname(__file__)
sys.path.append(directory + '/../../../../src/component/')

from mail_environment import LocalEmail 
def init(env: KnowledgePipelineEnvironment, params: dict):
    return LocalEmail(env, params)