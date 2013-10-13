import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import config as appConfig

engine = create_engine(appConfig.database+'://'+appConfig.db_user+':'+appConfig.db_password+'@'+appConfig.db_host+'/'+appConfig.db_database_name)

Session = sessionmaker(bind=engine)

# create a Session
session = Session()