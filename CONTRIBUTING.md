# Contributing / 参与开发

The project is being prepared for an Alpha release. Contributions can focus on
reproducibility, simulator adapters, data integrity, or safe local operation.
Contributions to the original project code are submitted under Apache-2.0.
Keep third-party code and assets under their own licenses and preserve notices.

欢迎改进可复现安装、仿真适配、数据一致性和安全运行。请先查看当前许可证与能力边界，
不要把新增菜单、配置项或测试替身当作集成已经完成的证据。

## Development

```sh
python3.11 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
python -m pytest
```

Keep changes scoped and add regression tests. Label unit tests that use doubles
as unit tests; they do not prove a simulator, GPU renderer or real robot works.
Do not upload private datasets, checkpoints, vendor runtimes or credentials.

## Integration Evidence

For a new integration, include exact dependency revisions, hardware, command,
exit status, artifact hashes and a reproducible acceptance protocol. Report data
splits and initialization conditions with evaluation metrics. Interface export
alone is not evidence of successful robot deployment.

Use issues for reproducible non-sensitive bugs and design proposals. Include the
expected behavior, actual behavior, versions, and a minimal sanitized task config.
