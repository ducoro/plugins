# Ducoro 插件市场

[Ducoro](https://ducoro.ai) 官方插件仓库，同时可直接用于 **Claude Code** 与 **OpenAI Codex**。

[English](README.md) | **简体中文**

每个插件以开放的跨宿主格式打包 **Agent Skill**（`SKILL.md`）以及可选的 **MCP 服务声明**（`.mcp.json`）。

## 现有插件

| 插件 | 用途 | 包含内容 |
| --- | --- | --- |
| [Starter Template](plugins/starter-template) | 用于联调测试与新建插件的最小参考模板 | Skill + MCP 示例 |
| [Docs Lookup](plugins/docs-lookup) | 根据最新文档回答库与框架相关问题 | Skill（Context7） |
| [Repo Research](plugins/repo-research) | 通过文档理解公开 GitHub 仓库 | Skill（DeepWiki） |
| [Git Workflows](plugins/git-workflows) | 编写清楚的提交信息和 Pull Request 描述 | Skill |

## 使用方式

- **Ducoro**：自动同步本仓库，按需将插件挂载到不同 Bot。
- **Claude Code**：通过 `.claude-plugin/marketplace.json` 添加本仓库（`/plugin marketplace add ducoro/plugins`）。
- **OpenAI Codex**：通过 `.agents/plugins/marketplace.json`（或根目录 `marketplace.json`）添加本仓库。

凡是需要凭证的 MCP 服务声明均只写环境变量占位符（例如 `${EXAMPLE_MCP_TOKEN}`），真实密钥请在各自宿主的本地凭证库中配置。

## 仓库结构

```text
.agents/plugins/marketplace.json   # 开放 Agent Plugins / Codex 市场索引
.claude-plugin/marketplace.json    # Claude Code 市场索引
marketplace.json                   # 根目录市场索引（同步镜像）
plugins/
  <plugin-name>/
    LICENSE
    plugin.json                    # 开放 Agent Plugins 清单
    .claude-plugin/plugin.json     # Claude Code 清单
    .codex-plugin/plugin.json      # Codex 清单
    .mcp.json                      # 可选：MCP 服务声明（严禁真实密钥）
    skills/
      <skill-name>/
        SKILL.md
        agents/openai.yaml         # 可选：发现元数据
```

## 参与贡献

- 人工贡献者请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。
- AI Agent 请直接阅读 [AGENTS.md](AGENTS.md)，按清单新建、修改与校验插件。
- 安全问题请通过[私密漏洞报告](https://github.com/ducoro/plugins/security/advisories/new)反馈，详情见 [SECURITY.md](SECURITY.md)。

## 许可证

采用 [Apache License 2.0](LICENSE)。第三方服务及其文档适用各自的条款。
