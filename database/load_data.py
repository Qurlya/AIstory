from io import BytesIO
import pandas as pd
from sqlalchemy import select

from database.models import EraModel
from .db_engine import database
from .models.event import EventModel
from .models.culture import CultureModel, CultureType


async def parse_events_datafile(file, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(file, sheet_name=sheet_name, engine='openpyxl')
    df['Difficulty'] = df['Difficulty'].fillna(0).astype('int64')
    df = df.dropna()

    return df


async def parse_culture_datafile(file, sheet_name: str) -> pd.DataFrame:
    df = pd.read_excel(file, sheet_name=sheet_name, engine='openpyxl')

    def capitalize_first(value):
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            return normalized
        return normalized[0].upper() + normalized[1:]

    return df.applymap(capitalize_first)


async def load_events_to_db(file_: BytesIO, sheet_='Лист1'):
    result = await parse_events_datafile(file_, sheet_)
    count: int = 0
    current_eras = {}

    async with database.session() as session:
        temp_db_eras = await session.execute(select(EraModel))
        db_eras = temp_db_eras.all()
        for _, row in result.iterrows():
            try:
                era_name = row['Era']
                if era_name not in db_eras and era_name not in current_eras:
                    new_era = EraModel(
                        name=era_name,
                    )
                    flush_era = await session.merge(new_era)
                    await session.flush()
                    current_eras[era_name] = flush_era.id

                event_to_add = EventModel(
                    name=row['Questions'],
                    date=row['Answer'],
                    difficulty=row['Difficulty'],
                    era_id=flush_era.id,
                )
                session.add(event_to_add)
                await session.commit()
                await session.refresh(event_to_add)
                count += 1

            except Exception as e:
                print(f"load_events_to_db err: {str(e)}")
                await session.rollback()
                continue

    return count


async def load_culture_to_db(file_: BytesIO, sheet_='Лист1'):
    result = await parse_culture_datafile(file_, sheet_)
    count: int = 0

    async with database.session() as session:
        for _, row in result.iterrows():
            try:
                culture_to_add = CultureModel(
                    img_name=row['photo'],
                    build_name=row['building'],
                    date=row['year'],
                    author=row['creator'] if pd.notna(row['creator']) else None,
                    king=row['ruler'],
                    style=row['style'],
                    city=row['city'],
                    type=CultureType(row['type'].strip().lower()),
                )
                session.add(culture_to_add)
                await session.commit()
                count += 1

            except Exception as e:
                print(f"load_culture_to_db err: {str(e)}")
                await session.rollback()
                continue

    return count
