from peewee import SqliteDatabase, TimestampField, Model
from src.config import DB_PATH

db = SqliteDatabase(DB_PATH)


class BaseModel(Model):
    class Meta:
        database = db


class FlightTelemetry(BaseModel):
    data_timestamp = TimestampField()
