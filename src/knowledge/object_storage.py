# import RDB LargeBinary
from sqlalchemy import Column, String, LargeBinary, create_engine, sessionmaker, pickle
from .object import KnowledgeObject

# implement object storage with RDB
# define object storage table
class ObjectStorageTable(Base):
    __tablename__ = 'object_storage'
    id = Column(String, primary_key=True)
    parent = Column(String, nullable=True)
    object = Column(LargeBinary, nullable=False)

    def __init__(self, id, parent, object): # pylint: disable=redefined-builtin
        self.id = id
        self.parent = parent
        self.object = object

# define object storage class
class ObjectStorage:
    async def __init__(self, db_url):
        self.engine = create_engine(db_url)
        self.session = sessionmaker(bind=self.engine)() # pylint: disable=not-callable

    async def get(self, id) -> [KnowledgeObject, KnowledgeObject]:
        obj = self.session.query(ObjectStorageTable).filter(ObjectStorageTable.id == id).first()
        if obj is None:
            return None
        return pickle.loads(obj.object)
    
    # define insert method
    async def insert(self, object, parent): # pylint: disable=redefined-builtin
        obj = ObjectStorageTable(id, parent, pickle.dumps(object))
        