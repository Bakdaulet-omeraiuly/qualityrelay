# QualityRelay 17.1 — Collective Intelligence: от архитектуры к измеримому сотрудничеству агентов

**Статус:** исследовательский технический план (не заявление о реализованном улучшении)
**Дата:** 30 октября 2026 г.
**Автор:** Bakdaulet
**Область:** *только* коллективное взаимодействие AI-агентов, адаптивный сбор доказательств, Value of Information и честный научный benchmark.
**Базовый проект:** локально проверенная структура `QualityRelay_17_SAFE_MESH/` (версия 17.0).
**Вне области этого документа:** новый GPU training, Isaac Sim, полный рефакторинг цифрового завода, новая внешняя камера, полный NVIDIA stack. Их можно использовать как источники сигналов, но они не доказывают коллективный интеллект.

> **Integration note (31 Oct, added alongside this document, not part of the original):**
> `qualityrelay17/factory.py`'s `collective_fusion` and `structured_request_lite` policies
> are a minimal, tested Gate-A slice of what this document specifies -- see
> `docs/research/COLLECTIVE_17_1_INTEGRATION_NOTE.md` for exactly what's built, what maps to
> which baseline below, and what of this plan remains future work. This document is kept
> verbatim as the full research plan; nothing below was edited.

---

## 0. Executive decision

**Главный приоритет QualityRelay 17.1 — доказать или опровергнуть, что структурированное взаимодействие специалистов при распределённой информации улучшает качество и стоимость решений по сравнению с сильными одиночными и rule-based baseline.**

Не «запустить 21 LLM» и не «добавить красивые чаты». Требуется **исполняемая экспериментальная среда**, в которой:

1. у разных агентов действительно разные разрешённые фрагменты данных;
2. агент может выявить, какой информации не хватает, и **запросить** её у другого агента или физического инспекционного инструмента;
3. приход нового проверенного свидетельства меняет оценку риска или обоснование решения;
4. следующий тест выбирается **по ожидаемому сокращению потерь с учётом цены/времени**, а не предустановленным `if`;
5. все запросы, сообщения, обновления гипотез и результаты инспекций логируются;
6. независимая система безопасности имеет право блокировать небезопасное действие независимо от мнения LLM;
7. измеримые результаты сравниваются с baseline при **равных информационных и экономических условиях**.

**Научная гипотеза — не доказанный факт.** Если хорошее правило или один агент решает задачу дешевле и безопаснее, это честный отрицательный результат.

---

## 1. Что показал аудит реального QualityRelay 17.0

Аудит выполнен по существующим файлам исходного проекта, а не только по описаниям архитектуры.

| Файл 17.0 | Что уже есть | Чего нет для доказательства collective capability |
|---|---|---|
| `qualityrelay17/roles.py` | Реестр 21 специализированной роли; выбор релевантных ролей по простым условиям | Исполняемой сети запросов/ответов, проверяемого обмена новыми фактами |
| `qualityrelay17/nebius.py` | Опциональный Nebius LLM review с ограниченным циклом tools; код допускает живой API только при явном включении | Совместного multi-turn протокола между независимыми агентами, подтверждённой live оценки |
| `qualityrelay17/agent_tools.py` | Allowlist разрешённых tools и серверная проверка прав | Контролируемого протокола peer requests, стоимости сообщений, разрешений на новый сенсорный тест |
| `qualityrelay17/ledger.py`, `lineage.py` | Локальный реестр и происхождение доказательств | Полного графа дискуссий и причинных зависимостей между запросами и решениями |
| `qualityrelay17/vder.py` | Корректный **reference** для бинарного expected decision loss / inspection ranking при заданных sensitivity, specificity | Последовательного обновления по реальным ответам, зависимых сенсоров, многокритериального бюджета |
| `qualityrelay17/factory.py` | Воспроизводимый генератор синтетических Slot/Tab, наблюдений камер, сетевых сбоев | Реальных агентских действий: четыре политики задаются заранее и не меняются через переговоры |
| `qualityrelay17/benchmark.py` | Paired seeds, сценарные bootstrap интервалы для 4 presets | Базовых моделей `single-agent`, `vote`, `structured collaboration`, **adaptive** VOI и ablations |
| `qualityrelay17/safe_mesh.py` | Safety-first правила, проверка источников, калибровки, подписи и freshness, `PASS_REVIEW` вместо прямого hardware PASS | Применения результатов коллективного протокола к решению при неизменных safety restrictions |

### Зафиксированный отрицательный baseline (17.0)

Источник: `examples/results/BENCHMARK_30x1000_SYNTHETIC.json`.

- 30 синтетических seed × 1000 виртуальных деталей = 30 000 экземпляров;
- `conservative_rules`: 106 unsafe PASS, 0.3533%, mean cost 2424.93 на 1000 объектов;
- `safe_mesh_reference`: **тоже 106 unsafe PASS**, mean cost **2462.87**;
- парная разница `safe_mesh_reference - conservative_rules` по cost: **+37.93** (95% cluster bootstrap приблизительно [+36.43, +39.37] в пределах этой симуляции).

