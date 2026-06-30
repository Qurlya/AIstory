import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.util.concurrency import asyncio

from database.models import EraModel, Task19Model

load_dotenv()

from database.db_engine import database


async def parse_simple_xlsx(file_path):
    df = pd.read_excel(file_path)
    df.columns = ['question', 'standard', 'era1', 'era2']

    async with database.session() as session:
        eras_cache = {}
        for _, row in df.iterrows():
            question = str(row['question']).strip()
            standard = str(row['standard']).strip()
            for i in ['era1', 'era2']:
                currentEra = str(row[i]).strip()
                if currentEra == 'nan':
                    continue
                if currentEra not in eras_cache:
                    stmt = select(EraModel).where(EraModel.name == currentEra)
                    era = (await session.execute(stmt)).scalar_one_or_none()
                    if not era:
                        era = EraModel(name=currentEra)
                        session.add(era)
                        await session.flush()
                    eras_cache[currentEra] = era
                era = eras_cache[currentEra]
                link = Task19Model(
                    question = question,
                    standard = standard,
                    era_id = era.id,
                )
                session.add(link)

if __name__ == "__main__":
    asyncio.run(parse_simple_xlsx("../data/task_19.xlsx"))
    asyncio.run(database.close())