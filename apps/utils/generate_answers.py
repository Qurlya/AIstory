import random
from typing import Dict, List
import re
import logging

logger = logging.getLogger(__name__)
MAX_GENERATION_ATTEMPTS = 30

def _stringify_date(date_value) -> str:
    if hasattr(date_value, "strftime"):
        return date_value.strftime("%Y-%m-%d")
    return str(date_value)


def _is_full_date(date_value) -> bool:
    return bool(re.match(r'^\d{4}-\d{2}-\d{2}', _stringify_date(date_value).strip()))


def _generate_full_date_options(correct_date, all_questions: List[Dict]) -> List[str]:
    same_type_dates = []
    for q in all_questions:
        date_value = q.get('date')
        if _is_full_date(date_value) and _stringify_date(date_value).strip() != _stringify_date(correct_date).strip():
            same_type_dates.append(date_value)

    unique_dates = list(dict.fromkeys(same_type_dates))
    random.shuffle(unique_dates)
    wrong_answers = unique_dates[:3]
    all_answers = [normalize_date_format(correct_date)] + [normalize_date_format(d) for d in wrong_answers]
    random.shuffle(all_answers)
    return all_answers


def extract_year_or_interval(date_str: str) -> tuple:
    date_str = _stringify_date(date_str).strip()

    if '.' in date_str and not date_str.startswith('00'):
        parts = date_str.split('.')
        if len(parts) == 2:
            return ('interval', parts[0].strip(), parts[1].strip())

    elif '-' in date_str and not date_str.startswith('00'):
        parts = date_str.split('-')
        if len(parts) == 2:
            return ('interval', parts[0].strip(), parts[1].strip())

    date_pattern = r'^\d{4}-\d{2}-\d{2}'
    if re.match(date_pattern, date_str):
        year = date_str.split('-')[0]
        return ('year', year)

    return ('year', date_str)


def normalize_date_format(date_str: str) -> str:
    date_str = _stringify_date(date_str).strip()

    full_date_match = re.match(r'^(\d{4})-(\d{2})-(\d{2})', date_str)
    if full_date_match:
        year, month, day = full_date_match.groups()
        return f"{day}.{month}.{year}"

    pretty_date_match = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', date_str)
    if pretty_date_match:
        return date_str

    date_type, *parts = extract_year_or_interval(date_str)

    if date_type == 'year':
        return str(parts[0])
    else:
        start, end = parts
        if '.' in date_str:
            return f"{start}.{end}"
        else:
            return f"{start}-{end}"