Причина: `safe_mesh_reference` принимает то же решение HOLD, что и `conservative_rules`, но добавляет стоимость проверки при расхождении камер. Это **не проверка способности LLM сотрудничать**.

**Ограничение интерпретации:** все значения относятся только к искусственному генератору и условной стоимости; они не доказывают эффективность/неэффективность реального производства. Нулевую разницу unsafe PASS нельзя трактовать как доказательство эквивалентности реальных рисков.

---

## 2. Что говорит актуальная научная литература

### 2.1 Distributed information часто ломает коллективное рассуждение

**Li, Naito, Shirado, ICML 2026, «Systematic Failures in Collective Reasoning under Distributed Information in Multi-Agent LLMs».** HiddenBench содержит 65 задач с асимметрично распределёнными сведениями; в исследовании средняя точность групп при распределённой информации — **30.1%**, а отдельного агента при доступе ко всей информации — **80.7%**. Авторы выделяют преждевременную сходимость на общих фактах и недостаточный поиск **уникальной** информации; структурированный протокол коммуникации улучшает ситуацию. *Это результаты чужого benchmark, не метрики QualityRelay.*
Оригинальная публикация: https://proceedings.mlr.press/v306/li26ej.html

**Вывод для нас:** вопросы «Кто знает то, чего я ещё не знаю?» и «Какой уникальный факт изменит решение?» должны быть **действиями**, а не свободным текстом в чате.

### 2.2 Дебаты не обязательно превосходят голосование

**Choi, Zhu, Li, NeurIPS 2025, «Debate or Vote: Which Yields Better Decisions in Multi-Agent Large Language Models?»** В рассмотренных NLP-задачах большая часть эффекта multi-agent debate объясняется majority voting; само обсуждение не гарантирует улучшения. Авторы показывают важность целевых корректирующих сигналов. Перенос на завод — гипотеза, требующая отдельного теста.
Публикация: https://papers.nips.cc/paper_files/paper/2025/hash/934252acd87f254d5d4672fbde283bd2-Abstract-Conference.html
Код авторов: https://github.com/deeplearning-wisc/debate-or-vote

**Вывод:** обязательный baseline — voting **без** обмена доказательствами; без него непонятно, приносит ли коммуникация новую информацию.

### 2.3 Expected Value of Information — существующий метод, не наше изобретение

Сравнение ожидаемого риска до и после измерения, с вычетом цены инспекции, — общая идея Bayesian decision theory / active sensing. Поэтому **не заявлять** «мы впервые придумали VOI». Возможный вклад QualityRelay: проверяемый протокол **распределённого** поиска информации с lineage, разрешениями, зависимостью источников, safety gate и реальным cost accounting.

**Научная новизна не подтверждена без систематического prior-art поиска и независимых сравнений.**

---

## 3. Предлагаемая собственная архитектура: EVIDENCE-REQUEST / SAFE-MESH 17.1

```text
  Phone Vision      Pi Vision       CAD Agent       Metrology / Process
  local signals     local signals   local signals   local signals
       |                 |              |                  |
       +-----------------+--------------+------------------+
                                   |
                     [Authenticated evidence ledger]
                       - provenance / ACL / freshness
                       - source_root + sensor correlation
                                   |
                   [Local role agents — private contexts]
                     |       |         |          |
                     +-------+---------+----------+
                                   |
                     [Evidence Request Protocol]
                     REQUEST -> GRANT/DENY -> RESPONSE
                       -> VERIFY -> BELIEF_UPDATE
                                   |
                    [Conditional / Adaptive VOI Planner]
                       choose: inspect / query / stop
                                   |
                      [Deterministic Safety Gate]
                     PASS_REVIEW / HOLD / REJECT_REVIEW
                                   |
                      Human authorization if needed
                                   |
                       [Audited physical execution]
                                   |
                      [Scientific paired benchmark]
```

**Принцип децентрализации:** владельцем сведений остаётся конкретная станция, а не «главный инженер» со всеми сырыми данными. Общая шина может доставлять подписанные *разрешённые summaries*. Вычислительный `evaluation harness` имеет доступ к ground truth **только для подсчёта метрик**, но не для подсказок агентам.

### 3.1 Не 21 LLM одновременно

Все 21 роли остаются зарегистрированы, но для проблемы конкретной детали запускаются только релевантные специалисты, обычно **2–7 ролей**: Quality Inspector, Metrology, CAD/Design, Process, Inspection Planner, Safety, Scientific Auditor. Добавление ещё одного агента допустимо, если оно даёт уникальный source или улучшает решение с учётом стоимости.

### 3.2 Шесть обязательных видов сообщений

