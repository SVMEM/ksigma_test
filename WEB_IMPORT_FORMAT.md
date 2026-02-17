# Web admin import format

Required columns/keys:
- `subject_code`
- `topic_name`
- `question_text`
- `options`
- `correct`

Optional:
- `subject_name`
- `subtopic_name`
- `qtype` (`single` or `multi`, default `single`)
- `explanation`

## CSV example

```csv
subject_code,subject_name,topic_name,subtopic_name,qtype,question_text,explanation,options,correct
biology,Биология,Клетка,Органоиды,single,Главная функция митохондрий?,Энергетический обмен,"A) Синтез белка|B) Выработка АТФ|C) Хранение воды",B
biology,Биология,Генетика,,multi,Выберите азотистые основания ДНК,Проверьте состав,"A) Аденин|B) Тимин|C) Урацил|D) Гуанин","A,B,D"
```

## JSON example

```json
[
  {
    "subject_code": "biology",
    "subject_name": "Биология",
    "topic_name": "Клетка",
    "subtopic_name": "Органоиды",
    "qtype": "single",
    "question_text": "Главная функция митохондрий?",
    "explanation": "Энергетический обмен",
    "options": ["Синтез белка", "Выработка АТФ", "Хранение воды"],
    "correct": "B"
  },
  {
    "subject_code": "biology",
    "topic_name": "Генетика",
    "qtype": "multi",
    "question_text": "Выберите азотистые основания ДНК",
    "options": {
      "A": "Аденин",
      "B": "Тимин",
      "C": "Урацил",
      "D": "Гуанин"
    },
    "correct": ["A", "B", "D"]
  }
]
```
