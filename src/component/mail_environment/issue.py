# define a knowledge base class
import json
import string
from aios_kernel import ComputeKernel, AIStorage, Environment, SimpleAIFunction, BaseAIAgent, AgentPrompt, AgentMsg
from knowledge import *
from .mail import MailStorage, Mail

class IssueState(Enum):
    Open = 1
    InProgress = 2
    Closed = 3

class IssueUpdateHistory:
    def __init__(self, source: str, changes: dict) -> None:
        self.source = source
        self.changes = changes
             

class Issue:
    def __init__(self) -> None:
        self.id = None
        self.summary = ""
        self.state = IssueState.Open
        self.source: str = None
        self.create_time: datetime = None
        self.deadline: datetime = None
        self.update_history = []
        self.children = []
        self.parent: ObjectID = None

    @classmethod
    def object_type(cls) -> ObjectType:
        return ObjectType.from_user_def_type_code(0)
        
    def to_prompt(self) -> str:
        prompt = {
            "id": self.id,
            "summary": self.summary,
            "state": self.state.name, 
            "deadline": self.deadline
        }
        return json.dumps(prompt)
    
    @classmethod
    def prompt_desc(cls) -> str:
        return '''a issue contains following fileds: {
            id: a guid string to identify a issue
            summary: summary of this issue
            state: state of this issue, will be one of [Open, InProgress, Closed], 
            deadline: if issue is not closed, deadline is the time to close this issue
        }
        '''
    
    def calculate_id(self) -> str:
        desc = {
            "summary": self.summary,
            "source": self.source,
            "create_time": self.create_time,
            "deadline": self.deadline,
            "parent": self.parent,
        }
        id = str(KnowledgeObject(Issue.object_type(), desc).calculate_id())
        self.id = id
        return id


class IssueStorage:
    def __init__(self, path: str, root: Issue=None) -> None:
        self.path = path
        if not os.path.exists(path):
            self.root = root
        else:
            self.root = json.load(open(path, "r"))

    def __flush(self):
        json.dump(self.root, open(self.path, "w"))

    def get_issue_by_id(self, id: str) -> Issue:
        self.root()

    def __get_issue_by_mail_in_subtree(self, root_issue: Issue, mail_id: str):
        if root_issue.source == mail_id:
            return root_issue
        if root_issue.children is None or len(root_issue.children) == 0:
            return None
        for child_issue in root_issue.children:
            this_issue = self.__get_issue_by_mail_in_subtree(child_issue, mail_id)
            if this_issue is not None:
                return this_issue
        return None

    def get_issue_by_mail(self, mail_storage: MailStorage, mail: Mail) -> Issue:
        if mail.reply_to is None:
            return self.root
        this_mail = mail_storage.get_mail_by_id(mail.reply_to)
        while True:
            issue = self.__get_issue_by_mail_in_subtree(self.root, this_mail.id)
            if issue is not None:
                return issue
            if this_mail.replay_to is None:
                return self.root
            this_mail = mail_storage.get_mail_by_id(this_mail.reply_to)

    
    def add_issue(self, source_id: str, issue: dict):
        parent_id = issue.get("parent")
        parent_issue = self.get_issue(parent_id)
        issue: Issue = issue
        issue["source"] = source_id
        issue.calculate_id()
        parent_issue.children.append(issue)
        self.__flush()

    def update_issue(self, source_id: str, update: dict):
        issue = self.get_issue(update["id"])
        source = update["source"]
        changes = {}
        for key, value in update.items():
            if key != "id" and key is not "source":
                changes[key] = {
                    "old": issue[key],
                    "new": value,
                }
                issue[key] = value
        issue.update_history.append(IssueUpdateHistory(source, changes))      

        self.__flush()
        

class IssueParserEnvironment(Environment):
    def __init__(self, env_id: str, storage: IssueStorage) -> None:
        super().__init__(env_id)
        self.storage = storage

        update_description = '''update issue with email object'''

        update_param = {
            "source_id": "update issue with which email object id", 
            "update_content": '''issue fileds to update, json format; 
                if id field exists, update the issue with the id;
                if id filed not exists, create a new issue with the content;
                other fileds in update_content will be updated to the issue;
            ''',
        }
        self.add_ai_function(SimpleAIFunction("update_issue", 
                                            update_description,
                                            self._update, 
                                            update_param))
        
    async def _update(self, source_id: str, update_content: str):
        update_issue = json.loads(update_content)
        issue_id = update_issue.get("id")
        if issue_id:
            self.storage.update_issue(source_id, update_issue)
        else:
            self.storage.add_issue(source_id, update_issue)



class IssueParser:
    def __init__(self, env: KnowledgePipelineEnvironment, config: dict):
        mail_path = string.Template(config["mail_path"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        issue_path = string.Template(config["issue_path"]).substitute(myai_dir=AIStorage.get_instance().get_myai_dir())
        config["path"] = issue_path
        
        self.env = env
        self.config = config
        self.mail_storage = MailStorage(mail_path)

        root_issue = None
        if "root_issue" in config:
            root_issue = Issue()
            root_issue.summary = config["root_issue"]
        self.issue_storage = IssueStorage(issue_path, root_issue)
        self.llm_env = IssueParserEnvironment("issue_parser", self.issue_storage)
    
    def get_path(self) -> str:
        return self.config["path"]

    async def parse(self, mail_id: ObjectID) -> str:
        mail_id = str(mail_id)
        mail = self.mail_storage.get_mail_by_id(mail_id)
        issue = self.issue_storage.get_issue_by_mail(self.mail_storage, mail)
        mail_str = mail.to_prompt()
        issue_str = issue.to_prompt()

        mail_desc = Mail.prompt_desc()
        issue_desc = Issue.prompt_desc()
        prompt = f'''I'll give a mail in json format, {mail_desc};
        and a issue in json format, {issue_desc};
        you should read this mail {mail_str}, see if this mail associated with this issue {issue_str};
        if this mail is about a new child issue of this issue, create a new issue with this mail, fill param update_content's summary field will mail content, set parent field with id of this issue; 
        if this mail will update this issue, set id filed to this issue, fill update_content param with new summary and new state with this mail content;
        then you should call update_issue function with source_id set to this mail id, and update_content in json format;
        if this mail is not associated with issue, you should ignore this mail without an function call;
        '''

        llm_result = await BaseAIAgent.do_llm_complection(self.llm_env, AgentPrompt(prompt), AgentMsg(), "gpt-4", 16000)
        return "update issue"