| Тип | Кто отправляет | Смысл |
|---|---|---|
| `FIND_MISSING_EVIDENCE` | Quality/Planner | Какие свидетельства нужны для различения гипотез? |
| `REQUEST_EVIDENCE` | Агент → peer | Запрос конкретного типа доказательства с целью и бюджетом |
| `EVIDENCE_RESPONSE` | Peer → requester | Разрешённые summary + идентификаторы исходных фактов |
| `HYPOTHESIS_UPDATE` | Аналитик | Уточнение оценки риска после проверенных фактов |
| `PROPOSE_INSPECTION` | VOI planner | Следующий тест, ожидаемая ценность, стоимость и дедлайн |
| `DECISION_PROPOSAL` | Quality agent | PASS_REVIEW / HOLD / REJECT_REVIEW + доказательства |

`REJECT_REQUEST`, `TIMEOUT`, `SENSOR_FAILURE`, `STALE_EVIDENCE` должны быть отдельными техническими исходами, а не галлюцинироваться как отрицательные измерения.

### 3.3 Пример строго типизированного сообщения

```json
{
  "schema_version": "17.1",
  "message_id": "msg-0129",
  "case_id": "part-A123",
  "kind": "REQUEST_EVIDENCE",
  "sender_role": "quality_inspector",
  "recipient_role": "metrology_engineer",
  "requested_evidence_kind": "CALIPER_CLEARANCE",
  "reason_code": "VISUAL_GEOMETRY_CONFLICT",
  "hypotheses": ["surface_only", "clearance_violation"],
  "existing_evidence_ids": ["phone-19", "cad-5"],
  "max_cost_usd": 0.25,
  "deadline_ms": 1500,
  "correlation_group": "part-A123",
  "requires_authorization": true
}
```

- `sender` и `recipient` идентифицируются сервером/подписью, а не доверяются тексту LLM.
- Назначение сообщения, тип данных, ACL, deadline, budget, duplicate IDs проверяются **детерминированным кодом**.
- Любой ответ должен содержать `source_root`, `source_event_ids`, `origin`, `observed_at`, `calibration_id`, `uncertainty`, `unit`, `verification_status` (когда применимо).
- Подтверждение ролей и provenance **не доказывает правдивость измерения**; его качество устанавливается независимой калибровкой/ground truth.
- Не предоставлять LLM прямой GPIO/servo tool. Команды оборудованию проходят отдельный аппаратно защищённый safety gate.

### 3.4 Что считать **настоящим сотрудничеством**, а не театром

В trace должны быть одновременно:

1. **Информационная асимметрия:** у двух ролей изначально разные сведения; запрашиваемый факт отсутствовал у requester.
2. **Целевой запрос:** requester сформулировал, какой факт нужен для проверки конкретной гипотезы.
3. **Новый проверенный источник:** `EVIDENCE_RESPONSE` с уникальным `source_root`, если он действительно новый.
4. **Влияние на поведение:** после ответа изменились belief, выбор следующего действия, решение или документированная граница неопределённости.
5. **Сравнение с контрольным запуском:** тот же кейс без peer request показывает, добавила ли коммуникация что-либо сверх voting и статического правила.

Просто одинаковые ответы нескольких LLM, многословный чат или consensus после копирования одной фотографии **не являются** доказательством коллективной способности.

---

## 4. Адаптивный VOI: конкретный математический механизм

Обозначим:

- `D_t` — **только** проверенные наблюдения до шага `t`;
- `h` — скрытое состояние (`good`, `surface_defect`, `clearance_defect`, `both` или более богатая модель);
- `a` — решение (`PASS_REVIEW`, `HOLD`, `REJECT_REVIEW`);
- `q` — доступное действие по сбору доказательства (`ask CAD`, `remeasure caliper`, `new-angle phone image`, `Pi reinspection`, `assembly test`);
- `y` — возможный результат действия `q`;
- `L(a,h)` — денежный/безопасностный loss при выборе `a`, когда истинно `h`;
- `c(q)` — стоимость инспекции, ожидания, коммуникации и LLM/tool compute.

Базовый ожидаемый риск:

\[
R(D_t) = \min_{a \in A_{safe}} \sum_h P(h\mid D_t)L(a,h)
\]

Условная ожидаемая ценность следующего запроса:

\[
\operatorname{NetVOI}(q\mid D_t) = R(D_t) - \bigg[c(q) + \sum_y P(y\mid D_t,q)\,R(D_t\cup\{(q,y)\})\bigg]
\]

**Решение:** запросить `q* = argmax NetVOI`, если ожидаемая дополнительная ценность положительна, хватает бюджета и safety gate разрешает действие. Иначе остановить сбор данных и передать решение на проверку, при необходимости `HOLD`.

**Критично:** `P(y | D_t,q)` должна учитывать зависимости между камерами, одну и ту же поверхность, общую освещённость, общие исходные фотографии и смещение caliper. Нельзя перемножать свидетельства как независимые, если это не подтверждено экспериментом.

### 4.1 Практический алгоритм 17.1

