"""Validated, atomic local keyword records shared by CLI and web."""
import json
import os
import tempfile
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'config/keywords.json'


def validate_rules(rules):
    if not isinstance(rules, list) or len(rules) > 100:
        raise ValueError('키워드는 최대 100개까지 저장할 수 있습니다.')
    result, seen = [], set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError('키워드 형식이 올바르지 않습니다.')
        keyword, weight = rule.get('keyword'), rule.get('weight')
        if not isinstance(keyword, str) or not 1 <= len(keyword.strip()) <= 60 or any(ord(c) < 32 for c in keyword):
            raise ValueError('키워드는 1~60자의 텍스트여야 합니다.')
        keyword = keyword.strip()
        if type(weight) is not int or not -100 <= weight <= 100:
            raise ValueError('가중치는 -100~100 사이 정수여야 합니다.')
        if keyword.casefold() in seen:
            raise ValueError('동일한 키워드는 한 번만 등록해 주세요.')
        seen.add(keyword.casefold())
        result.append({'keyword': keyword, 'weight': weight})
    return result


def load_rules():
    data = json.loads(PATH.read_text(encoding='utf-8'))
    return validate_rules(data.get('rules', [{'keyword': k, 'weight': 1} for k in data.get('keywords', [])]))


def save_rules(rules):
    rules = validate_rules(rules)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=PATH.parent, suffix='.tmp', delete=False) as f:
        temporary = f.name
        json.dump({'rules': rules}, f, ensure_ascii=False, indent=2)
    try:
        os.replace(temporary, PATH)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return rules


def keyword_score(title, rules):
    title = title.casefold()
    return sum(rule['weight'] for rule in rules if rule['keyword'].casefold() in title)
