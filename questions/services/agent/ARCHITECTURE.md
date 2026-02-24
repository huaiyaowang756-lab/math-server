# 意图识别与技能编排架构

## 概述

用户输入统一进入意图识别层，根据识别结果路由到对应技能；若无匹配技能则走闲聊流程。

```
用户输入 → 意图识别(LLM) → 技能路由 → 技能执行 → 统一响应
```

## 目录结构

```
agent/
├── __init__.py
├── intents.py          # 意图识别
├── orchestrator.py     # 编排器
├── skills/
│   ├── __init__.py     # 技能注册表
│   ├── base.py         # 技能基类
│   ├── question_recommend.py  # 推荐试题技能
│   └── chat.py         # 闲聊技能
└── ARCHITECTURE.md     # 本文档
```

## 意图类型

| 意图 | 说明 | 技能 |
|------|------|------|
| recommend_questions | 用户想获取/推荐数学题目 | QuestionRecommendSkill |
| chat | 闲聊、问候等 | ChatSkill |

## 扩展新技能

1. 在 `intents.py` 的 `IntentType` 中增加新意图
2. 在 `intents.py` 的 `INTENT_SYSTEM` 中补充新意图的判定说明
3. 在 `skills/` 下新建技能类，继承 `BaseSkill`，实现 `invoke`
4. 在 `skills/__init__.py` 的 `_init_registry` 中注册

## API

- `POST /api/chat/`：统一聊天入口，自动意图识别并路由
- `POST /api/questions/recommend/`：直接推荐试题（跳过意图识别，兼容旧调用）