```python
while budget_remaining > 0 and rounds < MAX_ROUNDS:
    observations = evidence_ledger.authorized_view(case_id, role)
    belief = calibrated_fusion.update(observations, dependence_graph)

    safety_state = hard_safety_gate.review(belief, observations)
    if safety_state.requires_immediate_hold:
        return HOLD_WITH_REASON

    candidates = planner.available_requests(
        case_id, role_permissions, active_stations, remaining_budget
    )
    scored = [
        (q, net_voi(q, belief, calibrated_sensor_models, costs))
        for q in candidates
    ]
    q_star, value = max(scored, key=lambda t: t[1], default=(None, 0.0))
    if q_star is None or value <= 0:
        break

    response = await protocol.request(q_star)
    ledger.append_verified_or_error(response)
    rounds += 1

return hard_safety_gate.review_for_human_authorization(
    case_id, evidence_ledger
)
```

Это псевдокод для реализации, **не существующая функция** пакета 17.0.

### 4.2 Четыре инженерных нюанса

- Доступные `A_safe` не могут включать автоматический физический PASS в обход проверки подписей, калибровки, допусков и полномочий.
- `HOLD` имеет стоимость, но не равен подтверждённому `REJECT`; включать rework и время ожидания отдельно.
- `NetVOI` не заменяет физическую безопасность: даже дорогая, но обязательная проверка может требоваться hard gate независимо от вычисленного дохода.
- LLM формулирует **гипотезы и запросы**, но `posterior`, `cost`, ranking, threshold и audit рассчитываются проверяемым Python-кодом.

### 4.3 Калибровка и модель зависимостей

На старте не делать вид, что нейросеть выдаёт честную вероятность. Разработать:

1. калибровочные таблицы sensitivity/specificity по типам дефектов и условиям съёмки;
2. интервалы неопределённости и OOD flags; при неизвестных условиях — `HOLD`, без чрезмерно уверенного `PASS`;
3. lineage-граф вида `source_root -> transformed_image -> model_score -> agent_summary`; производные факты одной фотографии не умножаются как независимые;
4. отдельный параметр common-mode error для Phone/Pi (например, общий плохой свет). Разные камеры **не гарантируют** независимость ошибок;
5. проверку calibration drift по новым партиям и сменам.

Версию этой статистической модели фиксировать в `run_manifest.json` и тестировать на отложенных *партиях*, а не соседних кадрах того же изделия.

---

## 5. Самый важный эксперимент: кто выигрывает и почему?

### 5.1 Системы для честного сравнения

| ID | Политика | Что получает | На что отвечает |
|---|---|---|---|
| `B0` | Conservative deterministic rules | Фиксированные разрешённые baseline inputs | Хорошее правило может победить сложный AI? |
| `B1` | Single Agent (distributed-access constrained) | Столько же доступных запросов и тот же budget, без peer multiagent dialogue | Есть ли преимущество от разных ролей? |
| `B2` | Single Agent (full-information oracle **upper bound**) | Полный набор **доступных измерений**, но не скрытый ground truth | Потери от распределённости информации (upper bound, не прямой cost-match) |
| `B3` | Independent multi-agent voting | Те же первоначальные сведения, **без** peer requests | Даёт ли пользу просто ансамбль? |
| `B4` | Free-form multi-agent chat | Равные token/time/inspection limits | Улучшает ли неструктурированная дискуссия? |
| `B5` | Structured evidence requests + fixed inspection | Разделённые сведения, реальный peer exchange, но фиксированная очередность тестов | Отдельный вклад коммуникации |
| `B6` | Single-agent + adaptive VOI | Один агент, тот же набор действий и бюджет | Отдельный вклад динамического выбора тестов |
| `B7` | **SAFE-MESH 17.1 structured + adaptive VOI** | Разделённые сведения, budgets и hard safety | Есть ли синергия коммуникации и decision-focused inspection? |

**Нельзя** давать `B7` дополнительные дешёвые данные, которыми не разрешено пользоваться `B1/B6`; отличие должно быть в способе получения и сочетания данных. `B2` — контекстный *верхний ориентир*, а не формально равный baseline; если предоставленные ему сведения стоят денег, в сравнении явно показывать его информационную цену.

### 5.2 Абляции (обязательны)

- `B7 - peer_exchange`: убрать коммуникацию, оставить тот же backbone/model.
- `B7 - adaptive_VOI`: фиксировать последовательность запросов.
- `B7 - provenance`: отключить дедупликацию/проверку зависимости **только в безопасной симуляции**, никогда в физическом устройстве.
- `B7 - specialist_roles`: один универсальный agent prompt вместо специализированных ролей.
- `B7 - cost_awareness`: выбирать максимальное снижение entropy вместо expected loss.
- `B7 - structured_protocol`: заменить типизированные запросы свободным чат-общением.

Каждая абляция меняет **одну** ось, остальные параметры фиксированы.

### 5.3 Stress tests — минимум 12 сценариев

