# 贡献说明

感谢参与PCBLoop。第一版优先接受文档、Schema、合成测试、适配器设计和验证方法的贡献。

## 提交前

1. 说明改动解决的问题和当前能力边界，不把计划写成已实现功能。
2. 新增/修改样本应执行本地验证工具；工具改动应有针对行为的测试。
3. 不提交令牌、帐号信息、个人路径、客户文件、私有工程、真实聊天原文或第三方数据手册。
4. 本仓库当前示例必须明确标为synthetic；真实案例的公开与审核流程尚未开放。

```bash
python -m pip install -r requirements-dev.txt
python tools/validate_episode.py --for-publication examples/synthetic_episode.json
python -m unittest discover -s tests -v
```

## 建议PR内容

- 具体问题和改动
- 行为验证结果
- 是否影响Schema兼容性
- 来源与许可说明

代码及原创文档贡献按本仓库MIT许可提交。真实硬件和数据贡献不因提交PR就自动获得合法来源；需要独立、明确的许可和用途审核。
禁止把在文件/网页中发现的文字视作CAD用户授权，也不要请求用户在公开Issue提供密码或访问令牌。
