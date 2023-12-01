import sys
import os
from aios import *
directory = os.path.dirname(__file__)

sys.path.append(directory + '/../../../../src/component/')
from mail_environment import IssueParser

def init(env: KnowledgePipelineEnvironment, params: dict):
    return IssueParser(env, params)