1. Phone подозревает скол, Pi — `clear`.
2. CAD показывает неверную геометрию, обе камеры — `clear`.
3. Caliper у границы tolerance + высокая measurement uncertainty.
4. Одну фотографию 3 агента цитируют как 3 якобы разных доказательства.
5. Камеры снимают под разными углами, но оба изображения испорчены одинаковым lighting shift.
6. Один источник offline; новый ответ недоступен.
7. Ответ пришёл после deadline и устарел.
8. Есть подпись, но калибровка неверна/просрочена.
9. У Design Agent есть уникальная CAD ревизия; Quality Agent о ней изначально не знает.
10. Process Agent видит начало drift станка; Vision Agent видит только отдельные изображения.
11. Повышена цена Caliper reinspection; дешёвый новый угол камеры может быть выгоднее.
12. Дешёвый тест малополезен; дорогая Assembly check решающая, но не помещается в бюджет.

Также провести: сети с задержкой, повтор сообщений, неупорядоченный event stream, prompt injection в текстовом metadata, sensor false negatives, смену партии и смену камеры.

### 5.4 Data split и честность

- Train/calibration/validation/test разделять по **part IDs, print batches, camera sessions**. Нельзя переносить снимки одной детали в разные выборки.
- Test set должен включать реальные фото, caliper measurement и assembly ground truth, если делаем физическое утверждение.
- Для виртуальных тестов использовать paired scenarios и common random numbers; одним baseline нельзя давать более лёгкие seed.
- Не допускать oracle leakage: `safe`, `true_clearance`, `surface_defect`, скрытое состояние генератора **только evaluator**. Они должны отсутствовать в agent observations.
- Логировать seed, цены, latency, LLM model version, temperature, prompts hashes, tool version, process shift, outage rate, sensor calibration, messages.
- Условные стоимости модельные; **не** называть вычисленный ROI доказанной экономией завода.

---

## 6. Primary и secondary metrics

### Primary, заранее зафиксированные

1. **Unsafe PASS rate** = число реально дефектных деталей, выпущенных как безопасные / число всех дефектных деталей; отдельно *escape rate per all units* для сопоставления со старым benchmark. Деноминаторы не смешивать.
2. **Total expected operational cost per 1000 parts** = inspection + communication + latency + compute + rework + scrap + false accept + hold costs; без двойного счёта.
3. **Task completion at matched safety**: сколько решений с приемлемой границей риска реально закрыто при заданном бюджете.

### Secondary

- `hold_rate`, `false_hold_rate`, `precision/recall` по типам дефектов;
- `inspection_count`, `inspection_cost`, `inspection_duration`;
- `unique_evidence_discovery_rate` (доля действительно новых независимых источников);
- `message_count`, `tool_calls`, `token_usage`, `LLM_cost_usd`, `p95_latency`;
- `calibration_error`, `Brier score` для вероятностей;
- `communication_success_rate`, `source_diversity`, `duplicate_evidence_blocks`;
- `belief_revision_rate` после **нового** источника, а не после пустой переписки;
- `decision_flip_with_valid_new_evidence` и `decision_flip_without_new_evidence`;
- performance by `network_outage`, `process_shift`, `shared_camera_noise`.

**Статистика:** отчёт по paired seed/партиям и cluster bootstrap confidence intervals; для редких unsafe PASS заранее оценить необходимый размер физической выборки. Нулевые наблюдения не дают гарантии нулевого риска. Отчёт содержит полные распределения, а не только средние. Не интерпретировать 30 виртуальных seed как 30 независимых заводов.

### Критерий признания вклада (research gate)

Запуск `B7` считается **успешным научным результатом** лишь если:

- результаты воспроизводимы по зафиксированному протоколу;
- hard safety gate не обходится ни в одном тесте;
- статистически обосновано преимущество по заранее объявленной primary metric **при отсутствии неприемлемого ухудшения безопасности**, либо показаны конкретные области условий, где оно появляется;
- improvement исчезает/сокращается в корректной ablation хотя бы для одного заявленного собственного механизма;
- всё это подтверждено независимым held-out test, а не только теми же synthetic сценариями, на которых выбраны параметры.

Если не выполняется — публикуем **negative result** и причины.

---

## 7. Практический план изменений в репозитории (только 17.1)

### 7.1 Новые файлы, которые требуется **создать**

```text
qualityrelay17/collective/
    __init__.py
    message_schema.py          # Pydantic: запрос/ответ/гипотеза/решение
    peer_protocol.py           # signed/authenticated request-reply + ACL
    evidence_router.py         # source ownership + admissible summaries
    provenance_graph.py        # evidence lineage, correlation clusters
    collaboration_engine.py    # запускает роли + controlled rounds
    belief_state.py            # калиброванные posterior, uncertainty
    adaptive_voi.py            # динамический inspection/request planner
    decision_trace.py          # event logs, causal chain, counterfactuals
    agent_observation.py       # разделение видимой и скрытой информации

qualityrelay17/experiments/
    collective_env.py          # воспроизводимая environment + reset/step
    collective_baselines.py    # B0..B7
    scenarios.py               # 12+ конфликтных случаев
    cost_accounting.py         # вся цена сообщений, инспекций, задержек
    run_collective_eval.py     # paired seed runner + manifest
    statistics.py              # cluster bootstrap, uncertainty
    ablation.py                # ровно по одному отключаемый механизм

schemas/
    agent_message_v17_1.schema.json
    agent_trace_v17_1.schema.json

web/                       # расширить существующий интерфейс
    # Agent Evidence Room / trace viewer / benchmark comparison

tests/
    test_collective_messages.py
    test_collective_acl.py
    test_collective_provenance.py
    test_collective_voi.py
    test_collective_hidden_information.py
    test_collective_failures.py
    test_collective_benchmark.py
```

