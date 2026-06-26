from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.util.concurrency import asyncio

load_dotenv()

from database.db_engine import database
from database.models import CategoryModel, PersonModel, PersonCategoryModel


async def parse_simple_xlsx(file_path):
    all_data = []
    for file_path in Path(file_path).glob('*.xlsx'):
        df = pd.read_excel(file_path)

        category_header = df.columns[1]

        df.columns = ['person', 'value']
        df['category'] = category_header
        all_data.append(df)

    final_df = pd.concat(all_data, ignore_index=True)

    def format_person(text):
        import re
        text = str(text).title()
        return re.sub(r'\bИ\b', 'и', text)

    def format_sentence(text):
        text = str(text)
        return text[0].upper() + text[1:]
    final_df['person'] = final_df['person'].apply(format_person)
    final_df['value'] = final_df['value'].apply(format_sentence)
    final_df['category'] = final_df['category'].apply(format_sentence)
    final_df = final_df.replace(to_replace=r'i', value='I', regex=True)

    async with database.session() as session:
        categories_cache = {}
        persons_cache = {}

        for _, row in final_df.iterrows():
            p_name = str(row['person']).strip()
            cat_name = str(row['category']).strip()
            val = str(row['value']).strip()

            if cat_name not in categories_cache:
                stmt = select(CategoryModel).where(CategoryModel.name == cat_name)
                cat = (await session.execute(stmt)).scalar_one_or_none()
                if not cat:
                    cat = CategoryModel(name=cat_name)
                    session.add(cat)
                    await session.flush()
                categories_cache[cat_name] = cat

            if p_name not in persons_cache:
                stmt = select(PersonModel).where(PersonModel.person_name == p_name)
                pers = (await session.execute(stmt)).scalar_one_or_none()
                if not pers:
                    pers = PersonModel(person_name=p_name)
                    session.add(pers)
                    await session.flush()
                persons_cache[p_name] = pers

            cat = categories_cache[cat_name]
            pers = persons_cache[p_name]

            link = PersonCategoryModel(
                person_id=pers.id,
                category_id=cat.id,
                value=val
            )
            session.add(link)


if __name__ == "__main__":
    asyncio.run(parse_simple_xlsx("../data/"))
    asyncio.run(database.close())