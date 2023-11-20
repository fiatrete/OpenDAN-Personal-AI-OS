# define a knowledge base class
import json
import string
from aios_kernel import AIStorage, Environment, SimpleAIFunction, CustomAIAgent, AgentPrompt, AgentMsg
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

    def to_json_dict(self) -> dict:
        return {
            "source": self.source,
            "changes": self.changes,
        }
    
    @classmethod
    def from_json_dict(cls, json_dict: dict) -> "IssueUpdateHistory":
        return IssueUpdateHistory(json_dict["source"], json_dict["changes"])

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
        self.parent: str = None

    def to_json_dict(self) -> dict:
        json_dict = {
            "id": self.id,
            "summary": self.summary,
            "state": self.state.name, 
            "create_time": self.create_time,
            "deadline": self.deadline,
            "source": self.source,
            "parent": self.parent,
        }
        if self.children is not None and len(self.children) > 0:
            json_dict["children"] = []
            for child in self.children:
                json_dict["children"].append(child.to_json_dict())
        if self.update_history is not None and len(self.update_history) > 0:
            json_dict["update_history"] = []
            for history in self.update_history:
                json_dict["update_history"].append(history.to_json_dict())
        
        return json_dict

    @classmethod
    def from_json_dict(cls, json_dict: dict) -> "Issue":
        issue = Issue()
        issue.id = json_dict["id"]
        issue.summary = json_dict["summary"]
        issue.state = IssueState[json_dict["state"]]
        issue.create_time = json_dict["create_time"]
        issue.deadline = json_dict["deadline"]
        issue.source = json_dict["source"]
        issue.parent = json_dict["parent"]
        if "children" in json_dict:
            issue.children = []
            for child_json_dict in json_dict["children"]:
                child = Issue.from_json_dict(child_json_dict)
                issue.children.append(child)
        if "update_history" in json_dict:
            issue.update_history = []
            for history_json_dict in json_dict["update_history"]:
                history = IssueUpdateHistory.from_json_dict(history_json_dict)
                issue.update_history.append(history)
        return issue
        

    @classmethod
    def object_type(cls) -> ObjectType:
        return ObjectType.from_user_def_type_code(0)
    
    def __to_desc(self, desc_list:[], recursion=None):
        desc = {
            "id": self.id,
            "summary": self.summary,
            "state": self.state.name, 
            "deadline": self.deadline,
        }
        desc_list.append(desc)
        if not recursion or not self.parent:
            return 
        else:
            parent = recursion.get_issue_by_id(self.parent)
            parent.__to_desc(desc_list, recursion)
        
    def to_prompt(self, recursion=None) -> str:
        desc_list = []
        self.__to_desc(desc_list, recursion)
        root = desc_list.pop()
        while len(desc_list) > 0:
            child = desc_list.pop()
            root["child"] = child
            root = child
        return json.dumps(root)
            
    
    @classmethod
    def prompt_desc(cls) -> str:
        return '''a issue contains following fileds: {
            id: a guid string to identify a issue
            summary: summary of this issue
            state: state of this issue, will be one of [Open, InProgress, Closed], 
            deadline: if issue is not closed, deadline is the time to close this issue,
            children: child issues of this issue
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
            self.__flush()
        else:
            root_dict = json.load(open(path, "r", encoding="utf-8"))
            self.root = Issue.from_json_dict(root_dict)

    def __flush(self):
        json.dump(self.root.to_json_dict(), open(self.path, "w", encoding="utf-8"), ensure_ascii=False, indent=4)

    def __get_issue_by_id_in_subtree(self, root_issue: Issue, id: str):
        if root_issue.id == id:
            return root_issue
        if root_issue.children is None or len(root_issue.children) == 0:
            return None
        for child_issue in root_issue.children:
            this_issue = self.__get_issue_by_id_in_subtree(child_issue, id)
            if this_issue is not None:
                return this_issue
        return None

    def get_issue_by_id(self, id: str) -> Issue:
        return self.__get_issue_by_id_in_subtree(self.root, id)

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

    
    def add_issue(self, source_id: str, parent_id: str, summary: str):
        parent_issue = self.get_issue_by_id(parent_id)
        issue = Issue()
        issue.summary = summary
        issue.source = source_id
        issue.parent = parent_id
        issue.calculate_id()
        parent_issue.children.append(issue)
        self.__flush()
        return issue

    def update_issue(self, source_id: str, issue_id: str, update: dict):
        issue = self.get_issue_by_id(issue_id)
        changes = {}
        for key, value in update.items():
            changes[key] = {
                "old": issue[key],
                "new": value,
            }
            issue.__dict__[key] = value
        issue.update_history.append(IssueUpdateHistory(source_id, changes))      

        self.__flush()
        return issue
        

class IssueParserEnvironment(Environment):
    def __init__(self, env_id: str, storage: IssueStorage) -> None:
        super().__init__(env_id)
        self.storage = storage

        create_description = '''create a new issue'''
        create_param = {
            "mail_id": "new issue with which email object id", 
            "issue_id": '''new issue's parent issue id''',
            "summary": '''new issue's summary''',
        }
        self.add_ai_function(SimpleAIFunction("create_issue", 
                                            create_description,
                                            self._create, 
                                            create_param))
        
        update_description = '''update an existing issue'''
        update_param = {
            "mail_id": "update issue with which email object id", 
            "issue_id": '''update issue's id''',
            "summary": '''issue's new summary''',
        }
        self.add_ai_function(SimpleAIFunction("update_issue", 
                                            update_description,
                                            self._update, 
                                            update_param))
        
    async def _create(self, mail_id: str, issue_id: str, summary: str):
        issue = self.storage.add_issue(mail_id, issue_id, summary)
        return issue.id
            
    async def _update(self, mail_id: str, issue_id: str, summary: str):
        update = {}
        update["summary"] = summary
        issue = self.storage.update_issue(mail_id, issue_id, update)
        return issue.id


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
            root_config = config["root_issue"]
            root_issue = IssueParser.__load_issue_config(root_config)
            IssueParser.__calac_issue_id(root_issue)

        self.issue_storage = IssueStorage(issue_path, root_issue)
        self.llm_env = IssueParserEnvironment("issue_parser", self.issue_storage)

    @classmethod
    def __load_issue_config(cls, issue_config: dict) -> Issue: 
        issue = Issue()
        issue.summary = issue_config["summary"]
        if "children" in issue_config:
            for child_config in issue_config["children"]:
                child_issue = cls.__load_issue_config(child_config)
                issue.children.append(child_issue)
        return issue
    
    @classmethod
    def __calac_issue_id(cls, issue: Issue):
        issue_id = issue.calculate_id()
        for child in issue.children:
            child.parent = issue_id
            cls.__calac_issue_id(child)
        
    
    def get_path(self) -> str:
        return self.config["path"]

    async def parse(self, mail_id: ObjectID) -> str:
        mail_id = str(mail_id)
        mail = self.mail_storage.get_mail_by_id(mail_id)
        issue = self.issue_storage.get_issue_by_mail(self.mail_storage, mail)
        mail_str = mail.to_prompt()
        issue_str = issue.to_prompt(recursion=self.issue_storage)

        mail_desc = Mail.prompt_desc()
        issue_desc = Issue.prompt_desc()
        prompt = AgentPrompt()
        prompt.system_message = {"role": "system", "content": f'''
        I'm a CEO of a company named 巴克云; You'ar my assistant, and you should help me to manage my issues. Issues is a concept in software development of this company, but I use it to manage my work.
        I'll give you a mail in json format, {mail_desc};
        and a issue in json format, {issue_desc}. Read mail's fileds and issue's fileds, and decide if you should update the issue or create a new issue with this mail.
        Then call the function create_issue or update_issue.
        if this mail is not associated with issue, you should ignore this mail.'''}
        
        prompt.append(AgentPrompt(f'''Mail is {mail_str}, issue is {issue_str}. Answer me the function's return value or None if igonred.               
        '''))

        llm_result = await CustomAIAgent("issue parser", "gpt-4-1106-preview", 4000).do_llm_complection(prompt, env=self.llm_env)
        return "update issue"

