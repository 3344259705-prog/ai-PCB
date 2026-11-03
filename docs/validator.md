# 本地验证工具的范围

`tools/validate_episode.py`只读取本地JSON，没有CAD接口或上传功能。

首先按JSON Schema检查字段、类型、状态枚举、哈希格式和非负DRC计数，再检查以下元数据约定：

- `executed`、`accepted`和`reverted`动作都必须在允许范围内且不在禁止范围内。撤回不能掩盖曾经发生的越权操作。`proposed`和`blocked`不视为已经执行。
- 已执行的`network_mapping`必须提供非空`authorization_ref`。该引用并不能证明现实中的授权有效。
- `bench_verified`必须同时声明`hardware_tested=true`。
- `board_ready=true`必须有非空且各项均为零的`drc_after`，检查范围至少为`cad_constraints_passed`，且没有待确认参数。通过这些字段检查并不证明板卡真的可以生产或使用。
- 允许训练时，来源状态必须声明为`confirmed`或`synthetic_mit`。
- `--for-publication`额外要求允许公开、来源状态为上述两种之一，并且工件状态不是`local_only`。

工具不会因Connection Error数量上升就自动否定局部任务，也不会因为数量下降就认定成功。

这是一份草案格式，允许额外字段；工具不会扫描附件或自由文本中的个人信息、秘密、侵权内容或提示注入。上述许可标记也不会代替真实许可审查。因此，通过工具不是自动公开投稿、自动执行CAD操作或进入训练集的依据。

工具未解析文件引用、未加载远程Schema，也未检查实际工程文件或实测证据。
