# Ducoro 插件市场

[Ducoro](https://ducoro.ai) 官方插件仓库。

[English](README.md) | **简体中文**

每个插件围绕 Ducoro 的 Space、展板（Board）、Connector 与 `ducoro-cli` 能力打包 **Agent Skill**（`SKILL.md`）、脚本、展板与可选的 **MCP 服务声明**（`.mcp.json`）。

## 现有插件

| 插件 | 用途 | 包含内容 |
| --- | --- | --- |
| [Starter Template](plugins/starter-template) | 用于联调测试与新建插件的最小参考模板 | Skill + MCP 示例 |
| [Docs Lookup](plugins/docs-lookup) | 根据最新文档回答库与框架相关问题 | Skill（Context7） |
| [Repo Research](plugins/repo-research) | 通过文档理解公开 GitHub 仓库 | Skill（DeepWiki） |
| [Git Workflows](plugins/git-workflows) | 编写清楚的提交信息和 Pull Request 描述 | Skill |
| [Content Operations](plugins/content-operations) | 覆盖 14 个平台的端到端内容运营闭环（选题、创作、分发、互动、复盘与展板） | Skills + Scripts + Boards |

## 使用方式

- **Ducoro**：通过根目录 `marketplace.json` 自动同步本仓库，按需将插件挂载到不同 Bot。

凡是需要凭证的 MCP 服务声明均只写环境变量占位符（例如 `${EXAMPLE_MCP_TOKEN}`），真实密钥请在 Ducoro 本地凭证库中配置。

## 仓库结构

```text
marketplace.json                   # 插件市场索引
plugins/
  <plugin-name>/
    LICENSE
    plugin.json                    # 插件清单
    .mcp.json                      # 可选：MCP 服务声明（严禁真实密钥）
    skills/
      <skill-name>/
        SKILL.md
```

## 参与贡献

- 人工贡献者请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
- AI Agent 请直接阅读 [AGENTS.md](AGENTS.md)，按清单新建、修改与校验插件。
- 安全问题请通过[私密漏洞报告](https://github.com/ducoro/plugins/security/advisories/new)反馈，详情见 [SECURITY.md](SECURITY.md)。

## 许可证

采用 [Apache License 2.0](LICENSE)。第三方服务及其文档适用各自的条款。