async def generate_smart_answers(correct_question: Dict, all_questions: List[Dict]) -> List[str]:
    correct_date = correct_question['date']

    if _is_full_date(correct_date):
        return _generate_full_date_options(correct_date, all_questions)

    correct_type, *correct_parts = extract_year_or_interval(correct_date)

    same_type_dates = []
    for q in all_questions:
        q_type, *_ = extract_year_or_interval(q['date'])
        if q_type == correct_type:
            same_type_dates.append(q['date'])

    same_type_dates = list(set(same_type_dates))
    same_type_dates = [d for d in same_type_dates if d != correct_date]

    if correct_type == 'year':
        correct_year = correct_parts[0]

        year_dates = []
        for date_str in same_type_dates:
            q_type, *parts = extract_year_or_interval(date_str)
            if q_type == 'year':
                try:
                    year_dates.append(int(parts[0]))
                except ValueError:
                    continue

        year_dates.sort()

        try:
            correct_year_num = int(correct_year)
        except ValueError:
            correct_year_num = 0

        wrong_answers = []

        if year_dates:
            diffs = [abs(year - correct_year_num) for year in year_dates]
            sorted_years = [year for _, year in sorted(zip(diffs, year_dates))]

            for year in sorted_years:
                if str(year) != correct_year and str(year) not in wrong_answers:
                    wrong_answers.append(str(year))
                    if len(wrong_answers) >= 2:
                        break

        attempts = 0
        while len(wrong_answers) < 2 and attempts < MAX_GENERATION_ATTEMPTS:
            attempts += 1
            if year_dates:
                random_year = random.choice(year_dates)
            else:
                random_year = correct_year_num + random.randint(1, 100)

            if str(random_year) != correct_year and str(random_year) not in wrong_answers:
                wrong_answers.append(str(random_year))
        if len(wrong_answers) < 2:
            logger.warning(
                "Достигнут лимит генерации неправильных ответов (year). correct_date=%s wrong_answers=%s",
                correct_date,
                wrong_answers,
            )
            fallback_year = correct_year_num + 77
            while len(wrong_answers) < 2:
                candidate = str(fallback_year)
                if candidate != correct_year and candidate not in wrong_answers:
                    wrong_answers.append(candidate)
                fallback_year += 17

    else:
        start_year, end_year = correct_parts
        try:
            start_num = int(start_year) if start_year.isdigit() else 0
        except AttributeError:
            start_num = 0

        try:
            end_num = int(end_year) if end_year.isdigit() else 0
        except AttributeError:
            end_num = 0

        intervals = []
        for date_str in same_type_dates:
            q_type, *parts = extract_year_or_interval(date_str)
            if q_type == 'interval':
                intervals.append(date_str)

        wrong_answers = []

        if len(intervals) >= 2:
            selected_intervals = random.sample(intervals, 2)
            wrong_answers.extend(selected_intervals)
        elif intervals:
            wrong_answers.extend(intervals)

        attempts = 0
        while len(wrong_answers) < 2 and attempts < MAX_GENERATION_ATTEMPTS:
            attempts += 1
            offset = random.randint(10, 50)
            new_start = start_num + offset
            new_end = end_num + offset

            separator = '.' if '.' in correct_date else '-'
            new_interval = f"{new_start}{separator}{new_end}"

            if new_interval != correct_date and new_interval not in wrong_answers:
                wrong_answers.append(new_interval)
        if len(wrong_answers) < 2:
            logger.warning(
                "Достигнут лимит генерации неправильных ответов (interval). correct_date=%s wrong_answers=%s",
                correct_date,
                wrong_answers,
            )
            separator = '.' if '.' in correct_date else '-'
            offset = 60
            while len(wrong_answers) < 2:
                fallback_interval = f"{start_num + offset}{separator}{end_num + offset}"
                if fallback_interval != correct_date and fallback_interval not in wrong_answers:
                    wrong_answers.append(fallback_interval)
                offset += 10

    if same_type_dates:
        random_wrong = random.choice(same_type_dates)
        attempts = 0
        while (random_wrong == correct_date or random_wrong in wrong_answers) and attempts < MAX_GENERATION_ATTEMPTS:
            attempts += 1
            random_wrong = random.choice(same_type_dates)
        if random_wrong == correct_date or random_wrong in wrong_answers:
            logger.warning(
                "Достигнут лимит выбора случайного неправильного ответа. correct_date=%s wrong_answers=%s",
                correct_date,
                wrong_answers,
            )
            random_wrong = next((d for d in same_type_dates if d != correct_date and d not in wrong_answers), None)
            if not random_wrong:
                random_wrong = f"{correct_parts[0]}_fallback"
        wrong_answers.append(random_wrong)
    else:
        if correct_type == 'year':
            offset = random.randint(10, 100)
            random_wrong = str(int(correct_parts[0]) + offset) if correct_parts[0].isdigit() else str(offset)
        else:
            offset = random.randint(10, 50)
            separator = '.' if '.' in correct_date else '-'
            start_val = int(correct_parts[0]) if correct_parts[0].isdigit() else 0
            end_val = int(correct_parts[1]) if correct_parts[1].isdigit() else 0
            random_wrong = f"{start_val + offset}{separator}{end_val + offset}"
        wrong_answers.append(random_wrong)

    wrong_answers = wrong_answers[:3]

    all_answers = [normalize_date_format(correct_date)] + [normalize_date_format(d) for d in wrong_answers]

    random.shuffle(all_answers)

    return all_answers


