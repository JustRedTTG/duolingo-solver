import os

from sqlalchemy import create_engine, Column, Integer, String

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from dotenv import load_dotenv

load_dotenv()

Base = declarative_base()

engine = create_engine(os.environ.get('DATABASE_CONNECTION_STRING'), echo=True)


class QuestionAnswer(Base):
    __tablename__ = 'question_answers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    question = Column(String)
    answer = Column(String)


Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
