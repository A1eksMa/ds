# 09 — `ds update`: синхронизировать `source.json` с базой

`source.json` объявляет `old_junk_field`, который ни разу не встречается в загружаемых данных,
а `email`/`phone` приходят явочным порядком, не будучи объявленными вовсе. `ds update`
приводит файл в соответствие: убирает показатель без единой транзакции, добавляет показатели
с данными как есть (без типа/флагов — их выставляет человек).

## Запуск

```bash
bash run.sh /tmp/ex09
```

```
--- source.json до update ---
{ "name": "CRM", "key_label": "customer_id", "labels": [{ "name": "old_junk_field", ... }] }

--- ds update: old_junk_field никогда не грузился, email/phone пришли явочным порядком ---
added: email, phone
removed: old_junk_field

--- source.json после update ---
{
  "name": "CRM",
  "key_label": "customer_id",
  "labels": [
    { "name": "email" },
    { "name": "phone" }
  ]
}
```

Запись показателя, у которого данные всё ещё есть, `update` не трогает — вручную выставленные
`type`/`archive`/`publish`/`p`/`description` сохраняются как есть.
