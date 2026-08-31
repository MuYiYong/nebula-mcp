# 远端只读 MCP 评测

[`remote_readonly.xml`](remote_readonly.xml) 包含 10 个相互独立的固定 Schema 问题。答案仅来自 `/default_schema/cypher_compat_381_type` 的 `DESCRIBE GRAPH TYPE` 结果，不依赖业务行数、查询耗时或写操作。

`tests/integration/test_remote_readonly.py::test_remote_mcp_evaluation_answers` 会为每个 `qa_pair` 独立调用一次 `nebula_get_graph_schema`，再把 MCP structured content 中的事实与 `expected_answer` 比较。评测文件中的 `fact_key` 只是自动核验键，不是 Server 输入。

默认测试不会连接远端。运行时提供只读账号，并显式开启：

```bash
NEBULA_RUN_REMOTE_TESTS=1 \
NEBULA_ADDRESSES=HOST:PORT \
NEBULA_USERNAME=USER \
NEBULA_PASSWORD=PASSWORD \
.venv/bin/python -m pytest tests/integration -q
```

评测不得加入 mutation/DDL，也不应使用可变数据计数作为固定答案。如果目标 Graph Type 被有意修改，应先重新读取 Schema、人工复核问题，再更新期望值。