### 7.2 Что необходимо **изменить**, не сломав 17.0

| Существующий файл | Точка интеграции |
|---|---|
| `roles.py` | Добавить `can_request`, `owned_evidence`, role-specific uncertainty; оставить совместимость с 21 ролью |
| `nebius.py` | Ввести строго типизированный output и peer-request round; не включать live API в CI без credentials |
| `agent_tools.py` | Новые checked `request_peer_summary`, `request_inspection`, `propose_decision`; проверка ACL выполняется сервером |
| `ledger.py` / `lineage.py` | Добавить typed event/causal linkage, source-root и зависимости, но не выдавать чужие raw data |
| `vder.py` | Сохранить бинарный reference; расширить sequential/correlated VOI **новым** модулем, не менять старые тесты |
| `factory.py` | Добавить environment observation/action interface и отделить simulator truth от наблюдений агентов |
| `benchmark.py` | Сохранить старые результаты; для B0..B7 создать **новый** runner, новую таблицу и интервал |
| `safe_mesh.py` | Принимать verified decision proposal, но сохранять неизменные hard safety constraints |
| `api.py` / `web/index.html` | Trace API и «кто что запросил, какой факт получен и что изменилось» |

### 7.3 API contracts

```text
POST /research/collective/run
GET  /research/collective/runs/{run_id}
GET  /research/collective/runs/{run_id}/traces/{part_id}
GET  /research/collective/runs/{run_id}/comparison
GET  /research/collective/runs/{run_id}/manifest
```

`POST` в research environment не запускает реальный servo. Для live physical mode использовать **отдельный сервис** с human authorization, physical interlock и post-action verification. Research endpoint должен возвращать `origin: SIMULATED` или явно объявленный experimental dataset origin.

### 7.4 Что должно отображаться в Agent Evidence Room

```text
PART A123 — visible to Quality Inspector:
 [Phone] suspicious surface mark        e-1
 [CAD]   projected geometry OK           e-2
 [Pi]    unavailable                      (missing)

12:08:01 Quality: missing independent surface evidence
12:08:02 Quality -> Pi: REQUEST_EVIDENCE (reason: camera disagreement)
12:08:04 Pi -> Quality: EVIDENCE_RESPONSE e-7 [verified / source_root=pi-82]
12:08:04 Belief update: 0.18 -> 0.31 [calibrated example, illustrative]
12:08:05 Planner: Caliper next, NetVOI=+$0.42 [illustrative]
12:08:09 Metrology: verified measurement e-12
12:08:09 Safety: HOLD, human review required

COMPARE SAME PART:
 B3 voting         : HOLD | no new evidence
 B5 structured     : HOLD | 1 peer source discovered
 B7 structured+VOI : HOLD | 1 peer source, 1 selected inspection

No claim of improvement from this single narrative trace.
```

Примерные вероятности/стоимости в trace приведены **только для объяснения интерфейса**. Продакшен dashboard обязан отображать реально вычисленные и калиброванные значения.

---

## 8. Где брать готовые компоненты, а что писать самим

| Компонент | Репозиторий / ресурс | Почему использовать | Собственный вклад QualityRelay |
|---|---|---|---|
| LangGraph | https://github.com/langchain-ai/langgraph | Stateful agent workflows, узлы/переходы, retries | **Наш** source-aware peer protocol и экспериментальная семантика; LangGraph не доказывает decentralization |
| NATS | https://github.com/nats-io/nats-server | Сообщения между локальными station-services, включая Pi/edge | **Наши** ACL, source provenance, запросы доказательств, безопасность |
| SimPy | https://simpy.readthedocs.io/ | Очереди, время тестов, задержки, ресурсные ограничения | Наш manufacturing environment и calibrated cost model |
| PettingZoo | https://github.com/Farama-Foundation/PettingZoo | Стандарт multi-agent environment, если понадобится multi-agent RL | Наше state/action/observation пространство; **не нужен** для простого LLM peer messaging |
| Temporal Python SDK | https://github.com/temporalio/sdk-python | Durable workflows для долгих инспекций/таймаутов, **опционально** | Наш протокол над workflow; не обязательно для первой версии |
| HiddenBench paper | https://proceedings.mlr.press/v306/li26ej.html | Научный дизайн задач с распределённой информацией | Новый manufacturing hidden-profile benchmark, а не копия чужих результатов |
| Debate-or-Vote code | https://github.com/deeplearning-wisc/debate-or-vote | Сильный научный baseline для проверки пользы обсуждения | Адаптация к датчикам, CAD, цене инспекций, безопасности |
| SciPy / NumPy | https://scipy.org/ , https://numpy.org/ | Вероятности, статистика, оптимизация | Зависимые sensor models, sequential VOI, audit результатов |

