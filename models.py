# models.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.database import Base
from datetime import datetime, timezone

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password = Column(String)  # hashé plus tard
    gender = Column(String)    # "M" ou "F"

    locations = relationship("Location", back_populates="user")

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    latitude = Column(Float)
    longitude = Column(Float)

    user = relationship("User", back_populates="locations")

class Crossing(Base):
    __tablename__ = "crossings"

    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"))
    user2_id = Column(Integer, ForeignKey("users.id"))
    distance = Column(Float)  # distance en mètres
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))

class Like(Base):
    __tablename__ = "likes"

    id = Column(Integer, primary_key=True, index=True)
    liker_id = Column(Integer, ForeignKey("users.id"))
    liked_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))

class Match(Base):
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    user1_id = Column(Integer, ForeignKey("users.id"))
    user2_id = Column(Integer, ForeignKey("users.id"))
    timestamp = Column(DateTime, default=datetime.now(timezone.utc))