async def generate_smart_answers_event_date(correct_question: Dict, all_questions: List[Dict]) -> List[str]:
    correct_date = correct_question['date']

    if _is_full_date(correct_date):
        return _generate_full_date_options(correct_date, all_questions)

    correct_type, *correct_parts = extract_year_or_interval(correct_date)

    same_type_dates = []
    for q in all_questions:
        q_type, *_ = extract_year_or_interval(q['date'])
        if q_type == correct_type:
            same_type_dates.append(q['date'])

    same_type_dates = list(set(same_type_dates))
    same_type_dates = [d for d in same_type_dates if d != correct_date]

    if correct_type == 'year':
        correct_year = correct_parts[0]

        year_dates = []
        for date_str in same_type_dates:
            q_type, *parts = extract_year_or_interval(date_str)
            if q_type == 'year':
                try:
                    year_dates.append(int(parts[0]))
                except ValueError:
                    continue

        year_dates.sort()

        try:
            correct_year_num = int(correct_year)
        except ValueError:
            correct_year_num = 0

        wrong_answers = []

        if year_dates:
            diffs = [abs(year - correct_year_num) for year in year_dates]
            sorted_years = [year for _, year in sorted(zip(diffs, year_dates))]

            for year in sorted_years:
                if str(year) != correct_year and str(year) not in wrong_answers:
                    wrong_answers.append(str(year))
                    if len(wrong_answers) >= 2:
                        break

        attempts = 0
        while len(wrong_answers) < 2 and attempts < MAX_GENERATION_ATTEMPTS:
            attempts += 1
            if year_dates:
                random_year = random.choice(year_dates)
            else:
                random_year = correct_year_num + random.randint(1, 100)

            if str(random_year) != correct_year and str(random_year) not in wrong_answers:
                wrong_answers.append(str(random_year))
        if len(wrong_answers) < 2:
            logger.warning(
                "Достигнут лимит генерации неправильных ответов (year/event_date). correct_date=%s wrong_answers=%s",
                correct_date,
                wrong_answers,
            )
            fallback_year = correct_year_num + 77
            while len(wrong_answers) < 2:
                candidate = str(fallback_year)
                if candidate != correct_year and candidate not in wrong_answers:
                    wrong_answers.append(candidate)
                fallback_year += 17

    else:
        start_year, end_year = correct_parts
        try:
            start_num = int(start_year) if start_year.isdigit() else 0
        except AttributeError:
            start_num = 0

        try:
            end_num = int(end_year) if end_year.isdigit() else 0
        except AttributeError:
            end_num = 0

        intervals = []
        for date_str in same_type_dates:
            q_type, *parts = extract_year_or_interval(date_str)
            if q_type == 'interval':
                intervals.append(date_str)

        wrong_answers = []

        if len(intervals) >= 2:
            selected_intervals = random.sample(intervals, 2)
            wrong_answers.extend(selected_intervals)
        elif intervals:
            wrong_answers.extend(intervals)

        attempts = 0
        while len(wrong_answers) < 2 and attempts < MAX_GENERATION_ATTEMPTS:
            attempts += 1
            offset = random.randint(10, 50)
            new_start = start_num + offset
            new_end = end_num + offset

            separator = '.' if '.' in correct_date else '-'
            new_interval = f"{new_start}{separator}{new_end}"

            if new_interval != correct_date and new_interval not in wrong_answers:
                wrong_answers.append(new_interval)
        if len(wrong_answers) < 2:
            logger.warning(
                "Достигнут лимит генерации неправильных ответов (interval/event_date). correct_date=%s wrong_answers=%s",
                correct_date,
                wrong_answers,
            )
            separator = '.' if '.' in correct_date else '-'
            offset = 60
            while len(wrong_answers) < 2:
                fallback_interval = f"{start_num + offset}{separator}{end_num + offset}"
                if fallback_interval != correct_date and fallback_interval not in wrong_answers:
                    wrong_answers.append(fallback_interval)
                offset += 10

    if same_type_dates:
        random_wrong = random.choice(same_type_dates)
        attempts = 0
        while (random_wrong == correct_date or random_wrong in wrong_answers) and attempts < MAX_GENERATION_ATTEMPTS:
            attempts += 1
            random_wrong = random.choice(same_type_dates)
        if random_wrong == correct_date or random_wrong in wrong_answers:
            logger.warning(
                "Достигнут лимит выбора случайного неправильного ответа (event_date). correct_date=%s wrong_answers=%s",
                correct_date,
                wrong_answers,
            )
            random_wrong = next((d for d in same_type_dates if d != correct_date and d not in wrong_answers), None)
            if not random_wrong:
                random_wrong = f"{correct_parts[0]}_fallback"
        wrong_answers.append(random_wrong)
    else:
        if correct_type == 'year':
            offset = random.randint(10, 100)
            random_wrong = str(int(correct_parts[0]) + offset) if correct_parts[0].isdigit() else str(offset)
        else:
            offset = random.randint(10, 50)
            separator = '.' if '.' in correct_date else '-'
            start_val = int(correct_parts[0]) if correct_parts[0].isdigit() else 0
            end_val = int(correct_parts[1]) if correct_parts[1].isdigit() else 0
            random_wrong = f"{start_val + offset}{separator}{end_val + offset}"
        wrong_answers.append(random_wrong)

    wrong_answers = wrong_answers[:3]

    all_answers = [normalize_date_format(correct_date)] + [normalize_date_format(d) for d in wrong_answers]

    random.shuffle(all_answers)

    return all_answers

async def generate_smart_answers_date_event(correct_answer: Dict, all_answers: List[Dict]) -> List[str]:
    correct_event = correct_answer['name']
    all_events = list(set(q['name'] for q in all_answers if 'name' in q))
    
    wrong_events = [event for event in all_events if event != correct_event]
    random.shuffle(wrong_events)
    wrong_answers = wrong_events[:3]
    
    all_options = [correct_event] + wrong_answers
    random.shuffle(all_options)
    return all_options
