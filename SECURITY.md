# Security / 安全边界

This Alpha is a **single-user, trusted-local orchestration tool**, not a public
multi-tenant service. The API can execute configured commands, install runtimes,
and access caller-selected filesystem paths. It has no built-in authentication
or authorization. Do not expose the API, bridge, or noVNC ports to the Internet.

本项目当前是单用户可信环境工具。API 可执行命令、安装依赖、访问路径，尚无内置鉴权。
不要把 API、交互桥接或 noVNC 直接暴露到公网。项目开源不等于服务可以公开访问。

## Running Safely

- Bind to `127.0.0.1`; use an SSH tunnel or a trusted VPN for personal access.
- Run as an unprivileged user with a dedicated state directory.
- Review all task YAML and external commands before execution. Treat them as code.
- Do not load untrusted policies, datasets, archives, MJCF, URDF, or mesh files.
- Keep credentials outside this repository and outside published logs/recordings.
- Do not execute generated rollout interfaces on hardware without reviewing joint
  mappings, calibration, limits, timing, watchdogs and emergency-stop behavior.
- Pipeline serialization is scoped to its state directory. Interactive sessions
  and the native viewer do not yet share a global GPU resource lock.

## Reporting

Do not publish vulnerabilities, credentials, private addresses, or exploit
payloads in public issues. GitHub private vulnerability reporting is enabled:
[Report privately](https://github.com/eust-w/open-embodied-simops/security/advisories/new).
Do not attach sensitive details to a public issue.

No security audit or production-hardening claim is made for this Alpha.