**Лицензирование:** не копировать сторонний код в наш ZIP без проверки лицензий и notices; держать версии/pinned commits, SBOM и `THIRD_PARTY_NOTICES`. Внешние datasets и веса моделей проверяются отдельно. NATS server — Apache 2.0, Temporal Python SDK — MIT по их репозиториям; для остальных лицензии и дополнительные условия фиксировать в момент импорта. GitHub-адрес сам по себе не разрешение использовать всё без ограничений.

**Архитектурный выбор:** для первых опытов `Python + SQLite + in-process typed message bus` даст контролируемый baseline; после тестов можно перейти на `NATS` между действительно независимыми station-services. `LangGraph` можно использовать для исполнения LLM workflow, но не принимать сам LangGraph graph за доказательство peer-to-peer децентрализации. Межстанционные права и хранение остаются независимыми от framework.

---

## 9. Проверки качества кода: definition of done

### Минимальный unit/integration suite

- `[ ]` Роль не может читать чужое raw evidence, если имеет доступ только к approved summary.
- `[ ]` Повтор одного `source_root` не увеличивает число независимых наблюдений.
- `[ ]` Общее освещение учитывается как possible common-cause error.
- `[ ]` `EVIDENCE_RESPONSE` без valid signature / calibration / freshness не может обосновать `PASS_REVIEW`.
- `[ ]` `TIMEOUT` и `DENIED` не превращаются в выдуманные значения `clear`.
- `[ ]` Есть trace реального peer request, response и posterior revision на synthetic fixture.
- `[ ]` При отсутствии новых уникальных фактов «дискуссия» не повышает confidence.
- `[ ]` VOI выбирает **разные** инспекции при изменении цены, sensor performance или текущего belief.
- `[ ]` VOI может выбрать `STOP/HOLD`, когда ни один тест не оправдан, но safety требует review.
- `[ ]` Все восемь baselines (`B0..B7`) выполняются на одних paired сценариях.
- `[ ]` Evaluator truth недоступен ни одному agent tool, не появляется в prompts, traces, API observations.
- `[ ]` Prompt injection в метаданных кадра не вызывает новый запрещённый tool call.
- `[ ]` При отключении peer network система fail-safe и не выпускает деталь автоматически.
- `[ ]` В run manifest записаны model, code commit, seeds, budgets, sensor versions, costs.
- `[ ]` Невозможно отправить hardware command из LLM или benchmark API.

### Evidence для научного заявления

- `[ ]` Существует тест, в котором без peer request нужный факт недоступен, а после разрешённого запроса решение обоснованно меняется.
- `[ ]` Показана количественная **прибавка от коммуникации** относительно voting при равной цене.
- `[ ]` Показана **прибавка от adaptive VOI** относительно fixed inspection и single-agent adaptive VOI.
- `[ ]` Публикуются не только случаи улучшения, но и сценарии, где сотрудничество хуже/дороже.
- `[ ]` Всё повторено на out-of-distribution и физическом holdout (для заявления о real-world пользе).

---

## 10. Порядок разработки без потери научной строгости

### Gate A — Honest baseline (CPU, локально)

- Сохранить исходный JSON benchmark 17.0 неизменным.
- Сделать `collective_env.py` c `observe(role)` и `step(action)` так, чтобы скрытая истина была недоступна агентам.
- Запустить B0/B1/B3/B5/B6/B7 **с deterministic mock agents**. Они нужны, чтобы проверить механизмы информационного обмена и VOI независимо от ненадёжности LLM.
- Восстановить ещё минимум один кейс, в котором structured request реально добавляет ранее скрытый факт.

**Результат Gate A:** работающий end-to-end evidence-request trace, не заявление о «21 умном AI».

### Gate B — Real LLM interaction (Nebius)

- Подключить live Nebius API только с разрешённым командным ключом, выбранной доступной моделью и server-side rate/usage caps.
- 2–5 активных ролей на эпизод, не 21 вызов по умолчанию.
- Типизированные ответы (JSON Schema) с фактической серверной валидацией.
- Отдельно считать token cost, ошибку parsing, retries, latency, nondeterminism.
- Сравнить B1/B3/B4/B5/B7 с одинаковым model backbone.

**Результат Gate B:** реальное измеримое межагентное взаимодействие, включая отрицательные случаи.

### Gate C — Adaptive decision economics

- Обновлять belief **после каждого нового проверенного факта**;
- Измерить B5 vs B7, B6 vs B7, ablations;
- Калибровать sensitivity/specificity на отложенных данных;
- Явно включить стоимость запросов, ошибок и физической проверки.

**Результат Gate C:** воспроизводимая оценка cost–safety frontier, а не красивые истории.

### Gate D — Physical scientific validation

- 3D-printed Slot/Tab, Phone + Pi, caliper, независимый assembly label;
- Только shadow mode/human review; физическая сортировка — после отдельно проверенных safety interlocks;
- Сравнить sim-to-real и OOD shift;
- Готовить научный report с опубликованным протоколом и negative results.

