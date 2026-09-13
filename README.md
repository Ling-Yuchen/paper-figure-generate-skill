# paper-figure-generate-skill

面向科研论文的可编辑SVG绘图skill，支持规整复杂框架、流程图及数据图，优先内嵌复用项目图标。

- [Skill入口](SKILL.md)：设计、绘制、检查与交付流程。
- [工具链](references/toolchain.md)：可选实现的作用、依赖、命令与替代方案。
- [验证与可移植性](references/validation.md)：迁移回归、复杂框架实绘与覆盖边界。

设计流程不绑定操作系统或宿主工具。Python检查器只需标准库；可选Node导出适配器分别使用Sharp或Playwright及已安装的兼容浏览器。缺少依赖时不会自动安装软件。

**验证范围：当前版本仅在 macOS 系统上完成验证。** Linux、Windows 等其他系统尚未实测；可移植性设计及目录迁移测试不代表已验证跨系统兼容性。在其他系统使用时，请按验证文档运行检查，并核对字体、渲染与导出效果。

发布或迁移时保留 `SKILL.md`、`references/`、`scripts/`、`icons/`及许可证；`tests/`用于维护验证。`tmp/`是本地试验产物，不是skill的运行依赖。
