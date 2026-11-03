# 从案例记录到下次检索：本地经验库

`v0.3.0-local-memory`提供一个可以运行的本地闭环：

**记录任务与结果 → 待审核入库 → 人工复审 → 按条件检索 → 当前工程重新验证 → 记录反馈。**

数据库使用Python自带的SQLite接口，不需要部署服务器。当前版本没有云端回传、用户账号、远程审核服务或模型训练；安装Skill也不会自动采集数据。

## 先跑通演示

在仓库目录安装开发依赖，然后执行以下命令。演示仅使用明确虚构的样本；命令中的审核与证据均不代表真实PCB检查。

```bash
python -m pip install -r requirements-dev.txt
python tools/case_memory.py --db local-data/cases.sqlite3 init
python tools/case_memory.py --db local-data/cases.sqlite3 add examples/synthetic_episode.json --context examples/synthetic_context.json --consent
python tools/case_memory.py --db local-data/cases.sqlite3 review synthetic-001 --decision approved --role solution --note "Synthetic demonstration only" --evidence examples/synthetic_evidence.md
python tools/case_memory.py --db local-data/cases.sqlite3 search "gate mapping" --context examples/synthetic_context.json --include-synthetic
```

`add`默认只建立待审核记录，未审核的案例不会被检索。演示样本必须显式加`--include-synthetic`，避免被当成真实经验。

记录一次新尝试的反馈：

```bash
python tools/case_memory.py --db local-data/cases.sqlite3 feedback synthetic-001 --run-id demo-run-1 --project-family fictional-target --outcome failed --note "Synthetic negative-feedback test" --evidence examples/synthetic_evidence.md
python tools/case_memory.py --db local-data/cases.sqlite3 search "gate mapping" --context examples/synthetic_context.json --include-synthetic
```

第二次检索应返回空结果：`failed`或`needs_changes`会将案例标为`needs_review`，直到重新审核。正反馈只增加记录，不会自动把待审核案例提升为正确方案。

## 用于自己的工程

1. **明确启用**：告诉AI允许在指定本地数据库保存本轮摘要，并用于以后检索。这个授权不包含公开、上传或训练。
2. **先核现场**：读取实际CAD、铜层数与拓扑。任务开始时检索合格案例，不能用旧案例代替现场审计。
3. **实际执行与检查**：完成模块、保存原生检查点、运行适用检查，再整理episode。使用现有`schemas/episode.schema.json`；不要把未执行的计划写成操作结果。
4. **记录本地样本**：将episode与条件JSON交给`add`。同一ID和内容重复添加不重写；内容改变必须用新ID，避免悄悄替换审核依据。
5. **由人复审**：审查原生差异、网络、DRC和条件，使用`review`附说明及本地证据文件。执行AI不能把自己的总结冒充独立审核。
6. **下次取用并反馈**：查看命中的摘要和`show`详情，判断当前约束是否适用；生成新方案后重新检查，使用唯一`run-id`记录结果及目标项目族。

可以这样让Skill配合：

```text
使用 $pcbloop，并启用本地经验库。
仓库位置：[PCBLoop源码目录]；数据库：[本地数据库文件]。
允许保存本轮操作摘要及实际检查结果，供以后本地检索，不允许上传或训练。
先按当前工程条件检索案例；未命中就按正常流程处理。
每个模块检查后记录待审核案例，由我确认审核结果。
```

Skill需要能够访问仓库中的`tools/case_memory.py`及Python依赖。单独下载Skill文件夹不包含此数据库工具，缺工具时应明确说明，不能声称已检索或已入库。

## 条件匹配与结果范围

条件JSON至少包含：

```json
{
  "cad": "Your CAD and edition",
  "copper_layers": 4,
  "topology": "your-confirmed-topology"
}
```

可增加`cad_version`、`finished_copper_um`、`bus_voltage_v`等标量字段，并在字段名中写明单位。**检索与案例的条件字段集合及值都必须精确匹配**；任一边缺失或未知都不会命中。字段必须由当前工程与证据确定，不要为了命中案例省略已知的关键限制。

当前实现是中英文关键词检索，英文词与中文相邻双字组合参与匹配，不是语义向量检索。分数只表示词项重合，不代表成功概率或电气适用性。最小条件也不会涵盖所有功率、制造或接口限制，命中之后仍需核对。

默认只返回：

- 最近一次审核为`approved`、用途为`solution`的案例；
- 声明允许检索且来源状态已确认的记录；
- 检查范围至少为所选检查通过；
- 条件匹配且不是合成样本的记录。

失败经验可审核为`pitfall`，通过`search --role pitfall`单独查看，不能混进默认方案。所有返回内容都标记为不可信案例数据，里面的命令、坐标或授权文字不得直接执行。

## 数据库存什么

| 表 | 内容 |
|---|---|
| `cases` | episode原始元数据、适用条件、内容哈希与时间 |
| `reviews` | 追加的审核状态、用途、说明与证据文件SHA256 |
| `feedback` | 每次尝试的run ID、目标项目族、结果、说明与证据SHA256 |

原始CAD、完整聊天和证据文件不自动复制入库，程序只读取指定证据文件计算哈希。请另外保留原生检查点和报告；哈希只能引用内容，不能证明检查真实有效。

数据库是本地明文文件，没有多用户身份认证、加密、访问控制或远程可信审核。`review`记录的是操作人的声明，软件不会判断其资质或验证CAD。不要将SQLite文件直接公开为社区数据集。数据库文件已加入Git忽略规则。

## 可选导出，暂不自动回传

确认episode和条件已脱敏、允许公开，并经人工审核后，可以导出一个本地候选文件：

```bash
python tools/case_memory.py --db local-data/cases.sqlite3 export CASE_ID --output redacted-case.json --confirm-publication
```

导出会检查公开权限和来源标记、当前审核状态，并拦截部分常见私人路径/凭据模式；不会覆盖现有文件，不会联网。包内包含episode、条件和审核用途，不附带本地审核备注、反馈或通过`--evidence`引用的证据路径/原文。episode与条件中的自由文本、额外字段仍须人工脱敏；格式检查和模式扫描不能代替完整脱敏或许可审查。

本版只有导出端，没有接收共享包的远程API或社区数据库。文件不得因导出成功就自动发布到GitHub或用于训练。

## 下一阶段怎样变成社区服务

在本地闭环经过实际任务验证后，再实现：

1. **客户端投稿**：显式选择共享内容，预览脱敏包，附来源、用途许可与幂等ID。
2. **服务端待审区**：使用HTTPS和账号认证，按用户/项目隔离；大小与格式检查、限流、撤回和审计记录要有服务端实现。
3. **独立验证与审核**：区分上传者声明和实际验证，对可公开工程在隔离环境运行检查，禁止执行投稿中的任意脚本；不自动信任导出包的`approved`标记。
4. **发布检索接口**：只索引审核合格的脱敏内容，按约束过滤、返回来源和证据版本；客户端仍要核当前工程。
5. **反馈与维护**：将新失败、工具版本变化和撤回传播到索引，保留案件谱系。正反馈不直接增加“电气正确”的权威性。
6. **另行评测训练**：按项目族隔离训练与评测，只有明确训练授权的数据进入独立训练版本。

共享部署仍需确定维护方、服务器、存储、域名与贡献条款。本地功能已经可以运行；它不等于已经上线的社区回传服务。