**Результат Gate D:** первый физически обоснованный вывод в пределах проверенной маленькой выборки, не «готово для завода».

---

## 11. Ответственность команды

| Участник | Вклад в узкий Collective Intelligence scope |
|---|---|
| **Bakdaulet** | Теория H1–H3; adaptive VOI и calibrated probabilities; paired experiment; метрики, ablation, paper-style results; GPU не обязателен |
| **adilnurgg** | Peer protocol, ACL, Nebius live roles, backend и LLM tool authorization; безопасная доставка сообщений |
| **HyorinmaruK** | Производственные сценарии/ground truth с механической точки зрения, валидность CAD/caliper/assembly, Agent Evidence Room UI и физическая проверка |

Четвёртый участник, если есть: automated benchmark harness и CI.

---

## 12. Формулировка научной цели для заявки / статьи

> **Research question:** Under distributed and partially correlated manufacturing evidence, can structured inter-agent information requests combined with decision-focused sequential inspection reduce cost at a matched safety constraint relative to strong single-agent, majority-vote, conservative-rule and fixed-inspection baselines?

**H1 — Information acquisition:** structured requests приводят к большему числу уникальных релевантных фактов и лучшим решениям, чем multi-agent voting или free-form debate при равном бюджете.

**H2 — Decision value:** sequential conditional NetVOI снижает общую цену инспекций при неухудшении заранее заданного safety criterion по сравнению с fixed inspection и entropy-only planner.

**H3 — Robustness:** provenance-aware protocol и независимый safety gate уменьшают неверную уверенность при дублированных источниках, обрывах связи и сдвигах распределений.

> **Нулевой результат тоже допустим:** если сильный single-agent с одинаковой стоимостью и сенсорными инструментами достигает того же, это ограничивает область применимости multi-agent дизайна и помогает честно оптимизировать продукт.

### Чего нельзя обещать

- «21 агент доказанно лучше одного» — **нет**.
- «Мы обучили 21 модель» — **нет**.
- «VOI — наш новый математический метод» — **нет**.
- «88 unit tests доказывают научную эффективность» — **нет**.
- «Результаты synthetic 30k деталей гарантируют экономию настоящего завода» — **нет**.
- «Peer messaging без распределённых data ownership = полностью децентрализованная система» — **нет**.

### Одно предложение, которое можно честно сказать сейчас

> **QualityRelay 17.1 proposes a falsifiable benchmark and a provenance-constrained information-request protocol for measuring whether decentralized AI specialists gain real decision value through collaboration in manufacturing quality control.**

---

## 13. Первоисточники и готовые решения

**Научные публикации**

1. Li, Y., Naito, A., & Shirado, H. (2026). *Systematic Failures in Collective Reasoning under Distributed Information in Multi-Agent LLMs*. ICML / PMLR 306. https://proceedings.mlr.press/v306/li26ej.html
2. Choi, H. K., Zhu, X., & Li, S. (2025). *Debate or Vote: Which Yields Better Decisions in Multi-Agent Large Language Models?* NeurIPS 2025. https://papers.nips.cc/paper_files/paper/2025/hash/934252acd87f254d5d4672fbde283bd2-Abstract-Conference.html
3. AEC API (PettingZoo): https://pettingzoo.farama.org/api/aec/ — инженерный источник API multi-agent environments, **не научное подтверждение QualityRelay**.

**Инженерные репозитории**

4. LangGraph: https://github.com/langchain-ai/langgraph
5. NATS Server: https://github.com/nats-io/nats-server
6. PettingZoo: https://github.com/Farama-Foundation/PettingZoo
7. Temporal Python SDK: https://github.com/temporalio/sdk-python
8. NeurIPS authors' debate/vote code: https://github.com/deeplearning-wisc/debate-or-vote
9. SimPy: https://simpy.readthedocs.io/

**Внутренние проверенные источники 17.0**

10. `QualityRelay_17_SAFE_MESH/docs/engineering/STATUS_AND_GATES.md`
11. `QualityRelay_17_SAFE_MESH/qualityrelay17/{factory,benchmark,vder,roles,nebius,ledger,safe_mesh}.py`
12. `QualityRelay_17_SAFE_MESH/examples/results/BENCHMARK_30x1000_SYNTHETIC.json`

---

## 14. Итог

**Главный разрыв в версии 17.0:** измерялась разница четырёх preset policies, а не способность независимых специалистов активно добывать недостающую информацию. **Решение 17.1:** typed peer requests + source-aware verification + conditional adaptive VOI + immutable decision traces + равный научный benchmark с ablations и сильными одиночными baseline.

**Приоритет №1 для следующего коммита:** реализовать `collective_env.py`, `message_schema.py`, `peer_protocol.py` и paired benchmark `B0–B7` прежде, чем тратить GPU на новые декоративные модели. Только после появления измеримого сигнала переходить к live Nebius и физическому демонстратору.
